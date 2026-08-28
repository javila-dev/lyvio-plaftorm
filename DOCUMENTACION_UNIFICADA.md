# Documentación Operativa Lyvio

Esta guía resume la información clave de las notas históricas del proyecto. Cada sección conserva los datos operativos que aportan valor diario al equipo y omite duplicaciones o ejemplos extensos que ya están incorporados en el código.

## Automatizaciones y Webhooks N8N

### Reactivación de suscripciones
- **Trigger:** Django invoca `notify_n8n_subscription_reactivated` al reactivar/renovar con éxito.
- **Seguridad:** Header `X-API-Key` con el valor de `N8N_WEBHOOKS_TOKEN` (mantenerlo en `.env` y variables de N8N, nunca en texto plano).
- **Flujo sincrónico:** Django espera `200 OK` antes de actualizar la base de datos; si N8N falla o responde distinto de `success: true`, se aborta la reactivación y se informa al usuario.
- **Pasos en N8N:** Webhook → Function que prepara features → PATCH a Chatwoot → Respuesta JSON `{success: true}` → 200 OK a Django.
- **Campos mínimos del payload:** `event`, `subscription_id`, `company_id`, `chatwoot_account_id`, `plan_id`, `plan_name`, `billing_cycle`, fechas de periodo, `platform_token`.

### Suspensión automática de suscripciones canceladas
- **Programación:** Trigger diario (02:00 America/Bogota).
- **API Django:** `GET /dashboard/api/subscriptions/cancelled-to-suspend/` autenticado con `X-API-Key: CHATWOOT_PLATFORM_TOKEN`.
- **Proceso:** N8N itera la lista, actualiza la cuenta en Chatwoot (PATCH `accounts/{id}`), marca la suscripción como `suspended` en Django y puede notificar al usuario.
- **Datos clave en la respuesta:** `subscription_id`, `chatwoot_account_id`, plan, `current_period_end`, `days_expired`, identificadores de Wompi.

### Checklist de seguridad compartida
- [ ] Configurar Header Auth en los webhooks de N8N con `N8N_WEBHOOKS_TOKEN`.
- [ ] Validar respuestas 401 para requests sin token o token inválido.
- [ ] Registrar pruebas manuales (curl) antes de mover a producción.

## Autenticación y Control de Acceso

### SSO v2 (Chatwoot Account ID)
- **Objetivo:** Permitir acceso sin email usando `chatwoot_account_id`.
- **Características:** Tokens de un solo uso (expiran en 5 minutos), validación de suscripción activa y selección del primer usuario activo de la compañía.
- **Flujo:** N8N genera token → Django valida shared secret y timestamp → Ubica o crea la compañía → asegura suscripción activa → inicia sesión con un usuario elegible → invalida el token.
- **Alertas:** Monitorizar métricas de tokens generados/usados/expirados para detectar anomalías.

### Email opcional en el endpoint SSO
- **Cambio:** `/api/sso/generate-token/` ya no requiere `email` ni `chatwoot_user_id`.
- **Implementación técnica:** Ajustes en `sso/views.py`, migración `0002_make_email_optional`, y validaciones para compañías, suscripciones y usuarios antes de conceder acceso.
- **Impacto:** Mantiene compatibilidad retroactiva; los clientes existentes pueden seguir enviando email si lo desean.

### Onboarding y `chatwoot_user_id`
- Se almacena `chatwoot_user_id` en el usuario al finalizar el onboarding (`activation/views.py`).
- Scripts auxiliares (opcional) permiten auditar o completar IDs faltantes recorriendo compañías y comparando usuarios recientes.

## Plataforma Lyvio

