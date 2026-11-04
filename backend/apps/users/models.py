from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager
from .roles import ADMIN_ROLES, UserRole


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    institutional_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=24, choices=UserRole.choices, default=UserRole.STUDENT)
    legacy_role = models.CharField(max_length=24, blank=True, editable=False)
    technical_specialization = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    @property
    def is_staff(self):
        return self.role in ADMIN_ROLES

    def has_perm(self, perm, obj=None):
        return self.is_active and self.role in ADMIN_ROLES or super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        return self.is_active and self.role in ADMIN_ROLES or super().has_module_perms(app_label)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split()[0]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["full_name", "email"]
