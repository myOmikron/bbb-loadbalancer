from django.core.management.base import BaseCommand, CommandError
from common_files.models import BBBServer


def state(string):
    first_char = string.lower()[0]
    if first_char == "e":
        return BBBServer.ENABLED
    elif first_char == "d":
        return BBBServer.DISABLED
    elif first_char == "p":
        return BBBServer.PANIC
    else:
        raise ValueError("Invalid state argument")


class Command(BaseCommand):
    help = 'Change a server\' state'

    def add_arguments(self, parser):
        parser.add_argument('server_id', type=int, help="The server's unique id")
        parser.add_argument('server_state', type=state, help="Desired state")

    def handle(self, *args, server_id: int, server_state: str, **options):
        try:
            server = BBBServer.objects.get(server_id=server_id)
        except BBBServer.DoesNotExist:
            print("Unkown server")
            exit(1)

        server.state = server_state
        # TODO move meetings away if panic
        server.save()
