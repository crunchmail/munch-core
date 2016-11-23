from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import MinimumLengthValidator as DjangoMinimumLengthValidator  # noqa
from django.utils.translation import ungettext


class MinimumLengthValidator(DjangoMinimumLengthValidator):
    def __init__(self):
        super().__init__(getattr(settings, 'PASSWORD_MIN_LENGTH', 6))


class MinimumDigitValidator(object):
    def __init__(self):
        self.min_digit = getattr(settings, 'PASSWORD_MIN_DIGIT', 0)

    def validate(self, password, user=None):
        if self.min_digit:
            num_digit = sum(c.isdigit() for c in password)
            if num_digit < self.min_digit:
                raise ValidationError(
                    ungettext(
                        'This password must contain at least %(mini)d digit',
                        'This password must contain at least %(mini)d digits',
                        self.min_digit) % {'mini': self.min_digit})

    def get_help_text(self):
        help_text = ''
        if self.min_digit:
            help_text = ungettext(
                'Your password must contain at least %(mini)d digit',
                'Your password must contain at least %(mini)d digits',
                self.min_digit) % {'mini': self.min_digit}
        return help_text


class MinimumUppercaseValidator(object):
    def __init__(self):
        self.min_upper = getattr(settings, 'PASSWORD_MIN_UPPER', 0)

    def validate(self, password, user=None):
        if self.min_upper:
            num_upper = sum(c.isupper() for c in password)
            if num_upper < self.min_upper:
                raise ValidationError(
                    ungettext(
                        'This password must contain at least %(mini)d uppercase character',  # noqa
                        'This password must contain at least %(mini)d uppercase characters',  # noqa
                        self.min_upper) % {'mini': self.min_upper})

    def get_help_text(self):
        help_text = ''
        if self.min_upper:
            help_text = ungettext(
                'Your password must contain at least %(mini)d uppercase character',  # noqa
                'Your password must contain at least %(mini)d uppercase characters',  # noqa
                self.min_upper) % {'mini': self.min_upper}
        return help_text
