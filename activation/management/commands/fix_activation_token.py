from django.core.management.base import BaseCommand
from accounts.models import User, ActivationToken


class Command(BaseCommand):
    help = 'Fix activation token when user already exists'

    def add_arguments(self, parser):
        parser.add_argument('token', type=str, help='Activation token to fix')
        parser.add_argument('--delete-user', action='store_true', help='Delete existing user to allow reactivation')

    def handle(self, *args, **options):
        token_str = options['token']
        delete_user = options['delete_user']
        
        try:
            token = ActivationToken.objects.get(token=token_str)
            user = User.objects.filter(email=token.email).first()
            
            if not user:
                self.stdout.write(self.style.ERROR(f"❌ No hay usuario con email {token.email}"))
                return
                
            self.stdout.write(f"📧 Email: {token.email}")
            self.stdout.write(f"👤 Usuario creado: {user.date_joined}")
            self.stdout.write(f"📋 Token status: {token.status}")
            
            if delete_user:
                # Opción 1: Eliminar usuario para permitir reactivación
                user.delete()
                self.stdout.write(self.style.SUCCESS(f"🗑️  Usuario {token.email} eliminado"))
                self.stdout.write("✅ Ahora puedes usar el enlace de activación nuevamente")
            else:
                # Opción 2: Marcar token como usado ya que el usuario existe
                token.status = 'used'
                token.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Token marcado como 'used'"))
                self.stdout.write(f"👤 Usuario {token.email} ya existe y está activo")
                self.stdout.write("💡 Puedes iniciar sesión directamente en /bot-builder/")
                
        except ActivationToken.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Token no encontrado: {token_str}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))