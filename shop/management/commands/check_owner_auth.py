from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from shop.models import OwnerState
from shop.owner_security import configured, owner_email


class Command(BaseCommand):
    help = "Check owner-auth configuration without printing secrets or sending email."

    def handle(self, *args, **kwargs):
        state = OwnerState.objects.get(pk=1)
        missing = []
        if not owner_email():
            missing.append("OWNER_EMAIL (valid configured Gmail address)")
        if not settings.EMAIL_API_KEY:
            missing.append("EMAIL_API_KEY")
        if not settings.DEFAULT_FROM_EMAIL:
            missing.append("EMAIL_FROM (provider-authorized sender)")
        if not settings.OWNER_AUTH_DURABLE:
            missing.append("DATABASE_URL (persistent PostgreSQL on Render)")
        if not state.closed and len(settings.ADMIN_SETUP_SECRET) < 32:
            missing.append("ADMIN_SETUP_SECRET (at least 32 random characters)")
        if missing:
            raise CommandError("Missing configuration: " + ", ".join(missing))
        if not configured():
            raise CommandError("Owner email delivery is not configured securely.")
        self.stdout.write(
            "Owner-auth configuration is present. No email was sent. Verify live delivery through the protected setup or recovery flow."
        )
