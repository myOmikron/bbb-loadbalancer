import concurrent.futures

from bbb_loadbalancer.common_files.models import *


def execute_task(task):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(task)
        return future.result()


def get_server():
    return [x for x in BBBServer.objects.all()]


def set_server_reachability(reachability: bool, bbb_server_id):
    def write_to_db():
        try:
            server = BBBServer.objects.get(server_id=bbb_server_id)
            server.reachable = reachability
            server.save(force_update=True)
        except BBBServer.DoesNotExist:
            pass
    return write_to_db
