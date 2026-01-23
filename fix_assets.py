import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assets.models import Asset, Department
from core.models import CustomUser

def fix_assets():
    print("--- Current Departments ---")
    for d in Department.objects.all():
        print(f"[{d.id}] {d.name}")
        
    print("\n--- Fixing Asset Departments ---")
    assets = Asset.objects.filter(department__isnull=True, assigned_to__isnull=False)
    count = 0
    for asset in assets:
        user = asset.assigned_to
        if user.department:
            asset.department = user.department
            asset.save()
            print(f"Updated Asset '{asset.name}' -> Dept: {user.department.name} (from User {user.username})")
            count += 1
        else:
            print(f"Asset '{asset.name}' (User {user.username}) has no user department.")
            
    print(f"\nFixed {count} assets.")

if __name__ == "__main__":
    fix_assets()
