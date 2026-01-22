from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Initialize roles (groups) for the application'

    def handle(self, *args, **options):
        roles = ['Administrator', 'IT Support', 'Staff']
        for role in roles:
            group, created = Group.objects.get_or_create(name=role)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {role}'))
            else:
                self.stdout.write(self.style.WARNING(f'Group already exists: {role}'))
