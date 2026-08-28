"""
Tests unitarios para la aplicación SSO.
"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import time

from sso.models import SSOToken

User = get_user_model()


class SSOTokenModelTest(TestCase):
    """Tests para el modelo SSOToken"""
    
    def setUp(self):
        self.email = "test@example.com"
        self.token_value = "a" * 64
        self.expires_at = timezone.now() + timedelta(minutes=5)
        
    def test_create_token(self):
        """Test crear token SSO"""
        token = SSOToken.objects.create(
            token=self.token_value,
            email=self.email,
            chatwoot_account_id="1",
            chatwoot_user_id="123",
            request_id="test-request-1",
            expires_at=self.expires_at
        )
        
        self.assertEqual(token.email, self.email)
        self.assertEqual(token.token, self.token_value)
        self.assertFalse(token.used)
        self.assertIsNone(token.used_at)
    
    def test_is_valid_method(self):
        """Test método is_valid()"""
        token = SSOToken.objects.create(
            token=self.token_value,
            email=self.email,
            chatwoot_account_id="1",
            request_id="test-request-2",
            expires_at=self.expires_at
        )
        
        # Token no usado y no expirado debe ser válido
        self.assertTrue(token.is_valid())
        
        # Token usado no es válido
        token.used = True
        token.save()
        self.assertFalse(token.is_valid())
        
        # Token expirado no es válido
        token.used = False
        token.expires_at = timezone.now() - timedelta(minutes=1)
        token.save()
        self.assertFalse(token.is_valid())
    
    def test_mark_as_used_method(self):
        """Test método mark_as_used()"""
        token = SSOToken.objects.create(
            token=self.token_value,
            email=self.email,
            chatwoot_account_id="1",
            request_id="test-request-3",
            expires_at=self.expires_at
        )
        
        self.assertFalse(token.used)
        self.assertIsNone(token.used_at)
        
        token.mark_as_used()
        
        self.assertTrue(token.used)
        self.assertIsNotNone(token.used_at)


@override_settings(SSO_SHARED_SECRET='change-me-in-production-use-strong-random-value')
class SSOGenerateTokenViewTest(TestCase):
    """Tests para el endpoint de generación de tokens"""
    
    def setUp(self):
        self.client = Client()
        self.url = '/api/sso/generate-token/'
        self.valid_payload = {
            'account_id': '1',
            'shared_secret': 'change-me-in-production-use-strong-random-value',
            'timestamp': int(time.time()),
            'request_id': f'test-request-{int(time.time())}'
        }
        # Payload con email (opcional)
        self.valid_payload_with_email = {
            'email': 'test@example.com',
            'account_id': '1',
            'chatwoot_user_id': '123',
            'shared_secret': 'change-me-in-production-use-strong-random-value',
            'timestamp': int(time.time()),
            'request_id': f'test-request-email-{int(time.time())}'
        }
    
    def test_generate_token_success(self):
        """Test generar token exitosamente sin email"""
        response = self.client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('sso_token', data)
        self.assertIn('redirect_url', data)
        self.assertIn('expires_at', data)
        
        # Verificar que el token existe en BD
        token = SSOToken.objects.get(token=data['sso_token'])
        self.assertEqual(token.email, '')  # Email vacío porque no se envió
        self.assertEqual(token.chatwoot_account_id, '1')
        self.assertFalse(token.used)
    
    def test_generate_token_with_email(self):
        """Test generar token con email opcional"""
        response = self.client.post(
            self.url,
            data=self.valid_payload_with_email,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verificar que el token tiene el email
        token = SSOToken.objects.get(token=data['sso_token'])
        self.assertEqual(token.email, 'test@example.com')
        self.assertEqual(token.chatwoot_user_id, '123')
        self.assertFalse(token.used)
    
    def test_missing_fields(self):
        """Test campos requeridos faltantes"""
        payload = {'account_id': '1'}  # Faltan shared_secret, timestamp, request_id
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_invalid_shared_secret(self):
        """Test shared secret inválido"""
        payload = self.valid_payload.copy()
        payload['shared_secret'] = 'wrong-secret'
        
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_old_timestamp(self):
        """Test timestamp muy antiguo"""
        payload = self.valid_payload.copy()
        payload['timestamp'] = int(time.time()) - 100  # 100 segundos atrás
        
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_duplicate_request_id(self):
        """Test request_id duplicado"""
        # Primera request
        response1 = self.client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 201)
        
        # Segunda request con mismo request_id
        payload = self.valid_payload.copy()
        payload['timestamp'] = int(time.time())  # Actualizar timestamp
        
        response2 = self.client.post(
            self.url,
            data=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response2.status_code, 400)
        data = response2.json()
        self.assertFalse(data['success'])


class SSOLoginViewTest(TestCase):
    """Tests para el endpoint de login SSO"""
    
    def setUp(self):
        self.client = Client()
        self.url = '/sso/login'
        self.email = 'test@example.com'
        
        # Crear usuario
        self.user = User.objects.create_user(
            email=self.email,
            username=self.email,
            is_active=True
        )
        
        # Crear token válido
        self.valid_token = SSOToken.objects.create(
            token='valid-token-12345',
            email=self.email,
            chatwoot_account_id='1',
            request_id='test-login-1',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
    
    def test_login_success(self):
        """Test login exitoso con token válido"""
        response = self.client.get(f'{self.url}?token={self.valid_token.token}')
        
        # Debe redirigir a dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.url)
        
        # Token debe estar marcado como usado
        self.valid_token.refresh_from_db()
        self.assertTrue(self.valid_token.used)
        self.assertIsNotNone(self.valid_token.used_at)
    
    def test_missing_token(self):
        """Test sin token"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=missing_token', response.url)
    
    def test_invalid_token(self):
        """Test token inválido"""
        response = self.client.get(f'{self.url}?token=invalid-token-xyz')
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=invalid_token', response.url)
    
    def test_used_token(self):
        """Test token ya usado"""
        # Marcar token como usado
        self.valid_token.mark_as_used()
        
        response = self.client.get(f'{self.url}?token={self.valid_token.token}')
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=token_already_used', response.url)
    
    def test_expired_token(self):
        """Test token expirado"""
        # Crear token expirado
        expired_token = SSOToken.objects.create(
            token='expired-token-12345',
            email=self.email,
            chatwoot_account_id='1',
            request_id='test-login-expired',
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        response = self.client.get(f'{self.url}?token={expired_token.token}')
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=token_expired', response.url)
    
    def test_login_without_email(self):
        """Test login con token sin email - busca compañía por chatwoot_account_id"""
        from accounts.models import Company
        from subscriptions.models import Plan, Subscription
        
        # Crear una compañía con chatwoot_account_id
        company = Company.objects.create(
            name='Test Company SSO',
            email='company@test.com',
            chatwoot_account_id=999
        )
        
        # Crear un plan
        plan = Plan.objects.create(
            name='Starter Plan',
            slug='starter',
            plan_type='starter',
            price_monthly=10000,
            price_yearly=100000
        )
        
        # Crear suscripción para la compañía
        subscription = Subscription.objects.create(
            company=company,
            plan=plan,
            status='active',
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Crear un usuario asociado a esa compañía
        user = User.objects.create_user(
            email='user@company.com',
            username='user@company.com',
            is_active=True
        )
        user.company = company
        user.save()
        
        # Crear token sin email
        token_no_email = SSOToken.objects.create(
            token='token-no-email-12345',
            email='',  # Sin email
            chatwoot_account_id='999',
            request_id='test-login-no-email',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        response = self.client.get(f'{self.url}?token={token_no_email.token}')
        
        # Debe redirigir a dashboard (login exitoso)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.url)
        # NO debe tener sso_account_id porque se hace login real
        self.assertNotIn('sso_account_id', response.url)
        
        # Token debe estar marcado como usado
        token_no_email.refresh_from_db()
        self.assertTrue(token_no_email.used)
        self.assertIsNotNone(token_no_email.used_at)
        
        # Verificar que el usuario está logueado
        self.assertTrue('_auth_user_id' in self.client.session)
    
    def test_login_without_email_company_not_found(self):
        """Test login con token sin email pero compañía no existe"""
        # Crear token sin email para una compañía que no existe
        token_no_email = SSOToken.objects.create(
            token='token-no-company-12345',
            email='',  # Sin email
            chatwoot_account_id='99999',  # Esta compañía no existe
            request_id='test-login-no-company',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        response = self.client.get(f'{self.url}?token={token_no_email.token}')
        
        # Debe redirigir a login con error
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=company_not_found', response.url)
    
    def test_login_without_email_no_subscription(self):
        """Test login con token sin email pero compañía sin suscripción"""
        from accounts.models import Company
        
        # Crear compañía SIN suscripción
        company = Company.objects.create(
            name='Company Without Subscription',
            email='no-sub@test.com',
            chatwoot_account_id=888
        )
        
        # Crear usuario para esa compañía
        user = User.objects.create_user(
            email='user@nosub.com',
            username='user@nosub.com',
            is_active=True
        )
        user.company = company
        user.save()
        
        # Crear token sin email
        token_no_email = SSOToken.objects.create(
            token='token-no-sub-12345',
            email='',
            chatwoot_account_id='888',
            request_id='test-login-no-sub',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        response = self.client.get(f'{self.url}?token={token_no_email.token}')
        
        # Debe redirigir a login con error
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=no_subscription', response.url)




