from api.views import Create
from common_files.models import BBBServer, Meeting


def set_state(server: BBBServer, state: str):
    server.state = state
    server.save()

    # Move away all meetings on panic
    if state == BBBServer.PANIC:
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
