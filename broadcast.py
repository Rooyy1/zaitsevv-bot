"""
Рассылка по базе пользователей.

Вход: /рассылка <пароль>  (пароль задан в config.BROADCAST_PASSWORD)
Дальше бот пошагово спрашивает:
  1) текст сообщения (можно писать с форматированием прямо в Telegram —
     жирный/курсив/ссылки и т.д., бот скопирует форматирование как есть)
  2) нужны ли кнопки, и если да — в формате:
        Текст кнопки - https://ссылка
        Текст кнопки 2 - https://ссылка2
     (каждая кнопка на новой строке, кнопки будут в один столбец)
  3) подтверждение и запуск рассылки по всей базе с прогрессом
"""
import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

import database as db
from config import ADMIN_IDS, BROADCAST_PASSWORD

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class Broadcast(StatesGroup):
    waiting_password = State()
    waiting_text = State()
    waiting_buttons = State()
    waiting_confirm = State()


def _parse_buttons(raw: str) -> InlineKeyboardMarkup | None:
    raw = raw.strip()
    if raw.lower() in ("нет", "no", "-", "без кнопок"):
        return None
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or " - " not in line:
            continue
        text, url = line.rsplit(" - ", 1)
        text, url = text.strip(), url.strip()
        if text and url:
            rows.append([InlineKeyboardButton(text=text, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


@router.message(Command("рассылка"))
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2:
        # пароль сразу в команде: /рассылка trainerssZaitsev
        if parts[1].strip() == BROADCAST_PASSWORD:
            await state.set_state(Broadcast.waiting_text)
            await message.answer(
                "✅ Пароль верный.\n\n"
                "Пришли сообщение для рассылки (можно с форматированием — жирный, курсив, ссылки)."
            )
            return
        else:
            await message.answer("❌ Неверный пароль.")
            return

    await state.set_state(Broadcast.waiting_password)
    await message.answer("Введи пароль для доступа к рассылке:")


@router.message(Broadcast.waiting_password)
async def check_password(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    if (message.text or "").strip() != BROADCAST_PASSWORD:
        await message.answer("❌ Неверный пароль. Попробуй снова, либо /cancel")
        return
    await state.set_state(Broadcast.waiting_text)
    await message.answer(
        "✅ Пароль верный.\n\n"
        "Пришли сообщение для рассылки (можно с форматированием — жирный, курсив, ссылки)."
    )


@router.message(Broadcast.waiting_text)
async def receive_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    if not message.text and not message.caption:
        await message.answer("Пришли текстовое сообщение (или подпись к фото/файлу с текстом).")
        return

    # сохраняем html-разметку исходного сообщения через entities
    html_text = message.html_text if message.text else message.caption
    await state.update_data(
        text=html_text,
        photo_file_id=message.photo[-1].file_id if message.photo else None,
        document_file_id=message.document.file_id if message.document else None,
    )
    await state.set_state(Broadcast.waiting_buttons)
    await message.answer(
        "Добавить кнопки?\n\n"
        "Если да — пришли в формате (каждая с новой строки):\n"
        "<code>Текст кнопки - https://ссылка</code>\n\n"
        "Если кнопки не нужны — напиши «нет»",
        parse_mode="HTML",
    )


@router.message(Broadcast.waiting_buttons)
async def receive_buttons(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    kb = _parse_buttons(message.text or "")
    data = await state.get_data()
    await state.update_data(buttons=kb.model_dump() if kb else None)
    await state.set_state(Broadcast.waiting_confirm)

    preview = data["text"]
    count = len(await db.get_all_user_ids())
    await message.answer(
        f"📋 <b>Предпросмотр рассылки</b> (получат {count} чел.):\n\n{preview}",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await message.answer("Отправляем? Напиши «да» для запуска или «отмена» для отмены.")


@router.message(Broadcast.waiting_confirm)
async def confirm_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        return
    answer = (message.text or "").strip().lower()
    if answer not in ("да", "yes", "отправить"):
        await state.clear()
        await message.answer("Рассылка отменена.")
        return

    data = await state.get_data()
    text = data["text"]
    photo_file_id = data.get("photo_file_id")
    document_file_id = data.get("document_file_id")
    kb_data = data.get("buttons")
    kb = InlineKeyboardMarkup.model_validate(kb_data) if kb_data else None

    await state.clear()
    user_ids = await db.get_all_user_ids()
    status_msg = await message.answer(f"🚀 Рассылка запущена. Получателей: {len(user_ids)}")

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            if photo_file_id:
                await bot.send_photo(user_id, photo_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
            elif document_file_id:
                await bot.send_document(user_id, document_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
            sent += 1
        except TelegramForbiddenError:
            await db.deactivate_user(user_id)
            failed += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                if photo_file_id:
                    await bot.send_photo(user_id, photo_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
                elif document_file_id:
                    await bot.send_document(user_id, document_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
                else:
                    await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
                sent += 1
            except Exception:
                failed += 1
        except TelegramBadRequest:
            failed += 1
        # антифлуд — не более ~25 сообщений в секунду
        await asyncio.sleep(0.04)

    await status_msg.edit_text(f"✅ Рассылка завершена.\nУспешно: {sent}\nОшибок: {failed}")


@router.message(Command("cancel"))
async def cancel_any(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("Отменено.")
