"""
Management command para actualizar los planes con summary_features de ejemplo
"""
from django.core.management.base import BaseCommand
from subscriptions.models import Plan


class Command(BaseCommand):
    help = 'Actualiza los planes con summary_features de ejemplo'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Actualizando planes con summary_features...'))
        
        # Definir summary_features según el tipo de plan
        plan_summaries = {
            'starter': [
                'Widget de chat web',
                'Respuestas automáticas',
                'Reportes básicos',
            ],
            'professional': [
                'Múltiples canales (WhatsApp, Facebook, Instagram)',
                'Bots inteligentes con IA',
                'Centro de ayuda',
                'Integraciones avanzadas',
            ],
            'enterprise': [
                'Todos los canales disponibles',
                'Automatizaciones ilimitadas',
                'Campañas masivas',
                'Soporte prioritario',
            ],
        }
        
        # Actualizar cada plan
        updated_count = 0
        for plan in Plan.objects.all():
            # Si el plan ya tiene summary_features, no sobrescribir
            if plan.summary_features:
                self.stdout.write(
                    self.style.WARNING(f'  Plan "{plan.name}" ya tiene summary_features, omitiendo...')
                )
                continue
            
            # Buscar summary según plan_type
            summary = plan_summaries.get(plan.plan_type, [
                'Características personalizadas',
                'Soporte incluido',
            ])
            
            plan.summary_features = summary
            plan.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Plan "{plan.name}" actualizado con {len(summary)} features destacadas')
            )
            updated_count += 1
        
        if updated_count == 0:
            self.stdout.write(
                self.style.WARNING('\nNo se actualizaron planes (todos ya tenían summary_features)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ {updated_count} plan(es) actualizado(s) exitosamente')
            )
