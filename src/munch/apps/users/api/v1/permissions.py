from munch.core.utils.permissions import MunchResourcePermission


class MunchUserPermission(MunchResourcePermission):
    app_name = 'users'
    model_name = 'munchuser'

    def has_object_permission(self, request, view, obj):
        """ Check that the user isn't deleting itself
        """
        if (request.user == obj) and (request.method == 'DELETE'):
            return False
        return super().has_object_permission(request, view, obj)


class OrganizationPermission(MunchResourcePermission):
    app_name = 'users'
    model_name = 'organization'

    def has_object_permission(self, request, view, obj):
        if obj in request.user.organization.children.all():
            return True
        return super().has_object_permission(request, view, obj)

    def has_permission(self, request, view):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            user = request.user
            permissions = [
                'users.add_child_organization',
                'users.delete_child_organization']
            if user.is_authenticated():
                if user.groups.filter(name='administrators').exists():
                    if user.has_perms(permissions):
                        return True
        return super().has_permission(request, view)
