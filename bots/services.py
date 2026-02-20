import httpx
import json
from django.conf import settings
from minio import Minio
import logging

logger = logging.getLogger(__name__)

class ChatwootService:
    """Servicio para interactuar con la API de Chatwoot"""
    
    def __init__(self):
        self.api_url = settings.CHATWOOT_API_URL
        self.platform_token = settings.CHATWOOT_PLATFORM_TOKEN
    
    async def create_account(self, company_name, features=None, limits=None):
        """
        Crea una nueva cuenta en Chatwoot con features y limits del plan
        
        Args:
            company_name: Nombre de la empresa
            features: Dict con features de Chatwoot (inbound_emails, channel_email, etc.)
            limits: Dict con limits de Chatwoot (agents, inboxes)
        """
        async with httpx.AsyncClient() as client:
            try:
                payload = {'name': company_name}
                
                # Agregar features y limits si se proporcionan
                if features:
                    payload['features'] = features
                if limits:
                    payload['limits'] = limits
                
                logger.info(f"🆕 Creando cuenta Chatwoot: {company_name}")
                if features:
                    logger.info(f"   Features activas: {sum(1 for v in features.values() if v)}/{len(features)}")
                if limits:
                    logger.info(f"   Limits: {limits}")
                
                response = await client.post(
                    f"{self.api_url}/platform/api/v1/accounts",
                    headers={'api_access_token': self.platform_token},
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"✅ Cuenta Chatwoot creada: ID {result.get('id')}")
                return result
            except Exception as e:
                logger.error(f"❌ Error creando cuenta Chatwoot: {e}")
                raise
    
    async def update_account_features_limits(self, account_id, features=None, limits=None):
        """
        Actualiza features y limits de una cuenta existente en Chatwoot
        
        Args:
            account_id: ID de la cuenta en Chatwoot
            features: Dict con features de Chatwoot (inbound_emails, channel_email, etc.)
            limits: Dict con limits de Chatwoot (agents, inboxes)
        """
        async with httpx.AsyncClient() as client:
            try:
                payload = {}
                if features:
                    payload['features'] = features
                if limits:
                    payload['limits'] = limits
                
                logger.info(f"🔄 Actualizando cuenta Chatwoot ID {account_id}")
                if features:
                    logger.info(f"   Features activas: {sum(1 for v in features.values() if v)}/{len(features)}")
                if limits:
                    logger.info(f"   Limits: {limits}")
                
                response = await client.patch(
                    f"{self.api_url}/platform/api/v1/accounts/{account_id}",
                    headers={'api_access_token': self.platform_token},
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"✅ Cuenta Chatwoot actualizada: ID {account_id}")
                return result
            except Exception as e:
                logger.error(f"❌ Error actualizando cuenta Chatwoot: {e}")
                raise
    
    async def create_user(self, account_id, user):
        """Crea un usuario en una cuenta de Chatwoot"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/platform/api/v1/accounts/{account_id}/account_users",
                    headers={'api_access_token': self.platform_token},
                    json={
                        'name': user.get_full_name() or user.email,
                        'email': user.email,
                        'role': 'administrator'
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error creando usuario Chatwoot: {e}")
                raise
    
    async def create_inbox(self, account_id, inbox_name):
        """Crea un inbox en Chatwoot"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/api/v1/accounts/{account_id}/inboxes",
                    headers={'api_access_token': self.platform_token},
                    json={
                        'name': inbox_name,
                        'channel': {
                            'type': 'api',
                            'webhook_url': ''
                        }
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error creando inbox Chatwoot: {e}")
                raise

class N8NService:
    """Servicio para interactuar con n8n"""
    
    def __init__(self):
        self.webhook_url = settings.N8N_WEBHOOK_URL
    
    async def save_bot_config(self, inbox_id, config_data):
        """Guarda configuración del bot en Redis vía n8n"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.webhook_url}/webhook/save-inbox-config",
                    json={
                        "inbox_id": inbox_id,
                        "config": config_data
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error guardando config en n8n: {e}")
                raise
    
    async def process_documents(self, inbox_id, minio_paths):
        """Trigger procesamiento de documentos en n8n"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.webhook_url}/webhook/process-documents",
                    json={
                        "inbox_id": inbox_id,
                        "files": minio_paths,
                        "bucket": settings.MINIO_BUCKET
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error procesando documentos en n8n: {e}")
                raise
    
    async def complete_onboarding_webhook(self, webhook_data):
        """Envía datos completos de onboarding completado a n8n"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.webhook_url}/webhook/onboarding-complete",
                    json=webhook_data
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error enviando webhook de onboarding completo: {e}")
                raise
    
    async def activate_account_webhook(self, activation_data):
        """Envía datos de activación a n8n para crear cuenta Chatwoot completa"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                headers = {
                    'X-API-Key': settings.CHATWOOT_PLATFORM_TOKEN
                }
                
                # Payload sin api_access_token (va en headers)
                payload = activation_data
                
                # 🐛 DEBUG: Mostrar URL, headers y payload
                print("🔍 === WEBHOOK DEBUG ===")
                print(f"📍 URL: {self.webhook_url}")
                print(f"📋 Headers: {headers}")
                print(f"📦 Payload: {payload}")
                print("========================")
                
                response = await client.post(
                    self.webhook_url,  # Usar directamente la URL completa
                    json=payload,
                    headers=headers
                )
                
                # 🐛 DEBUG: Mostrar respuesta
                print(f"📥 Response Status: {response.status_code}")
                print(f"📥 Response Headers: {dict(response.headers)}")
                print(f"📥 Response Body: {response.text}")
                print("========================")
                
                # Si el webhook responde correctamente (200-299)
                if response.status_code >= 200 and response.status_code < 300:
                    response_data = response.json()
                    print(f"✅ Webhook exitoso! Data: {response_data}")
                    return response_data
                else:
                    # Si hay error, mostrar detalles
                    error_msg = f"Webhook falló con status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    print(f"❌ {error_msg}")
                    raise Exception(error_msg)
                    
            except httpx.HTTPError as e:
                logger.error(f"HTTP Error en webhook: {e}")
                print(f"❌ HTTP Error: {e}")
                raise
            except Exception as e:
                logger.error(f"Error enviando webhook de activación: {e}")
                print(f"❌ Exception details: {e}")
                raise
    
    async def delete_document_from_vectorstore(self, delete_data):
        """
        Elimina todos los vectores de un documento específico del vector store
        
        Args:
            delete_data: dict con:
                - document_id: ID del documento en Django
                - company_id: ID de la empresa
                - filename: nombre del archivo (opcional, para logs)
                - chatwoot_account_id: ID de cuenta Chatwoot (opcional)
        """
        delete_webhook_url = settings.DELETE_DOCUMENT_N8N_WEBHOOK_URL
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                logger.info(f"🗑️ Eliminando vectores del documento ID {delete_data['document_id']}")
                logger.info(f"   - Company ID: {delete_data['company_id']}")
                logger.info(f"   - Filename: {delete_data.get('filename', 'N/A')}")
                logger.info(f"   - Webhook URL: {delete_webhook_url}")
                
                # Headers con API Key
                headers = {
                    'X-API-Key': settings.CHATWOOT_PLATFORM_TOKEN,
                    'Content-Type': 'application/json'
                }
                
                # Payload
                payload = {
                    'document_id': delete_data['document_id'],
                    'company_id': delete_data['company_id'],
                    'filename': delete_data.get('filename', ''),
                    'bot_name': delete_data.get('bot_name', ''),
                    'chatwoot_account_id': delete_data.get('chatwoot_account_id', ''),
                    'chatwoot_access_token': delete_data.get('chatwoot_access_token', '')
                }
                
                response = await client.post(
                    delete_webhook_url,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"📥 Response Status: {response.status_code}")
                
                if response.status_code >= 200 and response.status_code < 300:
                    try:
                        response_data = response.json()
                        logger.info(f"✅ Vectores eliminados exitosamente del documento {delete_data['document_id']}")
                        logger.info(f"   Response: {response_data}")
                        return response_data
                    except:
                        logger.info(f"✅ Vectores eliminados exitosamente (no JSON response)")
                        return {'success': True, 'message': 'Document vectors deleted successfully'}
                else:
                    error_msg = f"Delete webhook falló con status {response.status_code}: {response.text}"
                    logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)
                    
            except httpx.HTTPError as e:
                logger.error(f"❌ HTTP Error eliminando vectores: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Error eliminando vectores: {e}")
                raise
    
    async def send_document_for_vectorization(self, document_data):
        """
        Envía un documento al webhook de n8n para vectorización
        
        Args:
            document_data: dict con:
                - file: archivo binario
                - filename: nombre del archivo
                - document_id: ID del documento en Django (para metadata)
                - company_id: ID de la empresa
                - company_name: nombre de la empresa
                - chatwoot_account_id: ID de cuenta Chatwoot
                - minio_path: ruta en MinIO
                - metadata: metadatos del documento (opcional)
        """
        webhook_url = settings.ADD_DOCUMENT_N8N_WEBHOOK_URL
        
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minutos timeout para archivos grandes
            try:
                logger.info(f"📤 Enviando documento {document_data['filename']} al webhook de vectorización")
                logger.info(f"   - Company: {document_data['company_name']} (ID: {document_data['company_id']})")
                logger.info(f"   - Chatwoot Account ID: {document_data.get('chatwoot_account_id', 'N/A')}")
                logger.info(f"   - MinIO Path: {document_data['minio_path']}")
                logger.info(f"   - Webhook URL: {webhook_url}")
                
                # Headers con API Key
                headers = {
                    'X-API-Key': settings.CHATWOOT_PLATFORM_TOKEN
                }
                
                # Detectar el Content-Type correcto según la extensión del archivo
                filename = document_data['filename']
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                
                mime_types = {
                    'pdf': 'application/pdf',
                    'txt': 'text/plain',
                    'md': 'text/markdown',
                    'doc': 'application/msword',
                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'csv': 'text/csv',
                    'json': 'application/json',
                }
                
                content_type = mime_types.get(file_ext, 'application/octet-stream')
                
                logger.info(f"   - Content-Type: {content_type} (extensión: .{file_ext})")
                
                # Preparar el multipart form data con el Content-Type correcto
                files = {
                    'file': (document_data['filename'], document_data['file'], content_type)
                }
                
                data = {
                    'document_id': str(document_data['document_id']),  # ID para metadata en pgvector
                    'company_id': str(document_data['company_id']),
                    'bot_name': str(document_data.get('bot_name', '')),
                    'company_name': document_data['company_name'],
                    'chatwoot_account_id': str(document_data.get('chatwoot_account_id', '')),
                    'chatwoot_access_token': str(document_data.get('chatwoot_access_token', '')),
                    'minio_path': document_data['minio_path'],
                    'filename': document_data['filename'],
                    'bucket': settings.MINIO_BUCKET,
                }
                
                # Agregar metadata si existe
                if 'metadata' in document_data and document_data['metadata']:
                    import json
                    data['metadata'] = json.dumps(document_data['metadata'])
                
                logger.info(f"   - Headers: X-API-Key: {settings.CHATWOOT_PLATFORM_TOKEN[:10]}...")
                logger.info(f"   - Chatwoot Access Token present: {'yes' if document_data.get('chatwoot_access_token') else 'no'}")
                
                response = await client.post(
                    webhook_url,
                    files=files,
                    data=data,
                    headers=headers
                )
                
                logger.info(f"📥 Response Status: {response.status_code}")
                
                if response.status_code >= 200 and response.status_code < 300:
                    try:
                        response_data = response.json()
                        logger.info(f"✅ Documento enviado exitosamente al webhook de vectorización")
                        logger.info(f"   Response: {response_data}")
                        return response_data
                    except:
                        logger.info(f"✅ Documento enviado exitosamente (no JSON response)")
                        return {'success': True, 'message': 'Document sent successfully'}
                else:
                    error_msg = f"Webhook falló con status {response.status_code}: {response.text}"
                    logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)
                    
            except httpx.HTTPError as e:
                logger.error(f"❌ HTTP Error enviando documento al webhook: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Error enviando documento al webhook: {e}")
                raise

