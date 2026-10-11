import hmac
import os
import secrets
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from markupsafe import Markup, escape
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

import notes as N  # noqa: E402  (читает .env при импорте)
import quest_config as Q  # noqa: E402
import storage as S  # noqa: E402
from models import DEFAULT_ENVELOPES, Envelope, Note, db  # noqa: E402

ON_VERCEL = bool(os.getenv("VERCEL"))
IMG_EXT = {"jpg", "jpeg", "png", "webp", "gif", "heic"}
AUDIO_EXT = {"mp3", "m4a", "ogg", "oga", "wav", "webm", "aac"}
TOGETHER_SINCE = date(2026, 9, 14)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        if ON_VERCEL:
            raise RuntimeError("DATABASE_URL не задан (строка подключения Supabase)")
        return f"sqlite:///{BASE / 'gift.db'}"
    # явный драйвер psycopg2: он не использует prepared statements,
    # что важно для пулера Supabase в режиме transaction (порт 6543)
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix):]
    if url.startswith("postgresql") and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def init_db():
    """Таблицы + стартовые конверты. Безопасно вызывать много раз."""
    db.create_all()
    if Envelope.query.count() == 0:
        for i, (title, emoji) in enumerate(DEFAULT_ENVELOPES):
            db.session.add(Envelope(title=title, emoji=emoji, position=i))
        db.session.commit()


class RestorePath:
    """На Vercel vercel.json переписывает все запросы на одну функцию и передаёт
    исходный путь в параметре __path. Возвращаем его во Flask, чтобы маршруты работали
    при любой точке входа (app.py или api/index.py)."""

    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        from urllib.parse import parse_qsl, urlencode
        qs = environ.get("QUERY_STRING", "")
        if "__path=" in qs:
            pairs = parse_qsl(qs, keep_blank_values=True)
            orig = next((v for k, v in pairs if k == "__path"), None)
            if orig is not None:
                environ["PATH_INFO"] = orig if orig.startswith("/") else "/" + orig
                environ["SCRIPT_NAME"] = ""
                environ["QUERY_STRING"] = urlencode([(k, v) for k, v in pairs if k != "__path"])
        return self.wsgi(environ, start_response)


def create_app():
    secret = os.getenv("SECRET_KEY")
    if ON_VERCEL and not secret:
        raise RuntimeError("SECRET_KEY не задан")
    url = database_url()
    app = Flask(__name__, static_folder=str(BASE / "public" / "static"), static_url_path="/static")
    app.config.update(
        SECRET_KEY=secret or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=url,
        # serverless: не держим пул соединений, их держит пулер Supabase
        SQLALCHEMY_ENGINE_OPTIONS={"poolclass": NullPool} if url.startswith("postgresql") else {},
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=365),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "1" if ON_VERCEL else "0") == "1",
    )
    db.init_app(app)

    if os.getenv("AUTO_INIT", "0" if ON_VERCEL else "1") == "1":
        with app.app_context():
            init_db()
            S.ensure_bucket()

    @app.cli.command("init")
    def init_command():
        """Создать таблицы, стартовые конверты и бакет."""
        init_db()
        S.ensure_bucket()
        print("Готово: таблицы, конверты и хранилище на месте")

    register_routes(app)
    app.wsgi_app = RestorePath(app.wsgi_app)
    return app


# ---------------------------------------------------------------- helpers
def quest_level() -> int:
    return session.get("quest_level", -1)


def unlocked() -> bool:
    return quest_level() >= len(Q.LEVELS)


def require_unlocked(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not unlocked():
            return redirect(url_for("quest"))
        return f(*a, **kw)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*a, **kw)
    return wrapper


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token", "")
    if not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400, "CSRF")


KIND_EXT = {"image": IMG_EXT, "audio": AUDIO_EXT}


def apply_media(obj, form):
    """Поля image/audio из формы: новый путь (уже загружен браузером) или удаление."""
    for field in ("image", "audio"):
        old = getattr(obj, field)
        if form.get(f"remove_{field}"):
            S.delete(old)
            setattr(obj, field, None)
            old = None
        new = form.get(f"{field}_path", "").strip()
        if new and S.valid_path(new) and new.startswith(field + "/") and new != old:
            S.delete(old)
            setattr(obj, field, new)


