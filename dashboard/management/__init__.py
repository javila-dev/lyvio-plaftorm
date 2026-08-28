from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Make user admin/staff'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email del usuario')

    def handle(self, *args, **options):
        email = options['email']
        
        try:
            user = User.objects.get(email=email)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Usuario {email} es ahora administrador')
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Usuario {email} no encontrado')
            )