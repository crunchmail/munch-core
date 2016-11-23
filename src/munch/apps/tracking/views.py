import logging

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponseNotAllowed
from django.views.decorators.cache import cache_control

from munch.core.utils import get_mail_by_identifier

from .utils import WebKey
from .models import LinkMap
from .tasks import create_track_record

log = logging.getLogger(__name__)

# 1px transparent gif
TRACKER_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff"
    b"\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b")


def do_track_and_redirect(mail_identifier, link_identifier):
    link_map = LinkMap.objects.filter(
        identifier=link_identifier).only('link').first()
    if link_map:
        create_track_record.apply_async(kwargs={
            'identifier': mail_identifier,
            'kind': 'click',
            'properties': {'link': link_identifier}})
        return HttpResponseRedirect(link_map.link)
    return HttpResponse(
        'No URL found with this ID', content_type='text/html', charset='UTF-8')


@cache_control(no_cache=True, max_age=0)
def tracking_open(request, identifier):
    if request.method == 'GET':
        mail = get_mail_by_identifier(identifier, must_raise=False)
        if mail:
            create_track_record.apply_async(kwargs={
                'identifier': identifier,
                'kind': 'read', 'properties': {'source': 'pixel'}})
        return HttpResponse(TRACKER_PIXEL, content_type='image/gif')
    return HttpResponseNotAllowed(permitted_methods=['GET'])


def tracking_redirect(request, identifier, link_identifier):
    if request.method == 'GET':
        return do_track_and_redirect(identifier, link_identifier)
    return HttpResponseNotAllowed(permitted_methods=['GET'])


def web_tracking_open(request, msg):
    """ Tracks opening from the hosted version

    Not a view, called by hosted.views
    """
    token = request.GET.get('web_key', None)
    if token:
        identifier = WebKey(token).get_identifier()
        if identifier:
            create_track_record.apply_async(kwargs={
                'identifier': identifier,
                'kind': 'read', 'properties': {'source': 'browser'}})
            return get_mail_by_identifier(identifier)


def web_tracking_redirect(request, web_key, link_identifier):
    if request.method == 'GET':
        identifier = WebKey(web_key).get_identifier()
        return do_track_and_redirect(identifier, link_identifier)
    return HttpResponseNotAllowed(permitted_methods=['GET'])
