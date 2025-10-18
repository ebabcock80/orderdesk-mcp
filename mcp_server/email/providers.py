"""Email providers for OrderDesk MCP Server."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from mcp_server.email.service import EmailMessage, EmailProvider
from mcp_server.utils.logging import logger


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider for sending emails."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        from_email: str | None = None,
    ):
        """
        Initialize SMTP email provider.

        Args:
            host: SMTP server hostname
            port: SMTP server port
            username: SMTP authentication username (optional)
            password: SMTP authentication password (optional)
            use_tls: Whether to use TLS (default: True)
            from_email: Default sender email address
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email

    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send email via SMTP.

        Args:
            message: Email message to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = message.from_email or self.from_email
            msg["To"] = message.to

            # Add text part (if available)
            if message.text_body:
                text_part = MIMEText(message.text_body, "plain", "utf-8")
                msg.attach(text_part)

            # Add HTML part
            html_part = MIMEText(message.html_body, "html", "utf-8")
            msg.attach(html_part)

            # Connect to SMTP server
            if self.use_tls:
                server = smtplib.SMTP(self.host, self.port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=10)

            # Authenticate if credentials provided
            if self.username and self.password:
                server.login(self.username, self.password)

            # Send email
            server.send_message(msg)
            server.quit()

            logger.info(
                "SMTP email sent successfully",
                to=message.to,
                subject=message.subject,
                host=self.host,
            )
            return True

        except smtplib.SMTPException as e:
            logger.error(
                "SMTP error sending email",
                error=str(e),
                to=message.to,
                subject=message.subject,
                host=self.host,
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                error=str(e),
                to=message.to,
                subject=message.subject,
                host=self.host,
            )
            return False

    async def is_configured(self) -> bool:
        """
        Check if SMTP provider is properly configured.

        Returns:
            True if configured (has host, port, from_email)
        """
        return bool(self.host and self.port and self.from_email)


class ConsoleEmailProvider(EmailProvider):
    """Console email provider for development/testing (prints to console)."""

    def __init__(self, from_email: str = "noreply@localhost"):
        """Initialize console email provider."""
        self.from_email = from_email

    async def send_email(self, message: EmailMessage) -> bool:
        """
        'Send' email by printing to console.

        Args:
            message: Email message to send

        Returns:
            Always True
        """
        print("\n" + "=" * 80)
        print("📧 EMAIL (Console Mode)")
        print("=" * 80)
        print(f"From: {message.from_email or self.from_email}")
        print(f"To: {message.to}")
        print(f"Subject: {message.subject}")
        print("-" * 80)
        if message.text_body:
            print("TEXT BODY:")
            print(message.text_body)
            print("-" * 80)
        print("HTML BODY:")
        print(message.html_body)
        print("=" * 80 + "\n")

        logger.info(
            "Console email 'sent'",
            to=message.to,
            subject=message.subject,
        )
        return True

    async def is_configured(self) -> bool:
        """Console provider is always configured."""
        return True

