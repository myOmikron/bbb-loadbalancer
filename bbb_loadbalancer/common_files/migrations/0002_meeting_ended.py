# Generated by Django 3.2.3 on 2021-05-19 19:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_files', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='ended',
            field=models.BooleanField(default=False),
        ),
    ]