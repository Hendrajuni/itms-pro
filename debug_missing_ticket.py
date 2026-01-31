
import os
import django
from django.db.models import Q, Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from tickets.models import Ticket

User = get_user_model()
try:
    user = User.objects.get(email='henjun89@gmail.com')
except User.DoesNotExist:
    print("User not found")
    exit()

print(f"--- DEBUGGING TICKETS FOR {user.username} ---")

# 1. List ALL tickets assigned to him
all_tickets = Ticket.objects.filter(assigned_to=user)
print(f"Total Assigned: {all_tickets.count()}")

for t in all_tickets:
    print(f"ID: {t.id} | Code: {t.ticket_code} | Title: {t.title} | Status: '{t.status}'")

# 2. Check the specific filter used in views.py
print("\n--- VIEW QUERY CHECK ---")
count_in_view = Ticket.objects.filter(
    assigned_to=user, 
    status__in=['Open', 'In Progress']
).count()
print(f"Count with current filter ['Open', 'In Progress']: {count_in_view}")

# 3. Check what happens if we add 'Assigned'
count_expected = Ticket.objects.filter(
    assigned_to=user, 
    status__in=['Open', 'In Progress', 'Assigned', 'Pending_Vendor']
).count()
print(f"Count with expanded filter ['Open', 'In Progress', 'Assigned', 'Pending_Vendor']: {count_expected}")
