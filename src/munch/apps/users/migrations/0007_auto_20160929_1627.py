# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-29 14:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_munchuser_invited_by'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='organizationsettings',
            name='notification_email',
        ),
        migrations.AlterField(
            model_name='organization',
            name='contact_email',
            field=models.EmailField(help_text='Main contact email for organization. Will also receive status/optouts notifications', max_length=254, verbose_name='contact email address'),
        ),
    ]