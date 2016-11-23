import re

from django.core.validators import RegexValidator


# SMTP status codes
rfc3463_regex = re.compile(r'([234](\.\d{1,3}){2})')
rfc3463_regex_validator = RegexValidator(
    regex=rfc3463_regex.pattern,
    message='status code should follow rfc3463')
