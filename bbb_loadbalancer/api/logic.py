"""
The core logic of the loadbalancer
"""
import random

from django.db.models import QuerySet, Sum, Q
from typing import Tuple

from api.bbb_api import send_api_request, build_api_url
from common_files.config import LoadBalancerConfig
from common_files.models import BBBServer, Meeting


config = LoadBalancerConfig.from_json("../config.json")


class Loadbalancer:
    """Object imitating a BBBServer to create api urls"""
    api_url = f"https://{config.hostname}/bigbluebutton/api/"
    secret = config.secret


def get_next_server(queryset: QuerySet = None) -> BBBServer:
    """
    Get the next server to create a meeting on.

    Get a list of the servers with the smallest load total and return one at random
    :param queryset: optional queryset to limit the search (state and load will be handled)
    :return: a server with the smallest load total
    """
    if queryset is None:
        queryset = BBBServer.objects

    # Get all servers with a calculated load attribute
    servers = list(queryset
                   .filter(state=BBBServer.ENABLED, reachable=True)
                   .annotate(load=Sum("meeting__load", filter=Q(meeting__ended=False)))
                   .order_by("load"))

    # Remove server above smallest load
    smallest_load = servers[0].load
    for i in range(len(servers)):
        server = servers[i]
        if server.load != smallest_load:
            break
    else:
        i = len(servers)
    servers = servers[:i]

    # Choose one at random
    return random.choice(servers)


def create_meeting(server: BBBServer, meeting_id: str, parameters: dict = None) -> Tuple[Meeting, dict]:
    if parameters is None:
        parameters = {}

    if not Meeting.running.filter(meeting_id=meeting_id).exists():
        # Register the meeting to get an id and delete it if the bbb api call fails
        meeting = Meeting.objects.create(
            meeting_id=meeting_id,
            internal_id=Meeting.TEMP_INTERNAL_ID,
            server=server,
            load=parameters["load"] if "load" in parameters else 1,
            create_query=dict(parameters),
        )
    else:
        meeting = Meeting.running.get(meeting_id=meeting_id)

    # Direct logoutURL to us
    parameters["logoutURL"] = build_api_url(Loadbalancer, "rejoin", {"meetingID": meeting.id})

    # Call bbb's api
    response = send_api_request(server, "create", parameters)

    # Update new meeting
    if meeting.internal_id == Meeting.TEMP_INTERNAL_ID:
        if response["returncode"] == "SUCCESS":
            meeting.internal_id = response["internalMeetingID"]
            meeting.save()
        else:
            meeting.delete()

    return meeting, response
