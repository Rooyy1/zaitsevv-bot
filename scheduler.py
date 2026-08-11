"""
Планировщик воронки.

Работает не через asyncio.sleep(интервал) на каждого юзера (это не
переживает рестарт бота), а через периодическое сканирование БД:
каждые SCHEDULER_TICK_SECONDS секунд проверяем, у кого из пользователей
"созрел" следующий этап воронки, и отправляем.

Это тот же паттерн restart-safe рассылки, что используется в остальных
ботах — таймстампы лежат в БД, а не в памяти процесса.
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InputMediaPhoto

import database as db
import messages as msg
from config import (
    SCHEDULER_TICK_SECONDS,
    DOZHIM2_PHOTO_1,
    DOZHIM2_PHOTO_2,
    DOZHIM2_PHOTO_3,
    DOZHIM3_PHOTO_ID,
)
from keyboards import zapisatsya_kb

logger = logging.getLogger(__name__)


async def _send_safe(bot: Bot, user_id: int, **kwargs) -> bool:
    """Отправка с обработкой блокировки бота пользователем."""
    try:
        await bot.send_message(chat_id=user_id, **kwargs)
        return True
    except TelegramForbiddenError:
        # пользователь заблокировал бота — деактивируем, чтобы не долбить дальше
        await db.deactivate_user(user_id)
        logger.info(f"Пользователь {user_id} заблокировал бота, деактивирован")
        return False
    except TelegramBadRequest as e:
        logger.warning(f"Ошибка отправки пользователю {user_id}: {e}")
        return False


async def _process_leadmagnet(bot: Bot, interval: int) -> None:
    user_ids = await db.get_users_due_for("welcome", "leadmagnet", interval)
    if not user_ids:
        return
    leadmagnet_file_id = await db.get_setting("leadmagnet_file_id")
    for user_id in user_ids:
        if leadmagnet_file_id:
            try:
                await bot.send_document(
                    chat_id=user_id,
                    document=leadmagnet_file_id,
                    caption=msg.LEAD_MAGNET_TEXT,
                    parse_mode="HTML",
                )
                await db.mark_stage_sent(user_id, "leadmagnet")
            except TelegramForbiddenError:
                await db.deactivate_user(user_id)
            except TelegramBadRequest as e:
                logger.warning(f"Не смог отправить лид-магнит {user_id}: {e}")
        else:
            # файл ещё не загружен админом — просто текст, чтобы не блокировать воронку
            sent = await _send_safe(bot, user_id, text=msg.LEAD_MAGNET_TEXT, parse_mode="HTML")
            if sent:
                await db.mark_stage_sent(user_id, "leadmagnet")


async def _process_offer(bot: Bot, interval: int, contact_username: str) -> None:
    user_ids = await db.get_users_due_for("leadmagnet", "offer", interval)
    if not user_ids:
        return
    text = msg.OFFER_TEXT
    kb = zapisatsya_kb(contact_username, button_text=msg.BTN_ZANYAT_MESTO)
    for user_id in user_ids:
        sent = await _send_safe(bot, user_id, text=text, parse_mode="HTML", reply_markup=kb)
        if sent:
            await db.mark_stage_sent(user_id, "offer")


async def _process_dozhim1(bot: Bot, interval: int, contact_username: str) -> None:
    user_ids = await db.get_users_due_for("offer", "dozhim1", interval)
    if not user_ids:
        return
    text = msg.DOZHIM1_TEXT
    kb = zapisatsya_kb(contact_username, button_text=msg.BTN_ZAPISATSYA)
    for user_id in user_ids:
        sent = await _send_safe(bot, user_id, text=text, parse_mode="HTML", reply_markup=kb)
        if sent:
            await db.mark_stage_sent(user_id, "dozhim1")


async def _process_dozhim2(bot: Bot, interval: int, contact_username: str) -> None:
    # считается от offer_sent_at, а не от dozhim1 — как размечено на карте
    user_ids = await db.get_users_due_for("offer", "dozhim2", interval)
    if not user_ids:
        return
    text = msg.DOZHIM2_TEXT
    media = [
        InputMediaPhoto(media=DOZHIM2_PHOTO_1, caption=text, parse_mode="HTML"),
        InputMediaPhoto(media=DOZHIM2_PHOTO_2),
        InputMediaPhoto(media=DOZHIM2_PHOTO_3),
    ]
    for user_id in user_ids:
        try:
            await bot.send_media_group(chat_id=user_id, media=media)
            await db.mark_stage_sent(user_id, "dozhim2")
        except TelegramForbiddenError:
            await db.deactivate_user(user_id)
            logger.info(f"Пользователь {user_id} заблокировал бота, деактивирован")
        except TelegramBadRequest as e:
            logger.warning(f"Не смог отправить дожим 2 (альбом) пользователю {user_id}: {e}")


async def _process_dozhim3(bot: Bot, interval: int, contact_username: str) -> None:
    user_ids = await db.get_users_due_for("dozhim2", "dozhim3", interval)
    if not user_ids:
        return
    text = msg.DOZHIM3_TEXT
    kb = zapisatsya_kb(contact_username, button_text=msg.BTN_ZHMI)
    for user_id in user_ids:
        try:
            await bot.send_photo(
                chat_id=user_id,
                photo=DOZHIM3_PHOTO_ID,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            await db.mark_stage_sent(user_id, "dozhim3")
        except TelegramForbiddenError:
            await db.deactivate_user(user_id)
            logger.info(f"Пользователь {user_id} заблокировал бота, деактивирован")
        except TelegramBadRequest as e:
            logger.warning(f"Не смог отправить дожим 3 пользователю {user_id}: {e}")


async def scheduler_loop(bot: Bot) -> None:
    logger.info("Планировщик воронки запущен")
    while True:
        try:
            intervals = await db.get_all_intervals()
            contact_username = await db.get_setting("contact_username")
            # fallback на дефолтный юзернейм, если в БД пусто
            if not contact_username:
                from config import DEFAULT_CONTACT_USERNAME
                contact_username = DEFAULT_CONTACT_USERNAME

            await _process_leadmagnet(bot, intervals["interval_leadmagnet"])
            await _process_offer(bot, intervals["interval_offer"], contact_username)
            await _process_dozhim1(bot, intervals["interval_dozhim1"], contact_username)
            await _process_dozhim2(bot, intervals["interval_dozhim2"], contact_username)
            await _process_dozhim3(bot, intervals["interval_dozhim3"], contact_username)
        except Exception:
            logger.exception("Ошибка в цикле планировщика")

        await asyncio.sleep(SCHEDULER_TICK_SECONDS)
