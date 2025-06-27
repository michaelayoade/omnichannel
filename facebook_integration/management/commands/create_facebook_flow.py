from django.core.management.base import BaseCommand, CommandError

from facebook_integration.models import FacebookConversationFlow, FacebookPage


class Command(BaseCommand):
    help = "Create predefined Facebook Messenger conversation flows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id", type=str, required=True, help="Facebook Page ID"
        )

        parser.add_argument(
            "--flow-type",
            type=str,
            choices=["welcome", "lead_generation", "customer_service", "faq", "all"],
            default="welcome",
            help="Type of flow to create",
        )

        parser.add_argument(
            "--force", action="store_true", help="Overwrite existing flows"
        )

    def handle(self, *args, **options):
        try:
            # Get the Facebook page
            try:
                page = FacebookPage.objects.get(page_id=options["page_id"])
            except FacebookPage.DoesNotExist:
                raise CommandError(f'Page {options["page_id"]} not found')

            flow_type = options["flow_type"]

            if flow_type == "all":
                self._create_welcome_flow(page, options["force"])
                self._create_lead_generation_flow(page, options["force"])
                self._create_customer_service_flow(page, options["force"])
                self._create_faq_flow(page, options["force"])
            elif flow_type == "welcome":
                self._create_welcome_flow(page, options["force"])
            elif flow_type == "lead_generation":
                self._create_lead_generation_flow(page, options["force"])
            elif flow_type == "customer_service":
                self._create_customer_service_flow(page, options["force"])
            elif flow_type == "faq":
                self._create_faq_flow(page, options["force"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {flow_type} flow(s) for {page.page_name}"
                )
            )

        except Exception as e:
            raise CommandError(f"Flow creation failed: {str(e)}")

    def _create_welcome_flow(self, page, force=False):
        """Create a welcome flow."""

        flow_name = f"Welcome Flow - {page.page_name}"

        if (
            not force
            and FacebookConversationFlow.objects.filter(
                page=page, name=flow_name
            ).exists()
        ):
            self.stdout.write(f"Welcome flow already exists for {page.page_name}")
            return

        flow_steps = {
            "start": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": f"Hello {{first_name}}! 👋 Welcome to {page.page_name}!",
                    },
                    {"type": "delay", "seconds": 1},
                    {
                        "type": "send_quick_replies",
                        "text": "How can we help you today?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Learn More",
                                "payload": "LEARN_MORE",
                            },
                            {
                                "content_type": "text",
                                "title": "Get Support",
                                "payload": "GET_SUPPORT",
                            },
                            {
                                "content_type": "text",
                                "title": "Contact Us",
                                "payload": "CONTACT_US",
                            },
                        ],
                    },
                ],
                "next": {
                    "quick_reply_payload:LEARN_MORE": "learn_more",
                    "quick_reply_payload:GET_SUPPORT": "get_support",
                    "quick_reply_payload:CONTACT_US": "contact_us",
                },
                "default_next": "help",
            },
            "learn_more": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": f"Great! {page.page_name} offers amazing services and products. Here's what we can do for you:",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "What would you like to know more about?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Our Services",
                                "payload": "SERVICES",
                            },
                            {
                                "content_type": "text",
                                "title": "Pricing",
                                "payload": "PRICING",
                            },
                            {
                                "content_type": "text",
                                "title": "Contact Sales",
                                "payload": "CONTACT_SALES",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "get_support": {
                "actions": [
                    {"type": "send_text", "text": "I'm here to help! 🤝"},
                    {
                        "type": "send_quick_replies",
                        "text": "What kind of support do you need?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Technical Issue",
                                "payload": "TECH_SUPPORT",
                            },
                            {
                                "content_type": "text",
                                "title": "Billing Question",
                                "payload": "BILLING_SUPPORT",
                            },
                            {
                                "content_type": "text",
                                "title": "General Question",
                                "payload": "GENERAL_SUPPORT",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "contact_us": {
                "actions": [
                    {"type": "send_text", "text": "We'd love to hear from you! 📞"},
                    {
                        "type": "send_text",
                        "text": "You can reach us at:\\n\\n📧 Email: contact@company.com\\n📞 Phone: +1 (555) 123-4567\\n🕒 Hours: Mon-Fri 9AM-6PM",
                    },
                ],
                "next": "end",
            },
            "help": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I can help you with information about our services, support, or connecting you with our team.",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "What would you like to do?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Start Over",
                                "payload": "GET_STARTED",
                            },
                            {
                                "content_type": "text",
                                "title": "Talk to Human",
                                "payload": "HUMAN_AGENT",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "end": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Thanks for chatting with us! Feel free to message us anytime if you need help. 😊",
                    }
                ]
            },
        }

        FacebookConversationFlow.objects.update_or_create(
            page=page,
            name=flow_name,
            defaults={
                "flow_type": "welcome",
                "description": "Welcome new users and provide initial options",
                "trigger_type": "get_started",
                "trigger_value": "GET_STARTED",
                "flow_steps": flow_steps,
                "is_active": True,
                "priority": 10,
            },
        )

        self.stdout.write(f"✓ Created welcome flow for {page.page_name}")

    def _create_lead_generation_flow(self, page, force=False):
        """Create a lead generation flow."""

        flow_name = f"Lead Generation - {page.page_name}"

        if (
            not force
            and FacebookConversationFlow.objects.filter(
                page=page, name=flow_name
            ).exists()
        ):
            self.stdout.write(
                f"Lead generation flow already exists for {page.page_name}"
            )
            return

        flow_steps = {
            "start": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Great! I'd love to learn more about your needs so we can help you better. 📋",
                    },
                    {"type": "send_text", "text": "What's your name?"},
                ],
                "next": "collect_name",
            },
            "collect_name": {
                "actions": [
                    {
                        "type": "set_variable",
                        "name": "lead_name",
                        "value": "{{message_text}}",
                    },
                    {
                        "type": "send_text",
                        "text": "Nice to meet you, {{lead_name}}! 👋",
                    },
                    {"type": "send_text", "text": "What's your email address?"},
                ],
                "next": "collect_email",
            },
            "collect_email": {
                "actions": [
                    {
                        "type": "set_variable",
                        "name": "lead_email",
                        "value": "{{message_text}}",
                    },
                    {
                        "type": "send_text",
                        "text": "Perfect! What type of business are you in?",
                    },
                ],
                "next": "collect_business",
            },
            "collect_business": {
                "actions": [
                    {
                        "type": "set_variable",
                        "name": "lead_business",
                        "value": "{{message_text}}",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "What's your main interest in our services?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Product Demo",
                                "payload": "DEMO",
                            },
                            {
                                "content_type": "text",
                                "title": "Pricing Info",
                                "payload": "PRICING",
                            },
                            {
                                "content_type": "text",
                                "title": "Custom Solution",
                                "payload": "CUSTOM",
                            },
                        ],
                    },
                ],
                "next": "collect_interest",
            },
            "collect_interest": {
                "actions": [
                    {
                        "type": "set_variable",
                        "name": "lead_interest",
                        "value": "{{quick_reply_payload}}",
                    },
                    {
                        "type": "send_text",
                        "text": "Excellent! Thanks for providing that information, {{lead_name}}. 🎉",
                    },
                    {
                        "type": "send_text",
                        "text": "Our sales team will reach out to you at {{lead_email}} within 24 hours to discuss your {{lead_interest}} needs.",
                    },
                    {
                        "type": "send_text",
                        "text": "In the meantime, feel free to ask me any questions!",
                    },
                ],
                "next": "end",
            },
            "end": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Thanks again for your interest! We're excited to work with you. 🚀",
                    }
                ]
            },
        }

        FacebookConversationFlow.objects.update_or_create(
            page=page,
            name=flow_name,
            defaults={
                "flow_type": "lead_generation",
                "description": "Collect lead information from interested prospects",
                "trigger_type": "keyword",
                "trigger_value": "lead,interested,demo,sales,pricing",
                "flow_steps": flow_steps,
                "is_active": True,
                "priority": 8,
            },
        )

        self.stdout.write(f"✓ Created lead generation flow for {page.page_name}")

    def _create_customer_service_flow(self, page, force=False):
        """Create a customer service flow."""

        flow_name = f"Customer Service - {page.page_name}"

        if (
            not force
            and FacebookConversationFlow.objects.filter(
                page=page, name=flow_name
            ).exists()
        ):
            self.stdout.write(
                f"Customer service flow already exists for {page.page_name}"
            )
            return

        flow_steps = {
            "start": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I'm here to help with your support needs! 🛟",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "What type of issue are you experiencing?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Technical Issue",
                                "payload": "TECH_ISSUE",
                            },
                            {
                                "content_type": "text",
                                "title": "Billing Question",
                                "payload": "BILLING_ISSUE",
                            },
                            {
                                "content_type": "text",
                                "title": "Account Problem",
                                "payload": "ACCOUNT_ISSUE",
                            },
                            {
                                "content_type": "text",
                                "title": "Other",
                                "payload": "OTHER_ISSUE",
                            },
                        ],
                    },
                ],
                "next": {
                    "quick_reply_payload:TECH_ISSUE": "tech_support",
                    "quick_reply_payload:BILLING_ISSUE": "billing_support",
                    "quick_reply_payload:ACCOUNT_ISSUE": "account_support",
                    "quick_reply_payload:OTHER_ISSUE": "general_support",
                },
            },
            "tech_support": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I understand you're having a technical issue. Let me help you troubleshoot! 🔧",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "Can you describe what's happening?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "App won't start",
                                "payload": "APP_WONT_START",
                            },
                            {
                                "content_type": "text",
                                "title": "Can't log in",
                                "payload": "CANT_LOGIN",
                            },
                            {
                                "content_type": "text",
                                "title": "Feature not working",
                                "payload": "FEATURE_BROKEN",
                            },
                            {
                                "content_type": "text",
                                "title": "Other technical issue",
                                "payload": "OTHER_TECH",
                            },
                        ],
                    },
                ],
                "next": "escalate_to_tech",
            },
            "billing_support": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I can help with billing questions! 💳",
                    },
                    {
                        "type": "send_text",
                        "text": "For account security, I'll need to connect you with our billing team who can verify your account and assist you.",
                    },
                ],
                "next": "escalate_to_billing",
            },
            "account_support": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I can help with account-related issues! 👤",
                    },
                    {
                        "type": "send_text",
                        "text": "Let me connect you with our account specialists who can securely access your account and help resolve the issue.",
                    },
                ],
                "next": "escalate_to_account",
            },
            "general_support": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "No problem! I'm here to help with any questions you have. 💬",
                    },
                    {
                        "type": "send_text",
                        "text": "Please describe your question or issue, and I'll either help you directly or connect you with the right team member.",
                    },
                ],
                "next": "escalate_to_general",
            },
            "escalate_to_tech": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "I'm connecting you with our technical support team who can help resolve this issue. 🔧",
                    },
                    {
                        "type": "send_text",
                        "text": "A support agent will be with you shortly. In the meantime, please provide any additional details about the issue.",
                    },
                ],
                "next": "end",
            },
            "escalate_to_billing": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Connecting you with our billing team now... 💳",
                    }
                ],
                "next": "end",
            },
            "escalate_to_account": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Transferring you to our account specialists... 👤",
                    }
                ],
                "next": "end",
            },
            "escalate_to_general": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Let me connect you with a support agent who can help... 💬",
                    }
                ],
                "next": "end",
            },
            "end": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Thank you for contacting support. We're here to help! 🤝",
                    }
                ]
            },
        }

        FacebookConversationFlow.objects.update_or_create(
            page=page,
            name=flow_name,
            defaults={
                "flow_type": "customer_service",
                "description": "Handle customer support requests and route to appropriate teams",
                "trigger_type": "keyword",
                "trigger_value": "help,support,issue,problem,bug,billing,account",
                "flow_steps": flow_steps,
                "is_active": True,
                "priority": 9,
            },
        )

        self.stdout.write(f"✓ Created customer service flow for {page.page_name}")

    def _create_faq_flow(self, page, force=False):
        """Create an FAQ flow."""

        flow_name = f"FAQ - {page.page_name}"

        if (
            not force
            and FacebookConversationFlow.objects.filter(
                page=page, name=flow_name
            ).exists()
        ):
            self.stdout.write(f"FAQ flow already exists for {page.page_name}")
            return

        flow_steps = {
            "start": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Here are some frequently asked questions! 📚",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "What would you like to know?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Pricing",
                                "payload": "FAQ_PRICING",
                            },
                            {
                                "content_type": "text",
                                "title": "Features",
                                "payload": "FAQ_FEATURES",
                            },
                            {
                                "content_type": "text",
                                "title": "Support",
                                "payload": "FAQ_SUPPORT",
                            },
                            {
                                "content_type": "text",
                                "title": "Getting Started",
                                "payload": "FAQ_GETTING_STARTED",
                            },
                        ],
                    },
                ],
                "next": {
                    "quick_reply_payload:FAQ_PRICING": "faq_pricing",
                    "quick_reply_payload:FAQ_FEATURES": "faq_features",
                    "quick_reply_payload:FAQ_SUPPORT": "faq_support",
                    "quick_reply_payload:FAQ_GETTING_STARTED": "faq_getting_started",
                },
            },
            "faq_pricing": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "💰 Pricing Information:\\n\\n• Basic Plan: $19/month\\n• Pro Plan: $49/month\\n• Enterprise: Custom pricing\\n\\nAll plans include a 14-day free trial!",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "Would you like to know more?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Start Free Trial",
                                "payload": "START_TRIAL",
                            },
                            {
                                "content_type": "text",
                                "title": "Compare Plans",
                                "payload": "COMPARE_PLANS",
                            },
                            {
                                "content_type": "text",
                                "title": "More Questions",
                                "payload": "MORE_FAQ",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "faq_features": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "✨ Key Features:\\n\\n• Advanced Analytics\\n• Team Collaboration\\n• API Integration\\n• 24/7 Support\\n• Mobile Apps\\n• Custom Branding",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "Interested in learning more?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Request Demo",
                                "payload": "REQUEST_DEMO",
                            },
                            {
                                "content_type": "text",
                                "title": "See All Features",
                                "payload": "ALL_FEATURES",
                            },
                            {
                                "content_type": "text",
                                "title": "More Questions",
                                "payload": "MORE_FAQ",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "faq_support": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "🛟 Support Options:\\n\\n• 24/7 Live Chat\\n• Email Support\\n• Phone Support (Pro+)\\n• Knowledge Base\\n• Video Tutorials\\n• Community Forum",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "How can we help you today?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Contact Support",
                                "payload": "CONTACT_SUPPORT",
                            },
                            {
                                "content_type": "text",
                                "title": "Knowledge Base",
                                "payload": "KNOWLEDGE_BASE",
                            },
                            {
                                "content_type": "text",
                                "title": "More Questions",
                                "payload": "MORE_FAQ",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "faq_getting_started": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "🚀 Getting Started is Easy:\\n\\n1. Sign up for free trial\\n2. Complete quick setup wizard\\n3. Import your data\\n4. Invite team members\\n5. Start using the platform!",
                    },
                    {
                        "type": "send_quick_replies",
                        "text": "Ready to get started?",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Sign Up Now",
                                "payload": "SIGN_UP",
                            },
                            {
                                "content_type": "text",
                                "title": "Watch Tutorial",
                                "payload": "TUTORIAL",
                            },
                            {
                                "content_type": "text",
                                "title": "More Questions",
                                "payload": "MORE_FAQ",
                            },
                        ],
                    },
                ],
                "next": "end",
            },
            "end": {
                "actions": [
                    {
                        "type": "send_text",
                        "text": "Hope that answered your question! Feel free to ask if you need anything else. 😊",
                    }
                ]
            },
        }

        FacebookConversationFlow.objects.update_or_create(
            page=page,
            name=flow_name,
            defaults={
                "flow_type": "faq",
                "description": "Answer frequently asked questions",
                "trigger_type": "keyword",
                "trigger_value": "faq,questions,pricing,features,help",
                "flow_steps": flow_steps,
                "is_active": True,
                "priority": 7,
            },
        )

        self.stdout.write(f"✓ Created FAQ flow for {page.page_name}")
