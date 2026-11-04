from getpass import getpass
from types import SimpleNamespace

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.campus.models import Location, Team
from apps.issues.models import Issue, IssueCategory
from apps.issues.serializers import IssueCreateSerializer
from apps.routing.models import Assignment, RoutingRule
from apps.sla.models import SlaPolicy
from apps.users.models import User
from apps.users.roles import UserRole
from apps.workorders.models import WorkOrder


USERS = (
    ("DEMO-STU-001", "demo-student1@example.test", "Demo Student 1", UserRole.STUDENT, ""),
    ("DEMO-STU-002", "demo-student2@example.test", "Demo Student 2", UserRole.STUDENT, ""),
    ("DEMO-STAFF-001", "demo-staff1@example.test", "Demo Staff 1", UserRole.STAFF, ""),
    ("DEMO-STAFF-002", "demo-staff2@example.test", "Demo Staff 2", UserRole.STAFF, ""),
    ("DEMO-TECH-001", "demo-it-technician@example.test", "Demo IT Technician", UserRole.TECHNICAL_STAFF, "IT Support"),
    ("DEMO-TECH-002", "demo-network-technician@example.test", "Demo Network Technician", UserRole.TECHNICAL_STAFF, "Network"),
    ("DEMO-TECH-003", "demo-electrical-technician@example.test", "Demo Electrical Technician", UserRole.TECHNICAL_STAFF, "Electrical"),
    ("DEMO-TECH-004", "demo-maintenance-technician@example.test", "Demo Maintenance Technician", UserRole.TECHNICAL_STAFF, "Maintenance"),
    ("DEMO-ADMIN-001", "demo-admin@example.test", "Demo Admin", UserRole.ADMIN, ""),
)

TEAM_FOR_SPECIALIZATION = {
    "IT Support": "IT Support",
    "Network": "Network Operations",
    "Electrical": "Electrical Maintenance",
    "Maintenance": "Facilities",
}

ROUTING_RULES = (
    ("DEMO-RULE-WIFI", "Wi-Fi", "Network Operations"),
    ("DEMO-RULE-NETWORK", "Network", "Network Operations"),
    ("DEMO-RULE-LAB", "Laboratory", "IT Support"),
    ("DEMO-RULE-CLASSROOM", "Classroom", "IT Support"),
    ("DEMO-RULE-ELECTRICAL", "Electrical", "Electrical Maintenance"),
    ("DEMO-RULE-FURNITURE", "Furniture", "Facilities"),
)

DEMO_ISSUES = (
    {"ref": "DEMO-ISSUE-001", "reporter": "DEMO-STU-001", "category": "Wi-Fi", "location": "Classroom 1", "title": "Wi-Fi is unavailable in the classroom", "description": "The classroom Wi-Fi connection is unavailable during scheduled study hours. Please check access in the room."},
    {"ref": "DEMO-ISSUE-002", "reporter": "DEMO-STU-002", "category": "Laboratory", "location": "Computer Lab 1", "title": "Laboratory computer will not start", "description": "A workstation in the computer laboratory does not start when its power button is pressed. The power connection appears secure."},
    {"ref": "DEMO-ISSUE-003", "reporter": "DEMO-STAFF-001", "category": "Classroom", "location": "Classroom 1", "title": "Projector is not working during a lecture", "description": "The classroom projector is not displaying the lecture material during the current teaching session. Please prioritize an operational check.", "request_priority": True, "priority_reason": "An active lecture is underway and students cannot see the teaching material."},
    {"ref": "DEMO-ISSUE-004", "reporter": "DEMO-STAFF-001", "category": "Electrical", "location": "Classroom 1", "title": "Electrical fault reported in classroom", "description": "A classroom power outlet is intermittently sparking and should be inspected before further use."},
    {"ref": "DEMO-ISSUE-005", "reporter": "DEMO-STAFF-002", "category": "Furniture", "location": "Classroom 1", "title": "Broken classroom desk requires repair", "description": "A student desk has a loose leg and cannot be used safely until it is repaired or replaced."},
    {"ref": "DEMO-ISSUE-006", "reporter": "DEMO-STAFF-002", "category": "Network", "location": "Computer Lab 1", "title": "Network connectivity disruption in computer lab", "description": "Several lab workstations are losing access to campus network services during scheduled sessions.", "request_priority": True, "priority_reason": "Scheduled lab instruction is disrupted for multiple users by the connectivity loss."},
)

