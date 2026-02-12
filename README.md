# GitHub LOC Counter + Telegram Bot

Інструмент для підрахунку кількості написаних рядків коду (non-empty LOC):
- локально по папці;
- по GitHub-репозиторію за посиланням;
- по конкретній папці в репозиторії (`/tree/...`);
- через Telegram-бота з кнопками.

## Можливості

- Підрахунок `non-empty` рядків (порожні не враховуються).
- Рекурсивний обхід директорій.
- Фільтр по розширеннях (`--ext`).
- Ігнор службових папок (`.git`, `node_modules`, `venv`, `dist`, `build` тощо).
- Вивід топу файлів за LOC (`--top`).
- Telegram-бот:
  - український інтерфейс;
  - кнопки `Топ 10 / Топ 20`;
  - inline-кнопки для швидкого оновлення результату;
  - гарний HTML-вивід у `pre` блоці.

## Структура

- `count_loc.py` - CLI-скрипт для підрахунку LOC.
- `tg_loc_bot.py` - Telegram-бот поверх `count_loc.py`.
- `requirements.txt` - залежності для бота.
- `Dockerfile` - контейнер для деплою (зокрема Fly.io).
- `.dockerignore` - ігнор зайвих файлів при build.

## Вимоги

- Python `3.10+`

## Встановлення

```bash
pip install -r requirements.txt
```

## Використання CLI

### 1. Інтерактивний режим

```bash
python count_loc.py
```

Скрипт попросить вставити:
- GitHub URL, або
- локальний шлях, або
- `Enter` для поточної папки.

### 2. Локальна папка

```bash
python count_loc.py C:\path\to\project
```

### 3. GitHub репозиторій

```bash
python count_loc.py https://github.com/owner/repo
```

### 4. Конкретна папка в репозиторії

```bash
python count_loc.py https://github.com/owner/repo/tree/main/src/keyboards
```

### 5. Додаткові параметри

```bash
python count_loc.py "https://github.com/owner/repo" --top 30 --ext py,js,ts --ignore-dirs .git,node_modules,venv
```

## Використання Telegram-бота

### 1. Додай токен

Відкрий `tg_loc_bot.py` і встав токен у:

```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
```

Або використовуй змінну середовища `TELEGRAM_BOT_TOKEN`.

### 2. Запуск

```bash
python tg_loc_bot.py
```

### 3. Робота в Telegram

- Надішли `/start`
- Скинь GitHub посилання, наприклад:
  - `https://github.com/owner/repo`
  - `https://github.com/owner/repo/tree/main/src`
- Кнопками обирай формат виводу (`Топ 10 / Топ 20`)

## Deploy to Fly.io

### 1. Встанови Fly CLI

```bash
# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

# Або через scoop/choco, якщо користуєшся ними
```

### 2. Логін

```bash
fly auth login
```

### 3. Ініціалізація застосунку

У корені проєкту:

```bash
fly launch --no-deploy
```

Рекомендації під час майстра:
- `App name`: придумай унікальну назву (наприклад `locbot-123`)
- `Region`: обери найближчий регіон
- `Postgres/Redis`: `No`

### 4. Додай токен як secret (рекомендовано)

```bash
fly secrets set TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
```

Після цього можеш лишити `BOT_TOKEN = ""` у коді.

### 5. Деплой

```bash
fly deploy
```

### 6. Перевірка логів

```bash
fly logs
```

## Приклад результату

```text
Репозиторій: https://github.com/owner/repo
Файлів пораховано: 128
Загалом non-empty рядків: 9421

Топ 10 файлів:
     812  src/main.py
     603  src/service/api.py
...
```

## Типові проблеми

### `ImportError: cannot import name 'Update' from 'telegram'`

Встановлено неправильний пакет `telegram`.

```bash
python -m pip uninstall -y telegram
python -m pip install -U python-telegram-bot
```

### Бот пише, що токен не задано

Перевір, що:
- або в `tg_loc_bot.py` задано `BOT_TOKEN = "..."`,
- або на сервері встановлено `TELEGRAM_BOT_TOKEN`.

### URL на підпапку не працює

Використовуй формат:

```text
https://github.com/owner/repo/tree/branch/path/to/folder
```

## Примітки

- Підрахунок йде по `non-empty` рядках, а не по "чистому коду" без коментарів.
- За замовчуванням показується лише топ файлів (це не означає, що інших файлів немає).
- Якщо токен уже десь публікувався, обов'язково перевипусти його в BotFather (`/revoke`).
