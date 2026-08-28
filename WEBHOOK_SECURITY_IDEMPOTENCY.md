# 🔐 Seguridad e Idempotencia del Webhook de Wompi

## 📋 Resumen

Este documento detalla las mejoras de seguridad implementadas en el webhook de Wompi para garantizar:
1. ✅ **Autenticidad** de los webhooks (validación de firma)
2. ✅ **Idempotencia** (evitar procesamiento duplicado)
3. ✅ **Auditoría completa** de todos los eventos

---

## 🔒 1. Validación de Firma (X-Event-Checksum)

### Problema que Resuelve:
Sin validación de firma, cualquier persona podría enviar webhooks falsos a tu endpoint y:
- Activar suscripciones sin pago real
- Modificar estados de facturas
- Crear registros falsos en la base de datos

### Implementación:

**Código:** `/app/subscriptions/views.py` líneas 1241-1267

```python
# 1. Obtener firma del header
signature = request.META.get('HTTP_X_EVENT_CHECKSUM')

if not signature:
    logger.error("❌ WEBHOOK RECHAZADO: No se recibió X-Event-Checksum")
    return HttpResponse('Missing signature', status=401)

# 2. Verificar firma usando el secret de Wompi
wompi_service = WompiService()
if not wompi_service.verify_signature(request_body, signature):
    logger.error("❌ WEBHOOK RECHAZADO: Firma inválida")
    
    # Registrar intento malicioso
    webhook_event = WebhookEvent.objects.create(
        event_id=event_data.get('id', f"invalid-{timezone.now().timestamp()}"),
        status='invalid_signature',
        payload=event_data,
        signature=signature
    )
    
    return HttpResponse('Invalid signature', status=403)

logger.info("✅ Firma válida - Webhook autenticado correctamente")
```

### Cómo Funciona:

1. **Wompi calcula firma:**
   ```
   SHA256(event_data + events_secret)
   ```

2. **Envía en header:**
   ```
   X-Event-Checksum: abc123def456...
   ```

3. **Django recalcula firma:**
   ```python
   expected_signature = hashlib.sha256(
       request_body + settings.WOMPI_EVENTS_SECRET.encode()
   ).hexdigest()
   ```

4. **Compara:**
   ```python
   if signature != expected_signature:
       return 403  # Rechazar webhook
   ```

### Configuración Requerida:

En `settings.py`:
```python
WOMPI_EVENTS_SECRET = env('WOMPI_EVENTS_SECRET')  # Obtener de dashboard de Wompi
```

En `.env`:
```bash
WOMPI_EVENTS_SECRET=your_events_secret_here
```

---

## 🔄 2. Idempotencia (Evitar Duplicados)

### Problema que Resuelve:

Wompi puede enviar el mismo webhook múltiples veces si:
- No recibe respuesta 200 OK rápido
- Hay timeouts de red
- Hace reintentos automáticos

Sin idempotencia, esto causaría:
- ❌ Suscripciones activadas múltiples veces
- ❌ Facturas duplicadas
- ❌ Períodos de suscripción extendidos varias veces
- ❌ Notificaciones duplicadas a usuarios

### Implementación:

**Código:** `/app/subscriptions/views.py` líneas 1269-1297

```python
# 1. Extraer event_id único del webhook
event_id = event_data.get('id')  # Ej: "evt_abc123"

# 2. Verificar si ya procesamos este webhook antes
existing_webhook = WebhookEvent.objects.filter(event_id=event_id).first()

if existing_webhook:
    if existing_webhook.status in ['processed', 'duplicate']:
        logger.warning(f"⚠️ WEBHOOK DUPLICADO: event_id={event_id}")
        logger.warning(f"   Procesado el: {existing_webhook.processed_at}")
        
        # Marcar como duplicado
        existing_webhook.mark_as_duplicate()
        
        # Responder OK para que Wompi no reintente
        return HttpResponse('OK - Already processed', status=200)
    
    elif existing_webhook.status == 'processing':
        # Otro worker lo está procesando ahora mismo
        logger.warning(f"⚠️ WEBHOOK EN PROCESAMIENTO: event_id={event_id}")
        return HttpResponse('OK - Processing', status=200)

# 3. Primera vez que vemos este webhook - procesarlo
webhook_event = WebhookEvent.objects.create(
    event_id=event_id,
    event_type=event_type,
    transaction_id=transaction_id,
    status='processing',  # Marcar como "en proceso"
    payload=event_data
)
```

### Flujo de Estados:

```
┌──────────┐
│ received │ ──► Primera recepción del webhook
└────┬─────┘
     │
     ▼
┌────────────┐
│ processing │ ──► Se está procesando ahora
└────┬───────┘
     │
     ├────────────┐
     │            │
     ▼            ▼
┌───────────┐  ┌─────────┐
│ processed │  │ failed  │
└────┬──────┘  └─────────┘
     │
     │ (Si llega de nuevo)
     ▼
┌───────────┐
│ duplicate │ ──► Ya fue procesado antes
└───────────┘
```

