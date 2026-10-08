from django.conf import settings
from django.db import models


class Campus(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Building(models.Model):
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name="buildings")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["campus__name", "name"]
        constraints = [models.UniqueConstraint(fields=["campus", "code"], name="uniq_building_code_per_campus")]

    def __str__(self):
        return f"{self.name} · {self.campus.name}"


class Location(models.Model):
    class Kind(models.TextChoices):
        AREA = "AREA", "Area"
        FLOOR = "FLOOR", "Floor"
        CLASSROOM = "CLASSROOM", "Classroom"
        LABORATORY = "LABORATORY", "Laboratory"
        OFFICE = "OFFICE", "Office"
        HOSTEL = "HOSTEL", "Hostel"
        CAFETERIA = "CAFETERIA", "Cafeteria"
        OUTDOOR = "OUTDOOR", "Outdoor area"
        OTHER = "OTHER", "Other"

    building = models.ForeignKey(Building, on_delete=models.PROTECT, related_name="locations", null=True, blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, related_name="children", null=True, blank=True)
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=40, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.AREA)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["building__name", "name"]
        indexes = [models.Index(fields=["building", "is_active"])]

    @property
    def display_name(self):
        if self.building_id:
            return f"{self.building.name} · {self.name}"
        return self.name

    def __str__(self):
        return self.display_name


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="teams", null=True, blank=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="teams", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
