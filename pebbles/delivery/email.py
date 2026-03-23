"""Email delivery adapter for Pebbles."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from ..models import Pebble, Recipient
from ..config import Settings

logger = logging.getLogger(__name__)


class EmailDelivery:
    """Delivers pebbles via email using SMTP."""

    def __init__(self, settings: Settings):
        """Initialize email delivery.
        
        Args:
            settings: Configuration containing SMTP credentials
        """
        self.settings = settings
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.smtp_from = settings.smtp_from or settings.smtp_user

    def send(self, pebble: Pebble, recipient: Recipient) -> bool:
        """Send a pebble via email.
        
        Args:
            pebble: The pebble to send
            recipient: Target recipient with email address
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not recipient.email:
            logger.warning(f"Recipient {recipient.name} has no email address configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🪨 {pebble.title}"
            msg["From"] = self.smtp_from
            msg["To"] = recipient.email

            # Plain text version
            text_body = f"{pebble.title}\n\n{pebble.context}\n\n{pebble.url}"
            
            # HTML version
            html_body = f"""
            <html>
              <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
                  <h2 style="color: white; margin: 0;">🪨 {pebble.title}</h2>
                </div>
                <div style="background: #f7fafc; padding: 20px; border-radius: 0 0 8px 8px;">
                  <p style="color: #2d3748; line-height: 1.6;">{pebble.context}</p>
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

            logger.info(f"Sent pebble to {recipient.email}: {pebble.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient.email}: {e}")
            return False

    def close(self):
        """Close any resources (no-op for SMTP)."""
        pass