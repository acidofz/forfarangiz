"""Точка входа для Vercel: все запросы (кроме /static) переписываются сюда.

vercel.json передаёт исходный путь в параметре __path, а здесь мы
возвращаем его во Flask, чтобы маршруты (/quest, /home, /admin…) работали.
"""
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app  # noqa: E402


class RestorePath:
    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        pairs = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        orig = next((v for k, v in pairs if k == "__path"), None)
        if orig is not None:
            environ["PATH_INFO"] = orig if orig.startswith("/") else "/" + orig
            environ["SCRIPT_NAME"] = ""
            environ["QUERY_STRING"] = urlencode([(k, v) for k, v in pairs if k != "__path"])
        return self.wsgi(environ, start_response)


flask_app.wsgi_app = RestorePath(flask_app.wsgi_app)
app = flask_app
