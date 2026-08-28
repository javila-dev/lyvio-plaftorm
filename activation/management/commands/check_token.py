from django.core.management.base import BaseCommand
from accounts.models import User, ActivationToken


class Command(BaseCommand):
    help = 'Check activation token and user status'

    def add_arguments(self, parser):
        parser.add_argument('token', type=str, help='Activation token to check')

    def handle(self, *args, **options):
        token_str = options['token']
        
        try:
            token = ActivationToken.objects.get(token=token_str)
            self.stdout.write(f"📧 Token email: {token.email}")
            self.stdout.write(f"📋 Token status: {token.status}")
            self.stdout.write(f"✅ Token válido: {token.is_valid}")
            self.stdout.write(f"📅 Token creado: {token.created_at}")
            
            # Verificar si existe usuario
            user = User.objects.filter(email=token.email).first()
            if user:
                self.stdout.write(self.style.WARNING(f"👤 Usuario EXISTE: {user.email}"))
                self.stdout.write(f"🔓 Usuario activo: {user.is_active}")
                self.stdout.write(f"📊 Usuario staff: {user.is_staff}")
                self.stdout.write(f"📅 Usuario creado: {user.date_joined}")
                
                # Mostrar opción para eliminar usuario
                self.stdout.write(self.style.ERROR("\n❗ PROBLEMA: Usuario ya existe pero token sigue válido"))
                self.stdout.write("💡 Solución: Ejecuta 'python manage.py fix_activation_token {}'".format(token_str))
            else:
                self.stdout.write(self.style.SUCCESS("✅ No hay usuario con este email - token OK"))
                
        except ActivationToken.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Token no encontrado: {token_str}"))