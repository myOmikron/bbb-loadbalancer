import sys

from django.core.management.base import BaseCommand

from api.views import Create
from common_files.models import BBBServer, Meeting


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
        server.save()

        # Move away all meetings on panic
        if server_state == BBBServer.PANIC:
            for meeting in Meeting.running.filter(server=server):
                # Try sending the end call, hoping it can still reach the server
                try:
                    server.send_api_request(
                        "end", {"meetingID": meeting.meeting_id, "password": meeting.create_query["moderatorPW"]}
                    )
                except:
                    pass
                finally:
                    meeting.ended = True
                    meeting.save()

                # Reopen the meeting on a new server
                new_server = Create.get_next_server()
                response = new_server.send_api_request(
                    "create", meeting.create_query
                )
                if response["returncode"] == "SUCCESS":
                    Meeting.objects.create(
                        meeting_id=response["meetingID"],
                        internal_id=response["internalMeetingID"],
                        server=new_server,
                        load=meeting.load,
                        create_query=meeting.create_query,
                    )
                    print(f"Reopened '{meeting.meeting_id}' on #{new_server.server_id}", file=sys.stdout)
                else:
                    print(f"Couldn't reopen '{meeting.meeting_id}': {response['message']}", file=sys.stderr)
