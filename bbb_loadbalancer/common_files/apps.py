from django.apps import AppConfig


class CommonFilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common_files'


class CommonFilesConfigPoller(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bbb_loadbalancer.common_files'
