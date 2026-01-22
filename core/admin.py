from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Employee Info', {'fields': ('employee_id', 'department', 'location', 'job_title', 'phone_number', 'employee_status', 'photo', 'notes')}),
    )
    list_display = UserAdmin.list_display + ('employee_id', 'department', 'location', 'job_title', 'employee_status')
    list_filter = UserAdmin.list_filter + ('department', 'location', 'employee_status')
    search_fields = UserAdmin.search_fields + ('employee_id', 'job_title', 'phone_number')

# Register your models here.
