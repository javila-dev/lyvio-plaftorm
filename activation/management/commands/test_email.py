from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import smtplib


class Command(BaseCommand):
    help = 'Test email configuration'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send test email to')

    def handle(self, *args, **options):
        email = options['email']
        
        # Test 1: Basic SMTP connection
        self.stdout.write("🔧 Testing SMTP connection...")
        try:
            server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT)
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.quit()
            self.stdout.write(self.style.SUCCESS("✅ SMTP connection successful"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ SMTP connection failed: {e}"))
            return
        
        # Test 2: Django send_mail
        self.stdout.write("📧 Testing Django send_mail...")
        try:
            result = send_mail(
                subject='Test Email from Lyvio',
                message='This is a test email from Lyvio platform.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message='<h1>Test Email</h1><p>This is a test email from Lyvio platform.</p>',
                fail_silently=False,
            )
            if result:
                self.stdout.write(self.style.SUCCESS(f"✅ Email sent successfully to {email}"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️  Email function returned {result}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Email sending failed: {e}"))
        
        # Show current settings
        self.stdout.write("\n📋 Current email settings:")
        self.stdout.write(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}")
        self.stdout.write(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")