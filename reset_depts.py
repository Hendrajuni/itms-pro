import os
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assets.models import Department

def reset_departments():
    print("Deleting existing departments...")
    # This will strictly delete departments. Assets linking to them will have department=NULL
    count, _ = Department.objects.all().delete()
    print(f"Deleted {count} existing departments.")
    
    new_departments = [
        # Support / Back Office
        "Finance & Accounting",
        "HR & GA",
        "IT",
        "Procurement / Logistik",
        "Legal / Sustainability",
        
        # Estate
        "Agronomy / Tanaman",
        "Tata Usaha (KTU)",
        
        # Mill
        "Engineering / Teknik",
        "Processing / Pengolahan",
        "Laboratory / QC"
    ]
    
    print("Creating new departments...")
    for name in new_departments:
        Department.objects.create(name=name)
        print(f" - Created: {name}")

    print("Success! Departments have been reset.")

if __name__ == "__main__":
    reset_departments()
