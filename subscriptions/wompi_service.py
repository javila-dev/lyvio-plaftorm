import requests
import hashlib
import time
import logging
import json
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

class WompiService:
    """Servicio para manejar pagos con Wompi usando su API REST"""
    
    BASE_URL = "https://production.wompi.co/v1"
    SANDBOX_URL = "https://sandbox.wompi.co/v1"
    
    def __init__(self):
        self.public_key = settings.WOMPI_PUBLIC_KEY
        self.private_key = settings.WOMPI_PRIVATE_KEY
        self.test_mode = settings.WOMPI_TEST_MODE
        self.base_url = self.SANDBOX_URL if self.test_mode else self.BASE_URL
        self.events_secret = settings.WOMPI_EVENTS_SECRET
        self.integrity_secret = settings.WOMPI_INTEGRITY_SECRET
    
    def _debug_log(self, operation, data, prefix=""):
        """Logs detallados con formato JSON bonito para debugging"""
        separator = "=" * 80
        logger.info(f"\n{separator}")
        logger.info(f"{prefix}🔍 DEBUG: {operation}")
        logger.info(f"{separator}")
        try:
            if isinstance(data, dict):
                logger.info(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                logger.info(str(data))
        except Exception as e:
            logger.info(f"No se pudo formatear: {data}")
        logger.info(f"{separator}\n")
    
    def _get_headers(self, use_private_key=False):
        """Headers para las peticiones"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if use_private_key:
            headers['Authorization'] = f'Bearer {self.private_key}'
        return headers
    
    def create_acceptance_token(self):
        """
        Obtiene los tokens de aceptación de términos y condiciones
        Retorna un dict con tokens y enlaces a PDFs de políticas
        """
        url = f"{self.base_url}/merchants/{self.public_key}"
        
        try:
            logger.info(f"📡 REQUEST: GET {url}")
            response = requests.get(url, headers=self._get_headers())
            
            logger.info(f"📥 RESPONSE STATUS: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            self._debug_log("GET ACCEPTANCE TOKENS - Response completa", data)
            
            presigned_acceptance = data['data']['presigned_acceptance']
            presigned_personal_data = data['data']['presigned_personal_data_auth']
            
            # Retornar tokens y permalinks para mostrar al usuario
            result = {
                'acceptance_token': presigned_acceptance['acceptance_token'],
                'accept_personal_auth': presigned_personal_data['acceptance_token'],
                'terms_permalink': presigned_acceptance.get('permalink', ''),
                'personal_data_permalink': presigned_personal_data.get('permalink', '')
            }
            
            self._debug_log("GET ACCEPTANCE TOKENS - Tokens extraídos", result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo tokens de aceptación: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
            raise
    
    def tokenize_card(self, card_data):
        """
        Tokeniza una tarjeta de crédito/débito
        card_data = {
            'number': '4242424242424242',
            'exp_month': '06',
            'exp_year': '29', 
            'cvc': '123',
            'card_holder': 'Pedro Pérez'
        }
        """
        url = f"{self.base_url}/tokens/cards"
        
        headers = self._get_headers()
        headers['Authorization'] = f'Bearer {self.public_key}'  # Usar llave pública para tokenización
        
        try:
            # Ocultar número completo en logs
            safe_card_data = card_data.copy()
            if 'number' in safe_card_data:
                safe_card_data['number'] = f"****{safe_card_data['number'][-4:]}"
            if 'cvc' in safe_card_data:
                safe_card_data['cvc'] = "***"
            
            logger.info(f"📡 REQUEST: POST {url}")
            self._debug_log("TOKENIZE CARD - Request payload (sanitizado)", safe_card_data)
            
            response = requests.post(url, json=card_data, headers=headers)
            
            logger.info(f"📥 RESPONSE STATUS: {response.status_code}")
            
            # Si hay error, capturar respuesta antes de raise_for_status
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    logger.error(f"❌ Error de Wompi ({response.status_code}): {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"❌ Error de Wompi ({response.status_code}): {response.text}")
            
            response.raise_for_status()
            
            if not response.text:
                raise Exception("La respuesta de tokenización está vacía")
            
            try:
                data = response.json()
                self._debug_log("TOKENIZE CARD - Response completa", data)
            except ValueError:
                logger.error(f"❌ Error parseando JSON tokenización. Response: {response.text}")
                raise Exception(f"Respuesta inválida al tokenizar: {response.text[:200]}")
            
            if data.get('status') == 'CREATED':
                token_id = data['data']['id']
                logger.info(f"✅ Tarjeta tokenizada exitosamente: {token_id}")
                return token_id
            else:
                error_msg = data.get('error', {}).get('message', str(data))
                raise Exception(f"Error tokenizando tarjeta: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red al tokenizar: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"   Detalle del error: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"   Response text: {e.response.text}")
            raise Exception(f"Error de conexión con Wompi: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error tokenizando tarjeta: {e}")
            raise

    def create_payment_source(self, token, customer_email, acceptance_tokens):
        """
        Crea una fuente de pago usando un token de tarjeta
        acceptance_tokens debe ser un dict con 'acceptance_token' y 'accept_personal_auth'
        """
        url = f"{self.base_url}/payment_sources"
        
        payload = {
            "type": "CARD",
            "token": token,
            "customer_email": customer_email,
            "acceptance_token": acceptance_tokens['acceptance_token'],
            "accept_personal_auth": acceptance_tokens['accept_personal_auth']
        }
        
        headers = self._get_headers(use_private_key=True)  # Usar llave privada
        
        try:
            logger.info(f"📡 REQUEST: POST {url}")
            self._debug_log("CREATE PAYMENT SOURCE - Request payload", payload)
            
            response = requests.post(url, json=payload, headers=headers)
            
            logger.info(f"📥 RESPONSE STATUS: {response.status_code}")
            
            response.raise_for_status()
            
            # Verificar que la respuesta tenga contenido
            if not response.text:
                raise Exception("La respuesta de Wompi está vacía")
            
            try:
                data = response.json()
                self._debug_log("CREATE PAYMENT SOURCE - Response completa", data)
            except ValueError as json_error:
                logger.error(f"❌ Error parseando JSON. Response text: {response.text}")
                raise Exception(f"Respuesta inválida de Wompi: {response.text[:200]}")
            
            if data.get('data', {}).get('status') == 'AVAILABLE':
                payment_source_data = data['data']
                payment_source_id = payment_source_data['id']
                logger.info(f"✅ Fuente de pago creada exitosamente: {payment_source_id}")
                
                # Log específico de la info de tarjeta
                public_data = payment_source_data.get('public_data', {})
                card_info = {
                    'brand': public_data.get('brand'),
                    'last_four': public_data.get('last_four'),
                    'exp_month': public_data.get('exp_month'),
                    'exp_year': public_data.get('exp_year')
                }
                self._debug_log("CREATE PAYMENT SOURCE - Card info extraída", card_info)
                
                return payment_source_data  # Retornar data completa con info de tarjeta
            else:
                error_msg = data.get('error', {}).get('message', str(data))
                self._debug_log("CREATE PAYMENT SOURCE - ERROR response", data)
                raise Exception(f"Error creando fuente de pago: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al crear fuente de pago: {e}")
            raise Exception(f"Error de conexión con Wompi: {str(e)}")
        except Exception as e:
            logger.error(f"Error creando fuente de pago: {e}")
            raise

    def create_transaction_with_token(self, token, amount, customer_email, reference, acceptance_tokens):
        """
        Crea una transacción inicial con token y solicita guardar payment_source
        Esta transacción automáticamente crea el payment_source si se aprueba
        acceptance_tokens debe ser un dict con 'acceptance_token' y 'accept_personal_auth'
        """
        url = f"{self.base_url}/transactions"
        
        # Calcular firma de integridad
        amount_in_cents = int(amount * 100)
        currency = "COP"
        integrity_string = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        signature = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        payload = {
            "amount_in_cents": amount_in_cents,
            "currency": currency,
            "signature": signature,
            "customer_email": customer_email,
            "reference": reference,
            "payment_method": {
                "type": "CARD",
                "token": token,
                "installments": 1
            },
            "acceptance_token": acceptance_tokens['acceptance_token'],
            "save_payment_method": True  # Esto le dice a Wompi que guarde el método de pago
        }
        
        headers = self._get_headers(use_private_key=True)
        
        try:
            logger.info(f"Creando transacción con token - URL: {url}")
            logger.info(f"Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers)
            
            logger.info(f"Transaction Status Code: {response.status_code}")
            logger.info(f"Transaction Response: {response.text}")
            
            response.raise_for_status()
            
            if not response.text:
                raise Exception("La respuesta de transacción está vacía")
            
            try:
                data = response.json()
            except ValueError:
                logger.error(f"Error parseando JSON transacción. Response: {response.text}")
                raise Exception(f"Respuesta inválida al crear transacción: {response.text[:200]}")
            
            transaction_data = data.get('data', {})
            logger.info(f"Transacción creada: {transaction_data.get('id')}, Status: {transaction_data.get('status')}")
            
            # Obtener el payment_source_id si está disponible
            payment_source_id = transaction_data.get('payment_source_id')
            if payment_source_id:
                logger.info(f"Payment source creado automáticamente: {payment_source_id}")
            
            return transaction_data
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al crear transacción: {e}")
            raise Exception(f"Error de conexión con Wompi: {str(e)}")
        except Exception as e:
            logger.error(f"Error creando transacción: {e}")
            raise

    def create_recurring_transaction(self, payment_source_id, amount, customer_email, reference):
        """
        Crea una transacción recurrente usando una fuente de pago
        """
        url = f"{self.base_url}/transactions"
        
        # Calcular firma de integridad
        amount_in_cents = int(amount * 100)
        currency = "COP"
        integrity_string = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        signature = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        payload = {
            "amount_in_cents": amount_in_cents,
            "currency": currency,
            "signature": signature,
            "customer_email": customer_email,
            "reference": reference,
            "payment_source_id": payment_source_id,
            "payment_method": {
                "installments": 1  # Número de cuotas (1 para pago de contado)
            }
        }
        
        headers = self._get_headers(use_private_key=True)
        
        try:
            logger.info(f"📡 REQUEST: POST {url}")
            self._debug_log("CREATE RECURRING TRANSACTION - Request payload", payload)
            
            # Log del cálculo de firma de integridad
            integrity_debug = {
                'reference': reference,
                'amount_in_cents': amount_in_cents,
                'currency': currency,
                'integrity_string': f"{reference}{amount_in_cents}{currency}[INTEGRITY_SECRET]",
                'signature': signature
            }
            self._debug_log("CREATE RECURRING TRANSACTION - Integrity calculation", integrity_debug)
            
            response = requests.post(url, json=payload, headers=headers)
            
            logger.info(f"📥 RESPONSE STATUS: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            self._debug_log("CREATE RECURRING TRANSACTION - Response completa", data)
            
            transaction_data = data['data']
            transaction_status = transaction_data.get('status')
            transaction_id = transaction_data.get('id')
            
            logger.info(f"✅ Transacción creada: {transaction_id}, Status: {transaction_status}")
            
            # Log detallado del estado
            status_info = {
                'transaction_id': transaction_id,
                'status': transaction_status,
                'amount_in_cents': transaction_data.get('amount_in_cents'),
                'currency': transaction_data.get('currency'),
                'reference': transaction_data.get('reference'),
                'payment_source_id': transaction_data.get('payment_source_id'),
                'created_at': transaction_data.get('created_at'),
                'finalized_at': transaction_data.get('finalized_at')
            }
            self._debug_log("CREATE RECURRING TRANSACTION - Transaction details", status_info)
            
            return transaction_data
            
        except Exception as e:
            logger.error(f"❌ Error creando transacción recurrente: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    self._debug_log("CREATE RECURRING TRANSACTION - ERROR response", error_data)
                except:
                    pass
            raise
    
    def get_transaction_status(self, transaction_id):
        """
        Consulta el estado actual de una transacción por su ID
        """
        url = f"{self.base_url}/transactions/{transaction_id}"
        headers = self._get_headers(use_private_key=True)
        
        try:
            logger.info(f"📡 REQUEST: GET {url}")
            
            response = requests.get(url, headers=headers)
            logger.info(f"📥 RESPONSE STATUS: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            transaction_data = data.get('data', {})
            
            # Log resumido del estado
            status_info = {
                'transaction_id': transaction_data.get('id'),
                'status': transaction_data.get('status'),
                'reference': transaction_data.get('reference'),
                'amount_in_cents': transaction_data.get('amount_in_cents'),
                'payment_source_id': transaction_data.get('payment_source_id'),
                'created_at': transaction_data.get('created_at'),
                'finalized_at': transaction_data.get('finalized_at')
            }
            self._debug_log("GET TRANSACTION STATUS - Result", status_info)
            
            return transaction_data
            
        except Exception as e:
            logger.error(f"❌ Error consultando estado de transacción {transaction_id}: {e}")
            raise

    def get_payment_source(self, payment_source_id):
        """
        Obtiene información de una fuente de pago existente
        Retorna info de la tarjeta (brand, last_four, exp_month, exp_year)
        """
        url = f"{self.base_url}/payment_sources/{payment_source_id}"
        headers = self._get_headers(use_private_key=True)
        
        try:
            logger.info(f"Obteniendo info de payment_source: {payment_source_id}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            payment_source_info = data.get('data', {})
            logger.info(f"Payment source info obtenida: {payment_source_info}")
            return payment_source_info
            
        except Exception as e:
            logger.error(f"Error obteniendo payment_source: {e}")
            return None

    def create_payment_link(self, plan, user, billing_cycle='monthly', custom_amount=None):
        """Crea un link de pago en Wompi para usuario autenticado"""
        customer_data = {
            'customer_email': user.email,
            'customer_name': user.get_full_name() or user.email
        }
        return self._create_payment_link_internal(plan, customer_data, billing_cycle, user.id, custom_amount)
    
    def create_payment_link_anonymous(self, plan, payment_data, billing_cycle='monthly'):
        """Crea un link de pago en Wompi para usuario anónimo"""
        return self._create_payment_link_internal(plan, payment_data, billing_cycle)
    
    def _create_payment_link_internal(self, plan, payment_data, billing_cycle='monthly', user_id=None, custom_amount=None):
        """Método interno para crear links de pago"""
        url = f"{self.base_url}/payment_links"
        
        # Calcular monto según ciclo de facturación o usar monto personalizado
        if custom_amount is not None:
            amount_in_cents = int(custom_amount * 100)
        elif billing_cycle == 'yearly' and plan.price_yearly:
            amount_in_cents = int(plan.price_yearly * 100)
        else:
            amount_in_cents = int(plan.price_monthly * 100)
        
        # Generar referencia única
        user_ref = user_id if user_id else f"anon-{int(time.time())}"
        reference = f"LYVIO-{plan.id}-{user_ref}"
        
        # Calcular signature de integridad
        currency = "COP"
        integrity_string = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        integrity = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        payload = {
            "name": f"Suscripción {plan.name}",
            "description": f"Plan {plan.name} - {billing_cycle}",
            "single_use": True,  # Cambiar a True para un solo uso
            "collect_shipping": False,
            "currency": currency,
            "amount_in_cents": amount_in_cents,
            "reference": reference,
            "customer_data": {
                "email": payment_data['customer_email'],
                "full_name": payment_data['customer_name']
                # Remover phone_number si está vacío ya que puede causar problemas
            },
            "redirect_url": f"{settings.SITE_URL}/billing/payment/success/",
            "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z",  # 2 horas en formato ISO para estar seguro
            "signature": {
                "integrity": integrity
            }
        }
        
        # Solo agregar phone_number si existe y no está vacío
        if payment_data.get('phone_number'):
            payload["customer_data"]["phone_number"] = payment_data['phone_number']
        
        headers = {
            "Authorization": f"Bearer {self.private_key}",
            "Content-Type": "application/json"
        }
        
        # Log del payload para debugging
        logger.info(f"Enviando payload a Wompi: {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Respuesta exitosa de Wompi: {response_data}")
            
            # Extraer el ID del payment link y construir la URL
            payment_link_id = response_data.get('data', {}).get('id')
            if not payment_link_id:
                raise Exception(f"No se pudo obtener ID de payment link de la respuesta: {response_data}")
            
            # Construir la URL del payment link
            # Según la documentación de Wompi: https://docs.wompi.co/docs/colombia/widget-checkout-web/
            # La URL es la misma para sandbox y producción, el ambiente se detecta por las llaves
            payment_link_url = f"https://checkout.wompi.co/l/{payment_link_id}"
            
            return payment_link_url
        except requests.exceptions.RequestException as e:
            error_msg = f"Error creando link de pago: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - Detalles: {error_detail}"
                except:
                    error_msg += f" - Response: {e.response.text}"
            print(error_msg)
            raise Exception(error_msg)
    
    def create_transaction(self, amount_in_cents, currency, customer_email, payment_source_id, reference):
        """
        Crea una transacción con un payment_source_id existente
        payment_source_id: ID del payment source creado previamente
        """
        url = f"{self.base_url}/transactions"
        
        integrity_string = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        integrity = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        payload = {
            "amount_in_cents": amount_in_cents,
            "currency": currency,
            "customer_email": customer_email,
            "payment_source_id": payment_source_id,  # payment_source_id va en el nivel raíz
            "payment_method": {
                "installments": 1
            },
            "reference": reference,
            "signature": integrity
        }
        
        headers = {
            "Authorization": f"Bearer {self.private_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"📡 REQUEST: POST {url}")
            self._debug_log("CREATE TRANSACTION - Request payload", payload)
            
            response = requests.post(url, json=payload, headers=headers)
            
            logger.info(f"📡 RESPONSE Status: {response.status_code}")
            self._debug_log("CREATE TRANSACTION - Response", response.text)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error creando transacción: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"   Detalle del error: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"   Response text: {e.response.text}")
            return None
    
    def get_transaction(self, transaction_id):
        """Obtiene el estado de una transacción"""
        url = f"{self.base_url}/transactions/{transaction_id}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo transacción: {e}")
            return None
    
    def verify_signature(self, request_body, signature):
        """Verifica la firma de un evento webhook según documentación de Wompi"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Según la documentación: concatenar request body + events_secret
        body_str = request_body.decode('utf-8')
        string_to_hash = body_str + self.events_secret
        computed_signature = hashlib.sha256(string_to_hash.encode()).hexdigest()
        
        logger.info(f"Verificando firma webhook:")
        logger.info(f"  Body length: {len(body_str)}")
        logger.info(f"  Events secret: {self.events_secret[:10]}...")
        logger.info(f"  String to hash length: {len(string_to_hash)}")
        logger.info(f"  Received signature: {signature}")
        logger.info(f"  Computed signature: {computed_signature}")
        logger.info(f"  Match: {computed_signature == signature}")
        
        return computed_signature == signature
    
    def _compute_response_checksum(self, event_checksum):
        """
        Computa el checksum de respuesta para el webhook de Wompi
        Según documentación: sha256(event_checksum + events_secret)
        """
        string_to_hash = event_checksum + self.events_secret
        response_checksum = hashlib.sha256(string_to_hash.encode()).hexdigest()
        
        logger.info(f"Computando response checksum:")
        logger.info(f"  Event checksum: {event_checksum}")
        logger.info(f"  Events secret: {self.events_secret[:10]}...")
        logger.info(f"  Response checksum: {response_checksum}")
        
        return response_checksum
    
    def get_customer_transactions(self, customer_email, limit=50):
        """Obtiene las transacciones de un cliente por email"""
        url = f"{self.base_url}/transactions"
        params = {
            'customer_email': customer_email,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(use_private_key=True))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obteniendo transacciones del cliente: {e}")
            return None
    
    def get_payment_methods(self, customer_email):
        """Obtiene los métodos de pago guardados de un cliente"""
        url = f"{self.base_url}/payment_methods"
        params = {'customer_email': customer_email}
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(use_private_key=True))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obteniendo métodos de pago: {e}")
            return None
    
    def create_recurring_payment(self, subscription_id, amount, customer_email, payment_method_id):
        """Crea un pago recurrente para una suscripción"""
        url = f"{self.base_url}/transactions"
        
        # Calcular signature
        reference = f"RECURRING-{subscription_id}-{int(time.time())}"
        amount_in_cents = int(amount * 100)
        currency = "COP"
        integrity_string = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        integrity = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        payload = {
            "amount_in_cents": amount_in_cents,
            "currency": currency,
            "customer_email": customer_email,
            "payment_method": {
                "type": "CARD",
                "installments": 1,
                "token": payment_method_id
            },
            "reference": reference,
            "signature": {
                "integrity": integrity
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers(use_private_key=True))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creando pago recurrente: {e}")
            return None
    
    def cancel_recurring_payments(self, subscription_id):
        """Cancela los pagos recurrentes de una suscripción"""
        # En Wompi, esto se maneja cancelando el payment method token
        # o marcando la suscripción como cancelada en nuestro sistema
        logger.info(f"Cancelando pagos recurrentes para suscripción {subscription_id}")
        return True
    
    def format_amount_for_display(self, amount_in_cents):
        """Convierte centavos a formato de visualización"""
        return amount_in_cents / 100
    
    def validate_webhook_signature(self, event_data):
        """Valida la firma de un webhook de Wompi"""
        # Esta implementación depende del formato exacto del webhook
        # que envía Wompi
        try:
            signature = event_data.get('signature')
            if not signature:
                return False
            
            return self.verify_signature(event_data, signature)
        except Exception as e:
            logger.error(f"Error validando signature del webhook: {e}")
            return False