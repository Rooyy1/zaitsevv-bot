"""
Обработчик /start — точка входа пользователя в воронку.
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import database as db
import messages as msg

logger = logging.getLogger(__name__)
router = Router()

# ID фото для приветственного сообщения
WELCOME_PHOTO_ID = "AgACAgIAAxkBAANSamy7xhqcA4I0mIETogeUCwQUsRQAAk8Yaxs-vGhLkZA9CikuiAYBAAMCAAN5AAM9BA"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    
    # ИЗМЕНЕНИЕ: всегда создаем/обновляем пользователя и сбрасываем прогресс
    # Проверяем, существует ли пользователь
    existing = await db.get_user(user.id)
    
    if existing:
        # Пользователь есть — сбрасываем все этапы, чтобы начать заново
        await db.reset_user_progress(user.id)
        logger.info(f"Сброшен прогресс для пользователя {user.id}")
    else:
        # Новый пользователь
        await db.create_user_if_not_exists(user.id, user.username, user.full_name)
    
    # Отправляем приветственное сообщение с фото
    await message.answer_photo(
        photo=WELCOME_PHOTO_ID,
        caption=msg.WELCOME_TEXT,
        parse_mode="HTML"
    )
    
    # Отмечаем, что кружок отправлен
    await db.mark_stage_sent(user.id, "welcome")