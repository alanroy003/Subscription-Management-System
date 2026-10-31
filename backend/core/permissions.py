from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsTeam(BasePermission):
    """Admin or internal staff."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_team)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class TeamReadAdminWrite(BasePermission):
    """Catalog, taxes and discounts: staff may read, only the admin may change."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_team):
            return False
        return request.method in SAFE_METHODS or user.is_admin
