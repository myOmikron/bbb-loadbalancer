import concurrent.futures
import multiprocessing
from datetime import datetime, timedelta

from cli.set_state import set_state
from common_files.models import *


def execute_task(task):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(task)
        return future.result()


def get_servers():
    return [x for x in BBBServer.objects.all()]


def get_meetings():
    return [x for x in Meeting.objects.filter(ended=False)
            .exclude(internal_id=Meeting.TEMP_INTERNAL_ID)
            .exclude(created__gt=datetime.utcnow() - timedelta(seconds=10))]


def get_server_for_meeting(meeting_id):
    def get_from_db():
        return Meeting.objects.get(meeting_id=meeting_id, ended=False).server
    return get_from_db


def set_server_reachability(reachability: bool, server_id):
    def write_to_db():
        try:
            server = BBBServer.objects.get(server_id=server_id)
            if not reachability:
                server.reachable = 0
                if 0 <= server.unreachable < 2:
                    server.unreachable += 1
                if server.state == server.ENABLED and server.unreachable == 2:
                    # panicking requires its own logic which cli already implements
                    process = multiprocessing.Process(target=set_state, args=(server, server.PANIC))
                    process.start()
            else:
                server.unreachable = 0
                if 0 <= server.reachable < 20:
                    server.reachable += 1
                if server.state == server.PANIC and server.reachable == 20:
                    server.state = server.ENABLED
            server.save(force_update=True)
        except BBBServer.DoesNotExist:
            pass
    return write_to_db


def set_meeting_ended(meeting_id):
    def write_to_db():
        try:
            meeting = Meeting.objects.get(meeting_id=meeting_id, ended=False)
            meeting.ended = True
            meeting.save(force_update=True)
        except Meeting.DoesNotExist:
            pass
    return write_to_db
