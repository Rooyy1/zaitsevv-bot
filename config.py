"""
Конфигурация бота.
Все секреты (токен, пароль рассылки, айди админов) берутся из переменных окружения (.env).
"""
import os
from dotenv import load_dotenv

load_dotenv()
# Добавьте в конец файла:

# Прямое указание file_id (вставьте сюда свои ID)
WELCOME_VIDEO_FILE_ID = "DQACAgUAAxkBAAMNamh8fMPyzOb7zYyDKTkeQ1QxgMAAAjAgAAKTzMhVtTjerlSTMb89BA"  # например: "AQADAgAD...="
LEADMAGNET_FILE_ID = "BQACAgIAAxkBAAPTansumaVYZu9uE-JZHTH39cdyW9cAAriiAAJTJthL4AABkMgnkjWrPQQ"      # например: "BQACAgIAAxkB..."

# Фото для сообщения "дожим 3" (последнее место)
DOZHIM3_PHOTO_ID = "AgACAgIAAxkBAAPHanstaUSlZr7_IDt6Iy-D17RTd2gAAqEZaxtTJthLRpOUvtd9ohwBAAMCAAN5AAM9BA"

# Фото-отзывы для сообщения "дожим 2" (альбом из 3 фото)
DOZHIM2_PHOTO_1 = "AgACAgIAAxkBAAPOanstzNgyQ9iWa670TXf9GDzeBNUAAqMZaxtTJthLBIHvF3LuIFIBAAMCAAN5AAM9BA"
DOZHIM2_PHOTO_2 = "AgACAgIAAxkBAAPQanst0oPROWUeqr8xYDah8m8PCWsAAqQZaxtTJthL5MEzbCZnUZYBAAMCAAN5AAM9BA"
DOZHIM2_PHOTO_3 = "AgACAgIAAxkBAAPKanstjU3RvJaoEg_Czy6LBuEnD2EAAqIZaxtTJthLeYDNs3rLF6UBAAMCAAN5AAM9BA"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ID администраторов бота (через запятую в .env), например: ADMIN_IDS=123456789,987654321
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]

# Пароль для входа в рассылку
BROADCAST_PASSWORD = os.getenv("BROADCAST_PASSWORD", "trainerssZaitsev")

# Юзернейм, на который ведут все кнопки "ЗАПИСАТЬСЯ" (без @)
DEFAULT_CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "slava_gold")

DB_PATH = os.getenv("DB_PATH", "funnel_bot.db")

# ──────────────────────────────────────────────────────────────
# ИНТЕРВАЛЫ ВОРОНКИ (значения по умолчанию, в секундах).
# Их можно менять прямо в боте командой /интервалы — они хранятся в БД,
# эти значения используются только один раз, при первом запуске (сидинг).
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# ИНТЕРВАЛЫ ВОРОНКИ (значения по умолчанию, в секундах).
# Их можно менять прямо в боте командой /интервалы — они хранятся в БД,
# эти значения используются только один раз, при первом запуске (сидинг).
# ──────────────────────────────────────────────────────────────
DEFAULT_INTERVALS = {
    "interval_leadmagnet": 2,
    "interval_offer": 5,
    "interval_dozhim1": 10,
    "interval_dozhim2": 12,
    "interval_dozhim3": 14,
}

# Человекочитаемые названия интервалов для меню /интервалы
INTERVAL_LABELS = {
    "interval_leadmagnet": "Кружок → Лид-магнит",
    "interval_offer": "Лид-магнит → Оффер",
    "interval_dozhim1": "Оффер → Дожим 1",
    "interval_dozhim2": "Оффер → Дожим 2",
    "interval_dozhim3": "Дожим 2 → Дожим 3",
}

# Как часто сканировать базу и слать то, что "созрело" (в секундах)
SCHEDULER_TICK_SECONDS = 15
