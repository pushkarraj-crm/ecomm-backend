from rest_framework.permissions import BasePermission


class IsSeller(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_seller and
            not request.user.is_blacklisted
        )


class IsApprovedSeller(IsSeller):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.seller_status == 'approved'


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_customer


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff
