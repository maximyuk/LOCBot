#!/usr/bin/env python3
import asyncio
import html
import os
import re
import sys
import tempfile
import urllib.error
import zipfile
from pathlib import Path

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError as exc:
    print(
        "Встановлено неправильний пакет telegram.\n"
        "Виконай:\n"
        "  python -m pip uninstall -y telegram\n"
        "  python -m pip install -U python-telegram-bot",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from count_loc import (
    DEFAULT_EXTENSIONS,
    DEFAULT_IGNORE_DIRS,
    count_project,
    download_and_extract_repo,
    normalize_extensions,
)


URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
BTN_COUNT = "Порахувати LOC"
BTN_TOP_10 = "Топ 10"
BTN_TOP_20 = "Топ 20"
BTN_HELP = "Допомога"
BOT_TOKEN = ""


def _main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_COUNT, BTN_TOP_10], [BTN_TOP_20, BTN_HELP]],
        resize_keyboard=True,
    )


def _inline_result_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Оновити: Топ 10", callback_data="refresh_top_10"),
                InlineKeyboardButton("Оновити: Топ 20", callback_data="refresh_top_20"),
            ]
        ]
    )


def _count_repo_from_url(url: str, top: int):
    extensions = normalize_extensions(set(DEFAULT_EXTENSIONS))
    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    with tempfile.TemporaryDirectory(prefix="loc_counter_") as tmp:
        root = download_and_extract_repo(url, Path(tmp))
        per_file, total = count_project(root, extensions, ignore_dirs)
    return per_file, total, top


def _render_result(url: str, per_file, total: int, top: int) -> str:
    lines = [
        f"Репозиторій: {url}",
        f"Файлів пораховано: {len(per_file)}",
        f"Загалом non-empty рядків: {total}",
        "",
        f"Топ {min(top, len(per_file))} файлів:",
    ]
    for loc, rel in per_file[:top]:
        lines.append(f"{loc:>8}  {rel}")
    return "\n".join(lines)


def _render_result_html(url: str, per_file, total: int, top: int) -> str:
    text = _render_result(url, per_file, total, top)
    safe_text = html.escape(text)
    return f"<b>Результат підрахунку LOC</b>\n<pre>{safe_text}</pre>"


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    if not match:
        return None
    return match.group(0)


def _get_user_top(context: ContextTypes.DEFAULT_TYPE) -> int:
    return int(context.user_data.get("top", 10))


def _set_user_top(context: ContextTypes.DEFAULT_TYPE, top: int) -> None:
    context.user_data["top"] = top


async def _run_count(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, top: int) -> None:
    context.user_data["last_url"] = url
    await update.effective_message.reply_text("Рахую рядки коду, зачекай...")

    try:
        per_file, total, top = await asyncio.to_thread(_count_repo_from_url, url, top)
        result_html = _render_result_html(url, per_file, total, top)
        await update.effective_message.reply_text(
            result_html,
            parse_mode="HTML",
            reply_markup=_inline_result_buttons(),
        )
    except ValueError as exc:
        await update.effective_message.reply_text(f"Помилка: {exc}")
    except (urllib.error.URLError, zipfile.BadZipFile) as exc:
        await update.effective_message.reply_text(f"Не вдалося завантажити репозиторій: {exc}")
    except Exception as exc:
        await update.effective_message.reply_text(f"Невідома помилка: {exc}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _set_user_top(context, 10)
    await update.message.reply_text(
        "Надішли посилання на GitHub репозиторій.\n"
        "Приклад: https://github.com/owner/repo\n\n"
        "Можеш змінити формат кнопками: Топ 10 / Топ 20.",
        reply_markup=_main_keyboard(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команди:\n"
        "/start - запуск бота\n"
        "/help - ця довідка\n\n"
        "Кнопки:\n"
        "Порахувати LOC - підказка для вставки посилання\n"
        "Топ 10 / Топ 20 - скільки файлів показувати у результаті\n\n"
        "Можна просто кинути URL і бот одразу порахує.",
        reply_markup=_main_keyboard(),
    )


async def handle_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == BTN_COUNT:
        await update.message.reply_text("Встав GitHub URL репозиторію.")
        return True
    if text == BTN_TOP_10:
        _set_user_top(context, 10)
        await update.message.reply_text("Встановлено: показувати Топ 10 файлів.")
        return True
    if text == BTN_TOP_20:
        _set_user_top(context, 20)
        await update.message.reply_text("Встановлено: показувати Топ 20 файлів.")
        return True
    if text == BTN_HELP:
        await help_cmd(update, context)
        return True
    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return

    if await handle_button_text(update, context, text):
        return

    url = _extract_url(text)
    if not url:
        await update.message.reply_text(
            "Не знайшов посилання. Надішли GitHub URL, наприклад:\n"
            "https://github.com/owner/repo"
        )
        return

    top = _get_user_top(context)
    await _run_count(update, context, url, top)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    last_url = context.user_data.get("last_url")
    if not last_url:
        await query.message.reply_text("Немає останнього URL. Надішли нове посилання.")
        return

    if query.data == "refresh_top_10":
        top = 10
    elif query.data == "refresh_top_20":
        top = 20
    else:
        return

    _set_user_top(context, top)
    await query.message.reply_text(f"Оновлюю результат з налаштуванням: Топ {top}.")
    await _run_count(update, context, last_url, top)


def main() -> int:
    token = BOT_TOKEN.strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print(
            "Токен не задано.\n"
            "Встав токен у змінну BOT_TOKEN в tg_loc_bot.py"
        )
        return 1

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
