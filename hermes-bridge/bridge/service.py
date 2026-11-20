"""Логика моста Linky ↔ Hermes.

* submit_task   — принять задачу от Linky, без дублей, передать Hermes минимум контекста;
* sync_task     — прочитать дерево карточек Hermes и пересчитать статус;
* project_status — ответ на «что по проекту?» (с пометкой устаревания);
* pending_updates / ack_update — итоги, которые Linky ещё не сообщила.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from .hermes import HermesUnavailable, KanbanCLI
from .store import TERMINAL, Store

DEDUP_WINDOW_S = 24 * 3600

# --- что НЕ передаём в Hermes ------------------------------------------------
_REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email скрыт]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)"), "[телефон скрыт]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[номер карты скрыт]"),
    (re.compile(r"(?i)\b(?:sk|pk|api|token|key)[-_][A-Za-z0-9_-]{12,}\b"), "[ключ скрыт]"),
]


def redact(text: str) -> str:
    for rx, repl in _REDACT:
        text = rx.sub(repl, text)
    return text


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
                "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def slugify(name: str) -> str:
    """ASCII-slug проекта (он же tenant в Hermes Kanban): «AVA Rental (тест)» → ava-rental-test."""
    s = "".join(_TR.get(ch, ch) for ch in name.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "project-" + hashlib.sha256(name.encode()).hexdigest()[:8]


STATUS_RU = {
    "submitting": "отправляется в Hermes",
    "accepted": "принята Hermes, ждёт координатора",
    "planning": "координатор планирует",
    "in_progress": "в работе",
    "in_review": "на проверке",
    "needs_help": "нужна ваша помощь",
    "done": "готово",
    "failed": "ошибка",
    "cancelled": "отменена",
}

PILOT_RULES = (
    "Правила пилота: работать только с тестовыми данными; никаких внешних отправок "
    "(почта, мессенджеры, публикации) и платных прогонов/покупок без отдельного согласования — "
    "в таком случае заблокируй карточку с kind=needs_input и опиши, что нужно согласовать."
)


@dataclass
class Config:
    coordinator_profile: str = "coordinator"   # профиль-оркестратор в Hermes
    reviewer_profile: str = "reviewer"         # кто проверяет результат
    tz_offset_hours: int = 7                   # для времени в ответах (Бали = UTC+8, Пхукет = UTC+7)
    stale_after_s: int = 180                   # статус считается устаревшим, если не подтверждён дольше


class Bridge:
    def __init__(self, store: Store, kanban: KanbanCLI, cfg: Optional[Config] = None):
        self.store = store
        self.kanban = kanban
        self.cfg = cfg or Config()
        self._submit_lock = threading.Lock()

    # ------------------------------------------------------------------ utils
    def register_project(self, title: str, context: str = "") -> dict:
        """Завести проект и его краткий контекст (то, что Linky «знает» и передаёт Hermes)."""
        return self.store.upsert_project(slugify(title), title.strip(), context.strip())

    def _fmt(self, ts: Optional[float]) -> Optional[str]:
        if not ts:
            return None
        tz = timezone(timedelta(hours=self.cfg.tz_offset_hours))
        return datetime.fromtimestamp(ts, tz).strftime("%d.%m %H:%M")

    def build_brief(self, project: dict, title: str, brief: str) -> str:
        """Ровно то, что уходит в Hermes: проект, задача, критерии, правила. Без переписки."""
        ctx = (project.get("context") or "").strip()
        parts = [
            f"Проект: {project['title']}",
            f"Контекст проекта (кратко): {ctx}" if ctx else None,
            f"Задача: {title}",
            f"Детали и критерии приёмки: {brief}",
            (f"Порядок: разложи на карточки для исполнителей; последней поставь проверку результата "
             f"профилем «{self.cfg.reviewer_profile}». Итог — короткое резюме для голосового ответа."),
            PILOT_RULES,
        ]
        return redact("\n".join(p for p in parts if p))

    # ----------------------------------------------------------------- submit
    def submit_task(self, project: str, title: str, brief: str,
                    client_request_id: Optional[str] = None) -> dict:
        slug = slugify(project)
        proj = self.store.get_project(slug) or self.store.upsert_project(slug, project.strip())
        fp = hashlib.sha256(f"{slug}|{_norm(title)}|{_norm(brief)}".encode()).hexdigest()

        with self._submit_lock:
            existing = None
            if client_request_id:
                existing = self.store.find_by_request(slug, client_request_id)
            if not existing:
                existing = self.store.find_by_fingerprint(fp, time.time() - DEDUP_WINDOW_S)
            if existing:
                self.store.log(existing["linky_task_id"], "duplicate_submit",
                               {"client_request_id": client_request_id})
                task = existing
                duplicate = True
            else:
                task = self.store.insert_task(
                    project_slug=slug, client_request_id=client_request_id, fingerprint=fp,
                    title=title.strip(), brief_sent=self.build_brief(proj, title.strip(), brief.strip()))
                duplicate = False

        # Если карточки ещё нет (новая задача или прошлую попытку оборвало до ответа Hermes) —
        # создаём с ТЕМ ЖЕ ключом идемпотентности: Hermes вернёт уже существующую карточку.
        if not task["hermes_card_id"]:
            try:
                card = self.kanban.create(
                    title=f"[{proj['title']}] {task['title']}", body=task["brief_sent"],
                    assignee=self.cfg.coordinator_profile, tenant=slug,
                    idempotency_key=task["idempotency_key"])
                now = time.time()
                task = self.store.update_task(
                    task["linky_task_id"], hermes_card_id=card["id"], status="accepted",
                    hermes_status=card["status"], executor=card["assignee"],
                    hermes_updated_at=now, confirmed_at=now, sync_error=None)
                self.store.log(task["linky_task_id"], "hermes_accepted", {"card": card["id"]})
            except HermesUnavailable as e:
                self.store.update_task(task["linky_task_id"], sync_error=str(e),
                                       last_sync_attempt=time.time())
                return {
                    "accepted_by_hermes": False,
                    "linky_task_id": task["linky_task_id"],
                    "say": (f"Задачу записала под номером {task['linky_task_id']}, но Hermes сейчас "
                            f"не ответил. Отправлю повторно сама, дубля не будет."),
                    "error": str(e),
                }
        return {
            "accepted_by_hermes": True,
            "duplicate": duplicate,
            "linky_task_id": task["linky_task_id"],
            "hermes_card_id": task["hermes_card_id"],
            "project": slug,
            "say": (("Эта задача уже у Hermes" if duplicate else "Hermes принял задачу") +
                    f": номер {task['linky_task_id']}, карточка {task['hermes_card_id']}. "
                    f"Сообщу итог в чате."),
        }

    # ------------------------------------------------------------------- sync
    def _derive(self, cards: list[dict]) -> dict:
        root, rest = cards[0], cards[1:]
        team = [{"id": c["id"], "title": c["title"], "status": c["status"], "assignee": c["assignee"]}
                for c in cards]
        # blocked — ждёт человека; triage у дочерней карточки = повторные блокировки (эскалация)
        blocked = [c for c in cards if c["status"] == "blocked" or (c["status"] == "triage" and c is not root)]
        running = [c for c in cards if c["status"] in ("running", "ready", "claimed")]
        review = [c for c in cards if c["status"] == "review"]
        all_done = all(c["status"] in ("done", "archived") for c in cards)
        failed = [c for c in cards if c["status"] in ("failed", "cancelled")]

        executor = reviewer = needs_help = result = None
        if blocked:
            status = "needs_help"
            needs_help = "; ".join(
                (c["block_reason"] or c["last_comment"] or f"нужно решение по карточке {c['id']}").rstrip(". ")
                for c in blocked)
        elif failed:
            status = "failed"
            result = failed[0]["result"] or failed[0]["block_reason"]
        elif all_done and (rest or root["status"] == "done"):
            status = "done"
            # итог — у последней завершённой карточки (обычно — проверка)
            final = max(cards, key=lambda c: float(c["updated_at"] or 0))
            result = final["result"] or root["result"]
        elif review:
            status = "in_review"
        elif not rest and root["status"] in ("ready", "todo", "running"):
            status = "accepted" if root["status"] != "running" else "planning"
        else:
            status = "in_progress"

        if review:
            reviewer = ", ".join(sorted({c["reviewer"] or c["assignee"] for c in review if c["assignee"]}))
        rev_cards = [c for c in rest if c["assignee"] == self.cfg.reviewer_profile
                     and c["status"] in ("running", "ready", "claimed")]
        if rev_cards:
            status = "in_review" if status == "in_progress" else status
            reviewer = self.cfg.reviewer_profile
        workers = [c for c in running if c["assignee"] != self.cfg.reviewer_profile]
        if workers:
            executor = ", ".join(sorted({c["assignee"] for c in workers if c["assignee"]}))
        updated = max(float(c["updated_at"] or 0) for c in cards) or None
        return dict(status=status, executor=executor, reviewer=reviewer, needs_help=needs_help,
                    result=result, team=team, hermes_status=root["status"], hermes_updated_at=updated)

    def sync_task(self, task: dict) -> dict:
        import json as _json
        if task["status"] in TERMINAL:
            return task
        now = time.time()
        if not task["hermes_card_id"]:
            # Прошлая отправка не дошла — повторяем тем же ключом идемпотентности.
            return self._resend(task)
        try:
            cards = self.kanban.tree(task["hermes_card_id"])
        except HermesUnavailable as e:
            return self.store.update_task(task["linky_task_id"], sync_error=str(e), last_sync_attempt=now)
        d = self._derive(cards)
        prev = task["status"]
        task = self.store.update_task(
            task["linky_task_id"], status=d["status"], hermes_status=d["hermes_status"],
            executor=d["executor"], reviewer=d["reviewer"], needs_help=d["needs_help"],
            result=d["result"], team_json=_json.dumps(d["team"], ensure_ascii=False),
            hermes_updated_at=d["hermes_updated_at"], confirmed_at=now, last_sync_attempt=now,
            sync_error=None)
        if prev != task["status"]:
            self.store.log(task["linky_task_id"], "status", {"from": prev, "to": task["status"]})
        return task

    def _resend(self, task: dict) -> dict:
        try:
            card = self.kanban.create(
                title=f"[{self.store.get_project(task['project_slug'])['title']}] {task['title']}",
                body=task["brief_sent"], assignee=self.cfg.coordinator_profile,
                tenant=task["project_slug"], idempotency_key=task["idempotency_key"])
        except HermesUnavailable as e:
            return self.store.update_task(task["linky_task_id"], sync_error=str(e),
                                          last_sync_attempt=time.time())
        now = time.time()
        self.store.log(task["linky_task_id"], "hermes_accepted", {"card": card["id"], "resend": True})
        return self.store.update_task(task["linky_task_id"], hermes_card_id=card["id"], status="accepted",
                                      hermes_status=card["status"], confirmed_at=now,
                                      hermes_updated_at=now, sync_error=None)

    def sync_open(self) -> int:
        n = 0
        for t in self.store.open_tasks():
            self.sync_task(t)
            n += 1
        return n

    # ----------------------------------------------------------------- views
    def view(self, task: dict) -> dict:
        import json as _json
        now = time.time()
        stale = bool(task["sync_error"]) or (
            task["status"] not in TERMINAL and task["confirmed_at"]
            and now - task["confirmed_at"] > self.cfg.stale_after_s)
        st = STATUS_RU.get(task["status"], task["status"])
        bits = [f"«{task['title']}» ({task['linky_task_id']}): {st}"]
        if task["executor"] and task["status"] not in TERMINAL:
            bits.append(f"выполняет {task['executor']}")
        if task["reviewer"] and task["status"] not in TERMINAL:
            bits.append(f"проверяет {task['reviewer']}")
        if task["needs_help"]:
            bits.append(f"нужна помощь: {task['needs_help']}")
        if task["result"] and task["status"] == "done":
            bits.append(f"итог: {task['result']}")
        if stale:
            bits.append(f"свежих обновлений нет, последний подтверждённый статус на {self._fmt(task['confirmed_at'])}")
        return {
            "linky_task_id": task["linky_task_id"],
            "hermes_card_id": task["hermes_card_id"],
            "title": task["title"],
            "status": task["status"],
            "status_ru": st,
            "executor": task["executor"],
            "reviewer": task["reviewer"],
            "result": task["result"],
            "needs_help": task["needs_help"],
            "updated_at": self._fmt(task["hermes_updated_at"]),
            "confirmed_at": self._fmt(task["confirmed_at"]),
            "stale": stale,
            "team": _json.loads(task["team_json"]) if task["team_json"] else [],
            "say": "; ".join(b.rstrip(". ") for b in bits) + ".",
        }

    def project_status(self, project: str, refresh: bool = True) -> dict:
        slug = slugify(project)
        proj = self.store.get_project(slug)
        if not proj:
            known = ", ".join(p["title"] for p in self.store.list_projects()) or "нет"
            return {"found": False, "say": f"Проект «{project}» не найден. Известные проекты: {known}."}
        tasks = self.store.tasks_for_project(slug)
        if refresh:
            tasks = [self.sync_task(t) for t in tasks]
        views = [self.view(t) for t in tasks]
        if not views:
            say = f"По проекту {proj['title']} задач пока нет."
        else:
            say = f"Проект {proj['title']}, задач: {len(views)}. " + " ".join(v["say"] for v in views[:5])
        return {"found": True, "project": slug, "title": proj["title"], "tasks": views, "say": say}

    def task_status(self, linky_task_id: str, refresh: bool = True) -> dict:
        t = self.store.get_task(linky_task_id.strip().upper())
        if not t:
            return {"found": False, "say": f"Задача {linky_task_id} не найдена."}
        if refresh:
            t = self.sync_task(t)
        return {"found": True, **self.view(t)}

    def pending_updates(self, project: Optional[str] = None, refresh: bool = True) -> dict:
        if refresh:
            self.sync_open()
        items = [self.view(t) for t in self.store.unreported(slugify(project) if project else None)]
        return {"updates": items,
                "say": " ".join(i["say"] for i in items) if items else "Новых итогов нет."}

    def ack_update(self, linky_task_id: str) -> dict:
        t = self.store.get_task(linky_task_id.strip().upper())
        if not t:
            return {"ok": False}
        self.store.update_task(t["linky_task_id"], notified_status=t["status"])
        self.store.log(t["linky_task_id"], "reported", {"status": t["status"]})
        return {"ok": True, "linky_task_id": t["linky_task_id"], "reported_status": t["status"]}


class SyncLoop(threading.Thread):
    """Фоновое чтение Hermes: статус обновляется и без звонка."""

    def __init__(self, bridge: Bridge, interval: float = 60.0):
        super().__init__(daemon=True)
        self.bridge, self.interval = bridge, interval
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.bridge.sync_open()
            except Exception as e:  # никогда не роняем цикл
                self.bridge.store.log(None, "sync_loop_error", {"error": str(e)})

    def stop(self) -> None:
        self._stop.set()
