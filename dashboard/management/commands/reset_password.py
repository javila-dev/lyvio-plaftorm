from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Reset password for a user'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email del usuario')
        parser.add_argument('password', type=str, help='Nueva contraseña')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        
        try:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Contraseña cambiada para {email}')
            )
            self.stdout.write(f'Nueva contraseña: {password}')
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Usuario {email} no encontrado')
            )