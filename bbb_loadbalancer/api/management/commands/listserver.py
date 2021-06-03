from django.core.management.base import BaseCommand, CommandError
from common_files.models import BBBServer


class Command(BaseCommand):
    help = 'List all server in the cluster'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for server in BBBServer.objects.all():
            print(f"#{server.server_id}: {server.url}")
            print(f"\tsecret: {server.secret}")
            print(f"\tstate: {server.state}")
            print("\t" + "REACHABLE" if server.reachable else "NOT REACHABLE")
