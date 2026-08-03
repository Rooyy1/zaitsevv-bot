"""
Админ-панель:
- /интервалы — просмотр и изменение таймингов воронки (кнопками)
- /set_video — (ответом на кружок/видео-кружок) сохранить file_id приветственного кружка
- /set_leadmagnet — (ответом на файл) сохранить file_id лид-магнита
- /set_username — сменить юзернейм, на который ведут кнопки "ЗАПИСАТЬСЯ"
- /stats — короткая статистика по воронке
"""
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import ADMIN_IDS, INTERVAL_LABELS

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


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


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    import aiosqlite
    from config import DB_PATH

    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT COUNT(*), "
            "SUM(welcome_sent), SUM(leadmagnet_sent), SUM(offer_sent), "
            "SUM(dozhim1_sent), SUM(dozhim2_sent), SUM(dozhim3_sent), "
            "SUM(is_active) "
            "FROM users"
        ) as cur:
            row = await cur.fetchone()

    total, welcome, lead, offer, d1, d2, d3, active = [x or 0 for x in row]
    await message.answer(
        "📊 <b>Статистика воронки</b>\n\n"
        f"Всего пользователей: {total}\n"
        f"Активных (не заблокировали бота): {active}\n\n"
        f"Кружок отправлен: {welcome}\n"
        f"Лид-магнит отправлен: {lead}\n"
        f"Оффер отправлен: {offer}\n"
        f"Дожим 1 отправлен: {d1}\n"
        f"Дожим 2 отправлен: {d2}\n"
        f"Дожим 3 отправлен: {d3}\n",
        parse_mode="HTML",
    )
