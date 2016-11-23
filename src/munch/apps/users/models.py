import string
from random import choice

from django.db import models
from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from munch.core.mail.utils import mk_base64_uuid
from munch.core.mail.utils.emails import ServiceMessage
from munch.core.utils import get_login_url
from munch.core.utils.models import AbstractOwnedModel
from munch.core.utils.managers import OwnedModelQuerySet
from munch.core.utils.models import OwnedModelMixin
from munch.core.models import ValidationSignalsModel

from .tokens import token_generator


class Organization(ValidationSignalsModel, AbstractOwnedModel):
    name = models.CharField(
        _('name'), max_length=200, help_text=_("Organization name"))
    contact_email = models.EmailField(
        _('contact email address'),
        help_text=_(
            'Main contact email for organization. '
            'Will also receive status/optouts notifications'))
    can_external_optout = models.BooleanField(
        _('Can create messages with external optout'), default=False)
    can_attach_files = models.BooleanField(
        _('Can add attachments'), default=False)
    parent = models.ForeignKey(
        'self', null=True, blank=True, related_name='children')
    creation_date = models.DateTimeField(default=timezone.now)
    update_date = models.DateTimeField(blank=True)

    class Meta(OwnedModelMixin.Meta):
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')

    owner_path = 'self'
    author_path = AbstractOwnedModel.IRRELEVANT

    def __str__(self):
        return '{}'.format(self.name)

    def get_organization(self):
        return self

    def validate_children(self):
        if self.parent:
            if self.parent == self:
                raise ValidationError(
                    'Cannot set myself as parent.')
            if self.children.exists():
                raise ValidationError(
                    'Cannot have a parent and children at same time.')
            if self.parent.parent:
                raise ValidationError(
                    'Cannot be attached to a parent '
                    'organization that already has a parent.')

    def save(self, *args, **kwargs):
        created = not self.pk
        self.update_date = timezone.now()
        super().save(*args, **kwargs)
        if created:
            os = OrganizationSettings(organization=self)
            os.save()

    def get_all_users(self):
        return MunchUser.objects.filter(
            organization=self) | MunchUser.objects.filter(
                organization__in=self.children.all())


class OrganizationSettings(AbstractOwnedModel):
    nickname_valid_msg = _(
        'Nickname can only contain lowercase letters, '
        'numbers and dashes. It must be between 4 and 30 characters long')

    organization = models.OneToOneField(
        'Organization', related_name='settings',
        verbose_name=_('organization'))
    nickname = models.CharField(
        _('nickname'), max_length=30, blank=True, default='',
        help_text=_("Organization nickname for tracking links"),
        validators=[RegexValidator(
            '^[a-z0-9-]{4,30}$', message=nickname_valid_msg)])

    notify_message_status = models.BooleanField(
        _('Receive message status notification emails'), default=True)
    notify_optouts = models.BooleanField(
        _('Receive optouts notification emails'), default=False)
    external_optout_message = models.TextField(
        _("External optout contact"), blank=True, default='',
        help_text=_(
            "Text which will be display to recipients who want to contact you "
            "in order to unsubscribe in case of external optout"))

    owner_path = 'organization'
    author_path = AbstractOwnedModel.IRRELEVANT

    class Meta(AbstractOwnedModel.Meta):
        verbose_name = _("organization settings")
        verbose_name_plural = _("organization settings")

    def clean(self, *args, **kwargs):
        # a bit of duplicate with OrganizationSettingsSerializer.validate
        if (not self.organization.can_external_optout and
                self.external_optout_message.strip()):
            raise ValidationError(_(
                'External optout is not allowed, no need '
                'to provide a message'))


class MunchUserManager(BaseUserManager):
    def _create_user(self, identifier, password, is_superuser, **extra_fields):
        """
        Creates and saves a User with the given username, email and password.
        """
        if not identifier:
            raise ValueError(_('The given identifier must be set'))
        identifier = self.normalize_email(identifier)
        user = self.model(
            identifier=identifier, is_active=True,
            is_superuser=is_superuser, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, identifier, password, *args, **kwargs):
        return self._create_user(
            identifier, password, is_superuser=True, *args, **kwargs)


