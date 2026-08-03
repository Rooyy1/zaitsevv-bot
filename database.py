"""
Слой работы с БД (aiosqlite).
Вся воронка построена на таймстампах в БД, а не на asyncio.sleep —
это значит, что при перезапуске бота (например, редеплой на Railway)
ни один пользователь не "потеряется" и не получит сообщение повторно.
"""
import time
import aiosqlite
from typing import Optional, Any
from config import DB_PATH, DEFAULT_INTERVALS, WELCOME_VIDEO_FILE_ID, LEADMAGNET_FILE_ID
from config import DB_PATH, DEFAULT_INTERVALS

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    joined_at INTEGER,

    welcome_sent INTEGER DEFAULT 0,
    welcome_sent_at INTEGER,

    leadmagnet_sent INTEGER DEFAULT 0,
    leadmagnet_sent_at INTEGER,

    offer_sent INTEGER DEFAULT 0,
    offer_sent_at INTEGER,

    dozhim1_sent INTEGER DEFAULT 0,
    dozhim1_sent_at INTEGER,

    dozhim2_sent INTEGER DEFAULT 0,
    dozhim2_sent_at INTEGER,

    dozhim3_sent INTEGER DEFAULT 0,
    dozhim3_sent_at INTEGER,

    is_active INTEGER DEFAULT 1
);
"""

CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS)
        await db.execute(CREATE_SETTINGS)
        await db.commit()

        # сидируем интервалы по умолчанию
        for key, value in DEFAULT_INTERVALS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        
        # ИЗМЕНЕНИЕ: вставляем file_id из конфига
        for key, value in [
            ("welcome_video_file_id", WELCOME_VIDEO_FILE_ID),
            ("leadmagnet_file_id", LEADMAGNET_FILE_ID),
            ("contact_username", ""),  # оставляем пустым, можно задать позже
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        
        # ОБНОВЛЕНИЕ: если file_id уже есть, обновляем их
        await db.execute(
            "UPDATE settings SET value = ? WHERE key = 'welcome_video_file_id'",
            (WELCOME_VIDEO_FILE_ID,)
        )
        await db.execute(
            "UPDATE settings SET value = ? WHERE key = 'leadmagnet_file_id'",
            (LEADMAGNET_FILE_ID,)
        )
        
        await db.commit()



# ───────────────────────── settings ─────────────────────────

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            if row is None or row[0] in (None, ""):
                return default
            return row[0]


async def set_setting(key: str, value: Any) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        await db.commit()


async def get_all_intervals() -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'interval_%'"
        ) as cur:
            rows = await cur.fetchall()
            return {k: int(v) for k, v in rows}


# ───────────────────────── users ─────────────────────────

async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def create_user_if_not_exists(user_id: int, username: str | None, full_name: str | None) -> bool:
    """Возвращает True, если пользователь был создан заново (первый /start)."""
    existing = await get_user(user_id)
    if existing:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, int(time.time())),
        )
        await db.commit()
    return True


async def mark_stage_sent(user_id: int, stage: str) -> None:
    """stage: welcome | leadmagnet | offer | dozhim1 | dozhim2 | dozhim3"""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {stage}_sent = 1, {stage}_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        await db.commit()


async def get_all_user_ids(active_only: bool = True) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT user_id FROM users"
        if active_only:
            query += " WHERE is_active = 1"
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def deactivate_user(user_id: int) -> None:
    """Если бот получил ошибку 'бот заблокирован' — помечаем юзера неактивным."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        await db.commit()


# ─────────────────── выборки для планировщика ───────────────────

async def get_users_due_for(stage_from: str, stage_to: str, interval_seconds: int) -> list[int]:
    """
    Находит пользователей, у которых этап `stage_from` отправлен,
    этап `stage_to` ещё не отправлен, и с момента `stage_from_sent_at`
    прошло >= interval_seconds.
    """
    threshold = int(time.time()) - interval_seconds
    query = f"""
        SELECT user_id FROM users
        WHERE {stage_from}_sent = 1
          AND {stage_to}_sent = 0
          AND {stage_from}_sent_at <= ?
          AND is_active = 1
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, (threshold,)) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

# Добавьте в конец файла database.py:

async def reset_user_progress(user_id: int) -> None:
    """Сбрасывает все этапы воронки для пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET 
                welcome_sent = 0,
                welcome_sent_at = NULL,
                leadmagnet_sent = 0,
                leadmagnet_sent_at = NULL,
                offer_sent = 0,
                offer_sent_at = NULL,
                dozhim1_sent = 0,
                dozhim1_sent_at = NULL,
                dozhim2_sent = 0,
                dozhim2_sent_at = NULL,
                dozhim3_sent = 0,
                dozhim3_sent_at = NULL,
                is_active = 1
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()