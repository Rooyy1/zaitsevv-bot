"""
Админ-панель:
- /интервалы — просмотр и изменение таймингов воронки (кнопками)
- /set_video — (ответом на кружок/видео-кружок) сохранить file_id приветственного кружка
- /set_leadmagnet — (ответом на файл) сохранить file_id лид-магнита
- /set_username — сменить юзернейм, на который ведут кнопки "ЗАПИСАТЬСЯ"
- /стата — расширенная статистика по пользователям
"""
import logging
from datetime import datetime
import aiosqlite

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import messages as msg
from config import ADMIN_IDS, INTERVAL_LABELS, DB_PATH

logger = logging.getLogger(__name__)
router = Router()

WELCOME_PHOTO_ID = "AgACAgIAAxkBAAO-ansnW6x0iRPc0tXPRQk6vZPmeFEAAooZaxtTJthLmzTY7doa9p8BAAMCAAN5AAM9BA"


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== ИНТЕРВАЛЫ ====================

class IntervalEdit(StatesGroup):
    waiting_value = State()


def _format_duration(seconds: int) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    if secs or not parts:
        parts.append(f"{secs}с")
    return " ".join(parts)


def _intervals_kb(intervals: dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in INTERVAL_LABELS.items():
        value = intervals.get(key, 0)
        rows.append([
            InlineKeyboardButton(
                text=f"{label}: {_format_duration(value)} ✏️",
                callback_data=f"editint:{key}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("интервалы"))
@router.message(Command("intervals"))
async def cmd_intervals(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    intervals = await db.get_all_intervals()
    await message.answer(
        "⏱ <b>Тайминги воронки</b>\n\nНажми на пункт, чтобы изменить значение.",
        parse_mode="HTML",
        reply_markup=_intervals_kb(intervals),
    )


@router.callback_query(F.data.startswith("editint:"))
async def cb_edit_interval(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    key = callback.data.split(":", 1)[1]
    await state.update_data(interval_key=key)
    await state.set_state(IntervalEdit.waiting_value)
    label = INTERVAL_LABELS.get(key, key)
    await callback.message.answer(
        f"Введи новое значение для «{label}».\n\n"
        f"Можно писать так: <code>30с</code>, <code>10м</code>, <code>4ч</code>, <code>2д</code>, "
        f"или просто число секунд (например <code>3600</code>).",
        parse_mode="HTML",
    )
    await callback.answer()


def _parse_duration(text: str) -> int | None:
    text = text.strip().lower().replace(" ", "")
    if text.isdigit():
        return int(text)
    units = {"с": 1, "s": 1, "м": 60, "min": 60, "m": 60, "ч": 3600, "h": 3600, "д": 86400, "d": 86400}
    for suffix, mult in sorted(units.items(), key=lambda x: -len(x[0])):
        if text.endswith(suffix):
            number_part = text[: -len(suffix)]
            if number_part.replace(".", "", 1).isdigit():
                return int(float(number_part) * mult)
    return None


@router.message(IntervalEdit.waiting_value)
async def process_interval_value(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    seconds = _parse_duration(message.text or "")
    if seconds is None or seconds < 0:
        await message.answer("Не понял значение 🤔 Пример: <code>4ч</code> или <code>14400</code>", parse_mode="HTML")
        return
    data = await state.get_data()
    key = data["interval_key"]
    await db.set_setting(key, seconds)
    await state.clear()
    intervals = await db.get_all_intervals()
    await message.answer(
        f"Готово ✅ {INTERVAL_LABELS.get(key, key)} = {_format_duration(seconds)}",
    )
    await message.answer(
        "⏱ <b>Тайминги воронки</b>",
        parse_mode="HTML",
        reply_markup=_intervals_kb(intervals),
    )


# ==================== НАСТРОЙКИ ====================

@router.message(Command("set_video"))
async def cmd_set_video(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    reply = message.reply_to_message
    file_id = None
    if reply:
        if reply.video_note:
            file_id = reply.video_note.file_id
        elif reply.video:
            file_id = reply.video.file_id
    if not file_id:
        await message.answer(
            "Ответь этой командой на сообщение с видео-кружком (video note), чтобы сохранить его."
        )
        return
    await db.set_setting("welcome_video_file_id", file_id)
    await message.answer("✅ Приветственный кружок сохранён.")


@router.message(Command("set_leadmagnet"))
async def cmd_set_leadmagnet(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    reply = message.reply_to_message
    file_id = None
    if reply:
        if reply.document:
            file_id = reply.document.file_id
        elif reply.video:
            file_id = reply.video.file_id
        elif reply.photo:
            file_id = reply.photo[-1].file_id
    if not file_id:
        await message.answer(
            "Ответь этой командой на сообщение с файлом лид-магнита, чтобы сохранить его."
        )
        return
    await db.set_setting("leadmagnet_file_id", file_id)
    await message.answer("✅ Лид-магнит сохранён.")


@router.message(Command("set_username"))
async def cmd_set_username(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /set_username твой_юзернейм (без @)")
        return
    username = parts[1].strip().lstrip("@")
    await db.set_setting("contact_username", username)
    await message.answer(f"✅ Кнопки «ЗАПИСАТЬСЯ» теперь ведут на @{username}")


# ==================== СТАТИСТИКА ====================

@router.message(Command("стата"))
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Общее количество пользователей
        async with conn.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        
        # Активные пользователи
        async with conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cur:
            active = (await cur.fetchone())[0]
        
        # Кто прошёл каждый этап
        stages = {
            "welcome": "Приветствие",
            "leadmagnet": "Лид-магнит",
            "offer": "Оффер",
            "dozhim1": "Дожим 1",
            "dozhim2": "Дожим 2",
            "dozhim3": "Дожим 3",
        }
        
        stats_text = ""
        for key, label in stages.items():
            async with conn.execute(f"SELECT COUNT(*) FROM users WHERE {key}_sent = 1") as cur:
                count = (await cur.fetchone())[0]
                stats_text += f"• {label}: {count}\n"
        
        # Кто неактивен (заблокировали бота)
        async with conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 0") as cur:
            blocked = (await cur.fetchone())[0]
    
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {total}\n"
        f"🟢 <b>Активных:</b> {active}\n"
        f"🔴 <b>Заблокировали бота:</b> {blocked}\n\n"
        f"<b>📈 Прохождение воронки:</b>\n"
        f"{stats_text}\n"
        f"<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
        parse_mode="HTML"
    )


# ==================== /START С УВЕДОМЛЕНИЕМ ====================

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