#!/usr/bin/env python3
"""МАКЕТ Hermes для тестов — НЕ настоящий Hermes.

Повторяет только тот контракт, который мост использует по документации:
  hermes kanban create "<title>" --body … --assignee … --tenant … --idempotency-key K [--goal …] --json
  hermes kanban show <id> --json
  hermes kanban list --json
  hermes_mock.py serve <port>   → GET /api/status, GET /v1/capabilities, GET /health

Команда Hermes имитируется по времени (MOCK_STAGE_S секунд на этап), то есть
«работа продолжается» без участия моста и звонка:
  этап 0: корень у координатора (ready)  → 1: координатор планирует (running)
  → 2: корень done, исполнитель «executor» running, проверка «reviewer» todo
  → 3: исполнитель done, reviewer running → 4: всё done, итог.
В названии «[нужна помощь]» — исполнитель блокируется с причиной.
Файл <state>.down — имитация недоступности Hermes (exit 1).
"""
import json
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = os.environ.get("MOCK_HERMES_STATE", "/tmp/hermes_mock_state.json")
STAGE_S = float(os.environ.get("MOCK_STAGE_S", "1.0"))
VERSION = os.environ.get("MOCK_HERMES_VERSION", "0.19.0")


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"cards": {}, "idem": {}, "calls": []}


def save(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def arg(args, name, default=None):
    if name in args:
        return args[args.index(name) + 1]
    return default


def card(st, cid):
    c = dict(st["cards"][cid])
    return c


def advance(st):
    """Пересчитать состояние команды по прошедшему времени."""
    now = time.time()
    for root in [c for c in st["cards"].values() if c.get("parent") is None]:
        stage = int((now - root["created_at"]) / STAGE_S)
        help_needed = "[нужна помощь]" in root["title"]
        kids = root["children"]
        if stage >= 1 and root["status"] == "ready":
            root.update(status="running", updated_at=root["created_at"] + STAGE_S)
        if stage >= 2 and not kids:
            t = root["created_at"] + 2 * STAGE_S
            root.update(status="done", updated_at=t,
                        result="Разложил на 2 карточки: исполнение → проверка.")
            ex = new_card(st, f"Выполнить: {root['title']}", "executor", root["id"], t, "running")
            rv = new_card(st, f"Проверить результат: {root['title']}", "reviewer", root["id"], t, "todo")
            root["children"] = [ex["id"], rv["id"]]
            kids = root["children"]
        if not kids:
            continue
        ex, rv = st["cards"][kids[0]], st["cards"][kids[1]]
        if help_needed and stage >= 3 and ex["status"] == "running":
            ex.update(status="blocked", updated_at=root["created_at"] + 3 * STAGE_S,
                      block_reason="Нужно согласование: задача требует внешней отправки письма. "
                                   "Подтвердите или уберите этот шаг.")
            continue
        if stage >= 3 and ex["status"] == "running":
            ex.update(status="done", updated_at=root["created_at"] + 3 * STAGE_S,
                      result="Тестовый отчёт собран на тестовых данных (3 строки).")
            rv.update(status="running", updated_at=root["created_at"] + 3 * STAGE_S)
        if stage >= 4 and rv["status"] == "running":
            rv.update(status="done", updated_at=root["created_at"] + 4 * STAGE_S,
                      result="Проверено: тестовый отчёт собран, 3 строки, итоги сходятся.")


def new_card(st, title, assignee, parent, t, status):
    cid = "t_" + uuid.uuid4().hex[:6]
    c = {"id": cid, "title": title, "body": "", "assignee": assignee, "status": status,
         "parent": parent, "children": [], "created_at": t, "updated_at": t,
         "result": None, "block_reason": None, "comments": []}
    st["cards"][cid] = c
    return c


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))


def kanban(args):
    if os.path.exists(STATE + ".down"):
        print("hermes: gateway unavailable (mock outage)", file=sys.stderr)
        return 1
    st = load()
    advance(st)
    sub = args[0]
    st["calls"].append({"at": time.time(), "cmd": sub})
    if sub == "create":
        title, key = args[1], arg(args, "--idempotency-key")
        if key and key in st["idem"]:
            c = card(st, st["idem"][key])
            c["replayed"] = True
            save(st)
            return out(c) or 0
        c = new_card(st, title, arg(args, "--assignee"), None, time.time(), "ready")
        c.update(body=arg(args, "--body", ""), tenant=arg(args, "--tenant"),
                 goal="--goal" in args, idempotency_key=key)
        if key:
            st["idem"][key] = c["id"]
        save(st)
        return out(card(st, c["id"])) or 0
    if sub == "show":
        cid = args[1]
        save(st)
        if cid not in st["cards"]:
            print(f"no such task {cid}", file=sys.stderr)
            return 1
        return out(card(st, cid)) or 0
    if sub == "list":
        save(st)
        return out(list(st["cards"].values())) or 0
    print(f"mock: unsupported kanban {sub}", file=sys.stderr)
    return 2


def serve(port):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            down = os.path.exists(STATE + ".down")
            if self.path == "/api/status":
                body = {"version": VERSION, "gateway": "down" if down else "running",
                        "active_sessions": 0, "peer_access": 1}
            elif self.path == "/v1/capabilities":
                if self.headers.get("Authorization") != "Bearer " + os.environ.get("API_SERVER_KEY", "test"):
                    self.send_response(401); self.end_headers(); return
                body = {"object": "hermes.api_server.capabilities", "platform": "hermes-agent",
                        "auth": {"type": "bearer", "required": True},
                        "features": {"chat_completions": True, "responses_api": True,
                                     "run_submission": True, "run_status": True,
                                     "run_events_sse": True, "run_stop": True, "run_approval": True},
                        "endpoints": {"runs": "/v1/runs", "run_status": "/v1/runs/{run_id}",
                                      "run_events": "/v1/runs/{run_id}/events",
                                      "run_stop": "/v1/runs/{run_id}/stop"}}
            elif self.path == "/health":
                body = {"status": "ok"}
            else:
                self.send_response(404); self.end_headers(); return
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    HTTPServer(("127.0.0.1", port), H).serve_forever()


def main(argv):
    if argv[:1] == ["serve"]:
        return serve(int(argv[1]))
    if argv[:1] == ["--version"]:
        return print(f"Hermes Agent v{VERSION} (MOCK)") or 0
    if argv[:2] == ["-p", argv[1] if len(argv) > 1 else ""]:
        argv = argv[2:]
    if argv[:1] == ["kanban"]:
        rest = argv[1:]
        if rest[:1] == ["--board"]:
            rest = rest[2:]
        return kanban(rest)
    print("mock: unsupported", argv, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
