"""Interactive owner setup. Credentials and OTPs are never command-line arguments."""

import getpass
import secrets
import sys
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from shop.models import OwnerState
from shop.owner_security import configured, issue, verify


class Command(BaseCommand):
    help = "Initialize the first verified owner using private terminal prompts and Gmail verification."

    def handle(self, *args, **options):
        state = OwnerState.objects.get(pk=1)
        if state.closed or state.owner_id:
            raise CommandError("Owner initialization is permanently closed.")
        if not configured() or len(settings.ADMIN_SETUP_SECRET) < 32:
            raise CommandError(
                "Configure owner Gmail, email delivery, a strong setup secret and durable storage first. See docs/OWNER_SETUP.md."
            )
        if not sys.stdin.isatty():
            raise CommandError(
                "Use an interactive terminal. Secrets must not be supplied in arguments or piped input."
            )
        username = input("Administrator username [umid_w]: ").strip() or "umid_w"
        setup_secret = getpass.getpass("Deployment setup secret: ")
        password = getpass.getpass("New administrator password: ")
        confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            raise CommandError("Passwords do not match. No account was created.")
        binding = secrets.token_urlsafe(32)
        result = issue(
            "setup",
            username=username,
            password=password,
            binding=binding,
            source="interactive-cli",
            setup_secret=setup_secret,
        )
        if not result.ok:
            raise CommandError(result.error)
        self.stdout.write(
            "A verification code was sent only to the configured owner Gmail. It expires in 10 minutes. No account is active yet."
        )
        for _ in range(5):
            code = getpass.getpass("Owner verification code (hidden): ").strip()
            approved = verify(result.challenge.pk, code, binding)
            if approved.ok:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Owner activated. Sign in at /admin/login/. Remove ADMIN_SETUP_SECRET from private server settings."
                    )
                )
                return
            self.stderr.write(
                "Verification was not accepted. Check the code and its expiry."
            )
        raise CommandError("Verification limit reached. No account was activated.")
