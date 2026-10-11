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


# --- временная диагностика деплоя (уберём после настройки) ---
import os  # noqa: E402

from flask import jsonify, request  # noqa: E402


@flask_app.errorhandler(404)
def _debug_404(e):
    env = request.environ
    hdrs = {k: v for k, v in request.headers.items()
            if k.lower().startswith(("x-vercel", "x-now", "x-matched", "x-forwarded-uri", "x-invoke"))}
    return jsonify(
        error="not found",
        path=env.get("PATH_INFO"), script=env.get("SCRIPT_NAME"),
        query=env.get("QUERY_STRING"), raw_uri=env.get("RAW_URI") or env.get("REQUEST_URI"),
        commit=(os.getenv("VERCEL_GIT_COMMIT_SHA") or "")[:7],
        entry=__file__, headers=hdrs,
    ), 404


app = flask_app