# ---------------------------------------------------------------- routes
def register_routes(app: Flask):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.template_filter("paragraphs")
    def paragraphs(text: str):
        parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
        return Markup("".join(f"<p>{escape(p).replace(chr(10), Markup('<br>'))}</p>" for p in parts))

    @app.template_filter("plural_days")
    def plural_days(n: int):
        n = abs(int(n))
        if n % 10 == 1 and n % 100 != 11:
            return "день"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "дня"
        return "дней"

    # ----- квест
    @app.get("/")
    def index():
        return redirect(url_for("home" if unlocked() else "quest"))

    @app.get("/quest")
    def quest():
        if request.args.get("reset") is not None:
            session.pop("quest_level", None)
            session.pop("mistakes", None)
        return render_template("quest.html", intro=Q.INTRO, wrong=Q.WRONG, hint_after=Q.HINT_AFTER)

    @app.get("/api/quest")
    def quest_state():
        lvl = quest_level()
        if lvl < 0:
            return jsonify(stage="intro")
        if lvl >= len(Q.LEVELS):
            return jsonify(stage="final", final=Q.FINAL, total=len(Q.LEVELS))
        return jsonify(stage="level", level=Q.public_level(lvl))

    @app.post("/api/quest/start")
    def quest_start():
        check_csrf()
        session.permanent = True
        if quest_level() < 0:
            session["quest_level"] = 0
        return quest_state()

    @app.post("/api/quest/answer")
    def quest_answer():
        check_csrf()
        lvl = quest_level()
        if not 0 <= lvl < len(Q.LEVELS):
            return quest_state()
        answer = (request.get_json(silent=True) or {}).get("answer", "")[:200]
        level = Q.LEVELS[lvl]
        if Q.is_correct(answer, level):
            session["quest_level"] = lvl + 1
            return jsonify(correct=True, success=level["success"])
        return jsonify(correct=False)

    # ----- приложение
    @app.get("/home")
    @require_unlocked
    def home():
        envelopes = (Envelope.query.filter_by(published=True)
                     .order_by(Envelope.position, Envelope.id).all())
        days = (N.today() - TOGETHER_SINCE).days
        note = N.ensure_today_published()
        if note and not session.get("admin") and not note.seen_at:
            note.seen_at = datetime.utcnow()
            db.session.commit()
        return render_template("home.html", envelopes=envelopes, days=days, note=note,
                               has_archive=len(N.archive()) > 1)

    @app.get("/notes")
    @require_unlocked
    def notes_archive():
        return render_template("notes.html", notes=N.archive())

    @app.get("/envelope/<int:eid>")
    @require_unlocked
    def envelope(eid):
        env = db.get_or_404(Envelope, eid)
        if not env.published:
            abort(404)
        if not session.get("admin"):
            env.open_count += 1
            env.first_opened_at = env.first_opened_at or datetime.utcnow()
            db.session.commit()
        return render_template("envelope.html", env=env)

    @app.get("/media/<path:name>")
    @require_unlocked
    def media(name):
        if not S.valid_path(name):
            abort(404)
        if S.USE_SUPABASE:
            try:
                return redirect(S.public_url(name, ""))
            except (S.StorageError, Exception):
                abort(404)
        return send_from_directory(S.UPLOADS, name)

    @app.get("/healthz")
    def healthz():
        """Для пинга из GitHub Actions: держит проект Supabase активным."""
        try:
            db.session.execute(text("select 1"))
            return jsonify(ok=True)
        except SQLAlchemyError:
            return jsonify(ok=False), 503

    # ----- загрузка файлов (админ): браузер грузит напрямую по выданной ссылке
    @app.post("/admin/upload-url")
    @require_admin
    def admin_upload_url():
        check_csrf()
        data = request.get_json(silent=True) or {}
        kind = data.get("kind")
        name = str(data.get("filename", ""))
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ON_VERCEL and not S.USE_SUPABASE:
            return jsonify(error="Не настроено хранилище: добавь SUPABASE_SECRET_KEY в Vercel и сделай Redeploy"), 503
        if kind not in KIND_EXT or ext not in KIND_EXT[kind]:
            return jsonify(error=f"Формат .{ext or '?'} не поддерживается"), 400
        if ext == "jpeg":
            ext = "jpg"
        path = f"{kind}/{uuid.uuid4().hex}.{ext}"
        ctype = str(data.get("content_type") or "application/octet-stream")[:100]
        try:
            target = S.upload_target(path, ctype, url_for("admin_local_upload", path=path), csrf_token())
        except S.StorageError as e:
            return jsonify(error=f"Хранилище не ответило: {e}"), 502
        return jsonify(path=path, **target)

    @app.put("/admin/local-upload/<path:path>")
    @require_admin
    def admin_local_upload(path):
        check_csrf()
        if S.USE_SUPABASE or not S.valid_path(path):
            abort(404)
        S.save_local(path, request.get_data())
        return jsonify(ok=True)

    # ----- админка
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            check_csrf()
            pw = os.getenv("ADMIN_PASSWORD", "")
            if pw and hmac.compare_digest(request.form.get("password", ""), pw):
                session.permanent = True
                session["admin"] = True
                session["quest_level"] = max(quest_level(), len(Q.LEVELS))  # чтобы видеть всё
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("admin"))
            flash("Неверный пароль")
        return render_template("admin/login.html")

    @app.post("/admin/logout")
    def admin_logout():
        check_csrf()
        session.clear()
        return redirect(url_for("quest"))

    @app.get("/admin")
    @require_admin
    def admin():
        envelopes = Envelope.query.order_by(Envelope.position, Envelope.id).all()
        return render_template("admin/index.html", envelopes=envelopes)

    @app.route("/admin/envelope/new", methods=["GET", "POST"])
    @app.route("/admin/envelope/<int:eid>", methods=["GET", "POST"])
    @require_admin
    def admin_edit(eid=None):
        env = db.get_or_404(Envelope, eid) if eid else Envelope(emoji="💌", position=Envelope.query.count())
        if request.method == "POST":
            check_csrf()
            f = request.form
            env.title = f.get("title", "").strip() or "Без названия"
            env.emoji = f.get("emoji", "").strip()[:16] or "💌"
            env.body = f.get("body", "")
            url = f.get("music_url", "").strip()
            env.music_url = url if url.startswith(("https://", "http://")) else None
            try:
                env.position = int(f.get("position") or 0)
            except ValueError:
                env.position = 0
            env.published = "published" in f
            apply_media(env, f)
            db.session.add(env)
            db.session.commit()
            flash("Сохранено")
            return redirect(url_for("admin"))
        return render_template("admin/edit.html", env=env)

    @app.post("/admin/envelope/<int:eid>/delete")
    @require_admin
    def admin_delete(eid):
        check_csrf()
        env = db.get_or_404(Envelope, eid)
        S.delete(env.image)
        S.delete(env.audio)
        db.session.delete(env)
        db.session.commit()
        flash("Удалено")
        return redirect(url_for("admin"))

    # ----- админка: записки
    @app.get("/admin/notes")
    @require_admin
    def admin_notes():
        queued = (Note.query.filter(Note.published_on.is_(None))
                  .order_by(Note.scheduled_for.is_(None), Note.scheduled_for, Note.id).all())
        published = Note.query.filter(Note.published_on.isnot(None)).order_by(Note.published_on.desc()).all()
        return render_template("admin/notes.html", queued=queued, published=published,
                               queue_left=N.queue_left(),
                               note_time="%02d:%02d" % N.note_time())

    @app.route("/admin/note/new", methods=["GET", "POST"])
    @app.route("/admin/note/<int:nid>", methods=["GET", "POST"])
    @require_admin
    def admin_note_edit(nid=None):
        note = db.get_or_404(Note, nid) if nid else Note()
        if request.method == "POST":
            check_csrf()
            f = request.form
            note.text = f.get("text", "").strip()
            d = f.get("scheduled_for", "").strip()
            try:
                note.scheduled_for = date.fromisoformat(d) if d else None
            except ValueError:
                note.scheduled_for = None
            apply_media(note, f)
            if not (note.text or note.image or note.audio):
                flash("Пустую записку не сохраняю")
                return redirect(request.url)
            db.session.add(note)
            db.session.commit()
            flash("Записка сохранена")
            return redirect(url_for("admin_notes"))
        return render_template("admin/note_edit.html", note=note)

    @app.post("/admin/note/<int:nid>/delete")
    @require_admin
    def admin_note_delete(nid):
        check_csrf()
        note = db.get_or_404(Note, nid)
        S.delete(note.image)
        S.delete(note.audio)
        db.session.delete(note)
        db.session.commit()
        flash("Удалено")
        return redirect(url_for("admin_notes"))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
