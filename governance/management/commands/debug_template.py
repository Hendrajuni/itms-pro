from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from governance.views import ProjectDetailView
import re

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        
        factory = RequestFactory()
        request = factory.get('/governance/projects/2/')
        request.user = user
        
        view = ProjectDetailView.as_view()
        response = view(request, pk=2)
        response.render()
        html = response.content.decode('utf-8')
        
        # Find the edit button context
        for match in re.finditer(r'editExpenseModal', html):
            start = max(0, match.start() - 200)
            end = min(len(html), match.end() + 200)
            context = html[start:end]
            print(f"=== editExpenseModal at pos {match.start()} ===")
            print(context)
            print()
        
        # Check if sidebar has overflow hidden
        sidebar_match = re.search(r'sidebar.*?overflow[^;]*;', html, re.DOTALL | re.IGNORECASE)
        if sidebar_match:
            print(f"Sidebar overflow: {sidebar_match.group()[:200]}")
        
        # Check for the Google Sheets iframe - does it have specific height?
        iframe_match = re.search(r'<iframe[^>]*docs\.google[^>]*>', html)
        if iframe_match:
            print(f"\nIframe tag: {iframe_match.group()[:500]}")
