import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bbb_loadbalancer.common_files.config import LoadBalancerConfig

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

config = LoadBalancerConfig.from_json("../config.json")

DATABASES = {
    'default': {
        'ENGINE': config.database.engine,
        'NAME': config.database.name,
        'HOST': config.database.host,
        'PORT': config.database.port,
        'USER': config.database.user,
        'PASSWORD': config.database.password,
    }
}

INSTALLED_APPS = [
    "bbb_loadbalancer.common_files.apps.CommonFilesConfigPoller",
]

PLUGIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
SSH_USER = config.ssh_user
