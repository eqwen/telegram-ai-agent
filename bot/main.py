from __future__ import annotations

import asyncio
import html
import logging
from contextlib import suppress

import aiohttp
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import settings
from bot.memory import Message, SQLiteMemory
from bot.prompts import SYSTEM_PROMPT


logger = logging.getLogger(__name__)
memory = SQLiteMemory(settings.database_path, settings.max_context_messages)
TELEGRAM_MESSAGE_LIMIT = 4096


def build_prompt(messages: list[Message], user_message: str) -> str:
    parts = [f"System:\n{SYSTEM_PROMPT}", ""]

    for message in messages:
        speaker = "User" if message.role == "user" else "Assistant"
        parts.append(f"{speaker}:\n{message.content}")
        parts.append("")

    parts.append(f"User:\n{user_message}")
    parts.append("")
    parts.append("Assistant:")

    prompt = "\n".join(parts)
    if len(prompt) <= settings.max_prompt_chars:
        return prompt

    # If old messages are still too large after row pruning, trim by characters.
    return prompt[-settings.max_prompt_chars :]


async def ask_ollama(prompt: str) -> str:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(settings.ollama_url, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

    answer = str(data.get("response", "")).strip()
    if not answer:
        return "Я получил пустой ответ от модели. Попробуйте переформулировать запрос."
    return answer


def split_telegram_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        chunk = remaining[:limit]
        split_at = max(chunk.rfind("\n"), chunk.rfind(" "))
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [chunk for chunk in chunks if chunk]


async def reply_long_text(update: Update, text: str) -> None:
    if not update.message:
        return

    for chunk in split_telegram_text(text):
        await update.message.reply_text(chunk)


async def keep_typing(update: Update) -> None:
    if not update.effective_chat:
        return

    while True:
        await update.effective_chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not update.message:
        return

    await update.message.reply_text(
        "Привет! Я AI-ассистент в Telegram. Напишите вопрос, а я отвечу с учетом контекста нашей переписки.\n\n"
        "Команда /reset очищает память диалога."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not update.message or not update.effective_user:
        return

    await memory.reset(update.effective_user.id)
    await update.message.reply_text("Готово. Память этого диалога очищена.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    user_text = update.message.text or ""
    if not user_text.strip():
        await update.message.reply_text("Пожалуйста, отправьте текстовое сообщение.")
        return

    typing_task = asyncio.create_task(keep_typing(update))

    try:
        context_messages = await memory.get_context(user_id)
        prompt = build_prompt(context_messages, user_text)
        answer = await ask_ollama(prompt)

        await memory.add_message(user_id, "user", user_text)
        await memory.add_message(user_id, "assistant", answer)

        await reply_long_text(update, answer)
    except aiohttp.ClientResponseError as exc:
        logger.exception("Ollama returned HTTP error: %s", exc.status)
        await update.message.reply_text("Модель временно недоступна. Проверьте Ollama и попробуйте позже.")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        logger.exception("Ollama request failed")
        await update.message.reply_text("Не удалось связаться с Ollama. Попробуйте еще раз чуть позже.")
    except Exception:
        logger.exception("Unexpected error while handling message")
        await update.message.reply_text("Произошла ошибка. Я уже записал ее в лог.")
    finally:
        typing_task.cancel()
        with suppress(asyncio.CancelledError):
            await typing_task


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error. Update=%r", update, exc_info=context.error)

    if isinstance(update, Update) and update.message:
        message = html.escape("Произошла внутренняя ошибка. Попробуйте позже.")
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def post_init(application: Application) -> None:
    del application
    await memory.initialize()
    logger.info("SQLite memory initialized at %s", settings.database_path)


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    configure_logging()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram AI bot with Ollama model %s", settings.ollama_model)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
