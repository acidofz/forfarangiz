"""Конфиг квеста. Хранится только на сервере — в браузер уходят вопросы и подсказки, но не ответы."""
import re

INTRO = {
    "emoji": "💌",
    "title": "Привет, Фарангиз",
    "text": [
        "Я приготовил для тебя кое-что. Но просто так не отдам 😏",
        "Ответь на несколько вопросов про нас — и в конце узнаешь, где тебя ждёт сюрприз.",
    ],
    "button": "Начать",
}

LEVELS = [
    {
        "question": "Где мы познакомились?",
        "answers": [],  # ответы — в переменной окружения QUEST_ANSWERS
        "contains": True,
        "hint": "Там, где все пишут код и пьют слишком много кофе.",
        "image": None,
        "success": "Конечно! Лучшее, что дала мне эта школа 💻❤️",
    },
    {
        "question": "Какого числа мы начали встречаться?",
        "answers": [],  # ответы — в переменной окружения QUEST_ANSWERS
        "contains": True,
        "hint": "Середина сентября.",
        "image": None,
        "success": "Запомнила 🥹",
    },
    {
        "question": "Где мы впервые поели вместе?",
        "answers": [],  # ответы — в переменной окружения QUEST_ANSWERS
        "contains": True,
        "hint": "Твоя подсказка.",  # TODO: впиши подсказку
        "image": None,
        "success": "Да! Я тогда так волновался 😅",
    },
    {
        "question": "Что я сказал тебе в первый день?",
        "answers": [],  # ответы — в переменной окружения QUEST_ANSWERS
        "contains": True,
        "hint": "Это было про то, что мы делаем в школе 21.",
        "image": None,
        "success": "Ты помнишь 🥰",
    },
    {
        "question": "Последний вопрос. Кто тебя любит больше всех?",
        "answers": [],  # ответы — в переменной окружения QUEST_ANSWERS
        "contains": True,
        "hint": "Это тот, кто сделал этот сайт 😉",
        "image": None,
        "success": "Правильно ❤️",
    },
]

FINAL = {
    "emoji": "🎁",
    "title": "Ты прошла!",
    "text": [
        "Я знал, что ты справишься.",
        "Спасибо, что ты есть. Каждый день с тобой — лучший.",
    ],
    "clue": "Твой подарок ждёт тебя… дальше.",
    "signature": "— Амир",
    "button": "Дальше →",
}

WRONG = [
    "Не-а 🙃 Попробуй ещё",
    "Почти… но нет",
    "Ты точно это помнишь? 🤨",
    "Неправильно, но я всё равно тебя люблю",
    "Подумай ещё чуть-чуть 💭",
]

HINT_AFTER = 2


# Ответы можно хранить вне кода: переменная окружения QUEST_ANSWERS =
# JSON-список списков, по одному на вопрос: [["ответ 1", "вариант"], ["ответ 2"], ...]
# Тогда репозиторий можно держать публичным.
def _answers_from_env():
    import json
    import os
    raw = os.getenv("QUEST_ANSWERS")
    if not raw:
        return
    data = json.loads(raw)
    if len(data) != len(LEVELS):
        raise RuntimeError(f"QUEST_ANSWERS: {len(data)} ответов на {len(LEVELS)} вопросов")
    for lvl, answers in zip(LEVELS, data):
        lvl["answers"] = [str(a) for a in answers]


_answers_from_env()


def norm(s: str) -> str:
    s = str(s).lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_correct(answer: str, level: dict) -> bool:
    a = norm(answer)
    if not a:
        return False
    for ans in level["answers"]:
        b = norm(ans)
        if a == b or (level["contains"] and b in a):
            return True
    return False


def public_level(i: int) -> dict:
    """То, что можно отдать в браузер: без ответов."""
    lvl = LEVELS[i]
    return {
        "index": i,
        "total": len(LEVELS),
        "question": lvl["question"],
        "hint": lvl["hint"],
        "image": lvl["image"],
    }