class MinioService:
    """Servicio para interactuar con MinIO"""
    
    def __init__(self):
        # Obtener configuración de MinIO
        endpoint = settings.MINIO_ENDPOINT
        ak = settings.MINIO_ACCESS_KEY
        sk = settings.MINIO_SECRET_KEY

        logger.info(f"🔧 Configuración MinIO:")
        logger.info(f"   - Endpoint: {endpoint}")
        logger.info(f"   - Access Key: {ak[:5]}..." if ak else "   - Access Key: NO CONFIGURADO")
        logger.info(f"   - Secret Key: {'*' * len(sk) if sk else 'NO CONFIGURADO'}")
        logger.info(f"   - Bucket: {settings.MINIO_BUCKET}")
        
        # Determinar si usar HTTPS
        # Si el endpoint NO contiene localhost, 127.0.0.1, :9000 o minio:, usar HTTPS
        use_secure = not any(x in endpoint for x in ['localhost', '127.0.0.1', ':9000', 'minio:'])
        
        logger.info(f"   - Secure (HTTPS): {use_secure}")
        
        self.client = Minio(
            endpoint,
            access_key=ak,
            secret_key=sk,
            secure=use_secure
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Asegura que el bucket existe"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Bucket {self.bucket} creado")
        except Exception as e:
            logger.error(f"Error con bucket MinIO: {e}")
    
    def upload_file(self, file_obj, object_name):
        """Sube un archivo a MinIO"""
        try:
            file_obj.seek(0, 2)  # Ir al final
            file_size = file_obj.tell()
            file_obj.seek(0)  # Volver al inicio
            
            self.client.put_object(
                self.bucket,
                object_name,
                file_obj,
                length=file_size,
                content_type=file_obj.content_type if hasattr(file_obj, 'content_type') else 'application/octet-stream'
            )
            
            return {
                'object_name': object_name,
                'size': file_size
            }
        except Exception as e:
            logger.error(f"Error subiendo archivo a MinIO: {e}")
            raise
    
    def get_file_url(self, object_name, expires=3600):
        """Obtiene URL pre-firmada de un archivo"""
        try:
            return self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=expires
            )
        except Exception as e:
            logger.error(f"Error obteniendo URL de MinIO: {e}")
            raise
    
    def delete_file(self, object_name):
        """Elimina un archivo de MinIO"""
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(f"✅ Archivo eliminado de MinIO: {object_name}")
            return {'success': True, 'object_name': object_name}
        except Exception as e:
            logger.error(f"❌ Error eliminando archivo de MinIO: {e}")
            raise