import logging
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import messages as msg
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

WELCOME_PHOTO_ID = "AgACAgIAAxkBAAO-ansnW6x0iRPc0tXPRQk6vZPmeFEAAooZaxtTJthLmzTY7doa9p8BAAMCAAN5AAM9BA"


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    
    existing = await db.get_user(user.id)
    
    if existing:
        await db.reset_user_progress(user.id)
        logger.info(f"Сброшен прогресс для пользователя {user.id}")
        status = "🔄 Вернулся"
    else:
        await db.create_user_if_not_exists(user.id, user.username, user.full_name)
        status = "✅ Новый пользователь!"
    
    # --- УВЕДОМЛЕНИЕ АДМИНУ С КНОПКОЙ ---
    for admin_id in ADMIN_IDS:
        try:
            username = f"@{user.username}" if user.username else user.full_name
            
            # Кнопка для открытия чата с пользователем
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💬 Написать пользователю",
                        url=f"tg://user?id={user.id}"
                    )]
                ]
            )
            
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 <b>{status}</b>\n\n"
                    f"👤 {username}\n"
                    f"🆔 <code>{user.id}</code>\n"
                    f"📅 {message.date.strftime('%d.%m.%Y %H:%M:%S')}"
                ),
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
    
    # --- ПРИВЕТСТВИЕ ПОЛЬЗОВАТЕЛЮ ---
    await message.answer_photo(
        photo=WELCOME_PHOTO_ID,
        caption=msg.WELCOME_TEXT,
        parse_mode="HTML"
    )
    
    await db.mark_stage_sent(user.id, "welcome")