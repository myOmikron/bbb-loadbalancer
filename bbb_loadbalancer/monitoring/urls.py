from django.urls import path

from api.views import *
from monitoring.views import GetServers

urlpatterns = [
    path("getServers", GetServers.as_view(endpoint="getServers")),
]

