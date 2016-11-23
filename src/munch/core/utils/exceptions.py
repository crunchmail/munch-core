def exception_handler(exc, context):
    # Replace the POST data of the Django request with the parsed
    # data from the DRF
    # Necessary because we cannot read request data/stream more than once
    # This will allow us to see the parsed POST params
    # in the rollbar exception log
    # Based on https://github.com/tomchristie/django-rest-framework/pull/1671
    from rest_framework import views
    from django.http.request import QueryDict
    query = QueryDict('', mutable=True)
    try:
        if not isinstance(context['request'].data, dict):
            query.update({'_bulk_data': context['request'].data})
        else:
            query.update(context['request'].data)
        context['request']._request.POST = query
    except:
        pass
    return views.exception_handler(exc, context)
