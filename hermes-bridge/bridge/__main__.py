"""Запуск моста и проверка Hermes.

  python -m bridge check            # версия Hermes, доступные операции, доступ к Kanban
  python -m bridge serve            # MCP-сервер для Linky на 127.0.0.1:8765

Переменные окружения (секреты — только в .env с правами 600, не в git):
  BRIDGE_DB=./bridge.db  BRIDGE_TOKEN=…  BRIDGE_PATH_SECRET=…  BRIDGE_PORT=8765
  HERMES_BIN=hermes  HERMES_PROFILE=  HERMES_BOARD=
  HERMES_API_BASE=http://127.0.0.1:8642  HERMES_DASHBOARD=http://127.0.0.1:9119  API_SERVER_KEY=…
  COORDINATOR_PROFILE=coordinator  REVIEWER_PROFILE=reviewer  SYNC_INTERVAL=60
"""
from __future__ import annotations

import json
import os
import sys

from .hermes import HermesHTTP, HermesUnavailable, KanbanCLI
from .mcp_server import serve
from .service import Bridge, Config, SyncLoop
from .store import Store


def build() -> tuple[Bridge, HermesHTTP]:
    env = os.environ.get
    kanban = KanbanCLI(hermes_bin=env("HERMES_BIN", "hermes"), profile=env("HERMES_PROFILE") or None,
                       board=env("HERMES_BOARD") or None)
    http = HermesHTTP(api_base=env("HERMES_API_BASE", "http://127.0.0.1:8642"),
                      dashboard_base=env("HERMES_DASHBOARD", "http://127.0.0.1:9119"),
                      api_key=env("API_SERVER_KEY", ""))
    cfg = Config(coordinator_profile=env("COORDINATOR_PROFILE", "coordinator"),
                 reviewer_profile=env("REVIEWER_PROFILE", "reviewer"),
                 tz_offset_hours=int(env("BRIDGE_TZ_OFFSET", "7")))
    return Bridge(Store(env("BRIDGE_DB", "bridge.db")), kanban, cfg), http


REQUIRED_FEATURES = ["run_submission", "run_status", "run_events_sse", "run_stop"]


def check(bridge: Bridge, http: HermesHTTP) -> int:
    report: dict = {}
    try:
        st = http.status()
        report["hermes_version"] = st.get("version") or st.get("agent_version")
        report["gateway"] = st.get("gateway") or st.get("gateway_status")
    except HermesUnavailable as e:
        report["status_error"] = str(e)
    try:
        caps = http.capabilities()
        feats = caps.get("features", {})
        report["features"] = {f: bool(feats.get(f)) for f in REQUIRED_FEATURES}
        report["endpoints"] = sorted((caps.get("endpoints") or {}).keys())
    except HermesUnavailable as e:
        report["capabilities_error"] = str(e)
    try:
        bridge.kanban._run(["list", "--json"])
        report["kanban_cli"] = "ok"
    except HermesUnavailable as e:
        report["kanban_cli_error"] = str(e)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if "kanban_cli" in report and "hermes_version" in report else 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    bridge, http = build()
    if cmd == "check":
        return check(bridge, http)
    if cmd == "serve":
        loop = SyncLoop(bridge, float(os.environ.get("SYNC_INTERVAL", "60")))
        loop.start()
        srv = serve(bridge, "127.0.0.1", int(os.environ.get("BRIDGE_PORT", "8765")))
        print(f"linky-hermes-bridge: http://127.0.0.1:{srv.server_address[1]}/mcp", flush=True)
        try:
            srv.serve_forever()
        finally:
            loop.stop()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
