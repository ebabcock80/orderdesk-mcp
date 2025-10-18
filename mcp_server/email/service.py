"""Email service abstraction for OrderDesk MCP Server."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, FileSystemLoader

from mcp_server.utils.logging import logger


@dataclass
class EmailMessage:
    """Email message structure."""

    to: str
    subject: str
    html_body: str
    text_body: str | None = None
    from_email: str | None = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send an email message.

        Args:
            message: Email message to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def is_configured(self) -> bool:
        """
        Check if provider is properly configured.

        Returns:
            True if configured, False otherwise
        """
        pass


class EmailService:
    """Email service for sending emails via various providers."""

    def __init__(
        self, provider: EmailProvider | None = None, template_dir: str | None = None
    ):
        """
        Initialize email service.

        Args:
            provider: Email provider instance (SMTP, SendGrid, etc.)
            template_dir: Directory containing email templates
        """
        self.provider = provider
        self.template_dir = template_dir or "mcp_server/email/templates"

        # Initialize Jinja2 template environment
        self.template_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True,
        )

    async def send_email(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
        from_email: str | None = None,
    ) -> bool:
        """
        Send an email using a template.

        Args:
            to: Recipient email address
            subject: Email subject line
            template_name: Template file name (without extension)
            context: Template context variables
            from_email: Optional sender email (overrides provider default)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.provider:
            logger.error("Email service not configured - no provider set")
            return False

        if not await self.provider.is_configured():
            logger.error("Email provider not properly configured")
            return False

        try:
            # Render HTML template
            html_template = self.template_env.get_template(f"{template_name}.html")
            html_body = html_template.render(**context)

            # Try to render text template (optional)
            text_body = None
            try:
                text_template = self.template_env.get_template(f"{template_name}.txt")
                text_body = text_template.render(**context)
            except Exception:
                # Text template is optional
                pass

            # Create email message
            message = EmailMessage(
                to=to,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_email=from_email,
            )

            # Send via provider
            success = await self.provider.send_email(message)

            if success:
                logger.info(
                    "Email sent successfully",
                    to=to,
                    subject=subject,
                    template=template_name,
                )
            else:
                logger.error(
                    "Email sending failed",
                    to=to,
                    subject=subject,
                    template=template_name,
                )

            return success

        except Exception as e:
            logger.error(
                "Email sending error",
                error=str(e),
                to=to,
                subject=subject,
                template=template_name,
            )
            return False

    async def send_verification_email(
        self,
        to: str,
        verification_link: str,
        master_key: str | None = None,
    ) -> bool:
        """
        Send email verification with magic link.

        Args:
            to: Recipient email address
            verification_link: Magic link for verification
            master_key: Optional master key to show (for signup flow)

        Returns:
            True if sent successfully
        """
        context = {
            "email": to,
            "verification_link": verification_link,
            "master_key": master_key,
        }

        return await self.send_email(
            to=to,
            subject="Verify your OrderDesk MCP account",
            template_name="verification",
            context=context,
        )

    async def send_welcome_email(
        self,
        to: str,
        master_key: str,
    ) -> bool:
        """
        Send welcome email with master key.

        Args:
            to: Recipient email address
            master_key: Generated master key

        Returns:
            True if sent successfully
        """
        context = {
            "email": to,
            "master_key": master_key,
        }

        return await self.send_email(
            to=to,
            subject="Welcome to OrderDesk MCP",
            template_name="welcome",
            context=context,
        )

    def is_enabled(self) -> bool:
        """Check if email service is enabled and configured."""
        return self.provider is not None
