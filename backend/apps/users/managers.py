from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        if not full_name or not full_name.strip():
            raise ValueError("A full name is required.")
        user = self.model(
            email=self.normalize_email(email).lower(),
            full_name=full_name.strip(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        from .roles import UserRole

        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_superuser"]:
            raise ValueError("A system administrator must have is_superuser=True.")
        return self.create_user(email, full_name, password, **extra_fields)
