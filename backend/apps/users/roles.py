from django.db import models


class UserRole(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    STAFF = "STAFF", "Staff"
    TECHNICIAN = "TECHNICIAN", "Technician"
    SUPERVISOR = "SUPERVISOR", "Team supervisor"
    FACILITY_MANAGER = "FACILITY_MANAGER", "Facility manager"
    IT_MANAGER = "IT_MANAGER", "IT manager"
    DEPARTMENT_HEAD = "DEPARTMENT_HEAD", "Department head"
    CAMPUS_ADMIN = "CAMPUS_ADMIN", "Campus administrator"
    SYSTEM_ADMIN = "SYSTEM_ADMIN", "System administrator"


ADMIN_ROLES = {UserRole.CAMPUS_ADMIN, UserRole.SYSTEM_ADMIN}
ISSUE_MANAGEMENT_ROLES = ADMIN_ROLES | {
    UserRole.FACILITY_MANAGER,
    UserRole.IT_MANAGER,
    UserRole.DEPARTMENT_HEAD,
}
