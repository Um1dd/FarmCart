"""Transactional email over HTTPS (SMTP ports are restricted on free hosts)."""

import json
from urllib.request import Request, urlopen
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class EmailDeliveryError(Exception):
    pass


class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not settings.EMAIL_API_KEY or not settings.DEFAULT_FROM_EMAIL:
            raise EmailDeliveryError("Email delivery is not configured.")
        count = 0
        for message in email_messages:
            # Owner authentication may never use caller-supplied recipients.
            if message.to != [settings.OWNER_EMAIL] or message.cc or message.bcc:
                raise EmailDeliveryError("Invalid verification destination.")
            data = json.dumps(
                {
                    "from": settings.DEFAULT_FROM_EMAIL,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                }
            ).encode()
            request = Request(
                "https://api.resend.com/emails",
                data=data,
                headers={
                    "Authorization": "Bearer " + settings.EMAIL_API_KEY,
                    "Content-Type": "application/json",
                    "User-Agent": "FarmCart/1.0",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=15) as response:
                    if not 200 <= response.status < 300:
                        raise EmailDeliveryError("Email delivery failed.")
            except Exception:
                # Never propagate provider response bodies, credentials or message contents.
                raise EmailDeliveryError("Email delivery failed.") from None
            count += 1
        return count
