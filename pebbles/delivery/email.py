"""Email delivery adapter for Pebbles."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..models import Pebble, Recipient
from ..config import PebblesConfig

logger = logging.getLogger(__name__)


class EmailDelivery:
    """Delivers pebbles via email using SMTP.

    Expects the Recipient's `delivery_method` to be 'email' and
    `delivery_address` to hold the email address.
    """

    def __init__(self, config: PebblesConfig):
        self.smtp_host = config.smtp_host
        self.smtp_port = config.smtp_port
        self.smtp_user = config.smtp_user
        self.smtp_password = config.smtp_password
        self.smtp_from = config.smtp_from or config.smtp_user

    def send(self, pebble: Pebble, recipient: Recipient) -> bool:
        """Send a pebble via email. Returns True on success."""
        if recipient.delivery_method != "email":
            logger.warning(
                f"Recipient {recipient.name} delivery_method is '{recipient.delivery_method}', "
                f"expected 'email'"
            )
            return False

        to_address = recipient.delivery_address
        if not to_address:
            logger.warning(f"Recipient {recipient.name} has no delivery_address configured")
            return False

        if not all([self.smtp_host, self.smtp_user, self.smtp_password]):
            logger.error("SMTP credentials not fully configured; cannot send email")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🪨 {pebble.title}"
            msg["From"] = self.smtp_from
            msg["To"] = to_address

            text_body = f"{pebble.title}\n\n{pebble.description}\n\n{pebble.url}"

            html_body = f"""
            <html>
              <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
                  <h2 style="color: white; margin: 0;">🪨 {pebble.title}</h2>
                </div>
                <div style="background: #f7fafc; padding: 20px; border-radius: 0 0 8px 8px;">
                  <p style="color: #2d3748; line-height: 1.6;">{pebble.description}</p>
                  <a href="{pebble.url}" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 10px;">
                    Read More
                  </a>
                </div>
              </body>
            </html>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Sent pebble to {to_address}: {pebble.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {e}")
            return False

    def close(self):
        """Close any resources (no-op for SMTP)."""
        pass