### Modelo WebhookEvent:

**Archivo:** `/app/subscriptions/models.py` líneas 216-322

```python
class WebhookEvent(models.Model):
    # Identificación única
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=255, db_index=True)
    
    # Datos completos
    payload = models.JSONField()
    signature = models.CharField(max_length=255)
    
    # Estado del procesamiento
    status = models.CharField(
        max_length=20,
        choices=[
            ('received', 'Recibido'),
            ('processing', 'Procesando'),
            ('processed', 'Procesado'),
            ('failed', 'Fallido'),
            ('duplicate', 'Duplicado'),
            ('invalid_signature', 'Firma Inválida'),
        ]
    )
    error_message = models.TextField(blank=True)
    
    # Referencias
    subscription = models.ForeignKey(Subscription, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, null=True, blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadatos de seguridad
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
        ]
```

---

## 📊 3. Auditoría Completa

### Beneficios:

1. **Debugging:** Ver qué webhooks se recibieron y cuándo
2. **Monitoreo:** Detectar patrones anormales (muchos fallos, duplicados)
3. **Cumplimiento:** Registro completo de todas las transacciones
4. **Reconciliación:** Comparar con registros de Wompi

### Información Registrada:

Para cada webhook se guarda:
- ✅ `event_id`: ID único del evento
- ✅ `event_type`: Tipo de evento (transaction.updated, etc)
- ✅ `transaction_id`: ID de la transacción en Wompi
- ✅ `payload`: JSON completo del webhook
- ✅ `signature`: Firma recibida (X-Event-Checksum)
- ✅ `status`: Estado del procesamiento
- ✅ `error_message`: Mensaje de error si falló
- ✅ `subscription`: Suscripción afectada (si aplica)
- ✅ `invoice`: Factura creada/actualizada (si aplica)
- ✅ `received_at`: Timestamp de recepción
- ✅ `processed_at`: Timestamp de finalización
- ✅ `ip_address`: IP de origen
- ✅ `user_agent`: User-Agent del webhook

### Admin de Django:

Accede a `/admin/subscriptions/webhookevent/` para ver:

**Lista de webhooks:**
```
| ID | Event ID | Type                | Transaction | Status    | Sub | Invoice | Received           | Time   |
|----|----------|---------------------|-------------|-----------|-----|---------|--------------------|--------|
| 45 | evt_a1b2 | transaction.updated | txn_xyz123  | ✅ Procesado | #12 | #34     | 2025-11-05 10:30  | 234ms  |
| 44 | evt_c3d4 | transaction.updated | txn_abc456  | 🔄 Duplicado | #12 | #34     | 2025-11-05 10:31  | -      |
| 43 | evt_e5f6 | transaction.updated | txn_def789  | ❌ Fallido   | -   | -       | 2025-11-05 10:25  | 1.2s   |
```

**Filtros disponibles:**
- Por estado (processed, failed, duplicate, invalid_signature)
- Por tipo de evento
- Por fecha

**Búsqueda:**
- Por event_id
- Por transaction_id
- Por ID de suscripción
- Por ID de factura

---

## 🔧 4. Métodos del Modelo

### `mark_as_processing()`
```python
webhook_event.mark_as_processing()
```
Marca el webhook como "en procesamiento" para evitar que otro worker lo tome.

### `mark_as_processed(subscription, invoice)`
```python
webhook_event.mark_as_processed(
    subscription=subscription,
    invoice=invoice
)
```
Marca como procesado exitosamente y asocia suscripción/factura.

### `mark_as_failed(error_message)`
```python
webhook_event.mark_as_failed("Error al activar suscripción")
```
Marca como fallido con mensaje de error.

### `mark_as_duplicate()`
```python
webhook_event.mark_as_duplicate()
```
Marca como duplicado (ya fue procesado antes).

### `mark_as_invalid_signature()`
```python
webhook_event.mark_as_invalid_signature()
```
Marca como con firma inválida (intento malicioso).

---

## 🚀 5. Flujo Completo del Webhook

```
1. Wompi envía webhook
   ↓
2. Django recibe POST a /dashboard/wompi/webhook/
   ↓
3. ✅ VALIDAR FIRMA
   ├─ Sin firma → Rechazar (401)
   ├─ Firma inválida → Rechazar (403) + Registrar intento
   └─ Firma válida → Continuar
   ↓
4. ✅ VERIFICAR IDEMPOTENCIA
   ├─ event_id ya existe:
   │  ├─ status='processed' → Responder OK (200) sin procesar
   │  ├─ status='processing' → Responder OK (200) sin procesar
   │  └─ status='failed' → Reintentar procesamiento
   └─ event_id nuevo:
      └─ Crear WebhookEvent con status='processing'
   ↓
5. 🔄 PROCESAR WEBHOOK
   ├─ Buscar/actualizar suscripción
   ├─ Crear/actualizar invoice
   └─ Extender período si aplica
   ↓
6. ✅ MARCAR COMO PROCESADO
   ├─ Asociar subscription e invoice
   ├─ status='processed'
   └─ processed_at=now()
   ↓
7. 📤 RESPONDER A WOMPI
   └─ 200 OK con checksum de respuesta
```

