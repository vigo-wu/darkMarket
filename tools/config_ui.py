"""
darkMark 可视化配置页面

用法:
  python tools/config_ui.py
  python tools/config_ui.py --port 8765 --no-browser
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import (  # noqa: E402
    load_regions,
    load_watchlist,
    regions_from_dict,
    save_regions,
    save_watchlist,
    watchlist_from_dict,
    watchlist_to_dict,
    regions_to_dict,
)
from src.paths import ensure_runtime_layout, tools_static_dir  # noqa: E402

STATIC_DIR = tools_static_dir()
DEFAULT_PORT = 8765


class ConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"[config_ui] {args[0]}")

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._send_html(STATIC_DIR / "index.html")
        elif path == "/api/config":
            try:
                self._send_json({
                    "watchlist": watchlist_to_dict(load_watchlist()),
                    "regions": regions_to_dict(load_regions()),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path != "/api/config":
            self.send_error(404)
            return

        try:
            data = self._read_json_body()
            watchlist = watchlist_from_dict(data["watchlist"])
            regions = regions_from_dict(data["regions"])
            save_watchlist(watchlist)
            save_regions(regions)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"error": str(e)}, 400)


def main() -> None:
    ensure_runtime_layout()

    parser = argparse.ArgumentParser(description="darkMark 可视化配置页面")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ConfigHandler)
    url = f"http://127.0.0.1:{args.port}"

    print("=" * 50)
    print("darkMark 配置中心")
    print("=" * 50)
    print(f"地址: {url}")
    print("按 Ctrl+C 停止服务")
    print()

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n配置服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
