import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bbb_loadbalancer"))

from common_files.config import LoadBalancerConfig

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

TIME_ZONE = 'UTC'

INSTALLED_APPS = [
    "common_files.apps.CommonFilesConfig",
]

PLUGIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
SSH_USER = config.ssh_user
