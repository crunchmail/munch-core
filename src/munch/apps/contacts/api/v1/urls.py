from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register(
    'contacts/queues', views.ContactQueueViewSet, base_name='contactqueue')
router.register(
    'contacts/policies',
    views.ContactListPolicyViewSet, base_name='contactlistpolicy')
router.register(
    'contacts/lists', views.ContactListViewSet, base_name='contactlist')
router.register('contacts', views.ContactViewSet, base_name='contact')

urlpatterns = [
    url('^contacts/lists/(?P<contact_list_pk>\d+)/contacts/$',
        views.ContactListContacts.as_view({'post': 'create', 'get': 'list'})),
    url('^contacts/lists/(?P<contact_list_pk>\d+)/merge/$',
        views.ContactListMergeView.as_view()),
] + router.urls

api_urlpatterns_v1 += [url('', include(urlpatterns, namespace='contacts'))]
