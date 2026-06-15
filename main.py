#!/usr/bin/env python3
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler

from src.config import BOT_TOKEN, DATABASE_URL
from src.database.connection import init_pool
from src.handlers import start, platform_handler, af_handler, adj_handler
from src.handlers import singular_handler, farm_handler, proxy_handler, admin_handler
from src.handlers import subscription_handler

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Exiting.")
        sys.exit(1)
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not set. Exiting.")
        sys.exit(1)

    logger.info("Initializing database pool...")
    init_pool()

    logger.info("Running database migrations...")
    _run_migrations()

    logger.info("Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    # Start handler
    for handler in start.get_handlers():
        app.add_handler(handler)

    # Admin handler
    for handler in admin_handler.get_handlers():
        app.add_handler(handler)

    # Subscription handler
    for handler in subscription_handler.get_handlers():
        app.add_handler(handler)

    # Feature handlers
    for handler in af_handler.get_handlers():
        app.add_handler(handler)

    for handler in adj_handler.get_handlers():
        app.add_handler(handler)

    for handler in singular_handler.get_handlers():
        app.add_handler(handler)

    for handler in farm_handler.get_handlers():
        app.add_handler(handler)

    for handler in proxy_handler.get_handlers():
        app.add_handler(handler)

    for handler in platform_handler.get_handlers():
        app.add_handler(handler)

    app.add_handler(CallbackQueryHandler(start.start, pattern="^main_menu$"))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


def _run_migrations():
    from src.database.connection import get_db
    import psycopg2.extras

    schema_path = os.path.join(os.path.dirname(__file__), "sql", "schema.sql")
    if not os.path.exists(schema_path):
        logger.warning("schema.sql not found, skipping migration.")
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Database schema applied successfully.")


if __name__ == "__main__":
    main()
