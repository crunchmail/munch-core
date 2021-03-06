# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-22 10:18
from __future__ import unicode_literals

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import munch.core.mail.utils
import munch.core.models
import munch.core.utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='MunchUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('identifier', models.EmailField(help_text='identifier', max_length=254, unique=True, verbose_name='identifier')),
                ('is_active', models.BooleanField(default=False, verbose_name='active')),
                ('is_admin', models.BooleanField(default=False, verbose_name='admin')),
                ('secret', models.CharField(max_length=30, verbose_name='secret')),
                ('creation_date', models.DateTimeField(auto_now_add=True, verbose_name='creation date')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups')),
            ],
            options={
                'verbose_name_plural': 'users',
                'verbose_name': 'user',
                'default_permissions': ('view', 'add', 'change', 'delete', 'view_mine', 'change_mine', 'delete_mine', 'view_organizations', 'change_organizations', 'delete_organizations'),
            },
            bases=(munch.core.models.ValidationSignalsModel, models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.CreateModel(
            name='APIApplication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(max_length=50, verbose_name='identifier')),
                ('secret', models.CharField(default=munch.core.mail.utils.mk_base64_uuid, max_length=25, verbose_name='secret')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='author')),
            ],
            options={
                'verbose_name_plural': 'api applications',
                'verbose_name': 'api application',
            },
            bases=(models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Organization name', max_length=200, verbose_name='name')),
                ('contact_email', models.EmailField(help_text='Main contact email for organization', max_length=254, verbose_name='contact email address')),
                ('can_external_optout', models.BooleanField(default=False, verbose_name='Can create messages with external optout')),
                ('can_attach_files', models.BooleanField(default=False, verbose_name='Can add attachments')),
                ('password_reset_link', models.CharField(blank=True, max_length=200, validators=[django.core.validators.RegexValidator('{{\\s+api_reset_link\\s+}}')], verbose_name='password reset link')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('update_date', models.DateTimeField(blank=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='users.Organization')),
            ],
            options={
                'verbose_name_plural': 'organizations',
                'verbose_name': 'organization',
                'default_permissions': ('view', 'add', 'change', 'delete', 'view_mine', 'change_mine', 'delete_mine', 'view_organizations', 'change_organizations', 'delete_organizations'),
            },
            bases=(munch.core.models.ValidationSignalsModel, models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.CreateModel(
            name='OrganizationSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(blank=True, default='', help_text='Organization nickname for tracking links', max_length=30, validators=[django.core.validators.RegexValidator('^[a-z0-9-]{4,30}$', message='Nickname can only contain lowercase letters, numbers and dashes. It must be between 4 and 30 characters long')], verbose_name='nickname')),
                ('notification_email', models.EmailField(blank=True, default='', help_text='Email which will receive optout and status update notifications', max_length=254, verbose_name='notification email')),
                ('notify_message_status', models.BooleanField(default=True, verbose_name='Receive message status notification emails')),
                ('notify_optouts', models.BooleanField(default=False, verbose_name='Receive optouts notification emails')),
                ('external_optout_message', models.TextField(blank=True, default='', help_text='Text which will be display to recipients who want to contact you in order to unsubscribe in case of external optout', verbose_name='External optout contact')),
                ('organization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='users.Organization', verbose_name='organization')),
            ],
            options={
                'verbose_name_plural': 'organization settings',
                'verbose_name': 'organization settings',
                'default_permissions': ('view', 'add', 'change', 'delete', 'view_mine', 'change_mine', 'delete_mine', 'view_organizations', 'change_organizations', 'delete_organizations'),
                'abstract': False,
            },
            bases=(models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.CreateModel(
            name='SmtpApplication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(max_length=50, verbose_name='identifier')),
                ('username', models.CharField(db_index=True, default=munch.core.mail.utils.mk_base64_uuid, max_length=25, unique=True, verbose_name='username')),
                ('secret', models.CharField(default=munch.core.mail.utils.mk_base64_uuid, max_length=25, verbose_name='secret')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='author')),
            ],
            options={
                'verbose_name_plural': 'smtp applications',
                'verbose_name': 'smtp application',
            },
            bases=(models.Model, munch.core.utils.models.OwnedModelMixin),
        ),
        migrations.AddField(
            model_name='munchuser',
            name='organization',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='users', to='users.Organization', verbose_name='organization'),
        ),
        migrations.AddField(
            model_name='munchuser',
            name='user_permissions',
            field=models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions'),
        ),
        migrations.AlterUniqueTogether(
            name='smtpapplication',
            unique_together=set([('identifier', 'author')]),
        ),
        migrations.AlterUniqueTogether(
            name='apiapplication',
            unique_together=set([('identifier', 'author')]),
        ),
    ]
