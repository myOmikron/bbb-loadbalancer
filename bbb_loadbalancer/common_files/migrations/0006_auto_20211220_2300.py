# Generated by Django 3.2.4 on 2021-12-20 23:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_files', '0005_alter_meeting_created'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bbbserver',
            name='reachable',
        ),
        migrations.AddField(
            model_name='bbbserver',
            name='unreachable',
            field=models.IntegerField(default=0),
        ),
    ]