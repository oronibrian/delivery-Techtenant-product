from rest_framework import permissions


class IsCurrentUser(permissions.BasePermission):
    """
    Only allow a record if model is the current user.
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user and
            request.user.is_authenticated() and
            request.user == obj
        )


class IsCreator(permissions.IsAuthenticated):

    def has_object_permission(self, request, view, obj):
        return (
            request.user and
            request.user.is_authenticated() and
            request.user == obj.customer
        )
#
# class IsCustomerOrDriver(permissions.IsAuthenticated):
#     