# Для Фарангиз — v4 (Vercel + Supabase)

Квест → приложение: «мы вместе N дней», записка дня, архив, конверты «Открой, когда…».

- **Vercel** запускает Flask как serverless-функцию (регион Франкфурт).
- **Supabase Postgres** хранит конверты, записки и прогресс.
- **Supabase Storage** хранит фото и голосовые (приватный бакет, временные ссылки). Файлы грузятся из браузера напрямую, фото перед загрузкой сжимаются.
- **GitHub Actions** раз в 2 дня пингует сайт, чтобы бесплатный Supabase не уходил на паузу.

Локально без Supabase всё работает на SQLite и папке `uploads/`.

---

## Локальный запуск

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # SECRET_KEY и ADMIN_PASSWORD
flask --app app run
```

---

## Деплой

### 1. Supabase

1. Создай проект на supabase.com. **Region: Central EU (Frankfurt)**, рядом с функцией Vercel. Запиши пароль базы.
2. Кнопка **Connect** → **Transaction pooler** (порт **6543**) → скопируй строку, подставь пароль. Это `DATABASE_URL`.
3. **Project Settings → API Keys**:
   - URL проекта → `SUPABASE_URL` (`https://xxxx.supabase.co`)
   - **Secret key** (`sb_secret_…`) → `SUPABASE_SECRET_KEY`. Никому не показывай!
   - **Publishable key** (`sb_publishable_…`) → `SUPABASE_PUBLISHABLE_KEY`

   Если в проекте только старые ключи, подойдут `service_role` и `anon`.

### 2. Инициализация (один раз, со своего компьютера)

Впиши значения Supabase в `.env` и выполни:

```bash
flask --app app init
```

Команда создаст таблицы, 8 конвертов-черновиков и приватный бакет `gift`.

### 3. GitHub

Создай **приватный** репозиторий: в `quest_config.py` лежат ответы на квест. Залей проект:

```bash
git init && git add . && git commit -m "gift"
git branch -M main
git remote add origin git@github.com:ЛОГИН/gift.git
git push -u origin main
```

`.env` в репозиторий не попадёт, он в `.gitignore`.

### 4. Vercel

1. **Add New → Project** → выбери репозиторий.
2. **Framework Preset: Other**. Build и Output не трогай.
3. **Project Name** станет адресом: `forfarangiz` → `forfarangiz.vercel.app`.
4. **Environment Variables**:

   | Переменная | Значение |
   |---|---|
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `ADMIN_PASSWORD` | твой пароль |
   | `DATABASE_URL` | из шага 1.2 |
   | `SUPABASE_URL` | из шага 1.3 |
   | `SUPABASE_SECRET_KEY` | из шага 1.3 |
   | `SUPABASE_PUBLISHABLE_KEY` | из шага 1.3 |
   | `NOTE_TIME` | `08:30` |
   | `TZ_NAME` | `Asia/Tashkent` |

5. **Deploy**.

### 5. Проверка

- `https://АДРЕС/healthz` → `{"ok": true}`
- `https://АДРЕС/admin` → войди, загрузи фото в конверт, сохрани, открой конверт
- открой сайт в режиме инкогнито с телефона и пройди квест так, как пройдёт она

### 6. Keepalive (защита от паузы Supabase)

GitHub → репозиторий → **Settings → Secrets and variables → Actions → Variables** → **New variable**:
`SITE_URL` = `https://АДРЕС` (без `/` в конце).

Потом **Actions → keepalive → Run workflow**, чтобы проверить, что зелёное.

### 7. Свой домен (по желанию)

Vercel → проект → **Settings → Domains** → добавь домен и пропиши DNS-записи, которые покажет Vercel.

---

## Если что-то не работает

- **Vercel → проект → Logs**: там текст ошибки.
- `DATABASE_URL не задан` / `SECRET_KEY не задан`: проверь переменные, затем **Redeploy**.
- Фото не загружается («хранилище ответило 4xx»): проверь `SUPABASE_PUBLISHABLE_KEY` и что `flask --app app init` создал бакет (Supabase → Storage → `gift`).
- Сайт не открывается, а Supabase пишет **Paused** → **Restore project** в дашборде и проверь, что keepalive работает.

## Изменения в коде

Правишь локально → `git push` → Vercel сам передеплоит за минуту.
