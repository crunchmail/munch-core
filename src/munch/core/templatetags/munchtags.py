from django import template
from django.utils.translation import ugettext_lazy as _

register = template.Library()


@register.filter
def divide(value, arg):
    try:
        return int(value) / int(arg)
    except (ValueError, ZeroDivisionError):
        return None


@register.filter
def multiply(value, arg):
    try:
        return int(value) * int(arg)
    except (ValueError):
        return None


@register.filter
def percent(v):
    return '{:.0%}'.format(float(v))


@register.filter
def enabled_label(v):
    if v:
        return _('enabled')
    return _('disabled')
