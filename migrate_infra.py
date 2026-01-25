import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assets.models import Infrastructure, InfrastructureType

# Map old codes to (Name, Icon, Color)
MAPPING = {
    'TOWER': ('Tower Nodes', 'broadcast-tower', 'info'),
    'SERVER_RACK': ('Server Racks', 'server', 'primary'),
    'WALLMOUNT': ('Wallmount Racks', 'hdd', 'success'),
    'PANEL': ('Box Panels', 'bolt', 'warning'),
    'UPS': ('UPS / Power', 'battery-full', 'secondary'),
    'CABLING': ('Cabling', 'network-wired', 'secondary'),
    'COOLING': ('Cooling / AC', 'snowflake', 'info'),
    'OTHER': ('Other', 'cube', 'secondary'),
}

def run():
    print("Start migrating Infrastructure Types...")
    
    # 1. Create Types
    type_objects = {}
    for code, (label, icon, color) in MAPPING.items():
        obj, created = InfrastructureType.objects.get_or_create(
            name=label,
            defaults={
                'icon': icon,
                'color': color
            }
        )
        type_objects[code] = obj
        if created:
            print(f"Created Group: {label}")
        else:
             # Update simple fields just in case
            obj.icon = icon
            obj.color = color
            obj.save()
            print(f"Found Group: {label}")

    # 2. Update existing items
    items = Infrastructure.objects.all()
    count = 0
    for item in items:
        # Get old type code
        old_code = item.type
        if old_code in type_objects:
            # Only update if null (or force update?)
            # Force update for now to ensure sync
            item.infra_type = type_objects[old_code]
            item.save()
            count += 1
            
    print(f"Updated {count} infrastructure items.")
    print("Done.")

if __name__ == '__main__':
    run()
