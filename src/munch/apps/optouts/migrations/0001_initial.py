# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-22 16:48
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import munch.core.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0002_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='OptOut',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(db_index=True, max_length=150, unique=True, verbose_name='identifier')),
                ('address', models.EmailField(max_length=254, verbose_name='mail')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('origin', models.CharField(choices=[('mail', 'Email'), ('web', 'Web link'), ('feedback-loop', 'Detected as spam'), ('abuse', 'By abuse report'), ('bounce', 'Too much delivering errors')], max_length=20, verbose_name='origine')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='author')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Category', verbose_name='category')),
            ],
            options={
                'verbose_name': 'optout',
                'abstract': False,
                'default_permissions': ('view', 'add', 'change', 'delete', 'view_mine', 'change_mine', 'delete_mine', 'view_organizations', 'change_organizations', 'delete_organizations'),
                'verbose_name_plural': 'optouts',
            },
            bases=(models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
    ]
