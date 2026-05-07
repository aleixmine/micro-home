from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import random
import signal
import sys

state = {"playing": None}


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def json_response(data: dict) -> bytes:
    return json.dumps(data).encode("utf-8")


def handle_redirect(handler, _body=None):
    handler.send_response(302)
    handler.send_header("Location", "/climate")
    handler.end_headers()


def _serve_html(filename):
    def _handler(handler, _body=None):
        handler.send_response(200)
        handler.send_header("Content-type", "text/html")
        handler.end_headers()
        handler.wfile.write(read_file(filename))

    return _handler


def _serve_js(filename):
    def _handler(handler, _body=None):
        handler.send_response(200)
        handler.send_header("Content-type", "application/javascript")
        handler.end_headers()
        handler.wfile.write(read_file(filename))

    return _handler


def _serve_css(filename):
    def _handler(handler, _body=None):
        handler.send_response(200)
        handler.send_header("Content-type", "text/css")
        handler.end_headers()
        handler.wfile.write(read_file(filename))

    return _handler


def handle_api_climate(handler, _body=None):
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(
        json_response(
            {
                "humidity": round(50.0 + random.uniform(-10, 10), 1),
                "temperature": round(25.0 + random.uniform(-10, 10), 1),
            }
        )
    )


def handle_api_music_files(handler, _body=None):
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(
        json_response({"files": ["xenogenesis.wav", "ophelia.wav", "fly-away.wav"]})
    )


def handle_api_music_status(handler, _body=None):
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    playing = state["playing"]
    handler.wfile.write(
        json_response(
            {
                "file": playing,
                "playing": playing is not None,
            }
        )
    )


def handle_api_music_stop(handler, _body=None):
    state["playing"] = None  # bug original corregido
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(json_response({"status": "stopped"}))


def handle_api_about(handler, _body=None):
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(
        json_response(
            {
                "timestamp_ms": 2658771,
                "system": {
                    "micropython": True,
                    "implementation": {
                        "name": "micropython",
                        "version": [1, 28, 0, ""],
                    },
                    "platform": "esp32",
                    "version": "3.4.0; MicroPython v1.28.0 on 2026-04-06",
                },
                "flash_internal": {
                    "total_mb": 6.0,
                    "path": "/",
                    "mounted": True,
                    "block_size_b": 4096,
                    "used_mb": 0.12,
                    "used_pct": 2.0,
                    "free_mb": 5.88,
                },
                "sd_card": {
                    "total_mb": 960.0,
                    "path": "/sd",
                    "mounted": True,
                    "block_size_b": 16384,
                    "used_mb": 27.59,
                    "used_pct": 2.9,
                    "free_mb": 932.41,
                },
                "network": {
                    "available": True,
                    "ap": {"ip": "192.168.4.1", "active": True},
                    "sta": {
                        "ip": "10.10.0.36",
                        "connected": True,
                        "netmask": "255.255.255.0",
                        "active": True,
                        "gateway": "10.10.0.1",
                        "dns": "10.10.0.1",
                    },
                },
                "temperature": {
                    "source": "esp32.mcu_temperature",
                    "celsius": 46.0,
                    "fahrenheit": 114.8,
                },
                "ram": {
                    "used_kb": 55.83,
                    "total_kb": 155.94,
                    "used_pct": 35.8,
                    "free_kb": 100.11,
                },
                "cpu": {"freq_hz": 160_000_000, "freq_mhz": 160},
                "reset_cause": "power_on",
                "uptime": {
                    "ticks_ms": 2658771,
                    "formatted": "0d 00h 44m 18s",
                    "total_seconds": 2658,
                },
            }
        )
    )


def handle_api_music_play(handler, body: bytes):
    payload = json.loads(body.decode("utf-8"))
    state["playing"] = payload["file"]
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(
        json_response(
            {
                "file": payload["file"],
                "status": "playing",
            }
        )
    )


GET_ROUTES: dict[str, callable] = {
    "/": handle_redirect,
    "/climate": _serve_html("climate.html"),
    "/music": _serve_html("music.html"),
    "/about": _serve_html("about.html"),
    "/js/climate.js": _serve_js("js/climate.js"),
    "/js/navbar.js": _serve_js("js/navbar.js"),
    "/js/music.js": _serve_js("js/music.js"),
    "/js/about.js": _serve_js("js/about.js"),
    "/css/style.css": _serve_css("css/style.css"),
    "/api/climate": handle_api_climate,
    "/api/music/files": handle_api_music_files,
    "/api/music/status": handle_api_music_status,
    "/api/music/stop": handle_api_music_stop,
    "/api/about": handle_api_about,
}

POST_ROUTES: dict[str, callable] = {
    "/api/music/play": handle_api_music_play,
}


class Handler(BaseHTTPRequestHandler):
    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _not_found(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"404 Not found")

    def do_GET(self):
        route = GET_ROUTES.get(self.path)
        if route:
            route(self)
        else:
            self._not_found()

    def do_POST(self):
        route = POST_ROUTES.get(self.path)
        if route:
            route(self, self._read_body())
        else:
            self._not_found()

    def log_message(self, fmt, *args):
        pass


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("localhost", 8000), Handler)

    def shutdown(sig, frame):
        print(f"\nSeñal {signal.Signals(sig).name} recibida, parando...")
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("Servidor en http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
