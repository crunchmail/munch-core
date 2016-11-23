from django.contrib.auth import get_user_model
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework_jwt.views import JSONWebTokenAPIView

from munch.apps.campaigns.models import Mail
from munch.apps.campaigns.models import OptOut
from munch.apps.optouts.api.v1.filters import OptOutFilter
from munch.apps.optouts.api.v1.serializers import OptOutSerializer
from munch.core.utils.views import filtered
from munch.core.utils.views import paginated
from munch.core.utils.views import NestedView
from munch.core.utils.views import MunchModelViewSetMixin
from munch.core.utils.views import OrganizationOwnedViewSetMixin

from ...models import MunchUser
from ...models import Organization
from ...models import APIApplication
from ...models import SmtpApplication
from ...tokens import MunchUserTokenGenerator
from .filters import MunchUserFilter
from .permissions import MunchUserPermission
from .permissions import OrganizationPermission
from .serializers import MeSerializer
from .serializers import MunchUserSerializer
from .serializers import OrganizationSerializer
from .serializers import APIApplicationSerializer
from .serializers import SmtpApplicationSerializer
from .serializers import PasswordResetInitSerializer
from .serializers import PasswordChangeSerializer
from .serializers import MunchJSONWebTokenSerializer
from .serializers import InvitationSerializer


class MeAPIView(APIView):
    def get(self, request, format=None):
        if request.user.is_authenticated():
            serializer = MeSerializer(
                request.user, context={'request': request})
            return Response(serializer.data)
        return Response({}, status=status.HTTP_403_FORBIDDEN)


class OrganizationViewSet(
        OrganizationOwnedViewSetMixin, viewsets.ModelViewSet):
    model = Organization
    serializer_class = OrganizationSerializer
    permission_classes = [OrganizationPermission]

    @detail_route(methods=['get'])
    @paginated(OptOutSerializer)
    @filtered(OptOutFilter)
    def opt_outs(self, request, pk, format=None):
        identifiers = Mail.objects.filter(
            message__author__organization=self.get_object()).values_list(
            'identifier', flat=True)
        return OptOut.objects.filter(identifier__in=identifiers)

    @detail_route(methods=['get'])
    def children(self, request, pk, format=None):
        childs = Organization.objects.filter(parent=self.get_object())
        serializer = OrganizationSerializer(
            childs, many=True, context={'request': request})
        return Response(serializer.data)

    @detail_route(methods=['post'])
    def invite_user(self, request, pk, format=None):
        if not request.user.has_perm('users.invite_user_organization'):
            return Response(status=401)
        serializer = InvitationSerializer(
            data=request.data,
            context={'request': request, 'organization_id': pk})
        if serializer.is_valid():
            user = MunchUser(
                identifier=serializer.validated_data.get('identifier'),
                organization_id=pk, invited_by=request.user)
            user.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(NestedView):
    """
    Change human user password

    Can be done by the user itself or an admin of same organization.
    """

    parent_model = MunchUser
    serializer_class = PasswordChangeSerializer

    def post(self, request, user_pk):
        # Might be in HumanUserViewSet but here for comodity
        # (see HALLinksField)
        user = self.get_parent_object(user_pk)
        serializer = self.get_serializer(user=user, data=request.data)

        if serializer.is_valid():
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegenSecretView(NestedView):
    """
    Regenerate an user key

    returns the generated key
    """
    parent_model = MunchUser

    def post(self, request, user_pk):
        user = self.get_parent_object(user_pk)
        user.regen_secret()
        user.save()
        return Response(user.secret)


class MunchUserViewSet(
        MunchModelViewSetMixin,
        OrganizationOwnedViewSetMixin,
        viewsets.ReadOnlyModelViewSet):
    model = MunchUser
    serializer_class = MunchUserSerializer
    filter_class = MunchUserFilter
    permission_classes = [MunchUserPermission]


class PasswordResetInitView(APIView):
    """ That view allows to initiate a password reset

    It will always issue HTTP 201 so an attacker can't find if a
    given email is a munch user or not.
    """
    permission_classes = []

    def post(self, request, format=None):
        serializer = PasswordResetInitSerializer(data=request.data)
        if serializer.is_valid():
            # email = request.data['email']
            email = serializer.validated_data['email']
            try:
                user = MunchUser.objects.get(identifier=email)
            except MunchUser.DoesNotExist:
                # say nothing
                pass
            else:
                user.send_password_reset_email()
            return Response(status=status.HTTP_201_CREATED)
        else:
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetSetView(APIView):
    """ That view allows to set a new password given an uid and a token

    (the token is received by email)
    """
    # That's open to everybody
    permission_classes = []

    def post(self, request, format=None):
        UserModel = get_user_model()
        uidb64 = request.data['uid']
        token = request.data['token']
        new_password = request.data['new_password']

        token_generator = MunchUserTokenGenerator()
        try:
            # urlsafe_base64_decode() decodes to bytestring on Python 3
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = MunchUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
            user = None

        if token_generator.check_token(user, token):
            user.set_password(new_password)
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


class ObtainJSONWebToken(JSONWebTokenAPIView):
    """
    API View that receives a POST with a user's username and password.

    Returns a JSON Web Token that can be used for authenticated requests.
    """
    serializer_class = MunchJSONWebTokenSerializer


class APIApplicationViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = APIApplication
    serializer_class = APIApplicationSerializer

    @detail_route(methods=['post'])
    def regen_secret(self, request, pk=None):
        application = self.get_object()
        application.regen_secret()
        application.save()
        return Response(application.secret)


class SmtpApplicationViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = SmtpApplication
    serializer_class = SmtpApplicationSerializer

    @detail_route(methods=['post'])
    def regen_credentials(self, request, pk=None):
        application = self.get_object()
        application.regen_credentials()
        application.save()
        return Response(
            {"username": application.username, "secret": application.secret})
