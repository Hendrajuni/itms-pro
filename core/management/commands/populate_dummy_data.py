import random
from datetime import timedelta, date
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from assets.models import Asset, Department, Location, Vendor, Category, Infrastructure
from tickets.models import Ticket, TicketTopic
from maintenance.models import AssetMaintenance

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with dummy data for Assets, Maintenance, and Tickets'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting data population...")

        # 1. Ensure Admin User
        admin_user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True})
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write("Created admin user.")

        # 2. Locations
        loc_names = ['Head Office', 'Branch A', 'Branch B', 'Factory 1']
        locations = []
        for name in loc_names:
            loc, _ = Location.objects.get_or_create(name=name, defaults={'type': 'HO' if name == 'Head Office' else 'RO'})
            locations.append(loc)
        self.stdout.write(f"Created {len(locations)} Locations.")

        # 3. Departments
        dept_names = ['IT', 'HR', 'Finance', 'Operations', 'Sales']
        departments = []
        for name in dept_names:
            dept, _ = Department.objects.get_or_create(name=name, defaults={'manager': admin_user})
            departments.append(dept)
        self.stdout.write(f"Created {len(departments)} Departments.")

        # 4. Vendors
        vendor_data = [
            {'name': 'Dell Enterprises', 'email': 'sales@dell.example.com'},
            {'name': 'HP Inc', 'email': 'contact@hp.example.com'},
            {'name': 'Cisco Systems', 'email': 'support@cisco.example.com'},
            {'name': 'Microsoft', 'email': 'licensing@microsoft.example.com'},
        ]
        vendors = []
        for v in vendor_data:
            vendor, _ = Vendor.objects.get_or_create(name=v['name'], defaults={'email': v['email']})
            vendors.append(vendor)
        self.stdout.write(f"Created {len(vendors)} Vendors.")

        # 5. Categories
        categories = {
            'Laptop': 'HW',
            'Desktop': 'HW',
            'Server': 'HW',
            'Printer': 'HW',
            'Windows 11': 'SW',
            'Office 365': 'SW',
            'Switch': 'IN',
            'Router': 'IN',
        }
        cats = []
        for name, type_ in categories.items():
            cat, _ = Category.objects.get_or_create(name=name, defaults={'type': type_})
            cats.append(cat)
        self.stdout.write(f"Created {len(cats)} Categories.")

        # 6. Infrastructure (Dummy)
        infra_names = ['Server Room A', 'Network Rack B', 'Cabling Floor 1']
        infras = []
        for name in infra_names:
            # Requires fields check, assuming simple structure for now based on context
            try:
                # Need to check Infrastructure Model fields if strict, but generic create might work if simple
                # Assume basic name field exists
                infra, created = Infrastructure.objects.get_or_create(name=name, defaults={
                   'location': random.choice(locations),
                   'category': Category.objects.get(name='Switch') # Just mapping to a category
                })
                infras.append(infra)
            except Exception as e:
                self.stdout.write(f"Skipping Infra {name}: {e}")
        self.stdout.write(f"Created {len(infras)} Infrastructures.")

        # 7. Assets
        asset_names = ['Laptop Latitude 5420', 'ProBook 450 G8', 'PowerEdge R740', 'LaserJet Pro M404']
        assets = []
        for i in range(20):
            name = random.choice(asset_names)
            cat = Category.objects.filter(name__icontains=name.split()[0]).first() or cats[0]
            
            asset = Asset.objects.create(
                name=f"{name} - {i+1}",
                category=cat,
                vendor=random.choice(vendors),
                location=random.choice(locations),
                department=random.choice(departments),
                status=random.choice(['AVAILABLE', 'IN_USE', 'MAINTENANCE']),
                purchase_date=date.today() - timedelta(days=random.randint(10, 1000)),
                purchase_price=random.randint(500, 3000),
                assigned_to=admin_user if random.choice([True, False]) else None
            )
            assets.append(asset)
        self.stdout.write(f"Created {len(assets)} Assets.")

        # 8. Tickets
        topics = ['Laptop Slow', 'Internet Down', 'Printer Jam', 'Software Install']
        for i in range(15):
            Ticket.objects.create(
                title=f"{random.choice(topics)} - {i}",
                description="This is a dummy ticket description generated for testing.",
                created_by=admin_user,
                assigned_to=admin_user,
                asset=random.choice(assets) if random.random() > 0.5 else None,
                priority=random.choice(['Low', 'Medium', 'High']),
                status=random.choice(['Open', 'In_Progress', 'Resolved']),
                category=random.choice(['Hardware', 'Software', 'Network'])
            )
        self.stdout.write("Created 15 Tickets.")

        # 9. Maintenance
        for i in range(10):
            asset = random.choice(assets)
            AssetMaintenance.objects.create(
                asset=asset,
                title=f"Routine Maintenance {i}",
                scheduled_date=date.today() + timedelta(days=random.randint(-30, 30)),
                maintenance_type='Preventive',
                status=random.choice(['Scheduled', 'Completed']),
                technician=admin_user,
                notes="Checked fans, cleaned dust, updated firmware."
            )
        self.stdout.write("Created 10 Maintenance Logs.")

        self.stdout.write(self.style.SUCCESS("Dummy data population completed successfully!"))
