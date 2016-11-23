from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from .munchers import post_web_html_individual
from munch.apps.campaigns.models import Message
from munch.apps.tracking.views import web_tracking_open


def hosted_message(request, identifier):
    msg = get_object_or_404(Message, identifier=identifier)

    # Handles tracking  (optionally)
    mail = web_tracking_open(request, msg)

    if mail:
        html = post_web_html_individual.process(
            msg.html,
            app_url=msg.get_app_url(),
            track_clicks=msg.track_clicks,
            unsubscribe_url=mail.unsubscribe_url,
            mail_identifier=mail.identifier,
            links_map=msg.msg_links)
    else:
        html = msg.html
    return HttpResponse(html)
