import asyncio
import logging
import os
import time

import django

import settings

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        filename=os.path.join(settings.config.log_dir, "poller.log"),
        format='%(asctime)s :: %(levelname)s: %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S',
        level=logging.INFO
    )
    logging.Formatter.converter = time.gmtime

    from scheduler import Scheduler

    scheduler = Scheduler()
    await scheduler.run()


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    django.setup()
    asyncio.run(asyncio.get_event_loop().run_until_complete(main()))
