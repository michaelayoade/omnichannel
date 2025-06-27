import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Any

from django.core.files.base import ContentFile
from django.template import Context, Template
from django.utils import timezone

from email_integration import models
from email_integration.channels.adapters.base import BaseOutboundAdapter
from email_integration.exceptions import (
    AuthenticationError,
    ConnectionError,
    SendingError,
)
from email_integration.models import (
    EmailAccount,
    EmailAttachment,
    EmailMessage,
    EmailTemplate,
)
from email_integration.utils.email_parser import EmailThreadParser

logger = logging.getLogger(__name__)


class SMTPService(BaseOutboundAdapter):
    """SMTP service for sending emails through configured email accounts.
    Supports HTML/plain text emails, attachments, and template rendering.
    """

    def __init__(self, email_account: EmailAccount):
        super().__init__(email_account)
        self.account = email_account
        self.thread_parser = EmailThreadParser()

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create and configure SMTP connection."""
        try:
            if self.account.smtp_use_ssl:
                smtp = smtplib.SMTP_SSL(
                    self.account.smtp_server, self.account.smtp_port,
                )
            else:
                smtp = smtplib.SMTP(self.account.smtp_server, self.account.smtp_port)
                if self.account.smtp_use_tls:
                    smtp.starttls()

            smtp.login(self.account.smtp_username, self.account.smtp_password)
            return smtp

        except smtplib.SMTPAuthenticationError as e:
            raise AuthenticationError(f"SMTP authentication failed: {e}")
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
            raise ConnectionError(f"SMTP connection failed: {e}")
        except Exception as e:
            raise ConnectionError(f"An unexpected SMTP error occurred: {e}")

    def validate_credentials(self) -> bool:
        """Validate SMTP credentials by connecting and logging in."""
        try:
            with self._create_smtp_connection():
                # If context manager succeeds, login was successful.
                pass
            return True
        except (AuthenticationError, ConnectionError) as e:
            logger.warning(
                "Credential validation failed for account %s: %s", self.account_id, e,
            )
            return False

    def send(
        self,
        to_emails: list[str],
        subject: str,
        plain_body: str | None = None,
        html_body: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> EmailMessage:
        # Extract additional parameters from kwargs for backward compatibility
        # and specific SMTP features.
        cc_emails: list[str] | None = kwargs.get("cc_emails")
        bcc_emails: list[str] | None = kwargs.get("bcc_emails")
        reply_to: str | None = kwargs.get("reply_to")
        template_id: int | None = kwargs.get("template_id")
        template_context: dict[str, Any] | None = kwargs.get("template_context")
        in_reply_to: str | None = kwargs.get("in_reply_to")
        references: str | None = kwargs.get("references")
        priority: str = kwargs.get("priority", "normal")
        """
        Send an email through the SMTP service.

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            plain_body: Plain text body
            html_body: HTML body
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            reply_to: Reply-to address
            attachments: List of attachment dicts with 'content', 'filename',
                'content_type'
            template_id: Email template ID to use
            template_context: Context variables for template rendering
            in_reply_to: Message ID this email replies to
            references: Thread references
            priority: Email priority level

        Returns:
            EmailMessage object
        """

        # Use template if provided
        if template_id:
            template = EmailTemplate.objects.get(id=template_id)
            if template_context:
                subject = self._render_template(template.subject, template_context)
                plain_body = self._render_template(
                    template.plain_content, template_context,
                )
                html_body = self._render_template(
                    template.html_content, template_context,
                )
            else:
                subject = template.subject
                plain_body = template.plain_content
                html_body = template.html_content

        # Generate message ID and thread ID
        message_id = make_msgid()
        thread_id = self.thread_parser.generate_thread_id(
            subject, in_reply_to, references,
        )

        # Create email message record
        email_message = EmailMessage.objects.create(
            account=self.account,
            message_id=message_id,
            thread_id=thread_id,
            direction="outbound",
            status="pending",
            priority=priority,
            from_email=self.account.email_address,
            from_name=self.account.display_name,
            to_emails=to_emails,
            cc_emails=cc_emails or [],
            bcc_emails=bcc_emails or [],
            reply_to_email=reply_to or "",
            subject=subject,
            plain_body=plain_body or "",
            html_body=html_body or "",
            in_reply_to=in_reply_to or "",
            references=references or "",
            received_at=timezone.now(),
        )

        try:
            # Create MIME message
            msg = self._create_mime_message(
                to_emails=to_emails,
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                reply_to=reply_to,
                message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                priority=priority,
            )

            # Add attachments
            if attachments:
                self._add_attachments(msg, email_message, attachments)

            # Add signature and footer
            if self.account.signature or self.account.footer:
                self._add_signature_and_footer(msg, email_message)

            # Send email
            with self._create_smtp_connection() as smtp:
                all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
                smtp.send_message(msg, to_addrs=all_recipients)

            # Update message status
            email_message.status = "sent"
            email_message.sent_at = timezone.now()
            email_message.raw_message = msg.as_string()
            email_message.save()

            # Update account statistics
            self.account.total_emails_sent += 1
            self.account.save(update_fields=["total_emails_sent"])

            logger.info(f"Email sent successfully: {message_id}")
            return email_message

        except (AuthenticationError, ConnectionError) as e:
            # Critical configuration/connection errors
            email_message.status = "failed"
            email_message.failed_at = timezone.now()
            email_message.error_message = str(e)
            email_message.error_code = "channel_error"
            email_message.save()
            logger.error(
                f"SMTP channel error for account {self.account.email_address}: {e}",
            )
            raise  # Re-raise to be handled by the Celery task

        except (smtplib.SMTPException, SendingError) as e:
            # Errors during the sending process
            email_message.status = "failed"
            email_message.failed_at = timezone.now()
            email_message.error_message = str(e)
            email_message.error_code = "sending_error"
            email_message.save()
            logger.error(f"Failed to send email {message_id} via SMTP: {e}")
            raise SendingError(f"Failed to send email via SMTP: {e}") from e

        except Exception as e:
            # Catch any other unexpected errors
            email_message.status = "failed"
            email_message.failed_at = timezone.now()
            email_message.error_message = str(e)
            email_message.error_code = "unexpected_error"
            email_message.save()
            logger.error(
                f"An unexpected error occurred while sending email {message_id}: {e}",
            )
            raise SendingError(
                f"An unexpected error occurred while sending email: {e}",
            ) from e

    def _create_mime_message(
        self,
        to_emails: list[str],
        subject: str,
        plain_body: str | None = None,
        html_body: str | None = None,
        cc_emails: list[str] | None = None,
        bcc_emails: list[str] | None = None,
        reply_to: str | None = None,
        message_id: str | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
        priority: str = "normal",
    ) -> MIMEMultipart:
        """Create MIME message with headers."""
        # Determine message type
        if html_body and plain_body:
            msg = MIMEMultipart("alternative")
        else:
            msg = MIMEMultipart()

        # Set basic headers
        msg["From"] = formataddr(
            (self.account.display_name, self.account.email_address),
        )
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        msg["Message-ID"] = message_id

        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)

        if reply_to:
            msg["Reply-To"] = reply_to

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to

        if references:
            msg["References"] = references

        # Set priority headers
        if priority == "high":
            msg["X-Priority"] = "1"
            msg["Importance"] = "High"
        elif priority == "urgent":
            msg["X-Priority"] = "1"
            msg["Importance"] = "High"
            msg["X-MSMail-Priority"] = "High"
        elif priority == "low":
            msg["X-Priority"] = "5"
            msg["Importance"] = "Low"

        # Add message bodies
        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))

        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        return msg

    def _add_attachments(
        self, msg: MIMEMultipart, email_message: EmailMessage, attachments: list[dict],
    ):
        """Add attachments to email message."""
        for attachment in attachments:
            try:
                # Create attachment part
                part = MIMEBase("application", "octet-stream")

                if "content" in attachment:
                    # Binary content provided
                    part.set_payload(attachment["content"])
                elif "file_path" in attachment:
                    # File path provided
                    with open(attachment["file_path"], "rb") as f:
                        part.set_payload(f.read())
                else:
                    logger.warning(f"Attachment missing content: {attachment}")
                    continue

                encoders.encode_base64(part)

                # Set headers
                filename = attachment.get("filename", "attachment")
                content_type = attachment.get(
                    "content_type", "application/octet-stream",
                )

                part.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"',
                )
                part.add_header("Content-Type", content_type)

                msg.attach(part)

                # Create attachment record
                if "content" in attachment:
                    file_content = ContentFile(attachment["content"], name=filename)
                    attachment_obj = EmailAttachment.objects.create(
                        message=email_message,
                        filename=filename,
                        content_type=content_type,
                        size=len(attachment["content"]),
                        is_inline=attachment.get("is_inline", False),
                    )
                    attachment_obj.file_path.save(filename, file_content)

            except Exception as e:
                logger.error(f"Error adding attachment {attachment}: {e}")

    def _add_signature_and_footer(
        self, msg: MIMEMultipart, email_message: EmailMessage,
    ):
        """Add signature and footer to email message."""
        try:
            signature = self.account.signature
            footer = self.account.footer

            if not signature and not footer:
                return

            # Get existing parts
            parts = msg.get_payload()

            for i, part in enumerate(parts):
                if part.get_content_type() == "text/plain":
                    content = part.get_payload(decode=True).decode("utf-8")
                    if signature:
                        content += f"\n\n--\n{signature}"
                    if footer:
                        content += f"\n\n{footer}"

                    new_part = MIMEText(content, "plain", "utf-8")
                    parts[i] = new_part

                elif part.get_content_type() == "text/html":
                    content = part.get_payload(decode=True).decode("utf-8")

                    # Add signature and footer to HTML
                    if signature:
                        signature_html = (
                            f'<div class="signature"><br><br>--<br>{signature}</div>'
                        )
                        if "</body>" in content:
                            content = content.replace(
                                "</body>", f"{signature_html}</body>",
                            )
                        else:
                            content += signature_html

                    if footer:
                        footer_html = f'<div class="footer"><br><br>{footer}</div>'
                        if "</body>" in content:
                            content = content.replace(
                                "</body>", f"{footer_html}</body>",
                            )
                        else:
                            content += footer_html

                    new_part = MIMEText(content, "html", "utf-8")
                    parts[i] = new_part

            msg.set_payload(parts)

        except Exception as e:
            logger.error(f"Error adding signature/footer: {e}")

    def _render_template(self, template_content: str, context: dict) -> str:
        """Render template with context variables."""
        try:
            template = Template(template_content)
            return template.render(Context(context))
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return template_content

    def send_reply(
        self,
        original_message: EmailMessage,
        reply_body: str,
        reply_html: str | None = None,
        attachments: list[dict] | None = None,
    ) -> EmailMessage:
        """Send a reply to an existing email message."""
        # Build reply subject
        subject = original_message.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Build references
        references = original_message.references
        if references:
            references += f" {original_message.message_id}"
        else:
            references = original_message.message_id

        return self.send_email(
            to_emails=[original_message.from_email],
            subject=subject,
            plain_body=reply_body,
            html_body=reply_html,
            in_reply_to=original_message.message_id,
            references=references,
            attachments=attachments,
        )

    def send_forward(
        self,
        original_message: EmailMessage,
        to_emails: list[str],
        forward_body: str | None = None,
        forward_html: str | None = None,
        include_attachments: bool = True,
    ) -> EmailMessage:
        """Forward an existing email message."""
        # Build forward subject
        subject = original_message.subject
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"

        # Build forward body
        original_body = original_message.plain_body or original_message.html_body
        forward_text = "\n\n---------- Forwarded message ----------\n"
        forward_text += (
            f"From: {original_message.from_name} <{original_message.from_email}>\n"
        )
        forward_text += f"Date: {original_message.received_at}\n"
        forward_text += f"Subject: {original_message.subject}\n"
        forward_text += f"To: {', '.join(original_message.to_emails)}\n\n"
        forward_text += original_body

        final_body = forward_body + forward_text if forward_body else forward_text

        # Include attachments if requested
        attachments = []
        if include_attachments:
            for attachment in original_message.attachments.all():
                if attachment.file_path:
                    with open(attachment.file_path.path, "rb") as f:
                        attachments.append(
                            {
                                "content": f.read(),
                                "filename": attachment.filename,
                                "content_type": attachment.content_type,
                            },
                        )

        return self.send_email(
            to_emails=to_emails,
            subject=subject,
            plain_body=final_body,
            html_body=forward_html,
            attachments=attachments,
        )

    def test_connection(self) -> tuple[bool, str]:
        """Test SMTP connection and authentication."""
        try:
            with self._create_smtp_connection() as smtp:
                # Try to get server capabilities
                smtp.noop()
            return True, "SMTP connection successful"
        except SMTPError as e:
            return False, e.message
        except Exception as e:
            return False, f"Connection test failed: {e!s}"


class EmailTemplateService:
    """Service for managing email templates."""

    @staticmethod
    def render_template(template: EmailTemplate, context: dict) -> tuple[str, str, str]:
        """Render email template with context.

        Returns
        -------
            Tuple of (subject, plain_body, html_body)

        """
        try:
            # Render subject
            subject_template = Template(template.subject)
            subject = subject_template.render(Context(context))

            # Render plain content
            plain_body = ""
            if template.plain_content:
                plain_template = Template(template.plain_content)
                plain_body = plain_template.render(Context(context))

            # Render HTML content
            html_body = ""
            if template.html_content:
                html_template = Template(template.html_content)
                html_body = html_template.render(Context(context))

            return subject, plain_body, html_body

        except Exception as e:
            logger.error(f"Error rendering template {template.id}: {e}")
            return template.subject, template.plain_content, template.html_content

    @staticmethod
    def create_auto_reply_template(
        account: EmailAccount, subject: str, content: str,
    ) -> EmailTemplate:
        """Create an auto-reply template for an account."""
        return EmailTemplate.objects.create(
            account=account,
            name=f"Auto Reply - {account.name}",
            template_type="auto_reply",
            subject=subject,
            plain_content=content,
            html_content=f"<p>{content}</p>",
            is_active=True,
        )

    @staticmethod
    def get_templates_for_account(
        account: EmailAccount, template_type: str | None = None,
    ) -> list[EmailTemplate]:
        """Get available templates for an account."""
        queryset = EmailTemplate.objects.filter(
            models.Q(account=account) | models.Q(is_global=True), is_active=True,
        )

        if template_type:
            queryset = queryset.filter(template_type=template_type)

        return queryset.order_by("name")


def send_email_async(
    account_id: int,
    to_emails: list[str],
    subject: str,
    plain_body: str | None = None,
    html_body: str | None = None,
    **kwargs,
):
    """Utility function to send email asynchronously via Celery."""
    from ..tasks import send_email_task

    send_email_task.delay(
        account_id=account_id,
        to_emails=to_emails,
        subject=subject,
        plain_body=plain_body,
        html_body=html_body,
        **kwargs,
    )
