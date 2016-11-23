from django.conf.urls import url

from . import views

urlpatterns = [
    url(
        r'^subscriptions/(?P<identifier>[\w\-_]+)/optout/$',
        views.unsubscribe, name='unsubscribe'),
    url(
        r'^subscriptions/(?P<identifier>[\w\-_]+)/unsubscribed/$',
        views.unsubscribed, name='unsubscribed')
]
