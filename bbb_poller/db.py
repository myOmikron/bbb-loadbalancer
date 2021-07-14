import concurrent.futures
from datetime import datetime, timedelta

from bbb_loadbalancer.common_files.models import *


def execute_task(task):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(task)
        return future.result()


def get_server():
    return [x for x in BBBServer.objects.all()]


def get_meetings():
    return [x for x in Meeting.objects.filter(ended=False)
            .exclude(internal_id=Meeting.TEMP_INTERNAL_ID)
            .exclude(created__lt=datetime.utcnow() - timedelta(seconds=10))]


def get_server_for_meeting(meeting_id):
    def get_from_db():
        return Meeting.objects.get(meeting_id=meeting_id, ended=False).server
    return get_from_db


def set_server_reachability(reachability: bool, bbb_server_id):
    def write_to_db():
        try:
            server = BBBServer.objects.get(server_id=bbb_server_id)
            server.reachable = reachability
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
