import asyncio
import logging
import os

from bigbluebutton_api_python import BigBlueButton
from bigbluebutton_api_python.exception import BBBException

logger = logging.getLogger("poller")


class Check:
    def __init__(self, *, check_name, server_id, server_url, server_secret, reachable, task):
        self.check_name = check_name
        self.server_id = server_id
        self.server_url = server_url
        self.server_secret = server_secret
        self.reachable = reachable
        self.task = task


class CheckResult:
    def __init__(self, return_code, message):
        self.return_code = return_code
        self.message = message


def bbb_api_check(client, server_id, server_url, server_secret, reachable):

    async def check_api_reachability():
        ret = await client.request("GET", os.path.join(server_url, "api"))
        if ret.status_code == 200:
            return CheckResult(0, "API is reachable")
        else:
            return CheckResult(1, f"Status code: {ret.status_code}")

    return Check(
        check_name="API Reachability",
        server_id=server_id,
        server_url=server_url,
        server_secret=server_secret,
        reachable=reachable,
        task=check_api_reachability
    )


def process_check(file, cmd, server_id, server_url, server_secret, reachable):

    async def execute_file_check():
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return CheckResult(
            proc.returncode,
            stdout.decode("utf-8").strip()
        )

    return Check(
        check_name=f"FILE: {os.path.basename(file)}",
        server_id=server_id,
        server_url=server_url,
        server_secret=server_secret,
        reachable=reachable,
        task=execute_file_check
    )


def get_running_meetings(meeting_id, server):
    async def execute_request():
        b = BigBlueButton(server.url, server.secret)
        try:
            b.get_meeting_info(meeting_id)
        except BBBException:
            await asyncio.sleep(0.01)
            return False
        await asyncio.sleep(0.01)
        return True
    return execute_request
