# 起動
#   python main.py

import logging

import admin_screen
import backup
import config
from card_reader import NfcCardReader
from db import Database
from gui import App
from lock import GpioLock


def setup_log():
    config.LOG_PATH.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(config.LOG_PATH, encoding="utf-8")],
    )


def main():
    setup_log()
    logging.info("起動")

    database = Database(config.DB_PATH)
    database.create_tables()
    if config.USE_ADMIN_SCREEN:
        admin_screen.create_admin_table(database)

    card_reader = NfcCardReader(config.CARD_READER_PATH, config.CARD_TARGETS)
    lock = GpioLock(config.LOCK_GPIO_PIN, config.LOCK_ACTIVE_HIGH, config.LOCK_SWITCH_GPIO_PIN)

    app = App(database, card_reader, lock)
    if config.USE_BACKUP:
        backup.start_daily_backup(app)

    try:
        app.mainloop()
    finally:
        lock.close()  # 終わるときは必ず GPIO を OFF にする


if __name__ == "__main__":
    main()
