import logging

import staticconfig


class LoadBalancerConfig(staticconfig.Config):
    def __init__(self):
        super().__init__()
        self.database = staticconfig.Namespace()
        self.database.engine = "django.db.backends.mysql"
        self.database.name = "loadbalancer"
        self.database.host = "127.0.0.1"
        self.database.port = "3306"
        self.database.user = "bbb_loadbalancer"
        self.database.password = "change_me"

        self.django = staticconfig.Namespace()
        self.django.allowed_hosts = [
            "127.0.0.1"
        ]
        self.secret = "change_me"

        self.player = staticconfig.Namespace()
        self.player.api_url = "https://change_me/api/v1/"
        self.player.rcp_secret = "change_me"

        self.logging = staticconfig.Namespace()
        self.logging.file = "/var/log/bbb-loadbalancer.log"
        self.logging.level = "INFO"