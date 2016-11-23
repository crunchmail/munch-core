from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^report/(?P<identifier>[\w\-_]+)/$',
        views.abuse_report, name='abuse-report'),
    url(r'^thanks/(?P<identifier>[\w\-_]+)/$',
        views.abuse_report_thanks,
        name='abuse-report-thanks'),
]
