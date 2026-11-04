from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assets.models import Asset
from apps.campus.models import Building, Campus, Department, Location, Team
from apps.issues.models import IssueCategory
from apps.network.models import Network, NetworkDevice
from apps.users.models import User
from apps.users.roles import UserRole


class Command(BaseCommand):
    help = "Create a small, synthetic campus dataset for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        password = getpass("Password for newly created development accounts: ")
        if len(password) < 12:
            raise CommandError("Use a development password at least 12 characters long.")
        validate_password(password)

        campus, _ = Campus.objects.get_or_create(
            code="demo-campus",
            defaults={"name": "Development Campus", "description": "Synthetic development records; not official LPU infrastructure."},
        )

        buildings = {}
        for code, name in [
            ("academic", "Academic Block"),
            ("computing", "Computer Science Building"),
            ("engineering", "Engineering Block"),
            ("library", "Library"),
            ("hostel", "Hostel"),
            ("cafeteria", "Cafeteria"),
            ("sports", "Sports Complex"),
            ("admin", "Administration Block"),
        ]:
            buildings[code], _ = Building.objects.get_or_create(campus=campus, code=code, defaults={"name": name})

        location_specs = [
            ("classroom-1", "Classroom 1", "CLASSROOM", "academic"),
            ("cs-lab-1", "Computer Lab 1", "LABORATORY", "computing"),
            ("electronics-lab", "Electronics Laboratory", "LABORATORY", "engineering"),
            ("library-floor", "Ground Floor", "FLOOR", "library"),
            ("hostel-common", "Common Area", "HOSTEL", "hostel"),
            ("dining-area", "Dining Area", "CAFETERIA", "cafeteria"),
            ("outdoor-court", "Outdoor Court", "OUTDOOR", "sports"),
            ("admin-service", "Service Desk", "OFFICE", "admin"),
        ]
        locations = {}
        for code, name, kind, building_key in location_specs:
            locations[code], _ = Location.objects.get_or_create(
                building=buildings[building_key], code=code,
                defaults={"name": name, "kind": kind},
            )

        departments = {}
        for code, name in [
            ("facilities", "Facilities"), ("information-technology", "Information Technology"),
            ("student-services", "Student Services"), ("campus-operations", "Campus Operations"),
        ]:
            departments[code], _ = Department.objects.get_or_create(code=code, defaults={"name": name})

        team_specs = [
            ("Facilities", "facilities"), ("Electrical Maintenance", "facilities"),
            ("Plumbing", "facilities"), ("IT Support", "information-technology"),
            ("Network Operations", "information-technology"), ("Housekeeping", "campus-operations"),
            ("Hostel Operations", "campus-operations"), ("Security", "campus-operations"),
            ("Transport", "campus-operations"), ("Academic Administration", "student-services"),
        ]
        teams = {}
        for name, department_key in team_specs:
            teams[name], _ = Team.objects.get_or_create(name=name, defaults={"department": departments[department_key]})

        category_names = [
            "Electrical", "Plumbing", "Hostel", "Classroom", "Laboratory", "Wi-Fi", "Network",
            "IT Support", "Transport", "Library", "Security", "Housekeeping", "Furniture",
            "Air Conditioning", "Academic Administration", "Other",
        ]
        for name in category_names:
            IssueCategory.objects.get_or_create(name=name)

        users = [
            ("student@example.test", "Sample Student", UserRole.STUDENT, ""),
            ("staff@example.test", "Sample Staff", UserRole.STAFF, ""),
            ("technician@example.test", "Sample Technician", UserRole.TECHNICAL_STAFF, "IT Support"),
            ("supervisor@example.test", "Sample Supervisor", UserRole.ADMIN, "IT Support"),
            ("facility-manager@example.test", "Sample Facility Manager", UserRole.ADMIN, "Facilities"),
            ("it-manager@example.test", "Sample IT Manager", UserRole.ADMIN, "Network Operations"),
            ("department-head@example.test", "Sample Department Head", UserRole.ADMIN, "Academic Administration"),
            ("campus-admin@example.test", "Sample Campus Administrator", UserRole.ADMIN, ""),
            ("system-admin@example.test", "Sample System Administrator", UserRole.ADMIN, ""),
        ]
        demo_ids = {
            "student@example.test": "STU-DEV-001",
            "staff@example.test": "EMP-DEV-001",
            "technician@example.test": "EMP-DEV-TECH-001",
            "supervisor@example.test": "ADM-DEV-001",
            "facility-manager@example.test": "ADM-DEV-002",
            "it-manager@example.test": "ADM-DEV-003",
            "department-head@example.test": "ADM-DEV-004",
            "campus-admin@example.test": "ADM-DEV-005",
            "system-admin@example.test": "ADM-DEV-006",
        }
        for email, full_name, role, team_name in users:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"full_name": full_name, "role": role, "is_active": True, "is_superuser": email == "system-admin@example.test", "institutional_id": demo_ids[email]},
            )
            user.full_name = full_name
            user.role = role
            user.is_active = True
            user.institutional_id = user.institutional_id or demo_ids[email]
            if role == UserRole.TECHNICAL_STAFF and not user.technical_specialization:
                user.technical_specialization = "IT Support"
            if created:
                user.set_password(password)
            user.save()
            if team_name:
                teams[team_name].members.add(user)

        for code, name, asset_type, location_key in [
            ("AP-CS-001", "Wi-Fi Access Point", "Network equipment", "cs-lab-1"),
            ("AC-ACAD-001", "Air Conditioner", "HVAC", "classroom-1"),
            ("PJ-ACAD-001", "Projector", "Classroom equipment", "classroom-1"),
            ("WP-HOST-001", "Water Pump", "Plumbing equipment", "hostel-common"),
            ("EP-ENG-001", "Electrical Panel", "Electrical equipment", "electronics-lab"),
        ]:
            Asset.objects.get_or_create(
                asset_code=code,
                defaults={"name": name, "asset_type": asset_type, "location": locations[location_key]},
            )

        wifi, _ = Network.objects.get_or_create(
            campus=campus, code="dev-wifi",
            defaults={"building": buildings["computing"], "name": "Synthetic Computing Wi-Fi", "kind": Network.Kind.WIFI, "description": "Synthetic development network; not real LPU infrastructure."},
        )
        lan, _ = Network.objects.get_or_create(
            campus=campus, code="dev-lan",
            defaults={"building": buildings["computing"], "name": "Synthetic Computing LAN", "kind": Network.Kind.LAN, "description": "Synthetic development network; not real LPU infrastructure."},
        )
        wan, _ = Network.objects.get_or_create(
            campus=campus, code="dev-wan",
            defaults={"name": "Synthetic Campus WAN", "kind": Network.Kind.WAN, "description": "Synthetic development network; not real LPU infrastructure."},
        )
        for device_code, name, kind, network, location_key, asset_code in [
            ("DEV-NET-AP-01", "Synthetic Computer Lab Access Point", NetworkDevice.Kind.ACCESS_POINT, wifi, "cs-lab-1", "AP-CS-001"),
            ("DEV-NET-SW-01", "Synthetic Computing Switch", NetworkDevice.Kind.SWITCH, lan, "cs-lab-1", ""),
            ("DEV-NET-RTR-01", "Synthetic Campus Router", NetworkDevice.Kind.ROUTER, wan, "admin-service", ""),
            ("DEV-NET-GW-01", "Synthetic Campus Gateway", NetworkDevice.Kind.GATEWAY, wan, "admin-service", ""),
        ]:
            NetworkDevice.objects.get_or_create(
                device_code=device_code,
                defaults={
                    "name": name, "kind": kind, "network": network,
                    "location": locations[location_key],
                    "asset": Asset.objects.filter(asset_code=asset_code).first() if asset_code else None,
                    "manufacturer": "Synthetic Example Vendor", "model_number": "Development Model 1",
                },
            )

        self.stdout.write(self.style.SUCCESS("Synthetic development campus, categories, teams, users, assets, and network inventory are ready."))
        self.stdout.write("All seeded accounts use the password entered above. Do not reuse it outside local development.")
