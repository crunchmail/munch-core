from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ['HEAD', 'OPTIONS']:
            return True
        return (
            request.user and request.user.is_authenticated() and (
                request.user.is_admin or request.user.organization))

    def has_object_permission(self, request, view, obj):
        return ((request.user.is_authenticated()) and
                ((request.user.is_admin) or (
                    obj.get_owner() == request.user.organization)))


class IsAuthenticatedOrPreflight(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        if request.method == 'OPTIONS':
            return True
        return super().has_permission(request, view)


class MunchResourcePermission:
    app_name = 'campaigns'
    model_name = 'mail'

    @classmethod
    def mk_class(cls, model_class):
        class klass(cls):
            app_name = model_class._meta.app_label
            model_name = model_class._meta.model_name
        klass.__name__ = '{}Permission'.format(model_class.__name__)
        return klass

    # define a permission mapping HTTP methods
    verbs_permissions = {
        'GET': 'view',
        'HEAD': 'view',
        'POST': 'add',
        'PUT': 'change',
        'PATCH': 'change',
        'DELETE': 'delete'
    }

    def mk_perms(self, verb):
        """ Builds permissions names """
        return (
            self._mk_user_perm(verb),
            self._mk_organization_perm(verb),
            self._mk_main_perm(verb))

    def _mk_main_perm(self, verb):
        return '{}.{}_{}'.format(self.app_name, verb, self.model_name)

    def _mk_user_perm(self, verb):
        return '{}.{}_mine_{}'.format(self.app_name, verb, self.model_name)

    def _mk_organization_perm(self, verb):
        return '{}.{}_organizations_{}'.format(
            self.app_name, verb, self.model_name)

    def has_any_perm(self, user, perms):
        return any(user.has_perm(p) for p in perms)

    def has_permission(self, request, view):
        if request.method in ['HEAD', 'OPTIONS']:
            return True
        return self.has_any_perm(
            request.user,
            self.mk_perms(self.verbs_permissions[request.method]))

    def can_user_do(self, user, obj, verb):
        """ High-level object permissions checking

        :type user: MunchUser
        :type obj: the object we are interested in
        :param verb: 'add', 'change', 'delete' or 'view'

        :rtype: boolean
        """
        # if no author/owner, that's public resource
        # that can only be viewed
        if ((obj.defines_author() and obj.get_author() is None) or (
                obj.get_owner() is None)):
            return verb == 'view'
        elif user.has_perm(self._mk_main_perm(verb)):
            return True
        elif user.has_perm(self._mk_organization_perm(verb)):
            return user.organization == obj.get_owner()
        elif user.has_perm(self._mk_user_perm(verb)):
            return user == obj.get_author()
        return False

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated():
            return False
        if request.method == 'OPTIONS':
            return True
        else:
            perm_verb = self.verbs_permissions[request.method]
            return self.can_user_do(request.user, obj, perm_verb)

    def filter_queryset(self, qs, request):
        """ Filters queryset according to request and logged-in user perms
        """
        if request.user.is_authenticated():
            if request.user.has_perm(self._mk_main_perm('view')):
                return qs
            elif request.user.has_perm(self._mk_organization_perm('view')):
                return qs.from_owner(request.user.organization)
            elif request.user.has_perm(self._mk_user_perm('view')):
                return qs.from_author(request.user)

        return qs.none()
