"""Test factories for email_integration models using factory_boy.
This module provides reusable factories for creating test data.
"""

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from email_integration.enums import AccountStatus, RuleAction, RuleType
from email_integration.models import EmailAccount, EmailMessage, Rule


class EmailAccountFactory(DjangoModelFactory):
    """Factory for EmailAccount model."""

    class Meta:
        model = EmailAccount

    email_address = factory.Sequence(lambda n: f"test{n}@example.com")
    username = factory.LazyAttribute(lambda o: o.email_address.split("@")[0])
    status = AccountStatus.ACTIVE
    auto_polling_enabled = True
    poll_frequency = 300  # 5 minutes
    last_poll_at = factory.LazyFunction(
        lambda: timezone.now() - timezone.timedelta(minutes=10),
    )
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)

    # Use dynamic server settings based on email domain
    @factory.lazy_attribute
    def server_settings(self):
        domain = self.email_address.split("@")[1]
        return {
            "imap_server": f"imap.{domain}",
            "imap_port": 993,
            "smtp_server": f"smtp.{domain}",
            "smtp_port": 587,
            "use_ssl": True,
        }


class EmailMessageFactory(DjangoModelFactory):
    """Factory for EmailMessage model."""

    class Meta:
        model = EmailMessage

    account = factory.SubFactory(EmailAccountFactory)
    message_id = factory.Sequence(lambda n: f"message-id-{n}")
    conversation_id = factory.Sequence(lambda n: f"conv-{n}")
    subject = factory.Sequence(lambda n: f"Test Subject {n}")
    sender = factory.Sequence(lambda n: f"sender{n}@example.com")
    recipient = factory.LazyAttribute(lambda o: o.account.email_address)
    cc = factory.LazyAttribute(lambda o: f"cc@{o.account.email_address.split('@')[1]}")
    body = factory.Faker("paragraph")
    received_at = factory.LazyFunction(timezone.now)

    # Generate random attachments data
    @factory.lazy_attribute
    def attachments(self):
        return (
            []
            if factory.random.randint(0, 1) == 0
            else [
                {
                    "filename": f"attachment-{factory.random.randint(1, 100)}.pdf",
                    "content_type": "application/pdf",
                    "size": factory.random.randint(1000, 100000),
                },
            ]
        )


class RuleFactory(DjangoModelFactory):
    """Factory for Rule model."""

    class Meta:
        model = Rule

    account = factory.SubFactory(EmailAccountFactory)
    name = factory.Sequence(lambda n: f"Rule {n}")
    description = factory.Faker("sentence")
    is_active = True

    # Rules can be different types with different conditions
    rule_type = factory.Iterator([RuleType.SENDER, RuleType.SUBJECT, RuleType.CONTENT])

    @factory.lazy_attribute
    def conditions(self):
        if self.rule_type == RuleType.SENDER:
            return {"sender_contains": factory.Faker("domain_name").generate({})}
        elif self.rule_type == RuleType.SUBJECT:
            return {"subject_contains": factory.Faker("word").generate({})}
        else:  # CONTENT
            return {"body_contains": factory.Faker("word").generate({})}

    action = factory.Iterator([action.value for action in RuleAction])
    priority = factory.Sequence(lambda n: n)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