### Backend (Django)
- **Stack:** Django 4.2, PostgreSQL 13+ con `pgvector`, MinIO para archivos, Celery/Redis, N8N y Chatwoot como servicios externos.
- **Apps principales:** `accounts`, `activation`, `bots`, `bot_builder`, `dashboard`, `subscriptions`, `onboarding`.
- **Modelos clave:**
  - `Company`: datos corporativos, relación 1:1 con `Subscription` y `Trial`, credenciales de Chatwoot.
  - `BotConfig`: configuración IA (tono, sector, prompts, documentos asociados).
  - `Subscription` y `Trial`: seguimiento de plan, ciclo de facturación, integración con Wompi.
- **Procesos críticos:** ingesta de documentos (validaciones de plan, tamaño y formato, subida a MinIO, vectorización vía N8N), gestión de límites de plan y comunicación con Chatwoot.

### Operación y despliegue
- **Configuración inicial:** instalar dependencias, definir `.env`, ejecutar migraciones, crear superusuario.
- **Servicios auxiliares:** `celery -A lyvio worker -l info` y `celery -A lyvio beat` para tareas recurrentes.
- **Integraciones externas:** Wompi (pagos), Chatwoot (accounts/features), N8N (webhooks), MinIO (almacenamiento), Auth tokens administrados en `.env`.

### Interfaz de usuario (UI)
- **Estructura de templates:** `base.html` global, `subscriptions/base.html` con sidebar, vistas de dashboard y bot builder organizadas por secciones.
- **Bot Builder:** pasos guiados para elegir tipo de bot, tono, sector, contexto y documentos; validaciones dinámicas según plan y tipo de bot.
- **Validaciones visuales:** uso consistente de alertas Bootstrap (`success`, `error`, `warning`, `info`) y mensajes flash de Django.
- **Componentes reutilizables:** formularios para tono/sector, cargas de documentos, toasts de retroalimentación y toggles condicionales (ej. integración Cal.com obligatoria para bot médico).

### API pública
- **Base URL:** `https://platform.lyvio.io`.
- **Autenticación:** API Key mediante header `X-API-Key` (recomendado) o query param.
- **Endpoints principales:** suscripciones activas, renovaciones próximas, trials activos o por expirar, bots y webhooks para sincronización con N8N.
- **Respuestas:** JSON estructurado; revisar límites de paginación y filtros (`?days_until_expiry`, `?include_expired=true`).

## Experiencia de Usuario y Dashboard

- **Reactivación visible:** Alertas destacadas para suscripciones canceladas (con texto diferenciado según período de gracia) y tarjetas de acción que enlazan a reactivar o renovar.
- **Botón “Volver a Lyvio”:** En la barra superior (`templates/base.html`), visible solo cuando el usuario tiene compañía y `chatwoot_account_id`. Abre Chatwoot en nueva pestaña.
- **Plan admin (Django admin):** Formulario personalizado que descompone `features` en checkboxes agrupadas por categorías, evita errores al editar JSON manualmente.
- **Bot médico:** Integración Cal.com obligatoria; el toggle se fuerza a ON, campos de API Key/Event ID/URL son requeridos y se refuerza visualmente la obligatoriedad.

## Integraciones y Migraciones

### Calendly → Cal.com
- **Motivo:** Límites del plan gratuito de Calendly y mejor soporte white-label con Cal.com.
- **Estrategia sugerida:** Renombrar campos a genéricos (`calendar_provider`, `booking_url`, `api_key`), mantener compatibilidad temporal con `calendly_*`, y migrar datos con scripts que actualicen compañías/bots.
- **Checklist:** Actualizar credenciales, revisar flujos que consumen la API, ajustar UI y documentación para el nuevo proveedor.

## Licencias y Terceros

- La interfaz de administración incluye Select2 bajo licencia MIT. Conservar en el repositorio una referencia a la licencia original ubicada en `staticfiles/admin/{js,css}/vendor/select2/`.

## Próximos pasos sugeridos

- Validar en N8N que los webhooks críticos tienen Header Auth configurado.
- Revisar métricas de SSO y tasas de tokens expirados para detectar ajustes necesarios.
- Programar pruebas UX en staging para las pantallas de reactivación y bot builder.
