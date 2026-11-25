"""Singleton entry point for the advisory event engine. No order routes or tools."""

import asyncio
import logging
import os
import signal

from services.bot.runtime import Runtime
from services.bot.store import Store


async def run() -> None:
    import fcntl

    store = Store(os.environ.get("BOT_DB_PATH", ".local/bot/bot.sqlite3"))
    with open(store.path + ".worker.lock", "a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await Runtime(store).run(stop)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
