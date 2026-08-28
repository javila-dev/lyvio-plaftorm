# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: PYMEs y negocios en LatAm (especialmente Colombia) sin equipo técnico, que quieren automatizar la atención al cliente por WhatsApp/Instagram/Gmail con IA sin lidiar con la complejidad de operar Chatwoot directamente. Verticales servidas explícitamente vía plantillas de bot: salud/médico, inmobiliario, ventas, servicio al cliente, soporte.

Secondary: equipo interno de Lyvio (staff/superadmin) que opera el panel de administración (`dashboard:admin_dashboard`) para gestionar compañías, suscripciones y soporte.

## Product Purpose

Lyvio es una plataforma SaaS que envuelve Chatwoot (motor de conversación open-source) con IA (RAG vía pgvector) y automatización (N8N) para darle a un negocio un chatbot funcional en sus canales de mensajería, con onboarding, facturación y aprovisionamiento de cuenta 100% self-service. Éxito = el negocio activa su bot y mantiene una suscripción de pago activa (conversión de trial a pago).

## Positioning

Diferenciador frente a Chatwoot puro o herramientas como Wati: bot-builder no-code con plantillas preconfiguradas por industria (p. ej. bot médico con integración obligatoria de Cal.com para agendar citas), aprovisionamiento automático de la cuenta Chatwoot del cliente, pasarela de pago local (Wompi, Colombia) integrada al ciclo de suscripción, y toda la experiencia en español pensada para el mercado LatAm.

## Operating Context

- Backend Django 4.2 + PostgreSQL con `pgvector`, MinIO para archivos, Celery/Redis para tareas asíncronas.
- Servicios externos: Chatwoot (inbox/motor de conversación), N8N (automatizaciones y webhooks), Wompi (pagos, Colombia).
- Flujo típico: landing → selección de plan → registro de compañía → pago (Wompi) o trial → aprovisionamiento de cuenta Chatwoot vía N8N → bot builder (tono, sector, documentos) → operación diaria vía botón "Volver a Lyvio" (redirige al inbox de Chatwoot en `app.lyvio.io`).
- SSO v2 permite acceso sin email usando `chatwoot_account_id` (tokens de un solo uso, expiran en 5 minutos).
- Suspensión y reactivación de suscripciones automatizada por cron diario en N8N + API Django (`X-API-Key`).

## Capabilities and Constraints

- Debe mantenerse la integración con Chatwoot como motor real de conversación — Lyvio no reemplaza el inbox, lo envuelve y simplifica.
- Plantillas de bot por industria: doctor/salud (Cal.com obligatorio), inmobiliario, ventas, servicio al cliente, soporte.
- Límites de uso por plan (mensajes, conversaciones, documentos) durante el trial.
- Pagos y suscripciones ligados a Wompi (Colombia); moneda y facturación local.
- Ingesta de documentos con vectorización (pgvector) vía N8N para RAG del bot.
- Terminología: "Compañía" (`Company`) = cuenta cliente; "Bot" = inbox configurado en Chatwoot; `Trial` y `Subscription` son modelos separados y mutuamente excluyentes en el ciclo de vida de una compañía.

## Brand Commitments

- Nombre de marca: Lyvio ("Powered by 2Asoft" en el footer).
- Dominios de producto: `app.lyvio.io` (Chatwoot), `platform.lyvio.io` (API/plataforma), `lyvio.io` (landing).
- El propio código de la landing referencia "estilo Wati" (layout hero a 2 columnas, métricas destacadas) como inspiración de layout — tratar como referencia de composición, no como autoridad visual definitiva ni compromiso de marca.
- **Continuidad con Chatwoot (confirmado 2026-08-26):** la plataforma Django (`platform.lyvio.io`, superficie Operar) debe adoptar el sistema visual real de Chatwoot en `app.lyvio.io`, verificado en vivo: modo oscuro por defecto, fondos casi negros en escala Radix (`slate-2 ≈ #18191B`, texto `slate-12 ≈ #EDEEF0`), color de marca/acento real `#2781F6` (clase `bg-n-brand`), tipografía de sistema sin webfont, radios de 8px (`rounded-lg`), microinteracciones `active:scale-[0.97-0.98]` + `hover:brightness-110`, sin sombras duras. Objetivo: que saltar entre `app.lyvio.io` y `platform.lyvio.io` se sienta como la misma app, no un cambio de producto.
- **Landing como estándar de categoría (confirmado 2026-08-26):** para la landing (superficie Persuadir), el usuario eligió deliberadamente NO inventar un mundo visual propio, sino ejecutar la convención de categoría (landing SaaS de WhatsApp-business/chatbot) a calidad plena — medida contra **Wati, ManyChat y Chatwoot.com** como vara de craft. Libertad total de paleta (no se fuerza el azul `#2781F6` de Chatwoot aquí). Es una decisión de convención explícita, no timidez: ejecutar sin ironía ni excentricidad.
- **Acento de la landing (confirmado 2026-08-26):** tras probar un coral (`#FF4D3D`) que no convenció al usuario, el acento se re-derivó por muestreo real de píxeles del logo (`static/img/logo.png` / `logo_long.png`): tanto el ícono como el wordmark caen consistentemente en `rgb(142,187,254)`. Ese tono se usa como `--brand-soft` (tags, detalles sobre fondo oscuro); una versión más saturada y oscura de la misma familia, `#3A5FDB` (contraste 5.5:1 sobre blanco), lleva los CTA/hitos. Mismo eje de tono que el azul real de Chatwoot (`#2781F6`) sin ser idéntico — "misma familia, no gemelo idéntico".

## Evidence on Hand

- Logos reales de clientes en `static/img/marcas-confian/`: Andina Conceptos, Casas de Verano, Alttum Collection, Meraki. Es la única prueba social real disponible.
- No hay testimonios, métricas de resultados ni casos de éxito reales documentados — trabajo futuro no debe inventarlos ni fabricar cifras o testimonios.
- Documentos legales reales existentes: política de privacidad, términos de servicio, política de eliminación de datos (`static/files/*.pdf`).

## Product Principles

1. Chatwoot es el motor, Lyvio es la capa de simplicidad — nunca ocultar ni duplicar funcionalidad que Chatwoot ya resuelve bien.
2. Self-service de punta a punta: una PYME sin soporte técnico debe poder registrarse, pagar (o iniciar trial) y activar su bot sin intervención manual.
3. Local primero: español, pagos en pesos colombianos vía Wompi, cumplimiento de normativa de datos colombiana.
4. No inventar prueba social: usar solo los logos de clientes reales disponibles; no fabricar testimonios ni métricas hasta tener evidencia real.
5. La confianza es el producto: un negocio delega su atención al cliente a un bot; la plataforma debe transmitir seriedad y control, no ruido visual.
