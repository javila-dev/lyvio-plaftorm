from django.core.management.base import BaseCommand
from activation.views import send_activation_email


class Command(BaseCommand):
    help = 'Test activation email sending'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send activation email to')
        parser.add_argument('--company', type=str, default='Test Company', help='Company name for the email')

    def handle(self, *args, **options):
        email = options['email']
        company_name = options['company']
        
        self.stdout.write(f"📧 Sending activation email to {email} for company: {company_name}")
        
        try:
            result = send_activation_email(email, company_name)
            
            if result:
                self.stdout.write(self.style.SUCCESS(f"✅ Activation email sent successfully to {email}"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Activation email failed to send to {email}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error sending activation email: {e}"))