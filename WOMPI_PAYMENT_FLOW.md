# 💳 Flujo de Pagos con Wompi - Documentación Técnica

## 📋 Índice
1. [Estados de Transacciones](#estados-de-transacciones)
2. [Flujo de Primer Pago (Onboarding)](#flujo-de-primer-pago-onboarding)
3. [Flujo de Renovación Manual](#flujo-de-renovación-manual)
4. [Webhook de Wompi](#webhook-de-wompi)
5. [Manejo de Estados PENDING](#manejo-de-estados-pending)
6. [Casos Edge y Recuperación](#casos-edge-y-recuperación)

---

## 🎯 Estados de Transacciones

### Estados de Wompi:
- **`PENDING`**: Transacción creada, esperando confirmación del banco
- **`APPROVED`**: Pago aprobado y confirmado
- **`DECLINED`**: Pago rechazado por el banco
- **`ERROR`**: Error en el procesamiento
- **`VOIDED`**: Transacción anulada

### Estados de Suscripción en Lyvio:
- **`pending`**: Suscripción creada, esperando confirmación de pago
- **`active`**: Suscripción activa con pago confirmado
- **`cancelled`**: Suscripción cancelada por el usuario (dentro del período pagado)
- **`suspended`**: Suscripción suspendida por falta de pago
- **`past_due`**: Pago vencido, en período de gracia

### Estados de Invoice:
- **`pending`**: Factura creada, pago pendiente
- **`paid`**: Factura pagada
- **`failed`**: Pago fallido

---

## 💰 Flujo de Primer Pago (Onboarding)

### Código: `_process_card_payment()` en `/app/subscriptions/views.py`

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Usuario completa formulario de pago                          │
│    - Plan seleccionado                                           │
│    - Billing cycle (monthly/yearly)                              │
│    - Información de tarjeta                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Tokenización de Tarjeta                                      │
│    - Wompi crea payment_source_id                                │
│    - Se guarda para cobros futuros                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Creación de Transacción                                      │
│    - POST a Wompi con payment_source_id                          │
│    - Reference: LYVIO-FIRST-{plan_id}-{user_id}-{timestamp}     │
│    - Respuesta inicial: Status puede ser PENDING o APPROVED      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. POLLING (30 segundos)                                        │
│    - 15 intentos × 2 segundos                                    │
│    - GET a Wompi: /transactions/{transaction_id}                 │
│    - Verificar status en cada intento                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                    ┌─────┴─────┐
                    │  Status?   │
                    └─────┬─────┘
                          │
         ┌────────────────┼────────────────┬───────────────────┐
         │                │                │                   │
         ▼                ▼                ▼                   ▼
    ┌────────┐      ┌─────────┐     ┌──────────┐       ┌──────────┐
    │APPROVED│      │ PENDING │     │ DECLINED │       │  ERROR   │
    └────┬───┘      └────┬────┘     └────┬─────┘       └────┬─────┘
         │               │               │                   │
         │               │               └───────┬───────────┘
         │               │                       │
         ▼               ▼                       ▼
┌──────────────┐  ┌──────────────┐      ┌──────────────┐
│ Crear        │  │ Crear        │      │ NO crear     │
│ Subscription │  │ Subscription │      │ Subscription │
│ status =     │  │ status =     │      │              │
│ 'active'     │  │ 'pending'    │      │ Lanzar error │
└──────┬───────┘  └──────┬───────┘      └──────────────┘
       │                 │
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Notificar a  │  │ Mensaje:     │
│ Chatwoot     │  │ "Pago en     │
│              │  │ proceso"     │
└──────┬───────┘  └──────┬───────┘
       │                 │
       │                 │
       └────────┬────────┘
                │
                ▼
      ┌──────────────────┐
      │ Webhook de Wompi │
      │ actualizará si   │
      │ PENDING→APPROVED │
      └──────────────────┘
```

### Código Clave:

```python
# Después del polling (líneas 537-571 en views.py)
if transaction_status == 'APPROVED':
    subscription_status = 'active'
    success_message = f'¡Suscripción activada exitosamente!...'
    logger.info(f"✅ Pago APROBADO - Creando suscripción ACTIVA")

elif transaction_status == 'PENDING':
    # ⚠️ IMPORTANTE: Crear suscripción en estado pending
    # El webhook la activará cuando Wompi responda
    subscription_status = 'pending'
    success_message = (
        f'Tu pago está siendo procesado por el banco. '
        f'La suscripción quedará activa automáticamente...'
    )
    logger.warning(
        f"⏳ Pago AÚN PENDING después de 30s - "
        f"Creando suscripción en estado PENDING"
    )
```

---

## 🔄 Flujo de Renovación Manual

### Código: `renew_expired_subscription()` en `/app/subscriptions/views.py`

```
┌─────────────────────────────────────────────────────────────────┐
│ Usuario con suscripción expirada/cancelada                      │
│ Intenta renovar desde dashboard                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Validaciones Previas                                             │
│ ✓ Tiene billing_info?                                            │
│ ✓ Tiene payment_source_id guardado?                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Crear Transacción con Token Guardado                            │
│ - Usa payment_source_id existente                                │
│ - Reference: LYVIO-RENEW-{subscription_id}-{timestamp}          │
│ - NO hay polling, solo respuesta inmediata                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                    ┌─────┴─────┐
                    │  Status?   │
                    └─────┬─────┘
                          │
         ┌────────────────┼────────────────┬───────────────────┐
         │                │                │                   │
         ▼                ▼                ▼                   ▼
    ┌────────┐      ┌─────────┐     ┌──────────┐       ┌──────────┐
    │APPROVED│      │ PENDING │     │ DECLINED │       │  ERROR   │
    └────┬───┘      └────┬────┘     └────┬─────┘       └────┬─────┘
         │               │               │                   │
         │               │               └───────┬───────────┘
         │               │                       │
         ▼               ▼                       ▼
┌──────────────┐  ┌──────────────┐      ┌──────────────┐
│ 1. Notificar │  │ Crear Invoice│      │ Mostrar      │
│    N8N       │  │ status =     │      │ error        │
│              │  │ 'pending'    │      │              │
│ 2. Activar   │  │              │      │ Redirigir    │
│    Sub       │  │ Esperar      │      │ a formulario │
│              │  │ Webhook      │      └──────────────┘
│ 3. Crear     │  └──────┬───────┘
│    Invoice   │         │
└──────┬───────┘         │
       │                 │
       └────────┬────────┘
                │
                ▼
      ┌──────────────────┐
      │ Redirigir a      │
      │ dashboard        │
      └──────────────────┘
```

### Código Clave:

```python
# Líneas 1070-1153 en views.py
if transaction_status == 'APPROVED':
    # Pago aprobado inmediatamente
    # 1. Notificar a N8N
    n8n_response = notify_n8n_subscription_reactivated(subscription)
    if not n8n_response:
        # Crítico: Pago OK pero N8N falló
        # Guardar invoice y notificar equipo
        ...
    # 2. Activar suscripción
    subscription.status = 'active'
    subscription.save()
    # 3. Crear invoice
    Invoice.objects.create(status='paid', ...)
    
elif transaction_status == 'PENDING':
    # Pago pendiente
    Invoice.objects.create(
        status='pending',
        wompi_transaction_id=transaction_id,
        paid_at=None  # Se establecerá en webhook
    )
    messages.info(request, 'Tu pago está siendo procesado...')
```

---

## 🔔 Webhook de Wompi

### Endpoint: `/dashboard/wompi/webhook/`
### Código: `wompi_webhook()` en `/app/subscriptions/views.py` (líneas 1175-1650)

El webhook actúa como **RESPALDO** para casos donde:
1. El usuario cierra el navegador durante el proceso
2. El pago queda PENDING después del timeout
3. Wompi tarda más de 30 segundos en confirmar

```
┌─────────────────────────────────────────────────────────────────┐
│ Wompi envía POST a /dashboard/wompi/webhook/                    │
│ Event: transaction.updated                                       │
│ Header: X-Event-Checksum (firma)                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Verificar Firma (X-Event-Checksum)                           │
│    - Validar autenticidad del webhook                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Extraer Datos de la Transacción                              │
│    - Status: APPROVED / DECLINED / etc                           │
│    - Reference: LYVIO-FIRST- / LYVIO-REC- / LYVIO-RENEW-       │
│    - Transaction ID                                              │
│    - Amount                                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                    ┌─────┴─────┐
                    │  Status?   │
                    └─────┬─────┘
                          │
                          │
                          ▼ (APPROVED)
┌─────────────────────────────────────────────────────────────────┐
│ 3. Buscar Suscripción                                            │
│    Estrategias de búsqueda:                                      │
│    1️⃣ Por wompi_subscription_id (transaction_id)               │
│    2️⃣ Por reference (extraer subscription_id)                   │
│    3️⃣ Por payment_source_id                                     │
│    4️⃣ Por customer_email + timestamp reciente                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                 ┌────────┴────────┐
                 │ ¿Encontrada?     │
                 └────────┬────────┘
                          │
                 ┌────────┴────────┐
                 │ SÍ              │ NO → Log warning
                 ▼                 │
┌──────────────────────────────────┴──────────────────────────────┐
│ 4. Actualizar Suscripción                                        │
│    - Si status='pending': Cambiar a 'active'                     │
│    - Si status='active': Log "webhook duplicado"                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Verificar/Crear Invoice                                       │
│    - Buscar invoice con wompi_transaction_id                     │
│    - Si NO existe: Crear nueva factura                           │
│    - Si existe: Log "factura ya existe"                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Extender Período (si es cobro recurrente)                    │
│    - LYVIO-FIRST-: NO extender (ya tiene período inicial)       │
│    - LYVIO-REC-: Extender según billing_cycle                    │
│    - LYVIO-RENEW-: Calcular nuevo período desde hoy             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                 ┌────────────────┐
                 │ Return 200 OK  │
                 └────────────────┘
```

### Código Clave:

```python
# Líneas 1224-1285 en views.py
if status == 'APPROVED':
    # Buscar suscripción
    subscription = Subscription.objects.filter(
        wompi_subscription_id=transaction_id
    ).first()
    
    if not subscription and reference:
        # Extraer subscription_id de la referencia
        if 'LYVIO-REC-' in reference or 'LYVIO-RENEW-' in reference:
            parts = reference.split('-')
            subscription_id = int(parts[2])
            subscription = Subscription.objects.filter(id=subscription_id).first()
    
    if subscription:
        # Activar si estaba pending
        if subscription.status == 'pending':
            subscription.status = 'active'
            subscription.save()
            logger.info("🎉 Suscripción ACTIVADA - PENDING→ACTIVE")
        
        # Verificar/crear invoice
        existing_invoice = Invoice.objects.filter(
            wompi_transaction_id=transaction_id
        ).first()
        
        if not existing_invoice:
            Invoice.objects.create(
                subscription=subscription,
                amount=transaction_amount,
                status='paid',
                paid_at=timezone.now(),
                wompi_transaction_id=transaction_id
            )
```

---

## ⏳ Manejo de Estados PENDING

### ❓ ¿Qué pasa si después de 30 segundos sigue PENDING?

**ANTES (❌ Comportamiento Incorrecto):**
```python
# Versión antigua - RECHAZABA el pago
if transaction_status != 'APPROVED':
    error_msg = f"El pago no pudo ser confirmado..."
    raise Exception(error_msg)  # ❌ Lanza error
    # Resultado: NO se crea suscripción
    # Problema: Cuando Wompi aprueba después, el webhook no encuentra la suscripción
```

**AHORA (✅ Comportamiento Correcto):**
```python
# Versión nueva - CREA suscripción en estado pending
elif transaction_status == 'PENDING':
    subscription_status = 'pending'  # ✅ Crear en pending
    success_message = 'Tu pago está siendo procesado...'
    logger.warning("⏳ PENDING después de 30s - El webhook la activará")
    
# Resultado:
# 1. Se crea suscripción con status='pending'
# 2. Usuario ve mensaje: "Pago en proceso"
# 3. Webhook activará la suscripción cuando Wompi confirme
```

### 📊 Diagrama de Estados

```
CREAR TRANSACCIÓN
       │
       ▼
┌──────────────┐
│   PENDING    │ ◄─── Transacción creada
└──────┬───────┘
       │
       │ (30 segundos de polling)
       │
       ├───────► ⏱️ Timeout → Crear Subscription status='pending'
       │                      Usuario ve: "Pago en proceso"
       │                      Esperar webhook
       │
       ▼
┌──────────────┐
│   APPROVED   │ ◄─── Banco aprueba
└──────┬───────┘      (puede ser antes o después del timeout)
       │
       ▼
   🔔 WEBHOOK
       │
       ▼
┌──────────────┐
│ Subscription │
│ status =     │
│ 'active'     │
└──────────────┘
```

### 🎯 Casos de Uso:

#### **Caso 1: Pago rápido (< 30s)**
```
Usuario → Wompi (PENDING) → 5 segundos → Wompi (APPROVED)
       → Polling detecta APPROVED
       → Subscription creada con status='active'
       → Usuario ve: "¡Suscripción activada!"
       → Webhook llega después → "Ya está active" (duplicado, ignorado)
```

#### **Caso 2: Pago lento (> 30s)**
```
Usuario → Wompi (PENDING) → Polling 30s → Sigue PENDING
       → Timeout del polling
       → Subscription creada con status='pending'
       → Usuario ve: "Pago en proceso, te notificaremos"
       → 2 minutos después → Banco aprueba
       → Webhook llega con APPROVED
       → Subscription cambia a status='active'
       → Usuario recibe email de confirmación
```

#### **Caso 3: Usuario cierra navegador**
```
Usuario → Wompi (PENDING) → Usuario cierra página
       → NO se completa el flujo del frontend
       → Subscription NO se crea (si fue antes de timeout)
       ⚠️ Problema: Webhook no encuentra suscripción
       
Solución alternativa (en webhook):
       → Webhook busca por payment_source_id
       → Webhook busca por customer_email + timestamp reciente
```

---

## 🚨 Casos Edge y Recuperación

### 1. **Webhook llega ANTES que el polling termine**

**Escenario:**
- Banco muy rápido (< 2 segundos)
- Webhook llega antes del primer intento de polling

**Manejo:**
```python
# En webhook (líneas 1260-1263)
if subscription.status == 'active':
    logger.info("ℹ️ Suscripción ya ACTIVE (webhook duplicado)")
    # No hacer nada, ya está activa
```

### 2. **Webhook llega MÚLTIPLES veces**

**Escenario:**
- Wompi reintenta el webhook si no recibe 200 OK rápido
- Red lenta o servidor ocupado

**Manejo:**
```python
# Verificar invoice existente (líneas 1271-1277)
existing_invoice = Invoice.objects.filter(
    wompi_transaction_id=transaction_id
).first()

if existing_invoice:
    logger.info("ℹ️ Factura ya existe (webhook duplicado)")
    return HttpResponse('OK', status=200)  # Responder OK sin duplicar
```

### 3. **Pago APPROVED pero N8N falla**

**Escenario:**
- Wompi confirma pago (APPROVED)
- N8N no responde o retorna error
- No se puede activar features en Chatwoot

**Manejo:**
```python
# En renovación (líneas 1088-1106)
if not n8n_response:
    logger.error(
        f"CRÍTICO: Pago aprobado pero N8N falló. "
        f"Requiere intervención manual."
    )
    messages.error(
        request,
        'Tu pago fue procesado exitosamente, pero hubo un error '
        'al reactivar tu cuenta de Chatwoot. Nuestro equipo '
        'ha sido notificado...'
    )
    # Guardar invoice para tracking
    Invoice.objects.create(status='paid', ...)
    # NO activar subscription (requiere intervención manual)
```

### 4. **Transacción huérfana (no se encuentra suscripción)**

**Escenario:**
- Webhook recibe APPROVED
- No encuentra suscripción por ninguna estrategia

**Manejo:**
```python
# En webhook (líneas 1367-1465)
# Estrategia 1: Por wompi_subscription_id
subscription = Subscription.objects.filter(
    wompi_subscription_id=transaction_id
).first()

# Estrategia 2: Por reference
if not subscription and reference:
    # Extraer ID de LYVIO-REC-{id}-timestamp
    subscription_id = int(reference.split('-')[2])
    subscription = Subscription.objects.filter(id=subscription_id).first()

# Estrategia 3: Por payment_source_id
if not subscription:
    payment_source_id = transaction_data.get('payment_source_id')
    subscription = Subscription.objects.filter(
        payment_source_id=payment_source_id
    ).first()

# Estrategia 4: Por email + timestamp
if not subscription:
    customer_email = transaction_data.get('customer_email')
    recent_subs = Subscription.objects.filter(
        wompi_customer_email=customer_email,
        created_at__gte=timezone.now() - timedelta(minutes=5)
    ).first()

# Si aún no se encuentra:
if not subscription:
    logger.warning("⚠️ Transacción huérfana - No se encontró suscripción")
    # Enviar alerta a equipo de soporte
    # Guardar en tabla de transacciones huérfanas para revisión manual
```

---

## 📝 Resumen de Cambios Implementados

### ✅ Mejoras en Primer Pago:
- **ANTES:** Lanzaba error si PENDING después de 30s
- **AHORA:** Crea suscripción con status='pending', webhook la activa

### ✅ Mejoras en Renovación:
- **ANTES:** Solo manejaba APPROVED/DECLINED
- **AHORA:** Maneja también PENDING, crea invoice pending

### ✅ Mejoras en Webhook:
- **ANTES:** Solo buscaba por wompi_subscription_id
- **AHORA:** 4 estrategias de búsqueda para encontrar suscripción

### ✅ Mejoras en Mensajes:
- **ANTES:** Error genérico "Pago falló"
- **AHORA:** Mensajes específicos según contexto:
  - "Pago en proceso, te notificaremos"
  - "Pago rechazado por banco"
  - "Error al reactivar Chatwoot (pero pago OK)"

---

## 🔗 Referencias

### Archivos Clave:
- `/app/subscriptions/views.py`: Lógica principal de pagos
  - `_process_card_payment()`: Líneas 445-610 (primer pago)
  - `renew_expired_subscription()`: Líneas 985-1165 (renovación)
  - `wompi_webhook()`: Líneas 1175-1650 (webhook)

- `/app/subscriptions/wompi_service.py`: Cliente de Wompi API
  - `create_transaction_with_token()`: Crear transacción
  - `get_transaction_status()`: Consultar estado
  - `verify_signature()`: Validar webhook

### Documentación de Wompi:
- https://docs.wompi.co/docs/es/pagos-con-tarjeta
- https://docs.wompi.co/docs/es/webhooks

### Otros Documentos:
- `/app/SUBSCRIPTION_REACTIVATION_N8N_FLOW.md`: Flujo de reactivación con N8N
- `/app/DOCUMENTACION_UNIFICADA.md`: Documentación general del proyecto
