# Generated by Django 3.2.4 on 2021-06-24 13:07

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_files', '0003_meeting_moved_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='created',
            field=models.DateTimeField(blank=True, default=datetime.datetime.now),
        ),
    ]