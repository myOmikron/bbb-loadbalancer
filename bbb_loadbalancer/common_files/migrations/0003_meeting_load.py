# Generated by Django 3.2.3 on 2021-06-03 12:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_files', '0002_meeting_ended'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='load',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]