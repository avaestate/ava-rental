"""Адаптеры к официальным интерфейсам Hermes Agent.

Основной путь — Hermes Kanban (координатор + команда + проверка), через
официальный CLI `hermes kanban … --json` на том же хосте, где живёт Hermes.
Почему CLI, а не REST `/api/plugins/kanban/*`: по документации эти маршруты
дашборда НЕ аутентифицируются и рассчитаны только на localhost, а CLI
и инструменты агентов идут через тот же `kanban_db` слой.

Дополнительно:
  * `GET  /api/status`        (дашборд, :9119) — версия Hermes и состояние шлюза;
  * `GET  /v1/capabilities`   (API-сервер, :8642, Bearer) — какие операции доступны;
  * `POST /v1/runs` + `GET /v1/runs/{id}` — запуск/статус одиночного прогона
    (запасной путь, если мост стоит не на хосте Hermes).

Формат JSON `kanban show --json` в документации не расписан полностью,
поэтому `normalize_card` принимает несколько вариантов имён полей.
ЭТО НУЖНО СВЕРИТЬ на боевом сервере (см. README, «Что проверить на сервере»).
"""
from __future__ import annotations

import json
import shlex
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


class HermesUnavailable(Exception):
    """Hermes не ответил или ответил ошибкой — показываем последний подтверждённый статус."""


# --------------------------------------------------------------------------
# Kanban через CLI
# --------------------------------------------------------------------------
@dataclass
class KanbanCLI:
    hermes_bin: str = "hermes"
    profile: Optional[str] = None        # профиль, чей HERMES_HOME содержит доску
    board: Optional[str] = None          # --board <slug>, если доска не default
    timeout: float = 20.0

    def _base(self) -> list[str]:
        cmd = shlex.split(self.hermes_bin)
        if self.profile:
            cmd += ["-p", self.profile]
        cmd.append("kanban")
        if self.board:
            cmd += ["--board", self.board]
        return cmd

    def _run(self, args: list[str]) -> Any:
        try:
            proc = subprocess.run(self._base() + args, capture_output=True, text=True,
                                  timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise HermesUnavailable(f"hermes kanban: {e}") from e
        if proc.returncode != 0:
            raise HermesUnavailable(f"hermes kanban exit {proc.returncode}: {proc.stderr.strip()[:300]}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise HermesUnavailable(f"hermes kanban: не JSON: {proc.stdout[:200]!r}") from e

    def create(self, *, title: str, body: str, assignee: str, tenant: str,
               idempotency_key: str, goal: bool = True, goal_max_turns: int = 20,
               max_runtime: str = "2h") -> dict:
        args = ["create", title, "--body", body, "--assignee", assignee,
                "--tenant", tenant, "--idempotency-key", idempotency_key,
                "--max-runtime", max_runtime, "--json"]
        if goal:
            args += ["--goal", "--goal-max-turns", str(goal_max_turns)]
        return normalize_card(self._run(args))

    def show(self, card_id: str) -> dict:
        return normalize_card(self._run(["show", card_id, "--json"]))

    def tree(self, root_id: str, max_cards: int = 40) -> list[dict]:
        """Корень + все потомки (карточки, которые координатор создал для команды)."""
        seen: dict[str, dict] = {}
        queue = [root_id]
        while queue and len(seen) < max_cards:
            cid = queue.pop(0)
            if cid in seen:
                continue
            card = self.show(cid)
            seen[cid] = card
            queue.extend(c for c in card["children"] if c not in seen)
        return list(seen.values())


def _first(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def normalize_card(raw: Any) -> dict:
    """Привести ответ `kanban create/show --json` к одному виду."""
    if isinstance(raw, dict) and isinstance(raw.get("task"), dict):
        outer = raw
        raw = {**raw["task"], **{k: v for k, v in outer.items() if k != "task"}}
    if not isinstance(raw, dict):
        raise HermesUnavailable(f"неожиданный ответ kanban: {raw!r}"[:300])
    children = _first(raw, "children", "child_ids", default=[]) or []
    links = raw.get("links") or []
    for ln in links if isinstance(links, list) else []:
        if isinstance(ln, dict) and ln.get("parent_id") == _first(raw, "id", "task_id"):
            children.append(ln.get("child_id"))
    children = [c["id"] if isinstance(c, dict) else c for c in children if c]
    comments = raw.get("comments") or []
    return {
        "id": _first(raw, "id", "task_id"),
        "title": _first(raw, "title", default=""),
        "status": _first(raw, "status", default="unknown"),
        "assignee": _first(raw, "assignee"),
        "reviewer": _first(raw, "reviewer", "review_profile"),
        "result": _first(raw, "result", "summary", "completion_summary"),
        "block_reason": _first(raw, "block_reason", "blocked_reason"),
        "updated_at": _first(raw, "updated_at", "status_changed_at", "created_at"),
        "children": list(dict.fromkeys(children)),
        "last_comment": (comments[-1].get("body") if comments and isinstance(comments[-1], dict) else None),
        "replayed": bool(_first(raw, "replayed", "existing", "idempotency_replayed", default=False)),
    }


# --------------------------------------------------------------------------
# HTTP: версия, возможности, Runs API
# --------------------------------------------------------------------------
@dataclass
class HermesHTTP:
    api_base: str = "http://127.0.0.1:8642"        # API-сервер шлюза (или .../p/<profile>)
    dashboard_base: str = "http://127.0.0.1:9119"  # веб-дашборд
    api_key: str = ""
    timeout: float = 10.0

    def _req(self, method: str, url: str, body: Optional[dict] = None,
             headers: Optional[dict] = None) -> tuple[int, dict, dict]:
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, dict(r.headers), json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            payload = {}
            try:
                payload = json.loads(e.read() or b"{}")
            except Exception:
                pass
            return e.code, dict(e.headers or {}), payload
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise HermesUnavailable(f"{method} {url}: {e}") from e

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def status(self) -> dict:
        code, _, body = self._req("GET", f"{self.dashboard_base}/api/status")
        if code != 200:
            raise HermesUnavailable(f"/api/status → {code}")
        return body

    def capabilities(self) -> dict:
        code, _, body = self._req("GET", f"{self.api_base}/v1/capabilities", headers=self._auth())
        if code != 200:
            raise HermesUnavailable(f"/v1/capabilities → {code}")
        return body

    def health_detailed(self) -> dict:
        code, _, body = self._req("GET", f"{self.api_base}/health/detailed", headers=self._auth())
        if code != 200:
            raise HermesUnavailable(f"/health/detailed → {code}")
        return body

    def create_run(self, *, input_text: str, idempotency_key: str, session_id: str,
                   session_key: str, instructions: str = "") -> dict:
        body = {"input": input_text, "session_id": session_id}
        if instructions:
            body["instructions"] = instructions
        code, headers, payload = self._req(
            "POST", f"{self.api_base}/v1/runs", body,
            {**self._auth(), "Idempotency-Key": idempotency_key, "X-Hermes-Session-Key": session_key})
        if code in (200, 201, 202):
            payload["replayed"] = str(headers.get("Idempotency-Replayed", "")).lower() == "true"
            return payload
        if code in (429, 503):
            raise HermesUnavailable(f"/v1/runs → {code} (повторить позже)")
        raise RuntimeError(f"/v1/runs → {code}: {payload}")

    def get_run(self, run_id: str) -> dict:
        code, _, body = self._req("GET", f"{self.api_base}/v1/runs/{run_id}", headers=self._auth())
        if code != 200:
            raise HermesUnavailable(f"/v1/runs/{run_id} → {code}")
        return body
