import argparse
import os

import django
from django.conf import settings

from .argument_types import server, state
from common_files.models import BBBServer
from .set_state import set_state


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bbb_loadbalancer.settings')
django.setup()

parser = argparse.ArgumentParser(description="Cli for bbb-loadbalancer")
subparsers = parser.add_subparsers(title="commands", dest="command")


add = subparsers.add_parser("add", description="Add a server")
add.add_argument('server_id', type=int, help="A unique id to identify the server in requests")
add.add_argument('url', type=str, help="The bigbluebutton server's url")
add.add_argument('secret', type=str, help="The bigbluebutton server's shared secret")
def handle_add():
    if BBBServer.objects.filter(server_id=args.server_id).exists():
        parser.error("A server with this id exists already")

    print(f"Please add this ssh key on the server for the user '{settings.config.ssh_user}':")
    with open("~/.ssh/id_rsa.pub") as f:
        print(f.read())

    print("\nPress [Enter] to continue")
    try:
        input()
    except KeyboardInterrupt:
        pass

    if os.system(f"ssh {settings.config.ssh_user}@{args.url} 'echo Success'") == 0:
        BBBServer.objects.create(
            server_id=args.server_id,
            url=args.url,
            secret=args.secret
        )
    else:
        print("Failed to establish a ssh connection")


remove = subparsers.add_parser("remove", description="Remove a server")
remove.add_argument('server', type=server, help="The server's id")
def handle_remove():
    args.server.delete()


edit = subparsers.add_parser("edit", description="Edit a server")
edit.add_argument('server', type=server, help="The server's id")
edit.add_argument('--state', type=state, help="The server's state: ENABLED, DISABLED or PANIC\n"
                                              "(only the first character will be looked at; also accepts lower case)")
edit.add_argument('--secret', type=str, help="The new secret for the server")
edit.add_argument('--url', type=str, help="The new url for the server")
def handle_edit():
    if args.state:
        set_state(args.server, args.state)
    if args.secret:
        args.server.secret = args.secret
    if args.url:
        args.server.url = args.url
    args.server.save()


subparsers.add_parser("list", description="List all server")
def handle_list():
    for server in BBBServer.objects.all():
        print(f"#{server.server_id}: {server.url}")
        print(f"\tsecret: {server.secret}")
        print(f"\tstate: {server.state}")
        print("\t" + "REACHABLE" if server.reachable else "NOT REACHABLE")


panic = subparsers.add_parser("panic", description="Set a server to panic. "
                              "If a server panics, no new meetings can be created on it. "
                              "In addition this will move all its running meetings to other server.")
panic.add_argument('server', type=server, help="The server's id")
def handle_panic():
    set_state(args.server, BBBServer.PANIC)


disable = subparsers.add_parser("disable", description="Disable a server, so no new meetings will be created on it.")
disable.add_argument('server', type=server, help="The server's id")
def handle_disable():
    set_state(args.server, BBBServer.DISABLED)


enable = subparsers.add_parser("enable", description="Enable a server, so new meetings can be created on it.")
enable.add_argument('server', type=server, help="The server's id")
def handle_enable():
    set_state(args.server, BBBServer.ENABLED)


if __name__ == "__main__":
    args = parser.parse_args()
    globals()["handle_" + args.command]()
