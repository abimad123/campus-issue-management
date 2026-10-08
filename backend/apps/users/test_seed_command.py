from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset
from apps.campus.models import Building, Campus, Department, Location, Team
from apps.issues.models import IssueCategory
from apps.users.models import User


class DevelopmentSeedCommandTests(TestCase):
    @patch("apps.users.management.commands.seed_development.getpass", return_value="Dev-Only-Shared-Password-239!")
    def test_seed_creates_synthetic_records_idempotently(self, _getpass):
        output = StringIO()
        call_command("seed_development", stdout=output)
        call_command("seed_development", stdout=StringIO())

        self.assertEqual(Campus.objects.count(), 1)
        self.assertEqual(Building.objects.count(), 8)
        self.assertEqual(Location.objects.count(), 8)
        self.assertEqual(Department.objects.count(), 4)
        self.assertEqual(Team.objects.count(), 10)
        self.assertEqual(IssueCategory.objects.count(), 16)
        self.assertEqual(User.objects.count(), 9)
        self.assertEqual(Asset.objects.count(), 5)
        self.assertIn("Synthetic development", output.getvalue())
        self.assertTrue(User.objects.get(email="student@example.test").check_password("Dev-Only-Shared-Password-239!"))