WORK_ORDER_ISSUES = {"DEMO-ISSUE-002", "DEMO-ISSUE-003", "DEMO-ISSUE-004", "DEMO-ISSUE-005"}


class Command(BaseCommand):
    help = "Create idempotent synthetic accounts, routing/SLA configuration, issues, and work orders for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        accounts = self._accounts()
        new_accounts = [item for item in accounts.values() if item[1]]
        password = getpass("Development-only password for newly created demo accounts: ") if new_accounts else None
        if password is not None:
            if len(password) < 12:
                raise CommandError("Use a demo password at least 12 characters long.")
            validate_password(password)

        teams = self._teams()
        accounts = self._save_accounts(accounts, teams, password)
        categories, locations = self._reference_data()
        self._routing_rules(categories, teams)
        sla_policy = self._sla_policy()
        issues = self._issues(accounts, categories, locations)
        work_orders = self._work_orders(issues, accounts["DEMO-ADMIN-001"][0])

        self.stdout.write(self.style.SUCCESS(
            f"Synthetic development seed complete: {len(accounts)} demo accounts, "
            f"{len(issues)} demo issues, {len(work_orders)} demo work orders."
        ))
        self.stdout.write(f"Demo SLA policy: {sla_policy.name}")
        self.stdout.write("All demo logins use the password entered when their accounts were first created; existing passwords were not changed.")
        for reference, issue in issues.items():
            assignment = Assignment.objects.filter(issue=issue).order_by("-created_at", "-pk").first()
            if assignment and assignment.is_automatic:
                team_name = assignment.team.name if assignment.team_id else "No team"
                technician = (
                    f"{assignment.user.institutional_id or assignment.user.email} (user {assignment.user_id})"
                    if assignment.user_id else "unassigned"
                )
                outcome = f"automatic: {team_name} / {technician} ({assignment.reason})"
            elif issue.assigned_to_id:
                outcome = f"existing assignment: {issue.assigned_team.name} / {issue.assigned_to.institutional_id}"
            else:
                outcome = "unassigned: no successful automatic assignment recorded"
            self.stdout.write(f"{reference} {issue.ticket_number}: {outcome}; SLA={issue.sla_policy.name if issue.sla_policy_id else 'not configured'}")
        for institutional_id, email, _, _, _ in USERS:
            user = accounts[institutional_id][0]
            self.stdout.write(f"account={user.institutional_id} email={email} role={user.role} specialization={user.technical_specialization or '-'}")

    def _accounts(self):
        result = {}
        for requested_id, email, full_name, role, specialization in USERS:
            by_email = User.objects.filter(email__iexact=email).first()
            if by_email and by_email.institutional_id and not by_email.institutional_id.startswith("DEMO-"):
                raise CommandError(f"{email} already has a non-demo institutional ID; no records were changed.")
            if by_email and by_email.institutional_id:
                institutional_id = by_email.institutional_id
                owner = User.objects.filter(institutional_id=institutional_id).first()
                if owner and owner.pk != by_email.pk:
                    raise CommandError(f"{email} has a conflicting demo ID; no records were changed.")
            else:
                institutional_id = requested_id
                suffix = 2
                while True:
                    owner = User.objects.filter(institutional_id=institutional_id).first()
                    if owner is None or owner.email.casefold() == email.casefold():
                        break
                    institutional_id = f"{requested_id}-{suffix:02d}"
                    suffix += 1
            by_id = User.objects.filter(institutional_id=institutional_id).first()
            if by_id and by_id.email.casefold() != email.casefold():
                raise CommandError(f"Could not find an unused demo ID for {email}; no records were changed.")
            user = by_email or by_id
            is_new = user is None
            result[requested_id] = (user, is_new, email, full_name, role, specialization, institutional_id)
        return result

    def _teams(self):
        result = {}
        names = set(TEAM_FOR_SPECIALIZATION.values()) | {team for _, _, team in ROUTING_RULES}
        for name in names:
            try:
                team = Team.objects.get(name=name, is_active=True)
            except Team.DoesNotExist as exc:
                raise CommandError(f"Required active team '{name}' does not exist; no records were changed.") from exc
            result[name] = team
        return result

    def _save_accounts(self, account_rows, teams, password):
        accounts = {}
        for demo_key, (user, is_new, email, full_name, role, specialization, institutional_id) in account_rows.items():
            if is_new:
                if password is None:
                    raise CommandError("A password is required to create new demo accounts.")
                user = User.objects.create_user(
                    email=email, full_name=full_name, password=password, role=role,
                    institutional_id=institutional_id, technical_specialization=specialization,
                    is_active=True,
                )
            else:
                user.full_name = full_name
                user.role = role
                user.institutional_id = institutional_id
                user.technical_specialization = specialization
                user.is_active = True
                user.save(update_fields=["full_name", "role", "institutional_id", "technical_specialization", "is_active"])
            if specialization:
                teams[TEAM_FOR_SPECIALIZATION[specialization]].members.add(user)
            accounts[demo_key] = (user, is_new)
        return accounts

    def _reference_data(self):
        categories = {}
        locations = {}
        for spec in DEMO_ISSUES:
            category_name = spec["category"]
            location_name = spec["location"]
            try:
                categories[category_name] = IssueCategory.objects.get(name=category_name, is_active=True)
                locations[location_name] = Location.objects.get(name=location_name, is_active=True)
            except (IssueCategory.DoesNotExist, Location.DoesNotExist) as exc:
                raise CommandError(f"Required active demo category/location is missing: {exc}; no records were changed.") from exc
        return categories, locations

    def _routing_rules(self, categories, teams):
        for name, category_name, team_name in ROUTING_RULES:
            rule, _ = RoutingRule.objects.get_or_create(
                name=name,
                defaults={"category": categories[category_name], "target_team": teams[team_name], "priority_order": 10, "active": True},
            )
            rule.category = categories[category_name]
            rule.location = None
            rule.issue_priority = None
            rule.target_team = teams[team_name]
            rule.target_user = None
            rule.priority_order = 10
            rule.active = True
            rule.save()

    def _sla_policy(self):
        policy, _ = SlaPolicy.objects.get_or_create(
            name="DEMO - Standard campus response",
            defaults={"active": True, "priority_order": 10, "response_time_seconds": 14400, "resolution_time_seconds": 86400, "warning_before_seconds": 1800},
        )
        policy.active = True
        policy.category = None
        policy.issue_priority = None
        policy.priority_order = 10
        policy.response_time_seconds = 14400
        policy.resolution_time_seconds = 86400
        policy.warning_before_seconds = 1800
        policy.save()
        return policy

    def _issues(self, accounts, categories, locations):
        result = {}
        for spec in DEMO_ISSUES:
            reporter_id = spec["reporter"]
            reporter = accounts[reporter_id][0]
            reference = spec["ref"]
            issue = Issue.objects.filter(description__contains=f"Demo seed reference: {reference}").first()
            if issue:
                if issue.reporter_id != reporter.pk or issue.category.name != spec["category"] or issue.location.name != spec["location"]:
                    raise CommandError(f"{reference} already identifies a different issue; no records were changed.")
                result[reference] = issue
                continue

            payload = {
                "title": spec["title"],
                "description": f"{spec['description']}\n\nDemo seed reference: {reference}",
                "category": categories[spec["category"]].pk,
                "location": locations[spec["location"]].pk,
            }
            if spec.get("request_priority"):
                payload.update(request_priority=True, priority_reason=spec["priority_reason"])
            serializer = IssueCreateSerializer(data=payload, context={"request": SimpleNamespace(user=reporter)})
            serializer.is_valid(raise_exception=True)
            issue = serializer.save()
            result[reference] = issue
        return result

    def _work_orders(self, issues, admin):
        from apps.workorders.services import assign_work_order, create_work_order

        result = {}
        for reference in sorted(WORK_ORDER_ISSUES):
            issue = issues[reference]
            marker = f"Demo seed reference: DEMO-WO-{reference[-3:]}"
            work_order = WorkOrder.objects.filter(issue=issue, instructions__contains=marker).first()
            if work_order:
                result[reference] = work_order
                continue
            issue.refresh_from_db()
            if not issue.assigned_team_id or not issue.assigned_to_id:
                continue
            work_order = create_work_order(
                issue=issue,
                actor=admin,
                team=issue.assigned_team,
                title=f"{issue.title} — field work",
                instructions=f"Inspect and record the field condition for {issue.ticket_number}. {marker}",
            )
            assign_work_order(
                work_order=work_order,
                actor=admin,
                team=issue.assigned_team,
                technician=issue.assigned_to,
                reason=f"Seeded work order for assigned demo issue {issue.ticket_number}",
            )
            result[reference] = work_order
        return result
