import asyncio
import logging
import logging.handlers
import os
import zlib
import socket

import django

import settings

logger = logging.getLogger(__name__)


def namer(name):
    return name + ".gz"


def rotator(source, dest):
    with open(source, "rb") as sf:
        data = sf.read()
        compressed = zlib.compress(data, 9)
        with open(dest, "wb") as df:
            df.write(compressed)
    os.remove(source)


async def main():
    rotating_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(settings.config.log_dir, "poller.log"),
        # sunday
        when="W6",
        backupCount=15,
        utc=True,
        encoding="utf-8"
    )
    rotating_handler.rotator = rotator
    rotating_handler.namer = namer

    logging.basicConfig(
        format='%(asctime)s :: %(levelname)s: %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S',
        level=logging.INFO,
        handlers=[rotating_handler]
    )

    from scheduler import Scheduler

    scheduler = Scheduler()
    await scheduler.run()


if __name__ == '__main__':
    socket.setdefaulttimeout(5)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    django.setup()
    asyncio.run(asyncio.get_event_loop().run_until_complete(main()))
