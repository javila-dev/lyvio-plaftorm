"""
Management command para actualizar features y limits de cuentas Chatwoot existentes según su plan

Uso:
    python manage.py sync_chatwoot_features
"""

import asyncio
from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Company, Trial
from subscriptions.models import Subscription
from bots.services import ChatwootService


class Command(BaseCommand):
    help = 'Sincroniza features y limits de Chatwoot con los planes activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de una empresa específica para actualizar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar los cambios'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Sincronizando Features y Limits con Chatwoot ===\n'))

        company_id = options.get('company_id')
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY-RUN: No se aplicarán cambios\n'))

        # Filtrar empresas
        companies_query = Company.objects.filter(chatwoot_account_id__isnull=False)
        
        if company_id:
            companies_query = companies_query.filter(id=company_id)
            if not companies_query.exists():
                self.stdout.write(self.style.ERROR(f'❌ No se encontró empresa con ID {company_id}'))
                return

        companies = companies_query.select_related('subscription__plan', 'trial')
        
        if not companies.exists():
            self.stdout.write(self.style.WARNING('⚠️ No hay empresas con chatwoot_account_id configurado'))
            return

        self.stdout.write(f'📊 Empresas a procesar: {companies.count()}\n')

        service = ChatwootService()
        updated = 0
        errors = 0

        for company in companies:
            try:
                # Determinar si está en trial o tiene suscripción activa
                features = None
                limits = None
                plan_name = None

                # Prioridad 1: Suscripción activa
                if hasattr(company, 'subscription') and company.subscription.status == 'active':
                    plan = company.subscription.plan
                    features = plan.chatwoot_features
                    limits = plan.chatwoot_limits
                    plan_name = plan.name
                
                # Prioridad 2: Trial activo - usar plan Starter como referencia
                elif hasattr(company, 'trial') and company.trial.is_active:
                    from subscriptions.models import Plan
                    starter_plan = Plan.objects.filter(slug='starter').first()
                    if starter_plan:
                        features = starter_plan.chatwoot_features
                        # Para trial, usar limits más restrictivos
                        limits = {
                            "agents": 1,
                            "inboxes": 1
                        }
                        plan_name = "Trial (Starter)"
                
                if not features or not limits:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ {company.name} - Sin plan activo, saltando...'
                        )
                    )
                    continue

                self.stdout.write(f'\n📦 {company.name} ({company.id})')
                self.stdout.write(f'   Plan: {plan_name}')
                self.stdout.write(f'   Chatwoot ID: {company.chatwoot_account_id}')
                self.stdout.write(f'   Features activas: {sum(1 for v in features.values() if v)}/{len(features)}')
                self.stdout.write(f'   Limits: {limits}')

                if not dry_run:
                    # Actualizar en Chatwoot
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        service.update_account_features_limits(
                            company.chatwoot_account_id,
                            features=features,
                            limits=limits
                        )
                    )
                    
                    loop.close()

                    if result:
                        self.stdout.write(self.style.SUCCESS('   ✅ Actualizado exitosamente'))
                        updated += 1
                    else:
                        self.stdout.write(self.style.ERROR('   ❌ Error en la actualización'))
                        errors += 1
                else:
                    self.stdout.write(self.style.WARNING('   🔍 [DRY-RUN] No se aplicaron cambios'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error: {str(e)}'))
                errors += 1

        # Resumen
        self.stdout.write('\n' + '='*50)
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'✅ Actualizadas: {updated}'))
            if errors > 0:
                self.stdout.write(self.style.ERROR(f'❌ Errores: {errors}'))
        else:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY-RUN completado'))
        self.stdout.write('='*50 + '\n')
