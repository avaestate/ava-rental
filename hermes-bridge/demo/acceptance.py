#!/usr/bin/env python3
"""Приёмочный сценарий на тестовых данных.

Что настоящее: мост (MCP-сервер по HTTP, SQLite, идемпотентность, синхронизация).
Что имитировано: Linky — скриптовый MCP-клиент, который шлёт те же вызовы, что сделает
dot в ChatGPT; Hermes — макет mock/hermes_mock.py по документированному контракту.

Запуск:  python3 demo/acceptance.py   (из каталога hermes-bridge)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from bridge.hermes import HermesHTTP, KanbanCLI  # noqa: E402
from bridge.mcp_server import serve  # noqa: E402
from bridge.service import Bridge, Config, SyncLoop  # noqa: E402
from bridge.store import Store  # noqa: E402

STAGE_S = 1.0
TOKEN = "test-" + uuid.uuid4().hex
results: list[dict] = []
transcript: list[str] = []


def step(name: str, ok: bool, detail: str = "", real: str = "мост — реально; Hermes — макет") -> None:
    results.append({"step": name, "ok": bool(ok), "detail": detail, "what_ran": real})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


class LinkyClient:
    """Имитация Linky: MCP-клиент поверх HTTP (одна «сессия» = один звонок)."""

    def __init__(self, url: str, token: str):
        self.url, self.token, self.sid, self.n = url, token, None, 0

    def rpc(self, method: str, params: dict | None = None, notify: bool = False):
        self.n += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            msg["id"] = self.n
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
             "Authorization": f"Bearer {self.token}"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, json.dumps(msg).encode(), h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            body = r.read()
        return json.loads(body)["result"] if body else None

    def connect(self):
        self.sid = None
        info = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "linky-sim", "version": "0"}})
        self.rpc("notifications/initialized", notify=True)
        return info

    def call(self, name: str, **args):
        res = self.rpc("tools/call", {"name": name, "arguments": args})
        data = res["structuredContent"]
        transcript.append(f"Linky → {name}({json.dumps(args, ensure_ascii=False)})\n   ← say: {data.get('say')}")
        return data


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="linky-hermes-")
    state = os.path.join(tmp, "hermes_state.json")
    env = {**os.environ, "MOCK_HERMES_STATE": state, "MOCK_STAGE_S": str(STAGE_S), "API_SERVER_KEY": "test"}
    os.environ.update({"MOCK_HERMES_STATE": state, "MOCK_STAGE_S": str(STAGE_S)})
    mock = os.path.join(ROOT, "mock", "hermes_mock.py")

    # ---- Hermes (макет): HTTP для версии/возможностей + CLI для Kanban
    hp = subprocess.Popen([sys.executable, mock, "serve", "18642"], env=env)
    time.sleep(0.5)
    http = HermesHTTP(api_base="http://127.0.0.1:18642", dashboard_base="http://127.0.0.1:18642",
                      api_key="test")
    kanban = KanbanCLI(hermes_bin=f"{sys.executable} {mock}")
    store = Store(os.path.join(tmp, "bridge.db"))
    bridge = Bridge(store, kanban, Config())
    bridge.register_project("AVA Rental (тест)", "Тестовый проект: аренда вилл, только тестовые данные.")

    srv = serve(bridge, "127.0.0.1", 0, token=TOKEN, path_secret="")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    sync = SyncLoop(bridge, interval=0.5)
    sync.start()

    try:
        # 0. Проверка Hermes: версия и операции
        st, caps = http.status(), http.capabilities()
        feats = caps["features"]
        step("0. Версия Hermes и операции запуска/статуса",
             st.get("version") and all(feats.get(f) for f in ("run_submission", "run_status", "run_stop")),
             f"version={st.get('version')} (макет), features={sorted(k for k, v in feats.items() if v)}")

        # 0b. Чужой без токена не попадёт
        try:
            urllib.request.urlopen(urllib.request.Request(url, b"{}", {"Content-Type": "application/json"},
                                                          method="POST"), timeout=5)
            step("0b. Без токена доступ закрыт", False)
        except urllib.error.HTTPError as e:
            step("0b. Без токена доступ закрыт", e.code == 401, f"HTTP {e.code}", "мост — реально")

        # 1. Звонок №1: постановка задачи
        linky = LinkyClient(url, TOKEN)
        info = linky.connect()
        tools = [t["name"] for t in linky.rpc("tools/list")["tools"]]
        step("1a. Linky подключилась к MCP-мосту и видит инструменты",
             "hermes_submit_task" in tools, f"server={info['serverInfo']['name']}, tools={tools}",
             "мост — реально; Linky — скриптовый MCP-клиент")
        req_id = "call1-" + uuid.uuid4().hex[:6]
        r1 = linky.call("hermes_submit_task", project="AVA Rental (тест)",
                        title="Тестовый отчёт по заявкам",
                        brief="Собери тестовый отчёт по 3 тестовым заявкам: имя, вилла, даты. "
                              "Контакт клиента test@example.com, +7 999 123-45-67. Готово, когда итоги сходятся.",
                        client_request_id=req_id)
        step("1b. Hermes принял задачу, ID сохранён",
             r1["accepted_by_hermes"] and r1["hermes_card_id"] and store.get_task(r1["linky_task_id"]),
             f"linky_task_id={r1['linky_task_id']}, hermes_card_id={r1['hermes_card_id']}")
        sent = store.get_task(r1["linky_task_id"])["brief_sent"]
        step("1c. В Hermes ушёл только нужный контекст (личные данные скрыты)",
             "test@example.com" not in sent and "999" not in sent and "Правила пилота" in sent
             and "аренда вилл" in sent and store.count_tasks() == 1,
             "email и телефон заменены на [скрыт]; добавлены краткий контекст проекта и правила пилота",
             "мост — реально")

        # 2. Обрыв: повтор той же задачи
        r2 = linky.call("hermes_submit_task", project="AVA Rental (тест)", title="Тестовый отчёт по заявкам",
                        brief="(повтор после обрыва)", client_request_id=req_id)
        r3 = LinkyClient(url, TOKEN)
        r3.connect()
        r3 = r3.call("hermes_submit_task", project="AVA Rental (тест)",
                     title="Тестовый отчёт по заявкам",
                     brief="Собери тестовый отчёт по 3 тестовым заявкам: имя, вилла, даты. "
                           "Контакт клиента test@example.com, +7 999 123-45-67. Готово, когда итоги сходятся.")
        roots = [c for c in json.load(open(state))["cards"].values() if c["parent"] is None]
        step("2. Повтор после обрыва не создаёт дубль",
             r2["linky_task_id"] == r3["linky_task_id"] == r1["linky_task_id"] and len(roots) == 1
             and store.count_tasks() == 1,
             f"повтор с тем же ID и повтор без ID → {r1['linky_task_id']}; карточек в Hermes: {len(roots)}")

        # 2b. Сбой между записью и ответом Hermes: повтор тем же ключом идемпотентности
        t = store.get_task(r1["linky_task_id"])
        again = kanban.create(title="x", body="x", assignee="coordinator", tenant="ava-rental-test",
                              idempotency_key=t["idempotency_key"])
        step("2b. Ключ идемпотентности Hermes возвращает ту же карточку",
             again["id"] == t["hermes_card_id"] and again["replayed"],
             f"key={t['idempotency_key']} → {again['id']}")

        # 3. Звонок окончен; Hermes продолжает
        linky = None
        time.sleep(STAGE_S * 2.6)
        mid = bridge.task_status(r1["linky_task_id"], refresh=False)
        step("3a. После звонка Hermes работает, мост видит исполнителя",
             mid["status"] in ("in_progress", "in_review") and (mid["executor"] or mid["reviewer"]),
             f"статус={mid['status_ru']}, выполняет={mid['executor']}, проверяет={mid['reviewer']}, "
             f"обновлено={mid['updated_at']}")
        time.sleep(STAGE_S * 1.0)
        rev = bridge.task_status(r1["linky_task_id"], refresh=False)
        step("3b. Видно, кто проверяет результат", rev["reviewer"] == "reviewer" or rev["status"] == "done",
             f"статус={rev['status_ru']}, проверяет={rev['reviewer']}")
        time.sleep(STAGE_S * 1.5)

        # 4. Итог в чате: запланированная проверка Linky
        chat = LinkyClient(url, TOKEN)
        chat.connect()
        pu = chat.call("hermes_pending_updates")
        done = [u for u in pu["updates"] if u["linky_task_id"] == r1["linky_task_id"]]
        step("4a. Итог готов к сообщению в чате", done and done[0]["status"] == "done" and done[0]["result"],
             f"say: {pu['say']}")
        chat.call("hermes_ack_update", linky_task_id=r1["linky_task_id"])
        pu2 = chat.call("hermes_pending_updates")
        step("4b. Итог не повторяется после отметки", not pu2["updates"], pu2["say"])

        # 5. Звонок №2: «что по проекту?» без повторного объяснения
        call2 = LinkyClient(url, TOKEN)
        call2.connect()
        ps = call2.call("hermes_project_status", project="AVA Rental (тест)")
        step("5. Во втором звонке статус по проекту без повторного объяснения",
             ps["found"] and ps["tasks"][0]["status"] == "done" and ps["tasks"][0]["result"],
             f"say: {ps['say']}")

        # 6. Нужна помощь
        rh = call2.call("hermes_submit_task", project="AVA Rental (тест)",
                        title="Разослать тестовое письмо [нужна помощь]",
                        brief="Подготовь письмо по тестовым данным.", client_request_id="call2-help")
        time.sleep(STAGE_S * 3.6)
        hs = call2.call("hermes_task_status", linky_task_id=rh["linky_task_id"])
        step("6. Где нужна помощь — видно и озвучивается",
             hs["status"] == "needs_help" and hs["needs_help"], f"say: {hs['say']}")

        # 7. Hermes недоступен → последний подтверждённый статус и его время
        sync.stop()
        open(state + ".down", "w").close()
        down = call2.call("hermes_task_status", linky_task_id=rh["linky_task_id"])
        step("7. При недоступности Hermes — последний подтверждённый статус и время",
             down["stale"] and down["status"] == "needs_help" and down["confirmed_at"],
             f"say: {down['say']}")
        os.remove(state + ".down")
    except Exception as e:  # отчёт должен показать, где упало
        import traceback
        traceback.print_exc()
        step("сценарий прерван исключением", False, repr(e))
    finally:
        sync.stop()
        srv.shutdown()
        hp.terminate()

    passed = sum(r["ok"] for r in results)
    out = {"passed": passed, "total": len(results), "steps": results, "transcript": transcript,
           "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    path = os.path.join(HERE, "acceptance_result.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n{passed}/{len(results)} шагов прошли. Результат: {path}")
    print("\n".join(transcript))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
