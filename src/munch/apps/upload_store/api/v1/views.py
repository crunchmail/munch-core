from django.utils.dateparse import parse_duration
from rest_framework import generics
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from munch.core.utils.permissions import IsAuthenticatedOrPreflight

from ...models import Image
from ...models import UploadDuplicateError
from .serializers import ImageSerializer


@api_view(('GET',))
def api_root(request, format=None):
    return Response({})


class ImageDetail(generics.RetrieveAPIView):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = tuple()
    versioning_class = None


class ImageCreate(generics.CreateAPIView):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = (IsAuthenticatedOrPreflight,)
    http_method_names = ('post', 'options')
    versioning_class = None

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except UploadDuplicateError as e:
            dup = Image.objects.get(pk=e.instance.hash)
            # this usage of parse_duration is safe, because we already
            # validated the data (exception is thrown by the Model class, so
            # the validator passed).
            if 'expiration' in request.data:
                dup.expiration = parse_duration(request.data['expiration'])
            dup.save()

            serializer = self.get_serializer(dup)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)
