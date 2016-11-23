from django.template import Context
from django.template import Template
from django.utils.encoding import smart_text
from rest_framework.utils import formatting


description_tpl = Template("""
{% if filters %}Results can be filtered/ordered by:
    {% for filter in filters %}`{{ filter }}`
        {% if not forloop.last %}, {% endif %}{% endfor %}.
{% endif %}
{% if default_ordering %}
Default ordering is by `{{ default_ordering }}`.
{% endif %}""")


def get_view_description(view_cls, html=False, instance=None):
    """
    Given a view class, return a textual description to represent the view.
    This name is used in the browsable API, and in OPTIONS responses.
    This function is the default for the `VIEW_DESCRIPTION_FUNCTION` setting.
    """
    # doc can come from the class or from a detail_route or a list_route method
    documented_object = view_cls
    if instance:
        view_method = get_subroute_method(instance)
        if view_method:
            documented_object = view_method

    description = documented_object.__doc__ or ''
    description = formatting.dedent(smart_text(description))

    if hasattr(documented_object, 'filter_class'):
        default_filter = documented_object.filter_class()
        filters = default_filter.filters
        filters_doc = description_tpl.render(Context({
            'filters': filters,
            'default_ordering': default_filter._default_ordering_field()}))
        description += filters_doc

    if html:
        return formatting.markup_description(description)
    return description


def get_subroute_method(viewset):
    """ Detect if we are in a detail_route or list_route and return the relevant
    method, else return None
    """
    if viewset.action:
        view_method = getattr(viewset, viewset.action, None)
        # just an heuristic to check if it's a detail/list route
        if view_method and hasattr(view_method, 'bind_to_methods'):
            return view_method
