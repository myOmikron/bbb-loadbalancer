from django.core.management.base import BaseCommand, CommandError
from common_files.models import BBBServer


class Command(BaseCommand):
    help = 'Adds a server to the cluster'

    def add_arguments(self, parser):
        parser.add_argument('server_id', type=int, help="A unique id to identify the server in requests")
        parser.add_argument('url', type=str, help="The bigbluebutton server's url")
        parser.add_argument('secret', type=str, help="The bigbluebutton server's shared secret")

    def handle(self, *args, server_id: int, url: str, secret: str, **options):
        if BBBServer.objects.filter(server_id=server_id).exists():
            raise CommandError("A server with this id exists already")

        BBBServer.objects.create(
            server_id=server_id,
            url=url,
            secret=secret
        )
