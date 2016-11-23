# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-08-01 16:12
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import munch.apps.domains.fields
import munch.core.utils.models
import munch.core.utils.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SendingDomain',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, validators=[munch.core.utils.validators.DomainNameValidator()], verbose_name='name')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('update_date', models.DateTimeField(blank=True)),
                ('dkim_status', munch.apps.domains.fields.DomainCheckField(choices=[('ok', 'Configured'), ('ko', 'Not configured'), ('bad', 'Badly configured'), ('pending', 'Checking'), ('unknown', 'Unknown')], default='unknown', max_length=10, verbose_name='DKIM status')),
                ('dkim_status_date', models.DateTimeField(blank=True, null=True, verbose_name='DKIM status last change')),
                ('app_domain', models.CharField(blank=True, default='', help_text='Domain to use for application links generation', max_length=200, validators=[munch.core.utils.validators.DomainNameValidator()], verbose_name='Custom application domain')),
                ('app_domain_status', munch.apps.domains.fields.DomainCheckField(choices=[('ok', 'Configured'), ('ko', 'Not configured'), ('bad', 'Badly configured'), ('pending', 'Checking'), ('unknown', 'Unknown')], default='unknown', max_length=10, verbose_name='App domain status')),
                ('app_domain_status_date', models.DateTimeField(blank=True, null=True, verbose_name='App domain status last change')),
                ('alt_organizations', models.ManyToManyField(blank=True, to='users.Organization')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='domains', to='users.Organization', verbose_name='organization')),
            ],
            options={
                'verbose_name': 'sending domain',
                'verbose_name_plural': 'sending domains',
                'default_permissions': ('view', 'add', 'change', 'delete', 'view_mine', 'change_mine', 'delete_mine', 'view_organizations', 'change_organizations', 'delete_organizations'),
                'abstract': False,
            },
            bases=(models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.AlterUniqueTogether(
            name='sendingdomain',
            unique_together=set([('name', 'organization')]),
        ),
    ]
