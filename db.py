import statistics
import aiosqlite

DB_NAME = "filters.db"


# ---------------- INIT ----------------

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            source TEXT DEFAULT 'kufar',
            name TEXT,
            url TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            initialized INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS sent_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filter_id INTEGER NOT NULL,
            ad_id TEXT NOT NULL,
            UNIQUE(filter_id, ad_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS market_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filter_id INTEGER NOT NULL,
            ad_id TEXT NOT NULL,
            title TEXT,
            price REAL,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(filter_id, ad_id)
        )
        """)

        # ---------------- MIGRATIONS ----------------

        try:
            await db.execute(
                "ALTER TABLE filters ADD COLUMN source TEXT DEFAULT 'kufar'"
            )
        except:
            pass

        try:
            await db.execute(
                "ALTER TABLE filters ADD COLUMN name TEXT"
            )
        except:
            pass

        try:
            await db.execute(
                "ALTER TABLE filters ADD COLUMN active INTEGER DEFAULT 1"
            )
        except:
            pass

        try:
            await db.execute(
                "ALTER TABLE filters ADD COLUMN initialized INTEGER DEFAULT 0"
            )
        except:
            pass

        try:
            await db.execute(
                "ALTER TABLE filters ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
        except:
            pass

        await db.commit()


# ---------------- FILTERS ----------------

async def add_filter(
        telegram_id: int,
        url: str
):
    """
    Старый метод.
    Ничего не ломаем.
    """

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT INTO filters
            (
                telegram_id,
                url
            )
            VALUES (?, ?)
        """, (
            telegram_id,
            url
        ))

        await db.commit()


async def add_filter_v2(
        telegram_id: int,
        source: str,
        name: str,
        url: str
):
    """
    Новый метод.
    Для Mini App.
    """

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT INTO filters
            (
                telegram_id,
                source,
                name,
                url
            )
            VALUES (?, ?, ?, ?)
        """, (
            telegram_id,
            source,
            name,
            url
        ))

        await db.commit()


async def get_all_filters():

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute("""
            SELECT
                id,
                telegram_id,
                source,
                url,
                initialized
            FROM filters
            WHERE active = 1
        """)

        return await cur.fetchall()


async def get_user_filters(
        telegram_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute("""
            SELECT
                id,
                source,
                COALESCE(name, 'Без названия'),
                url
            FROM filters
            WHERE telegram_id = ?
            ORDER BY id DESC
        """, (
            telegram_id,
        ))

        return await cur.fetchall()


async def delete_filter(filter_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            "DELETE FROM filters WHERE id=?",
            (filter_id,)
        )

        await db.execute(
            "DELETE FROM sent_ads WHERE filter_id=?",
            (filter_id,)
        )

        await db.execute(
            "DELETE FROM market_ads WHERE filter_id=?",
            (filter_id,)
        )

        await db.commit()


async def deactivate_filter(filter_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE filters
            SET active = 0
            WHERE id = ?
        """, (
            filter_id,
        ))

        await db.commit()


async def mark_initialized(filter_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE filters
            SET initialized = 1
            WHERE id = ?
        """, (
            filter_id,
        ))

        await db.commit()


# ---------------- BOT DEDUP ----------------

async def ad_already_sent(
        filter_id: int,
        ad_id: str
):

    if not ad_id:
        return False

    ad_id = str(ad_id).strip()

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute("""
            SELECT 1
            FROM sent_ads
            WHERE filter_id=?
            AND ad_id=?
        """, (
            filter_id,
            ad_id
        ))

        return await cur.fetchone() is not None


async def save_sent_ad(
        filter_id: int,
        ad_id: str
):

    if not ad_id:
        return

    ad_id = str(ad_id).strip()

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT OR IGNORE INTO sent_ads
            (
                filter_id,
                ad_id
            )
            VALUES (?, ?)
        """, (
            filter_id,
            ad_id
        ))

        await db.commit()


# ---------------- MARKET ----------------

async def save_market_ad(
        filter_id,
        ad_id,
        title,
        price,
        link
):

    if not ad_id:
        return

    ad_id = str(ad_id).strip()

    if not price or not (10 <= price <= 10000000):
        price = None

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT OR IGNORE INTO market_ads
            (
                filter_id,
                ad_id,
                title,
                price,
                link
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            filter_id,
            ad_id,
            title,
            price,
            link
        ))

        await db.commit()


async def get_market_stats():

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute("""
            SELECT price
            FROM market_ads
            WHERE price IS NOT NULL
        """)

        rows = await cur.fetchall()

        prices = [
            r[0]
            for r in rows
            if r[0] and 10 <= r[0] <= 10000000
        ]

        if not prices:

            return {
                "total": 0,
                "avg_price": 0,
                "median_price": 0,
                "min_price": 0,
                "max_price": 0
            }

        return {
            "total": len(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "median_price": round(statistics.median(prices), 2),
            "min_price": min(prices),
            "max_price": max(prices)
        }


# ---------------- STATS ----------------

async def get_stats():

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute("""
            SELECT COUNT(*)
            FROM filters
            WHERE active = 1
        """)

        total_filters = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COUNT(*)
            FROM sent_ads
        """)

        total_sent = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COUNT(DISTINCT telegram_id)
            FROM filters
        """)

        total_users = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COUNT(*)
            FROM market_ads
        """)

        total_ads = (await cur.fetchone())[0]

        return {
            "total_users": total_users,
            "total_filters": total_filters,
            "total_sent": total_sent,
            "total_ads": total_ads
        }
    async def get_filters_for_panel():

        async with aiosqlite.connect(DB_NAME) as db:

            cur = await db.execute("""
                SELECT
                    id,
                    telegram_id,
                    source,
                    COALESCE(name, 'Без названия'),
                    url,
                    active
                FROM filters
                ORDER BY id DESC
            """)

        return await cur.fetchall()