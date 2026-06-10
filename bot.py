import asyncio
from parser_avby import fetch_ads_avby
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

from config import TOKEN, CHECK_INTERVAL

from db import (
    init_db,
    add_filter_v2,
    get_user_filters,
    get_all_filters,
    ad_already_sent,
    save_sent_ad,
    save_market_ad,
    delete_filter,
    get_stats,
    mark_initialized
)

from parser import fetch_ads_playwright


check_lock = asyncio.Lock()


# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 Kufar Monitor\n\n"
        "/add <url> - добавить поиск\n"
        "/list - мои поиски\n"
        "/delete <id> - удалить поиск\n"
        "/stats - статистика"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Использование:\n/add <url>"
        )
        return

    url = context.args[0].strip()

    # определяем источник

    if "kufar.by" in url:

        source = "kufar"

    elif "av.by" in url:

        source = "avby"

    else:

        await update.message.reply_text(
            "Поддерживаются только:\n"
            "- kufar.by\n"
            "- av.by"
        )
        return

    name = f"{source.upper()} поиск"

    await add_filter_v2(
        update.effective_user.id,
        source,
        name,
        url
    )

    await update.message.reply_text(
        f"✅ Поиск добавлен\n\n"
        f"Источник: {source}\n"
        f"{url}"
    )


async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    filters = await get_user_filters(
        update.effective_user.id
    )

    if not filters:

        await update.message.reply_text(
            "У вас нет поисков"
        )
        return

    text = "🔍 Ваши поиски\n\n"

    for f in filters:

        text += (
            f"ID: {f[0]}\n"
            f"Источник: {f[1]}\n"
            f"Название: {f[2]}\n"
            f"{f[3]}\n\n"
        )

    await update.message.reply_text(text)


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Использование:\n/delete ID"
        )
        return

    try:

        filter_id = int(context.args[0])

    except:

        await update.message.reply_text(
            "ID должен быть числом"
        )
        return

    await delete_filter(filter_id)

    await update.message.reply_text(
        f"🗑 Поиск #{filter_id} удалён"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    s = await get_stats()

    await update.message.reply_text(
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {s['total_users']}\n"
        f"🔍 Поисков: {s['total_filters']}\n"
        f"📨 Отправлено объявлений: {s['total_sent']}\n"
        f"📦 Объявлений в базе: {s['total_ads']}"
    )


# ---------------- CHECK ADS ----------------

async def check_ads(context: ContextTypes.DEFAULT_TYPE):

    if check_lock.locked():

        print("⛔️ SKIP (already running)")
        return

    async with check_lock:

        print("\n==============================")
        print("🚀 START CHECK CYCLE")
        print("==============================")

        filters = await get_all_filters()

        print(f"📦 TOTAL FILTERS: {len(filters)}")

        total_sent = 0

        for (
            filter_id,
            telegram_id,
            source,
            url,
            initialized
        ) in filters:

            print("\n------------------------------")
            print(f"📍 FILTER #{filter_id}")
            print(f"📡 SOURCE: {source}")
            print(f"🔗 URL: {url}")

            try:

                # ---------------- SOURCE ----------------

                if source == "kufar":

                    ads = await fetch_ads_playwright(
                        url
                    )

                elif source == "avby":

                    ads = await fetch_ads_avby(
                        url
                    )

                else:

                    ads = []
                print(
                    f"📄 FOUND ADS: {len(ads)}"
                )

                # ---------------- FIRST INIT ----------------

                if not initialized:

                    print(
                        f"🆕 FIRST START FILTER #{filter_id}"
                    )

                    for ad in ads:

                        item_id = ad.get("id")

                        if item_id:

                            await save_sent_ad(
                                filter_id,
                                str(item_id)
                            )

                    await mark_initialized(
                        filter_id
                    )

                    continue

                # ---------------- SEND ADS ----------------

                sent_count = 0

                MAX_SEND_PER_CYCLE = 10

                for ad in ads:

                    if sent_count >= MAX_SEND_PER_CYCLE:

                        print(
                            "🛑 LIMIT REACHED"
                        )
                        break

                    item_id = ad.get("id")

                    if not item_id:
                        continue

                    item_id = str(
                        item_id
                    ).strip()

                    if await ad_already_sent(
                        filter_id,
                        item_id
                    ):
                        continue

                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=
                        f"{ad['text']}\n\n"
                        f"{ad['link']}"
                    )

                    await save_sent_ad(
                        filter_id,
                        item_id
                    )

                    await save_market_ad(
                        filter_id,
                        item_id,
                        ad["text"],
                        ad.get("price"),
                        ad["link"]
                    )

                    sent_count += 1
                    total_sent += 1

                print(
                    f"📤 SENT FOR FILTER: {sent_count}"
                )

            except Exception as e:

                print(
                    f"❌ ERROR FILTER "
                    f"{filter_id}: {e}"
                )

        print("\n==============================")
        print(
            f"🏁 CYCLE DONE | "
            f"TOTAL SENT: {total_sent}"
        )
        print("==============================\n")


# ---------------- STARTUP ----------------

async def on_startup(app):

    await init_db()


# ---------------- MAIN ----------------

def main():

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    app.post_init = on_startup

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("add", add)
    )

    app.add_handler(
        CommandHandler("list", list_filters)
    )

    app.add_handler(
        CommandHandler("delete", delete)
    )

    app.add_handler(
        CommandHandler("stats", stats)
    )

    app.job_queue.run_repeating(
        check_ads,
        interval=CHECK_INTERVAL,
        first=5
    )

    print("🤖 BOT STARTED")

    app.run_polling()


if __name__ == "__main__":
    main()