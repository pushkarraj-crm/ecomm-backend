from django.conf import settings
from django.db import models

class AdminEmployee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='admin_employee', on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_admin_employees', on_delete=models.SET_NULL, null=True)
    session_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


def invitation_expiry():
    from datetime import timedelta
    from django.utils import timezone
    return timezone.now()+timedelta(hours=72)


class AdminInvitation(models.Model):
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='super_admin_invitations', on_delete=models.SET_NULL, null=True)
    expires_at = models.DateTimeField(default=invitation_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='accepted_admin_invitations', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
