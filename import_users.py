import os
import sys
import django
import zipfile
from xml.etree import ElementTree as ET
import re

# Setup environment Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from assets.models import Department, Location

User = get_user_model()

def read_simple_xlsx(filepath):
    """Membaca file .xlsx murni menggunakan library bawaan Python tanpa pandas/openpyxl"""
    with zipfile.ZipFile(filepath, 'r') as z:
        # Get shared strings
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            xml_content = z.read('xl/sharedStrings.xml')
            tree = ET.fromstring(xml_content)
            namespace = {'ns': tree.tag.split('}')[0].strip('{')} if '}' in tree.tag else {}
            for t in (tree.findall('.//ns:t', namespace) if namespace else tree.findall('.//t')):
                shared_strings.append(t.text or '')

        # Get sheet1
        sheet_xml = z.read('xl/worksheets/sheet1.xml')
        tree = ET.fromstring(sheet_xml)
        namespace = {'ns': tree.tag.split('}')[0].strip('{')} if '}' in tree.tag else {}
        
        rows = []
        for row_elem in (tree.findall('.//ns:row', namespace) if namespace else tree.findall('.//row')):
            row_data = {}
            for c_elem in (row_elem.findall('.//ns:c', namespace) if namespace else row_elem.findall('.//c')):
                cell_ref = c_elem.get('r') # e.g. A1, B1
                col_letter = re.match(r'([A-Z]+)', cell_ref).group(1)
                
                v_elem = c_elem.find('ns:v', namespace) if namespace else c_elem.find('v')
                if v_elem is not None:
                    value = v_elem.text
                    # Check if it's a shared string
                    if c_elem.get('t') == 's':
                        value = shared_strings[int(value)]
                    row_data[col_letter] = value
                else:
                    row_data[col_letter] = ''
            rows.append(row_data)
    
    if not rows: return []
    
    # Map letters to header names
    headers = rows[0]
    result = []
    for r in rows[1:]:
        # Jika baris kosong (tidak ada data sama sekali di kolom yang dikenali), skip
        if not any(r.get(col, '').strip() for col in headers):
            continue
            
        row_dict = {headers[col].strip(): r.get(col, '') for col in headers}
        result.append(row_dict)
        
    return result

def import_users(file_path):
    try:
        if file_path.endswith('.csv'):
            import csv
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                data = list(reader)
        elif file_path.endswith('.xlsx'):
            data = read_simple_xlsx(file_path)
        else:
            print("Format tidak didukung. Gunakan .csv atau .xlsx")
            sys.exit(1)
            
        success_count = 0
        error_count = 0

        print(f"Memulai import data user dari {file_path}...")
        print("-" * 30)

        for row in data:
            username = row.get('Username', '').strip()
            if not username:
                continue # Skip jika username kosong
                
            password = row.get('Password', '').strip()
            email = row.get('Email', '').strip()
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            employee_id = row.get('Employee ID', '').strip()
            department_name = row.get('Department', '').strip()
            location_name = row.get('Location', '').strip()
            job_title = row.get('Job Title', '').strip()
            phone_number = row.get('Phone Number', '').strip()
            employee_status = row.get('Employee Status', '').strip().upper()
            notes = row.get('Notes', '').strip()

            # Validasi status
            valid_statuses = ['ACTIVE', 'PROBATION', 'CONTRACT', 'RESIGNED']
            if employee_status not in valid_statuses:
                employee_status = 'ACTIVE' # Default

            try:
                # Handle Department
                department = None
                if department_name:
                    department, _ = Department.objects.get_or_create(name=department_name)
                    
                # Handle Location
                location = None
                if location_name:
                    location, _ = Location.objects.get_or_create(name=location_name)

                # Create atau Update User
                user, created = User.objects.get_or_create(username=username)
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                if employee_id:
                    user.employee_id = employee_id
                user.department = department
                user.location = location
                user.job_title = job_title
                user.phone_number = phone_number
                user.employee_status = employee_status
                user.notes = notes
                
                if password:
                    user.set_password(password)
                elif created:
                    user.set_password('Itms123!') # Password default
                    
                user.save()
                
                action = "Created" if created else "Updated"
                print(f"[{action}] User: {username}")
                success_count += 1
                
            except Exception as e:
                print(f"[Error] Gagal memproses user {username}: {e}")
                error_count += 1
                
        print("-" * 30)
        print(f"Import Selesai. Sukses: {success_count}, Error: {error_count}")
    except Exception as e:
        print(f"Gagal memproses file: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Penggunaan: python import_users.py <nama_file.xlsx atau .csv>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"File tidak ditemukan: {file_path}")
        sys.exit(1)
        
    import_users(file_path)
