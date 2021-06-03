from common_files.models import BBBServer


def server(server_id: str) -> BBBServer:
    try:
        return BBBServer.objects.get(server_id=int(server_id))
    except ValueError:
        raise ValueError("server ids must be integers") from None
    except BBBServer.DoesNotExist:
        raise ValueError("unknown server") from None


def state(string: str) -> str:
    first_char = string.lower()[0]
    if first_char == "e":
        return BBBServer.ENABLED
    elif first_char == "d":
        return BBBServer.DISABLED
    elif first_char == "p":
        return BBBServer.PANIC
    else:
        raise ValueError("Invalid state argument")

