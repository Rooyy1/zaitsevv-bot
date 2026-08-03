"""
Клавиатуры.

ВАЖНО про "ссылку с готовым текстом в поле ввода":
Telegram поддерживает формат ссылки  https://t.me/<username>?text=<текст>
При переходе по такой ссылке у получателя открывается личка с указанным
юзернеймом, и в поле ввода СРАЗУ подставляется заданный текст —
пользователю останется только нажать "отправить".
Это официальная (не хак) фича t.me-ссылок, работает в актуальных клиентах
Telegram (мобильные и десктоп).
"""
from urllib.parse import quote
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from messages import PREFILL_TEXT, BTN_ZAPISATSYA


def contact_deeplink(username: str, prefill_text: str = PREFILL_TEXT) -> str:
    username = username.lstrip("@")
    return f"https://t.me/{username}?text={quote(prefill_text)}"


def zapisatsya_kb(username: str, button_text: str = BTN_ZAPISATSYA) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, url=contact_deeplink(username))]
        ]
    )
