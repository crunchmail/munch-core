from ...utils.permissions import MunchResourcePermission


class CategoryPermission(MunchResourcePermission):
    app_name = 'core'
    model_name = 'category'

    def has_object_permission(self, request, view, obj):
        if request.method == 'DELETE':
            if obj.messages.exists():
                return False

        return super().has_object_permission(request, view, obj)
