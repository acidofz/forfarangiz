from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Envelope(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)        # "Открой, когда грустно"
    emoji = db.Column(db.String(16), default="💌")
    body = db.Column(db.Text, default="")                    # письмо
    image = db.Column(db.String(255))                        # имя файла в uploads/
    audio = db.Column(db.String(255))                        # голосовое
    music_url = db.Column(db.String(500))                    # ссылка на песню
    position = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=False)         # видно ли ей
    open_count = db.Column(db.Integer, default=0)
    first_opened_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Note(db.Model):
    """Записка дня."""
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, default="")
    image = db.Column(db.String(255))
    audio = db.Column(db.String(255))
    scheduled_for = db.Column(db.Date)       # конкретная дата, иначе — из очереди
    published_on = db.Column(db.Date)        # в какой день реально вышла
    seen_at = db.Column(db.DateTime)         # открыла на сайте
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


DEFAULT_ENVELOPES = [
    ("Открой, когда грустно", "🌧️"),
    ("Открой, когда скучаешь по мне", "🫂"),
    ("Открой, когда злишься на меня", "😤"),
    ("Открой, когда не можешь уснуть", "🌙"),
    ("Открой, когда устала", "☕"),
    ("Открой, когда хочешь улыбнуться", "🌸"),
    ("Открой, когда сомневаешься в себе", "💪"),
    ("Открой в свой день рождения", "🎂"),
]
