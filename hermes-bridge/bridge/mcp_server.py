"""Минимальный MCP-сервер (Streamable HTTP, JSON-ответы) для Linky.

Linky (dot в ChatGPT) подключает его как custom MCP server:
ChatGPT → Plugins → «+» → Add custom MCP server → URL `https://<мост>/mcp`.

Без внешних зависимостей: JSON-RPC 2.0 поверх POST /mcp
(initialize, tools/list, tools/call, ping). Доступ — по Bearer-токену
(BRIDGE_TOKEN) и/или по секретному сегменту пути (BRIDGE_PATH_SECRET),
сам сервис слушает только 127.0.0.1 и выставляется наружу через туннель.
"""
from __future__ import annotations

import hmac
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .service import Bridge

PROTOCOL_VERSION = "2025-06-18"

TOOLS: list[dict] = [
    {
        "name": "hermes_submit_task",
        "title": "Передать задачу команде Hermes",
        "description": (
            "Передаёт задачу координатору Hermes. Вызывай, когда пользователь голосом ставит задачу. "
            "Всегда передавай client_request_id — один и тот же для повторов этой же задачи "
            "(после обрыва связи повтор не создаст дубль). В brief — только суть и критерии приёмки, "
            "без личных данных. Ответ поля `say` можно зачитать пользователю."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Название проекта, напр. «AVA Rental»"},
                "title": {"type": "string", "description": "Короткое название задачи"},
                "brief": {"type": "string", "description": "Что сделать и как понять, что готово"},
                "client_request_id": {"type": "string",
                                      "description": "Уникальный ID этой постановки, один для всех повторов"},
            },
            "required": ["project", "title", "brief"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
                        "openWorldHint": False},
    },
    {
        "name": "hermes_project_status",
        "title": "Статус проекта",
        "description": ("Статус всех задач проекта в Hermes: кто выполняет и проверяет, итог, где нужна "
                        "помощь, время последнего обновления. Если Hermes недоступен — последний "
                        "подтверждённый статус и его время (stale=true)."),
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}},
                        "required": ["project"]},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "hermes_task_status",
        "title": "Статус задачи",
        "description": "Статус одной задачи по номеру Linky (LT-XXXXXXXX).",
        "inputSchema": {"type": "object", "properties": {"linky_task_id": {"type": "string"}},
                        "required": ["linky_task_id"]},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "hermes_pending_updates",
        "title": "Новые итоги",
        "description": ("Итоги и запросы помощи, которые ещё не сообщены пользователю. Вызывай в "
                        "запланированной проверке; после сообщения в чате вызови hermes_ack_update."),
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "hermes_ack_update",
        "title": "Отметить итог сообщённым",
        "description": "Отмечает, что текущий итог задачи уже сообщён пользователю (чтобы не повторять).",
        "inputSchema": {"type": "object", "properties": {"linky_task_id": {"type": "string"}},
                        "required": ["linky_task_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
                        "openWorldHint": False},
    },
    {
        "name": "hermes_list_projects",
        "title": "Список проектов",
        "description": "Проекты, по которым у моста есть задачи.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


def make_dispatch(bridge: Bridge) -> dict[str, Callable[..., Any]]:
    return {
        "hermes_submit_task": lambda a: bridge.submit_task(
            a["project"], a["title"], a["brief"], a.get("client_request_id")),
        "hermes_project_status": lambda a: bridge.project_status(a["project"]),
        "hermes_task_status": lambda a: bridge.task_status(a["linky_task_id"]),
        "hermes_pending_updates": lambda a: bridge.pending_updates(a.get("project")),
        "hermes_ack_update": lambda a: bridge.ack_update(a["linky_task_id"]),
        "hermes_list_projects": lambda a: {"projects": [
            {"slug": p["slug"], "title": p["title"]} for p in bridge.store.list_projects()]},
    }


def handle_rpc(bridge: Bridge, msg: dict, dispatch: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:  # notification (notifications/initialized и т.п.)
        return None

    def ok(result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "linky-hermes-bridge", "version": "0.1.0"},
                   "instructions": ("Мост между Linky и командой Hermes. Ставь задачи через "
                                    "hermes_submit_task, спрашивай статус через hermes_project_status.")})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        fn = dispatch.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            res = fn(args)
            return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                       "structuredContent": res, "isError": False})
        except Exception as e:
            bridge.store.log(None, "tool_error", {"tool": name, "error": str(e)})
            return ok({"content": [{"type": "text", "text": f"Ошибка моста: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def make_handler(bridge: Bridge, token: str = "", path_secret: str = ""):
    dispatch = make_dispatch(bridge)
    mcp_path = f"/{path_secret}/mcp" if path_secret else "/mcp"

    class H(BaseHTTPRequestHandler):
        server_version = "linky-hermes-bridge"

        def log_message(self, *a):  # тихо; события пишем в SQLite
            pass

        def _send(self, code: int, body: Any = None, headers: dict | None = None):
            data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            if body is not None:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            if not token:
                return True
            got = self.headers.get("Authorization", "")
            return hmac.compare_digest(got, f"Bearer {token}")

        def do_GET(self):
            if self.path == "/healthz":
                return self._send(200, {"ok": True})
            self._send(405, {"error": "use POST"} if self.path == mcp_path else {"error": "not found"})

        def do_DELETE(self):
            self._send(200 if self.path == mcp_path else 404)

        def do_POST(self):
            if self.path != mcp_path:
                return self._send(404, {"error": "not found"})
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                msg = json.loads(self.rfile.read(n) or b"null")
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"jsonrpc": "2.0", "id": None,
                                        "error": {"code": -32700, "message": "parse error"}})
            sid = self.headers.get("Mcp-Session-Id") or uuid.uuid4().hex
            hdr = {"Mcp-Session-Id": sid}
            if isinstance(msg, list):
                out = [r for r in (handle_rpc(bridge, m, dispatch) for m in msg) if r]
                return self._send(200, out, hdr) if out else self._send(202, None, hdr)
            res = handle_rpc(bridge, msg, dispatch)
            return self._send(200, res, hdr) if res else self._send(202, None, hdr)

    return H


def serve(bridge: Bridge, host: str = "127.0.0.1", port: int = 8765,
          token: str | None = None, path_secret: str | None = None) -> ThreadingHTTPServer:
    token = token if token is not None else os.environ.get("BRIDGE_TOKEN", "")
    path_secret = path_secret if path_secret is not None else os.environ.get("BRIDGE_PATH_SECRET", "")
    return ThreadingHTTPServer((host, port), make_handler(bridge, token, path_secret))
