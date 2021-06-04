from django.contrib import admin
from django.utils.html import format_html

from common_files.models import *


# ------ #
# Server #
# ------ #

@admin.action(description='Enable')
def enable_server(modeladmin, request, queryset):
    queryset.update(state=BBBServer.ENABLED)


@admin.action(description='Disable')
def disable_server(modeladmin, request, queryset):
    queryset.update(state=BBBServer.DISABLED)


@admin.register(BBBServer)
class BBBServerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "server_id", "enabled", "api_mate")
    ordering = ("server_id", )
    actions = (enable_server, disable_server)

    def enabled(self, obj: BBBServer) -> bool:
        return obj.state == BBBServer.ENABLED
    enabled.boolean = True

    def api_mate(self, obj: BBBServer) -> str:
        return format_html("<a href=\"{0}\">{0}</a>", obj.get_absolute_url())


# ------- #
# Meeting #
# ------- #

@admin.action(description='Mark a meeting as ended')
def mark_ended(modeladmin, request, queryset):
    queryset.update(ended=True)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "server", "ended")
    ordering = ("ended", )
    actions = (mark_ended,)
