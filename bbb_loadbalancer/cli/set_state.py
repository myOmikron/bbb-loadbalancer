import sys
from api.bbb_api import send_api_request
from api.logic import get_next_server, create_meeting
from common_files.models import BBBServer, Meeting


def set_state(server: BBBServer, state: str):
    server.state = state
    server.save()

    # Move away all meetings on panic
    if state == BBBServer.PANIC:
        for meeting in Meeting.running.filter(server=server):
            # Try sending the end call, hoping it can still reach the server
            try:
                send_api_request(server,
                    "end", {"meetingID": meeting.meeting_id, "password": meeting.create_query["moderatorPW"]}
                )
            except:
                pass
            finally:
                meeting.ended = True
                meeting.save()

            # Reopen the meeting on a new server
            new_server = get_next_server()
            _, response = create_meeting(new_server, meeting.meeting_id, meeting.create_query)
            if response["returncode"] == "SUCCESS":
                print(f"Reopened '{meeting.meeting_id}' on #{new_server.server_id}", file=sys.stdout)
            else:
                print(f"Couldn't reopen '{meeting.meeting_id}': {response['message']}", file=sys.stderr)
