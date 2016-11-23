from django.core.exceptions import ValidationError


def properties_schema_validator(value):
    from .models import PROP_TYPES

    if not isinstance(value, list):
        raise ValidationError("Must be a list")

    for contact_field in value:
        prop_name = contact_field.get('name', '').strip()
        if not prop_name:
            raise ValidationError("Every fields must have a name")
        prop_type = contact_field.get('type', None)
        if not prop_type:
            raise ValidationError("Every fields must have a type")
        if prop_type not in PROP_TYPES:
            raise ValidationError(
                '{} is not an authorized type'.format(prop_type))
