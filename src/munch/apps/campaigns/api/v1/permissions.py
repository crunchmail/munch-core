from rest_framework import permissions

from munch.core.utils.permissions import MunchResourcePermission

from ...models import Message


class AttachmentPermission(permissions.BasePermission):
    """ Permission is granted to attach files only to specified users, others
    can view their attachment (if any), no more.
    """
    def has_permission(self, request, view):
        if request.method in ['OPTIONS', 'HEAD']:
            return True
        elif request.user.is_authenticated():
            if request.method == 'GET':
                return True
            if request.user.is_staff or \
                    request.user.organization.can_attach_files:
                return True
        return False


class PreviewMailPermission(MunchResourcePermission):
    app_name = 'campaigns'
    model_name = 'message'

    def has_object_permission(self, request, view, obj):
        # checks for message_add
        allowed = super().has_object_permission(request, view, obj)

        if allowed:
            return self.can_user_do(request.user, obj, 'previewsend')
        else:
            return False


class MailPermission(MunchResourcePermission):
    def has_object_permission(self, request, view, obj):
        if request.method == 'DELETE':
            if obj.message.status in [Message.SENDING, Message.SENT]:
                return False
        return super().has_object_permission(request, view, obj)
