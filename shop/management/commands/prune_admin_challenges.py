from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from shop.models import AdminChallenge, SecurityThrottle


class Command(BaseCommand):
    help = "Remove expired verification material without logging sensitive values."

    def handle(self, *args, **kwargs):
        AdminChallenge.objects.filter(expires_at__lte=timezone.now()).delete()
        SecurityThrottle.objects.filter(
            window_start__lt=timezone.now() - timedelta(days=2)
        ).delete()
