import urllib

from django.urls import get_resolver
from django.urls import NoReverseMatch


def resolve_url(request, path=None):
    """Helper function that reports information on the request's url.

    Taken from http://code.google.com/p/greatlemers-django-tools \
                /source/browse/trunk/gdt_nav/models.py#158
    Apache License 2.0

    This utility function takes a request and analyses its url to generate the
    url_name and keyword arguments that can be used to generate the url via
    the reverse function or url tag.
    The url resolver doesn't return the name of the url that produces the
    given url so some hunting around has to be done to determine what exactly
    it should be.

    Keyword arguments:
    request -- The request object for the view that wants to generate some
    menus.
    path    -- The relative path (default: gets it from the request.path_info)

    Returns:
    A tuple of (url, url_name, url_kwargs)
    url -- The absolute representation of the requested url
    url_name -- The 'reversable' name of the requested url
    url_kwargs -- The keyword arguments that would be needed in order to
    'reverse' the url.
    """
    # Start by fetching the path from the request and using it to build
    # the full url.
    if not path:
        path = request.path_info

    url = request.build_absolute_uri(path)
    # make sure path is only the local path
    path = urllib.parse.urlparse(path).path

    # The url resolver which will generate some of the url info.
    # Get urlconf from request object if available.
    urlconf = getattr(request, "urlconf", None)
    resolver = get_resolver(urlconf)

    # Pull out the view function, and the url arguments and keywords.
    view_func, url_args, url_kwargs = resolver.resolve(path)

    # Fetch a list of all the signatures of the items that can be reversed
    # to produce the view function.
    sigs = resolver.reverse_dict.getlist(view_func)

    url_name = None
    # Loop through all the items in the reverse dictionary.
    for key, value in resolver.reverse_dict.items():
        # Check if the value of the mapping is one of our matching signatures
        # and that the key is a string.
        if value in sigs and type(key) == str:
            try:
                # See if we have the right parameters to use this reversal and
                # that it produces the correct url.
                if resolver.reverse(key, *url_args, **url_kwargs) == path[1:]:
                    # No exceptions were thrown so we have the right parameters
                    # and the path matched therefore we've found the url name
                    # we were seeking - which of course means we can
                    # stop looking.
                    url_name = key
                    break
            except NoReverseMatch:
                # The parameters were wrong - ah well, maybe the next one will
                # succeed.
                pass
    return url, url_name, url_kwargs
