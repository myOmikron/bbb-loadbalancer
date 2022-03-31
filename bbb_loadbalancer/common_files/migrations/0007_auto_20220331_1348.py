# Generated by Django 3.2.4 on 2022-03-31 13:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common_files', '0006_auto_20211220_2300'),
    ]

    operations = [
        migrations.AddField(
            model_name='bbbserver',
            name='reachable',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='bbbserver',
            name='unreachable',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
