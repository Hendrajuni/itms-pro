
import os
import django
from django.db.models import Count, Q, OuterRef, Subquery, IntegerField, F, Value
from django.db.models.functions import Coalesce

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from governance.models import DailyLog
from tickets.models import Ticket
from django.contrib.auth import get_user_model

User = get_user_model()
try:
    user = User.objects.get(email='henjun89@gmail.com')
except User.DoesNotExist:
    print("User not found")
    exit()

print(f"--- DEBUGGING DAILY LOGS FOR {user.username} ---")

# Mimic the view logic
queryset = DailyLog.objects.filter(executor=user).order_by('-date')

# Subquery logic
tickets_resolved_qs = Ticket.objects.filter(
    assigned_to=OuterRef('executor'),
    resolved_at__date=OuterRef('date')
).values('assigned_to').annotate(cnt=Count('id')).values('cnt')

# Annotate
queryset = queryset.annotate(
    manual_ticket_count=Count('items', filter=Q(items__content_type__model='ticket')),
    auto_ticket_count=Coalesce(Subquery(tickets_resolved_qs[:1], output_field=IntegerField()), 0)
).annotate(
    ticket_count=F('manual_ticket_count') + F('auto_ticket_count')
)

print(f"{'DATE':<15} | {'MANUAL':<8} | {'AUTO':<8} | {'TOTAL':<8}")
print("-" * 50)

for log in queryset[:10]:
    print(f"{log.date} | {log.manual_ticket_count:<8} | {log.auto_ticket_count:<8} | {log.ticket_count:<8}")

print("\nChecking tickets resolved for specific dates:")
# Check specific date like Jan 31
import datetime
check_date = datetime.date(2026, 1, 31)
tickets = Ticket.objects.filter(assigned_to=user, resolved_at__date=check_date)
print(f"Tickets resolved on {check_date}: {tickets.count()}")
for t in tickets:
    print(f" - {t.ticket_code} ({t.status})")
