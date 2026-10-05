from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import User


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "full_name", "phone_number", "role", "is_active")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ("email", "full_name", "phone_number", "role", "is_active", "is_superuser", "password", "groups", "user_permissions")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreateForm
    list_display = ("email", "full_name", "role", "is_active", "is_superuser", "date_joined")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("email", "full_name", "phone_number")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal details", {"fields": ("full_name", "phone_number", "role")}),
        ("Permissions", {"fields": ("is_active", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "full_name", "phone_number", "role", "is_active", "password")}),)

    def save_model(self, request, obj, form, change):
        if change and form.cleaned_data.get("password") and form.cleaned_data["password"] != obj.password:
            obj.set_password(form.cleaned_data["password"])
        super().save_model(request, obj, form, change)