class MunchUser(
        ValidationSignalsModel, AbstractBaseUser,
        PermissionsMixin, OwnedModelMixin):
    """
    Simple user model for munch users
    Includes both admins and regular users.
    """
    SECRET_LENGTH = 30

    identifier = models.EmailField(
        _('identifier'), unique=True, blank=False,
        null=False, help_text=_('identifier'))
    first_name = models.CharField(_('first name'), max_length=50, blank=False)
    last_name = models.CharField(_('last name'), max_length=50, blank=False)
    organization = models.ForeignKey(
        'Organization', verbose_name=_('organization'),
        null=True, related_name='users')
    is_active = models.BooleanField(_('active'), default=False)
    is_admin = models.BooleanField(_('admin'), default=False)

    secret = models.CharField(_('secret'), max_length=SECRET_LENGTH)

    creation_date = models.DateTimeField(_('creation date'), auto_now_add=True)

    invited_by = models.ForeignKey(
        'MunchUser', verbose_name=_('invited by'), null=True, blank=True,
        on_delete=models.SET_NULL)

    USERNAME_FIELD = 'identifier'

    objects = MunchUserManager.from_queryset(OwnedModelQuerySet)()

    owner_path = 'organization'
    author_path = 'self'

    class Meta(OwnedModelMixin.Meta):
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def save(self, *args, **kwargs):
        created = False
        if not self.pk:
            created = True

        # If no API key exists, just produce one.
        # Typically: at instance creation
        with transaction.atomic():
            if not self.secret:
                self.regen_secret()
            super().save(*args, **kwargs)

        if created and not self.password:
            transaction.on_commit(self.send_invitation_email)

    def regen_secret(self):
        self.secret = self._mk_random_secret()

    def _send_service_message(
            self, subject, template, template_html, extra_context={}):
        protocol, domain = settings.HELPDESK_URL.strip('/').split('://')
        context = {
            'identifier': self.identifier,
            'user_name': self.get_short_name(),
            'product_name': settings.PRODUCT_NAME,
            'protocol': protocol,
            'domain': domain,
            'user': self,
        }
        context.update(extra_context)
        message = ServiceMessage(
            subject=subject, to=self.identifier, template=template,
            render_context=context)
        message.add_html_part_if_exists(template_html)
        message.send()

    def send_invitation_email(self):
        self._send_service_message(
            subject=render_to_string(
                'users/emails/invitation_email_subject.txt', {
                    'product_name': settings.PRODUCT_NAME,
                    'user_name': self.get_short_name()}).strip(),
            template='users/emails/invitation_email.txt',
            template_html='users/emails/invitation_email.html',
            extra_context={
                'token': token_generator.make_token(self),
                'uid': urlsafe_base64_encode(force_bytes(self.pk))}
        )

    def send_invitation_complete_email(self):
        self._send_service_message(
            subject=render_to_string(
                'users/emails/invitation_complete_email_subject.txt', {
                    'product_name': settings.PRODUCT_NAME,
                    'user_name': self.get_short_name()}).strip(),
            template='users/emails/invitation_complete_email.txt',
            template_html='users/emails/invitation_complete_email.html',
            extra_context={'login_url': get_login_url()}
        )

    def send_password_reset_email(self):
        self._send_service_message(
            subject=render_to_string(
                'users/emails/password_reset_email_subject.txt', {
                    'product_name': settings.PRODUCT_NAME,
                    'user_name': self.get_short_name()}).strip(),
            template='users/emails/password_reset_email.txt',
            template_html='users/emails/password_reset_email.html',
            extra_context={
                'token': token_generator.make_token(self),
                'uid': urlsafe_base64_encode(force_bytes(self.pk))}
        )

    def send_password_reset_complete_email(self):
        self._send_service_message(
            subject=render_to_string(
                'users/emails/password_reset_complete_email_subject.txt', {
                    'product_name': settings.PRODUCT_NAME,
                    'user_name': self.get_short_name()}).strip(),
            template='users/emails/password_reset_complete_email.txt',
            template_html='users/emails/password_reset_complete_email.html',
            extra_context={'login_url': get_login_url()}
        )

    @property
    def full_name(self):
        return self.get_full_name()
    full_name.fget.short_description = _('name')

    def get_full_name(self):
        if self.first_name or self.last_name:
            return '{} {}'.format(self.first_name, self.last_name)
        else:
            return self.identifier

    def get_short_name(self):
        return self.first_name or self.identifier

    def __str__(self):
        return self.identifier

    @property
    def is_staff(self):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        if self.is_admin:
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        return True

    @classmethod
    def _mk_random_secret(cls, length=None):
        length = length or cls.SECRET_LENGTH
        chars = string.ascii_letters + string.digits
        return ''.join(choice(chars) for _ in range(length))


class APIApplication(AbstractOwnedModel):
    identifier = models.CharField(
        max_length=50, blank=False, null=False, verbose_name=_('identifier'))
    secret = models.CharField(
        _('secret'), max_length=25, default=mk_base64_uuid)
    author = models.ForeignKey(MunchUser, verbose_name=_('author'))

    owner_path = 'author__organization'
    author_path = 'author'

    class Meta:
        verbose_name = _('api application')
        verbose_name_plural = _('api applications')
        unique_together = [('identifier', 'author')]

    def __str__(self):
        return '{} ({})'.format(self.identifier, self.author)

    def regen_secret(self):
        self.secret = mk_base64_uuid()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.secret:
                self.regen_secret()
            super().save(*args, **kwargs)


class SmtpApplication(AbstractOwnedModel):
    identifier = models.CharField(
        max_length=50, blank=False, null=False, verbose_name=_('identifier'))
    username = models.CharField(
        max_length=25, db_index=True, unique=True,
        default=mk_base64_uuid, verbose_name=_('username'))
    secret = models.CharField(
        _('secret'), max_length=25, default=mk_base64_uuid)
    author = models.ForeignKey(MunchUser, verbose_name=_('author'))

    owner_path = 'author__organization'
    author_path = 'author'

    class Meta:
        verbose_name = _('smtp application')
        verbose_name_plural = _('smtp applications')
        unique_together = [('identifier', 'author')]

    def __str__(self):
        return '{} ({})'.format(self.identifier, self.author)

    def regen_credentials(self):
        self.username = mk_base64_uuid()
        self.secret = mk_base64_uuid()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.secret or not self.username:
                self.regen_credentials()
            super().save(*args, **kwargs)
