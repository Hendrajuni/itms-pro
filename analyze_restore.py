import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import CustomUser
from assets.models import Asset, Department

def analyze_restoration():
    print("--- Analyzing Users ---")
    users = CustomUser.objects.all()
    for u in users:
        dept_name = u.department.name if u.department else "None"
        print(f"User: {u.username}, Job: {u.job_title}, Current Dept: {dept_name}")

    print("\n--- Analyzing Assets ---")
    assets = Asset.objects.filter(department__isnull=True, assigned_to__isnull=False)
    print(f"Assets with NULL Dept but Assigned User: {assets.count()}")
    
if __name__ == "__main__":
    analyze_restoration()
