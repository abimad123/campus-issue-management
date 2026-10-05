from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager
from .roles import ADMIN_ROLES, UserRole


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=24, choices=UserRole.choices, default=UserRole.STUDENT)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    @property
    def is_staff(self):
        return self.role in ADMIN_ROLES

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split()[0]

    def __str__(self):
        return self.full_name

    class Meta:
        ordering = ["full_name", "email"]
