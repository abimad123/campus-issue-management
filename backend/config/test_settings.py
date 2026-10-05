"""Fast, database-isolated settings for automated tests; never use in deployment."""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "automated-tests-only-not-a-production-secret")

from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = []
MEDIA_ROOT = BASE_DIR / "test-media"
