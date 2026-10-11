"""Логика записки дня."""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from models import Note, db

TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Tashkent"))
LOW_QUEUE = 3


def note_time() -> tuple[int, int]:
    h, _, m = os.getenv("NOTE_TIME", "08:30").partition(":")
    return int(h), int(m or 0)


def today() -> date:
    return datetime.now(TZ).date()


def note_time_passed() -> bool:
    now = datetime.now(TZ)
    return (now.hour, now.minute) >= note_time()


def ensure_today_published() -> Note | None:
    """Если время записки уже наступило, а сегодняшняя ещё не вышла — выпускает её."""
    note = todays_note()
    if note or not note_time_passed():
        return note
    return publish_today()[0]


def todays_note() -> Note | None:
    return Note.query.filter_by(published_on=today()).first()


def queue_left() -> int:
    """Сколько записок без даты ещё ждёт в очереди."""
    return Note.query.filter(Note.published_on.is_(None), Note.scheduled_for.is_(None)).count()


def pick_note(day: date) -> Note | None:
    dated = (Note.query.filter(Note.published_on.is_(None), Note.scheduled_for == day)
             .order_by(Note.id).first())
    if dated:
        return dated
    return (Note.query.filter(Note.published_on.is_(None), Note.scheduled_for.is_(None))
            .order_by(Note.id).first())


def publish_today() -> tuple[Note | None, bool]:
    """Возвращает (записка, новая_ли). Идемпотентно: второй вызов за день вернёт ту же."""
    existing = todays_note()
    if existing:
        return existing, False
    note = pick_note(today())
    if note:
        note.published_on = today()
        db.session.commit()
    return note, bool(note)


def archive() -> list[Note]:
    return (Note.query.filter(Note.published_on.isnot(None), Note.published_on <= today())
            .order_by(Note.published_on.desc()).all())
