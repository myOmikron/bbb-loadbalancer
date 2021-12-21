import asyncio
import logging
import os

import httpx

import checks
import db
import settings

logger = logging.getLogger(__name__)


async def _execute_checks(server_id, check_list):
    server_online = True
    for check in check_list:
        for i in range(1, 4):
            ret: checks.CheckResult = await check.task()
            if ret.return_code == 0:
                logger.info(f"{check.check_name}: #{check.server_id}: OK : {ret.message}")
                break
            logger.error(f"{check.check_name}: #{check.server_id}: Try {i}/3: Check was not successful: {ret.message}")
            if i < 3:
                await asyncio.sleep(1)
        else:
            server_online = False
            logger.error(f"{check.check_name}: #{check.server_id}: failed")
            logger.error(f"Skipping all remaining checks")
            logger.debug("Writing to db...")
            break
    if not server_online:
        logger.debug("Writing to db...")
    db.execute_task(db.set_server_reachability(server_online, server_id))


async def _execute_meeting(meeting):
    server = db.execute_task(db.get_server_for_meeting(meeting.meeting_id))
    ret = await checks.get_running_meetings(meeting.meeting_id, server)()
    if not ret:
        logger.info(f"Meeting {meeting.meeting_id} ended on server {server.server_id}")
        logger.debug(f"Writing to db...")
        db.execute_task(db.set_meeting_ended(meeting.meeting_id))


class Scheduler:
    """Executes tasks.

    Tasks have to be Checks in every case.
    """
    def __init__(self):
        self.checks = {}
        self.meetings = []

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
            self.checks[server.server_id].append(checks.process_check(
                file,
                f"/bin/bash {file} {server.url.lstrip('https://').split('/')[0]} {settings.SSH_USER} {process}",
                server.server_id,
                server.url,
                server.secret,
                server.unreachable
            ))
        file = os.path.join(settings.PLUGIN_PATH, "check_systemd.sh")
        for systemd in systemd_list:
            self.checks[server.server_id].append(checks.process_check(
                file,
                f"/bin/bash {file} {server.url.lstrip('https://').split('/')[0]} {settings.SSH_USER} {systemd}",
                server.server_id,
                server.url,
                server.secret,
                server.unreachable
            ))
        self.checks[server.server_id].append(checks.bbb_api_check(client, server.server_id, server.url, server.secret, server.unreachable))

    async def run(self, interval=30):
        client = httpx.AsyncClient()

        while True:
            logger.info("Clearing checks and running meetings")
            self.checks = {}
            self.meetings = []
            logger.info("Reloading server")
            server_list = db.execute_task(db.get_servers)
            logger.debug(f"Loaded servers: {server_list}")
            for server in server_list:
                self.checks[server.server_id] = []
                self.schedule_tasks(server, client)

            meeting_list = db.execute_task(db.get_meetings)
            logger.debug(f"Running meeting to check: {meeting_list}")
            for meeting in meeting_list:
                self.meetings.append(meeting)

            for server in self.checks:
                asyncio.create_task(_execute_checks(server, self.checks[server]))

            for meeting in self.meetings:
                asyncio.create_task(_execute_meeting(meeting))

            await asyncio.sleep(interval)
