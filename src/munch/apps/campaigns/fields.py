from django.core import validators
from django.db import models
from django.db.models.signals import pre_save

import django_fsm


class EmailListField(models.CharField):
    """ Multiple emails

    after https://djangosnippets.org/snippets/3047/
    """
    class EmailListValidator(validators.EmailValidator):
        def __call__(self, value):
            if isinstance(value, (str, bytes)):
                value = value.split(',')
            for email in value:
                return super(
                    EmailListField.EmailListValidator, self).__call__(email)

    class Presentation(list):
        def __str__(self):
            return ",".join(self)

    default_validators = [EmailListValidator()]

    def get_db_prep_value(self, value, *args, **kwargs):
        if not value:
            return
        return ','.join(str(s) for s in value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)

    def to_python(self, value):
        if not value:
            return
        elif isinstance(value, self.Presentation):
            return value
        else:
            return self.Presentation(
                [address.strip() for address in value.split(',')])


class FSMAutoField(django_fsm.FSMField):
    """ Pass transitions on attr change rather than transition calls

    Design of FSM is to call transitions explicitly.

    Here we take another approach, if an attribute is changed and then saved,
    we search for the first matching transition and apply it befor saving.

    If no matching transition is found, then we raise a TransitionNotAllowed.
    """

    @staticmethod
    def _fsm_check_transitions(sender, instance, raw, **kwargs):
        fieldname = instance._fsm_state_field
        Model = sender._meta.model
        # Excludes new instance or fixture loading
        if (instance.pk is not None) and (not raw):
            new = getattr(instance, fieldname)
            old = getattr(Model.objects.get(pk=instance.pk), fieldname)
            if new != old:
                field = Model._meta.get_field(fieldname)
                transitions = field.get_all_transitions(Model)

                relevant_transitions = filter(
                    lambda t: (t.target == new) and (t.source in (old, '*')),
                    transitions)
                try:
                    transition = list(relevant_transitions)[0]
                except IndexError:
                    raise django_fsm.TransitionNotAllowed(
                        '{} -> {} transition is not allowed'.format(old, new))
                else:
                    transition.method(instance)

    def contribute_to_class(self, cls, name, virtual_only=False):
        super().contribute_to_class(cls, name, virtual_only=False)
        setattr(cls, '_fsm_state_field', name)
        pre_save.connect(
            self._fsm_check_transitions, sender=cls,
            dispatch_uid='_fsm_check_transitions')
