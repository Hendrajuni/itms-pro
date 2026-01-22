from django.utils import timezone
from django.core.cache import cache

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Update cache with current timestamp, expire in 5 mins (300s)
            cache.set(f'user_last_seen_{request.user.id}', timezone.now(), 300)

        response = self.get_response(request)
        return response