---

## 📝 6. Migración

Para aplicar los cambios a la base de datos:

```bash
# Ya ejecutado automáticamente
python manage.py makemigrations subscriptions
# Crea: subscriptions/migrations/0008_webhookevent.py

# Aplicar migración
python manage.py migrate subscriptions
```

---

## 🔍 7. Monitoreo y Alertas

### Consultas Útiles:

**Webhooks fallidos en las últimas 24 horas:**
```python
from datetime import timedelta
from django.utils import timezone
from subscriptions.models import WebhookEvent

failed_webhooks = WebhookEvent.objects.filter(
    status='failed',
    received_at__gte=timezone.now() - timedelta(hours=24)
)

for webhook in failed_webhooks:
    print(f"Event: {webhook.event_id}")
    print(f"Error: {webhook.error_message}")
    print(f"Transaction: {webhook.transaction_id}")
    print("---")
```

**Webhooks duplicados (posible problema de timeout):**
```python
from django.db.models import Count

duplicates = WebhookEvent.objects.filter(
    status='duplicate'
).values('transaction_id').annotate(
    count=Count('id')
).filter(count__gt=2).order_by('-count')

print(f"Transacciones con múltiples webhooks duplicados: {duplicates.count()}")
```

**Webhooks con firma inválida (posibles ataques):**
```python
invalid = WebhookEvent.objects.filter(
    status='invalid_signature'
).order_by('-received_at')[:10]

print(f"⚠️ {invalid.count()} webhooks con firma inválida detectados")
for webhook in invalid:
    print(f"IP: {webhook.ip_address}")
    print(f"User-Agent: {webhook.user_agent}")
    print(f"Received: {webhook.received_at}")
    print("---")
```

### Dashboard Recomendado:

Puedes crear un dashboard en el admin o usar Grafana/Datadog para monitorear:

- 📊 Webhooks recibidos por hora
- ❌ Tasa de fallos
- 🔄 Tasa de duplicados
- ⏱️ Tiempo promedio de procesamiento
- 🚫 Intentos con firma inválida

---

## ⚠️ 8. Troubleshooting

### Problema: Todos los webhooks son rechazados

**Causa:** `WOMPI_EVENTS_SECRET` incorrecto o no configurado

**Solución:**
1. Ir a dashboard de Wompi
2. Copiar el "Events Secret" (NO el "Private Key")
3. Actualizar `.env`:
   ```bash
   WOMPI_EVENTS_SECRET=prod_events_xxxxxxxxxxxxx
   ```
4. Reiniciar servidor

### Problema: Muchos webhooks duplicados

**Causa:** El servidor responde muy lento (> 5 segundos)

**Solución:**
1. Optimizar procesamiento del webhook
2. Usar workers asíncronos (Celery)
3. Responder 200 OK rápido, procesar después

### Problema: Webhook procesado pero suscripción no se activó

**Causa:** Error en la lógica de procesamiento después de validaciones

**Solución:**
1. Buscar el webhook en el admin: `/admin/subscriptions/webhookevent/`
2. Ver el `error_message`
3. Ver el `payload` completo
4. Revisar logs con el `event_id`

---

## 🎯 9. Checklist de Implementación

- [x] Modelo `WebhookEvent` creado
- [x] Migración generada (0008_webhookevent.py)
- [x] Validación de firma implementada
- [x] Idempotencia por `event_id` implementada
- [x] Admin de Django configurado
- [x] Métodos de estado (`mark_as_*`) implementados
- [x] Auditoría completa (IP, user-agent, timestamps)
- [ ] Aplicar migración: `python manage.py migrate`
- [ ] Configurar `WOMPI_EVENTS_SECRET` en producción
- [ ] Probar webhook con firma válida
- [ ] Probar webhook duplicado (debe responder OK sin procesar)
- [ ] Probar webhook con firma inválida (debe rechazar)
- [ ] Configurar alertas para webhooks fallidos

---

## 📚 10. Referencias

- [Documentación de Webhooks de Wompi](https://docs.wompi.co/docs/es/webhooks)
- [Verificación de Firma](https://docs.wompi.co/docs/es/webhooks#verificaci%C3%B3n-de-firma)
- `/app/subscriptions/views.py` - Implementación del webhook
- `/app/subscriptions/models.py` - Modelo WebhookEvent
- `/app/subscriptions/admin.py` - Admin de WebhookEvent
- `/app/WOMPI_PAYMENT_FLOW.md` - Flujo completo de pagos
