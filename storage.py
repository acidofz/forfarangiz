"""Хранилище файлов.

- Если задан SUPABASE_URL — Supabase Storage (приватный бакет, временные ссылки).
- Иначе — локальная папка uploads/ (для разработки на своём компьютере).

Файлы всегда загружаются из браузера напрямую (PUT по выданной ссылке),
поэтому на Vercel не упираемся в лимит ~4.5 МБ на запрос к функции.
"""
import os
import re
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
UPLOADS = Path(os.getenv("UPLOAD_DIR", BASE / "uploads"))

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY") or ""
PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or ""
BUCKET = os.getenv("SUPABASE_BUCKET", "gift")
SIGNED_TTL = 60 * 60 * 6  # ссылка на фото/аудио живёт 6 часов

PATH_RE = re.compile(r"^(image|audio)/[0-9a-f]{32}\.[a-z0-9]{2,5}$")
USE_SUPABASE = bool(SUPABASE_URL and SECRET_KEY)


class StorageError(RuntimeError):
    pass


def valid_path(path: str | None) -> bool:
    return bool(path and PATH_RE.match(path))


def _headers(json=True) -> dict:
    h = {"apikey": SECRET_KEY}
    # старые ключи service_role — это JWT, их можно (и нужно) слать ещё и в Authorization
    if SECRET_KEY.startswith("eyJ"):
        h["Authorization"] = f"Bearer {SECRET_KEY}"
    if json:
        h["Content-Type"] = "application/json"
    return h


def _api(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1{path}"


def _check(r: requests.Response, what: str) -> dict:
    if r.status_code >= 300:
        raise StorageError(f"{what}: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


# ---------------------------------------------------------------- API
def ensure_bucket():
    """Создаёт приватный бакет, если его ещё нет."""
    if not USE_SUPABASE:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        return
    r = requests.post(_api("/bucket"), headers=_headers(), timeout=15, json={
        "id": BUCKET, "name": BUCKET, "public": False, "file_size_limit": 50 * 1024 * 1024,
    })
    if r.status_code < 300 or "already exists" in r.text.lower() or r.status_code == 409:
        return
    raise StorageError(f"bucket: {r.status_code} {r.text[:300]}")


def upload_target(path: str, content_type: str, local_url: str, csrf: str) -> dict:
    """Куда и как браузеру загрузить файл."""
    if not USE_SUPABASE:
        return {"url": local_url, "method": "PUT",
                "headers": {"Content-Type": content_type, "X-CSRF-Token": csrf}}
    r = requests.post(_api(f"/object/upload/sign/{BUCKET}/{path}"), headers=_headers(), timeout=15)
    data = _check(r, "upload/sign")
    headers = {"Content-Type": content_type, "x-upsert": "false"}
    if PUBLISHABLE_KEY:
        headers["apikey"] = PUBLISHABLE_KEY
    return {"url": _api(data["url"]), "method": "PUT", "headers": headers}


def save_local(path: str, data: bytes):
    dest = UPLOADS / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


_signed_cache: dict[str, tuple[float, str]] = {}


def public_url(path: str, local_url: str) -> str:
    """Ссылка для <img>/<audio>. Для Supabase — временная подписанная (кэшируется в процессе)."""
    if not USE_SUPABASE:
        return local_url
    now = time.time()
    cached = _signed_cache.get(path)
    if cached and cached[0] > now:
        return cached[1]
    r = requests.post(_api(f"/object/sign/{BUCKET}/{path}"), headers=_headers(), timeout=15,
                      json={"expiresIn": SIGNED_TTL})
    url = _api(_check(r, "sign")["signedURL"])
    _signed_cache[path] = (now + SIGNED_TTL - 600, url)
    return url


def delete(path: str | None):
    if not valid_path(path):
        return
    if not USE_SUPABASE:
        (UPLOADS / path).unlink(missing_ok=True)
        return
    try:
        requests.delete(_api(f"/object/{BUCKET}"), headers=_headers(), timeout=15,
                        json={"prefixes": [path]})
    except requests.RequestException:
        pass  # не критично: останется лишний файл в бакете
