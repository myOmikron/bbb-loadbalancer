import asyncio
import logging
import os

import httpx

import checks
import db
import settings

logger = logging.getLogger(__name__)


async def _execute_check(check):
    for i in range(1, 4):
        ret: checks.CheckResult = await check.task()
        if ret.return_code == 0:
            logger.info(f"{check.check_name}: #{check.server_id}: OK : {ret.message}")
            if not check.reachable:
                logger.debug("Writing to db...")
                db.execute_task(db.set_server_reachability(True, check.server_id))
            break
        logger.error(f"{check.check_name}: #{check.server_id}: Try {i}/3: Check was not successful: {ret.message}")
        if i < 3:
            await asyncio.sleep(5)
    else:
        logger.error(f"{check.check_name}: #{check.server_id}: failed")
        logger.debug(f"Writing to db...")
        db.execute_task(db.set_server_reachability(False, check.server_id))


class Scheduler:
    """Executes tasks.

    Tasks have to be Checks in every case.
    """
    def __init__(self):
        self.checks = []

    def schedule_tasks(self, server, client):
        # File Checks
        process_list = [
            "nginx",
            "freeswitch",
            "redis-server",
            "mongod",
            "etherpad"
        ]
        systemd_list = [
            "bbb-html5-backend@1",
            "bbb-html5-backend@2",
            "bbb-html5-frontend@1",
            "bbb-html5-frontend@2",
        ]
        file = os.path.join(settings.PLUGIN_PATH, "check_running_processes.sh")
        for process in process_list:
            self.checks.append(checks.process_check(
                file,
                f"/bin/bash {file} {server.url.lstrip('https://').split('/')[0]} {settings.SSH_USER} {process}",
                server.server_id,
                server.url,
                server.secret,
                server.reachable
            ))
        file = os.path.join(settings.PLUGIN_PATH, "check_systemd.sh")
        for systemd in systemd_list:
            self.checks.append(checks.process_check(
                file,
                f"/bin/bash {file} {server.url.lstrip('https://').split('/')[0]} {settings.SSH_USER} {systemd}",
                server.server_id,
                server.url,
                server.secret,
                server.reachable
            ))
        self.checks.append(checks.bbb_api_check(client, server.server_id, server.url, server.secret, server.reachable))

    async def run(self, interval=60):
        client = httpx.AsyncClient()

        while True:
            logger.info("Clearing Checks")
            self.checks = []
            logger.info("Reloading server")
            server_list = db.execute_task(db.get_server)
            for server in server_list:
                self.schedule_tasks(server, client)

            for check in self.checks:
                asyncio.create_task(_execute_check(check))
            await asyncio.sleep(interval)
