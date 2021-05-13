from django.contrib import admin
from django.utils.html import format_html

from children.models import *


def clickable_url(obj):
    return format_html("<a href=\"{0}\">{0}</a>", obj.get_absolute_url())


clickable_url.__name__ = "url"


@admin.register(BBBServer)
class BBBServerAdmin(admin.ModelAdmin):
    list_display = ("__str__", clickable_url)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    pass
