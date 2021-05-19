from django.db import models


class BBBServer(models.Model):
    app_label = "common"

    url = models.CharField(max_length=255, default="")
    secret = models.CharField(max_length=255, default="")


class Meeting(models.Model):
    app_label = "common"

    meeting_id = models.CharField(max_length=255, default="")
    internal_id = models.CharField(max_length=255, default="")
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)
