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
    list_display = ("bbb_server", "reachable", "enabled", "api_mate")
    list_filter = ("state", "reachable")
    ordering = ("server_id", )
    actions = (enable_server, disable_server)
    fields = ("server_id", "secret", "state")
    readonly_fields = ("state", )

    def enabled(self, obj: BBBServer) -> bool:
        return obj.state == BBBServer.ENABLED
    enabled.boolean = True

    def api_mate(self, obj: BBBServer) -> str:
        return format_html("<a href=\"{0}\">{0}</a>", obj.get_absolute_url())

    def bbb_server(self, obj: BBBServer) -> str:
        return f"#{obj.server_id} {obj}"

    # You can't add servers using the admin interface, please use the cli
    def has_add_permission(self, request):
        return False

    # You can't delete servers using the admin interface, please use the cli
    def has_delete_permission(self, request, obj=None):
        return False


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
