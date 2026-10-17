"""Transactional email over HTTPS (SMTP ports are restricted on free hosts)."""

import json
import logging
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    # Only fixed, sanitized messages may be shown after owner authorization.
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
                        raise ValueError("Unexpected status")
                    receipt = json.loads(response.read(65536))
                    message_id = str(uuid.UUID(receipt["id"]))
                # A 2xx page alone does not prove that Resend accepted an email.
                logger.info("Owner mail accepted by Resend; message_id=%s", message_id)
            except HTTPError as error:
                status = error.code
                logger.warning("Owner mail rejected by Resend; http_status=%s", status)
                reasons = {
                    401: "E-poçt xidməti API açarını qəbul etmədi (401). Render-də EMAIL_API_KEY və Resend hesabını yoxlayın.",
                    403: "E-poçt göndərmə icazəsi rədd edildi (403). Resend hesabının Gmail-i, sender və Sending access icazəsini yoxlayın.",
                    422: "E-poçt xidməti göndərən/alıcı parametrlərini qəbul etmədi (422). Server konfiqurasiyasını yoxlayın.",
                    429: "E-poçt xidmətinin göndərmə limiti dolub (429). Bir qədər sonra cəhd edin.",
                }
                raise EmailDeliveryError(
                    reasons.get(
                        status,
                        "E-poçt xidməti sorğunu qəbul etmədi. Resend Logs bölməsini yoxlayın.",
                    )
                ) from None
            except Exception:
                logger.warning(
                    "Owner mail delivery could not be confirmed; no valid Resend receipt"
                )
                raise EmailDeliveryError(
                    "Göndəriş təsdiqlənmədi: server Resend-dən etibarlı məktub ID-si almadı. Render Logs bölməsini yoxlayın."
                ) from None
            count += 1
        return count
