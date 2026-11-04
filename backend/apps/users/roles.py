from django.db import models


class UserRole(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    STAFF = "STAFF", "Staff"
    TECHNICAL_STAFF = "TECHNICAL_STAFF", "Technical staff"
    ADMIN = "ADMIN", "Administrator"


ADMIN_ROLES = {UserRole.ADMIN}
ISSUE_MANAGEMENT_ROLES = ADMIN_ROLES
