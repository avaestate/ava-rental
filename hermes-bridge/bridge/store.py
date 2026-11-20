"""SQLite-хранилище связей: проект ↔ задача Linky ↔ карточка/запуск Hermes.

Одна таблица задач — источник правды для моста. Всё, что Linky когда-либо
слышала от Hermes, хранится здесь вместе со временем подтверждения, поэтому
при недоступности Hermes мы всегда можем отдать «последний подтверждённый
статус и его время».
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    slug        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    context     TEXT NOT NULL DEFAULT '',   -- краткий контекст, который можно передавать Hermes
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    linky_task_id      TEXT PRIMARY KEY,         -- ID, который Linky называет пользователю
    project_slug       TEXT NOT NULL REFERENCES projects(slug),
    client_request_id  TEXT,                     -- ID запроса от Linky (повтор после обрыва)
    fingerprint        TEXT NOT NULL,            -- хэш проекта+текста (если Linky потеряла ID)
    title              TEXT NOT NULL,
    brief_sent         TEXT NOT NULL,            -- ровно то, что ушло в Hermes
    idempotency_key    TEXT NOT NULL UNIQUE,     -- ключ идемпотентности Hermes
    hermes_card_id     TEXT,                     -- ID карточки Kanban (корень работы)
    hermes_run_id      TEXT,                     -- ID запуска /v1/runs (если используется)
    status             TEXT NOT NULL,            -- нормализованный статус моста
    hermes_status      TEXT,                     -- сырой статус Hermes
    executor           TEXT,
    reviewer           TEXT,
    result             TEXT,
    needs_help         TEXT,
    team_json          TEXT,                     -- снимок дерева карточек
    hermes_updated_at  REAL,                     -- время последнего изменения по данным Hermes
    confirmed_at       REAL,                     -- когда мы последний раз УСПЕШНО прочитали Hermes
    last_sync_attempt  REAL,
    sync_error         TEXT,
    notified_status    TEXT,                     -- какой статус уже сообщён пользователю
    created_at         REAL NOT NULL,
    UNIQUE(project_slug, client_request_id)
);
CREATE INDEX IF NOT EXISTS tasks_by_project ON tasks(project_slug, created_at);
CREATE INDEX IF NOT EXISTS tasks_by_fp ON tasks(fingerprint, created_at);

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    linky_task_id  TEXT,
    at             REAL NOT NULL,
    kind           TEXT NOT NULL,
    payload        TEXT
);
"""

TERMINAL = {"done", "failed", "cancelled"}


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    # ---- helpers -------------------------------------------------------
    def _one(self, sql: str, args: tuple = ()) -> Optional[dict]:
        with self._lock:
            row = self._db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def log(self, linky_task_id: Optional[str], kind: str, payload: Any = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events(linky_task_id, at, kind, payload) VALUES (?,?,?,?)",
                (linky_task_id, time.time(), kind,
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None),
            )

    # ---- projects ------------------------------------------------------
    def upsert_project(self, slug: str, title: str, context: str = "") -> dict:
        with self._lock:
            self._db.execute(
                "INSERT INTO projects(slug, title, context, created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, "
                "context=CASE WHEN excluded.context<>'' THEN excluded.context ELSE projects.context END",
                (slug, title, context, time.time()),
            )
        return self.get_project(slug)

    def get_project(self, slug: str) -> Optional[dict]:
        return self._one("SELECT * FROM projects WHERE slug=?", (slug,))

    def list_projects(self) -> list[dict]:
        return self._all("SELECT * FROM projects ORDER BY title")

    # ---- tasks ---------------------------------------------------------
    def find_by_request(self, project_slug: str, client_request_id: str) -> Optional[dict]:
        return self._one(
            "SELECT * FROM tasks WHERE project_slug=? AND client_request_id=?",
            (project_slug, client_request_id),
        )

    def find_by_fingerprint(self, fingerprint: str, since: float) -> Optional[dict]:
        return self._one(
            "SELECT * FROM tasks WHERE fingerprint=? AND created_at>=? AND status NOT IN ('failed','cancelled') "
            "ORDER BY created_at DESC LIMIT 1",
            (fingerprint, since),
        )

    def insert_task(self, *, project_slug: str, client_request_id: Optional[str], fingerprint: str,
                    title: str, brief_sent: str) -> dict:
        linky_task_id = "LT-" + uuid.uuid4().hex[:8].upper()
        idem = f"linky:{project_slug}:{linky_task_id}"
        with self._lock:
            self._db.execute(
                "INSERT INTO tasks(linky_task_id, project_slug, client_request_id, fingerprint, title, "
                "brief_sent, idempotency_key, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (linky_task_id, project_slug, client_request_id, fingerprint, title, brief_sent,
                 idem, "submitting", time.time()),
            )
        self.log(linky_task_id, "created", {"project": project_slug, "title": title})
        return self.get_task(linky_task_id)

    def get_task(self, linky_task_id: str) -> Optional[dict]:
        return self._one("SELECT * FROM tasks WHERE linky_task_id=?", (linky_task_id,))

    def update_task(self, linky_task_id: str, **fields: Any) -> dict:
        if fields:
            cols = ", ".join(f"{k}=?" for k in fields)
            with self._lock:
                self._db.execute(f"UPDATE tasks SET {cols} WHERE linky_task_id=?",
                                 (*fields.values(), linky_task_id))
        return self.get_task(linky_task_id)

    def tasks_for_project(self, project_slug: str, limit: int = 20) -> list[dict]:
        return self._all(
            "SELECT * FROM tasks WHERE project_slug=? ORDER BY created_at DESC LIMIT ?",
            (project_slug, limit),
        )

    def open_tasks(self) -> list[dict]:
        return self._all(
            "SELECT * FROM tasks WHERE status NOT IN ('done','failed','cancelled') ORDER BY created_at")

    def unreported(self, project_slug: Optional[str] = None) -> list[dict]:
        """Задачи, чей текущий «значимый» статус ещё не сообщён пользователю."""
        sql = ("SELECT * FROM tasks WHERE status IN ('done','failed','cancelled','needs_help') "
               "AND (notified_status IS NULL OR notified_status<>status)")
        args: tuple = ()
        if project_slug:
            sql += " AND project_slug=?"
            args = (project_slug,)
        return self._all(sql + " ORDER BY created_at", args)

    def count_tasks(self) -> int:
        return self._one("SELECT COUNT(*) AS n FROM tasks")["n"]
