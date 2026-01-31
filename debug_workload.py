
import os
import django
from django.db.models import Q, Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from tickets.models import Ticket
from governance.models import ProjectTask

User = get_user_model()

from django.db.models import Count, F, Q

print("\n--- USER CHECK ---")
users = User.objects.filter(email='henjun89@gmail.com')
print(f"Users with email 'henjun89@gmail.com': {users.count()}")
for u in users:
    print(f"ID: {u.id}, Username: {u.username}, Groups: {[g.name for g in u.groups.all()]}")

print("\n--- ANNOTATION QUERY DEBUG (WITH DISTINCT=TRUE) ---")
# Replicate the exact query from views.py but with distinct=True
annotated_users = User.objects.filter(email='henjun89@gmail.com').annotate(
    ticket_load=Count('tickets_assigned', filter=Q(tickets_assigned__status__in=['Open', 'In Progress']), distinct=True),
    project_load=Count('projecttask', filter=~Q(projecttask__status='Completed'), distinct=True)
).annotate(
    open_load=F('ticket_load') + F('project_load')
)

for u in annotated_users:
    print(f"User: {u.username}")
    print(f"  ticket_load (Annotation): {u.ticket_load}")
    print(f"  project_load (Annotation): {u.project_load}")
    print(f"  open_load (Annotation): {u.open_load}")

print("\n--- RAW TICKET COUNT CHECK ---")
# Count ALL tickets for this user to compare
u = users.first()
all_tickets = u.tickets_assigned.all()
print(f"Total Tickets Assigned (All Statuses): {all_tickets.count()}")
for t in all_tickets:
    print(f" - Ticket {t.id}: Status='{t.status}'")

# Check if maybe 'In Progress' logic is counting 'In_Progress'
print("\n--- FILTER TEST ---")
q_filter = Q(tickets_assigned__status__in=['Open', 'In Progress'])
filtered_count = User.objects.filter(id=u.id).aggregate(
    count=Count('tickets_assigned', filter=q_filter)
)
print(f"Filtered Count Result: {filtered_count}")

