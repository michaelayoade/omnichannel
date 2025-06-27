from django.db import models


class AccountType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual Account"
    SHARED = "shared", "Shared Mailbox"
    DEPARTMENT = "department", "Department Account"


class Protocol(models.TextChoices):
    IMAP = "imap", "IMAP"
    POP3 = "pop3", "POP3"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ERROR = "error", "Error"
    MAINTENANCE = "maintenance", "Maintenance"


class BounceType(models.TextChoices):
    HARD = "hard", "Hard Bounce"
    SOFT = "soft", "Soft Bounce"
    COMPLAINT = "complaint", "Complaint"
    DELIVERY_DELAY = "delivery_delay", "Delivery Delay"


class PollStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    ERROR = "error", "Error"
    PARTIAL = "partial", "Partial"
    NO_MESSAGES = "no_messages", "No Messages"


class MessageStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"
    RECEIVED = "received", "Received"
    READ = "read", "Read"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class MessagePriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class RuleType(models.TextChoices):
    AUTO_REPLY = "auto_reply", "Auto Reply"
    FORWARD = "forward", "Forward"
    FILTER = "filter", "Filter"
    ASSIGNMENT = "assignment", "Assignment"
    SET_PRIORITY = "priority", "Priority"


class ConditionType(models.TextChoices):
    FROM_CONTAINS = "from_contains", "From Contains"
    SUBJECT_CONTAINS = "subject_contains", "Subject Contains"
    BODY_CONTAINS = "body_contains", "Body Contains"
    FROM_EQUALS = "from_equals", "From Equals"
    SUBJECT_EQUALS = "subject_equals", "Subject Equals"
    HAS_ATTACHMENT = "has_attachment", "Has Attachment"
    DOMAIN_EQUALS = "domain_equals", "Domain Equals"


class TemplateType(models.TextChoices):
    REPLY = "reply", "Reply Template"
    AUTO_REPLY = "auto_reply", "Auto Reply"
    NOTIFICATION = "notification", "Notification"
    MARKETING = "marketing", "Marketing"
    SYSTEM = "system", "System"


class ThreadStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"
    ARCHIVED = "archived", "Archived"


class Channel(models.TextChoices):
    SMTP = "smtp", "SMTP"
    IMAP = "imap", "IMAP"
