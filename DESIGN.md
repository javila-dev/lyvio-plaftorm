---
name: Lyvio Landing
description: Landing SaaS de WhatsApp-business ejecutada al estándar de categoría, en el azul real del logo sobre papel cálido.
colors:
  ink: "#2A2723"
  ink-soft: "#5C5648"
  ink-faint: "#726B5A"
  paper: "#FBF8F2"
  paper-tint: "#F3EEE4"
  paper-tint-2: "#EFE8D8"
  line: "#E6DECB"
  brand-soft: "#8EBBFE"
  brand: "#3A5FDB"
  brand-strong: "#2E4FD1"
  brand-deep: "#1B2C7A"
  ok: "#1D9A6C"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(2.75rem, 6vw, 5rem)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(2rem, 4vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(0.9375rem, 1.5vw, 1.1875rem)"
    fontWeight: 700
    lineHeight: 1.15
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(0.8125rem, 1vw, 1.1875rem)"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(0.6875rem, 1vw, 0.75rem)"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  sm: "8px"
  md: "14px"
  lg: "20px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "24px"
  lg: "48px"
  section: "96px"
components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "14px 26px"
  button-primary-hover:
    backgroundColor: "{colors.brand-strong}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "14px 26px"
  plan-card-featured:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "32px 28px"
---

# Design System: Lyvio Landing

## Overview

**Creative North Star: "Papel de Confianza"**

La landing juega la convención de categoría (lo que Wati, ManyChat o Chatwoot.com ya ejecutan bien) sin ironía ni excentricidad, pero se niega a hacerlo en el gris frío y el gradiente morado-neón que tenía antes. Todo el lienzo es un papel cálido — el mismo tono de un recibo o una hoja de cuaderno, nunca blanco de hospital — y encima de ese papel vive un azul saturado, muestreado directamente del logo real de Lyvio (no inventado). El verde solo aparece donde algo está genuinamente confirmado o resuelto: un check, un sello "al día". Nunca es un segundo color de marca.

**Revisión 2026-08-26 — "se siente genérico, todo cuadrado":** tras vivir con la primera versión (estrictamente Restrained: azul solo en botones/hitos), el usuario pidió más vida y modernidad sin perder elegancia. La respuesta no fue un mundo visual nuevo — es la misma paleta, la misma tipografía, el mismo papel cálido — sino una estrategia de color de **dos velocidades**: el cuerpo de la página se mantiene Restrained (azul como acento puntual sobre papel), pero el **hero y el CTA final se comprometen de pared a pared** en `--brand-deep` (#1B2C7A, un paso más oscuro del mismo matiz), con tipografía mucho más grande (hasta 5rem) y profundidad real (la tarjeta de chat flota con sombra dramática y rotación sutil). La página abre y cierra con un golpe de color; respira en calma entre esos dos extremos.

La sensación de los componentes sigue siendo directa y sin degradados — la audacia nueva viene de escala tipográfica, bloques de color de página completa y profundidad real, nunca de gradientes ni ornamento.

**Key Characteristics:**
- Fondo de papel cálido, nunca gris frío ni blanco puro — en el cuerpo de la página.
- El mismo azul, en tres pasos: claro (detalles), saturado (acentos/botones), profundo (hero y CTA final de pared a pared).
- Verde reservado estrictamente a estados de éxito/confirmación, cobertura mínima.
- Cero degradados en todo el sitio, cero patrones decorativos flotantes, cero iconografía genérica de "IA".
- Contraste de escala tipográfica deliberado: títulos de sección grandes, el hero y el CTA final aún más.
- Inter como única tipografía, cifras siempre tabulares.

## Colors

Paleta de dos temperaturas: neutros cálidos (papel/tinta) que hacen de fondo, y un azul frío-saturado que corta contra ellos como el único acento real.

### Primary
- **Azul Lyvio** (`#3A5FDB`): CTA primario, enlaces destacados, bordes de plan resaltado, palabra clave del titular. Contraste 5.5:1 sobre `--paper`. Es una versión más oscura y saturada del mismo matiz (~216°) que aparece en el logo — nunca un azul distinto.
- **Azul Lyvio, hover** (`#2E4FD1`): estado hover/active de todo lo que use el azul primario.

### Secondary
- **Azul de logo** (`#8EBBFE`): el tono exacto muestreado de `static/img/logo.png` (rgb 142,187,254 en el ícono y el wordmark). Vive en detalles sobre fondo oscuro o saturado: la etiqueta "Hecho para Colombia" en DIAN, la palabra destacada del `h1` sobre el hero azul, el ícono de los checks dentro de tarjetas con `--brand` de fondo. Nunca lleva texto de cuerpo largo. (`--brand-tint`, el tinte claro que antes vivía detrás de los íconos, se retiró el 2026-08-26 — los íconos de Features/Verticals pasaron a círculo `--brand` sólido con símbolo blanco, más presencia que un tinte de fondo.)
- **Azul profundo** (`#1B2C7A`): mismo matiz que `--brand`, un paso más oscuro en su propia rampa tonal. Exclusivo de los dos bookends de página completa (hero, CTA final) — nunca en un componente suelto dentro del cuerpo de la página.

### Tertiary
- **Verde confirmado** (`#1D9A6C`): exclusivamente checkmarks, el punto "en línea" del chat de ejemplo, y el sello "AL DÍA" de la sección DIAN. No es un acento de marca — es un color de estado, y su área en pantalla se mide en píxeles de ícono, no en superficies.

### Neutral
- **Tinta** (`#2A2723`): texto de encabezados, fondo de la sección DIAN.
- **Tinta suave** (`#5C5648`): cuerpo de texto.
- **Tinta tenue** (`#726B5A`): texto secundario/hints, íconos inactivos. Corregido desde `#8F8878` (3.3–3.5:1, bajo AA) a 4.99–5.29:1 sobre papel/blanco tras el critique del 2026-08-26.
- **Papel** (`#FBF8F2`): fondo base de la página.
- **Papel con tinte** (`#F3EEE4`): fondo de secciones alternas (features, franja de logos).
- **Papel con tinte 2** (`#EFE8D8`): fondo de tarjetas de features/íconos.
- **Línea** (`#E6DECB`): bordes y separadores.

### Named Rules
**The One Blue Rule (revisada 2026-08-26).** El azul es el único color que puede cubrir una superficie — pero ahora en dos registros deliberados, no uno: `--brand` en botones/bordes/hitos puntuales dentro del cuerpo de la página, y `--brand-deep` cubriendo secciones enteras solo en los dos bookends (hero, CTA final). Fuera de esos dos lugares, sigue prohibido que el azul (o cualquier otro color) cubra una superficie grande — la excepción es nombrada y limitada, no una puerta abierta. El verde nunca cubre superficies, en ningún registro.

**The Warm Neutral Rule.** Ningún gris de este sistema es un gris frío. Cada neutro (`ink`, `ink-soft`, `ink-faint`, `paper`, `paper-tint`, `line`) lleva un matiz cálido (arena/marrón), incluso en tonos casi negros o casi blancos.

### Documented exceptions
- **Blanco puro** (`#fff`): texto sobre superficies oscuras (barra del chat de ejemplo, sección DIAN, ícono de WhatsApp) y fondo de la ficha de factura flotante. No es parte de la escala de papel — es "blanco literal sobre oscuro", una convención distinta y aceptada.
- **`#D6CBB0`** (thumb del scrollbar): un paso intermedio entre `line` y `ink-faint` que no vale la pena tokenizar como color de marca; vive solo en `::-webkit-scrollbar-thumb`.

## Typography

**Display Font:** Inter (con system-ui, -apple-system, 'Segoe UI', Roboto como fallback)
**Body Font:** Inter (misma familia, sin segunda tipografía)

**Character:** Una sola voz tipográfica de principio a fin — la landing, el logo y (por decisión explícita del usuario) la futura plataforma comparten Inter/system-sans, así que no hay fricción tipográfica entre superficies. Es la elección deliberada del camino "canon": ejecutar el estándar de categoría con una grotesca de trabajo, no una serif/display con personalidad propia.

### Hierarchy
- **Display** (700, `clamp(2.125rem, 5vw, 3.375rem)`, line-height 1.15): titular del hero, una sola vez por página.
- **Headline** (700, `clamp(1.375rem, 3vw, 2.5rem)`, line-height 1.15): título de cada sección (`h2`), título de comparación de planes, CTA final.
- **Title** (700, `clamp(0.9375rem, 1.5vw, 1.1875rem)`): nombre de plan, título de tarjeta de feature/vertical, precio destacado.
- **Body** (400, `clamp(0.8125rem, 1vw, 1.1875rem)`, line-height 1.6, medida ≤62ch): párrafos, descripciones, ítems de lista, celdas de tabla.
- **Label** (700, `clamp(0.6875rem, 1vw, 0.75rem)`, tracking 0.04em, mayúsculas): encabezados de tabla, badges, etiqueta de plan destacado.

**Escala real (no un sistema de 5 pasos rígido):** dentro de cada rol de arriba, el tamaño exacto se afina por componente en el mismo paso ~1px que ya usa el resto del sitio — 11 / 12 / 13 / 14 / 15 / 16 / 17 / 18 / 19 / 22 / 34 / 36 / 38 / 40 / 54px, siempre Inter, siempre dentro del rol que le corresponde por jerarquía. No es deriva: es afinación fina intencional, no una escala de 4 tamaños fijos.

### Named Rules
**The Tabular Numerals Rule.** Todo precio, conteo o cifra de comparación de planes lleva `font-variant-numeric: tabular-nums`. Los números nunca "bailan" al cambiar de plan o fila.

## Layout

Contenedor centrado a 1180px máximo, padding lateral 24px. Ritmo vertical de secciones a 96px (64px en mobile ≤860px). El hero usa una grilla de 2 columnas asimétrica (`1.05fr 0.95fr`, texto a la izquierda / mockup de chat a la derecha) que colapsa a una columna centrada bajo 860px.

**The No-Repeated-Grid Rule (confirmado 2026-08-26, tras feedback de "se siente genérico, todo cuadrado").** Ninguna sección puede repetir la silueta "encabezado + grid uniforme de tarjetas iguales" de la sección inmediatamente anterior — es el antipatrón que el propio craft-floor prohíbe ("same-size cards... cards are the lazy container"). Por eso:
- **Logos + Canales** viven en una sola sección (antes eran dos franjas casi idénticas seguidas).
- **Features** usa un grid asimétrico `1.15fr 1fr` con la primera tarjeta ocupando las dos filas (líder visual + 2 apiladas), no 3 cuadros iguales.
- **Verticals** es una tira con scroll horizontal y snap (`overflow-x: auto; scroll-snap-type: x proximity`), no un grid estático — y alterna el fondo con la sección anterior (`--paper` tras el `--paper-tint` de Features) en vez de repetirlo.
- El ritmo de fondo completo es: papel → papel (logos/canales) → tinte (features) → papel (verticals) → tinte (inbox preview) → oscuro (DIAN) → papel (precios/CTA) — nunca dos secciones seguidas con el mismo fondo Y la misma silueta de grid a la vez.

## Motion

**Lenis** (`lenis@1.3.26`, CDN) maneja scroll con inercia en todo el sitio — corre sobre el scroll nativo, nunca pelea con `position: sticky` (header) ni con `IntersectionObserver` (reveal). Se desactiva por completo si `prefers-reduced-motion: reduce`. Los enlaces internos (`href="#..."`) usan `lenis.scrollTo()` con offset `-76px` (alto del header) en vez del salto nativo del navegador.

**The Cascade Rule.** Dentro de `.feature-grid` y `.vertical-grid`, los hijos revelan en cascada (`transition-delay` creciente por `nth-child`, 0.06–0.08s de paso) en vez de aparecer todos a la vez — sigue siendo el único momento de reveal autorizado, solo con más pulso. No agregar retrasos de cascada a grupos fuera de esos dos.

## Elevation & Depth

Sistema plano por defecto: las superficies en reposo no llevan sombra. La sombra aparece únicamente como respuesta — hover de una tarjeta, el CTA primario, la ficha de factura DIAN flotando sobre el fondo oscuro. Todas las sombras llevan un tinte cálido (`rgba(42,39,35,...)`), nunca negro puro, y el botón primario además lleva un halo del propio azul de marca (`rgba(58,95,219,...)`) en vez de un halo neutro.

### Shadow Vocabulary
- **Ambient sm** (`0 1px 2px rgba(42,39,35,0.06)`): borde inferior sutil de superficies flotantes (header).
- **Ambient** (`0 1px 2px rgba(42,39,35,0.05), 0 12px 28px -10px rgba(42,39,35,0.18)`): tarjetas y elementos elevados en reposo/hover.
- **Brand glow** (`0 10px 20px -8px rgba(58,95,219,0.55)`): exclusiva del botón primario, refuerza que ese botón es la acción de marca.

### Named Rules
**The Real-Elevation Rule (revisada 2026-08-26, reemplaza "Flat-By-Default").** Tras el feedback de "todo se siente plano", las tarjetas (`.feature`, `.vertical-card`, `.plan-card`) dejaron de depender del borde de 1px como única señal — ahora cargan una sombra cálida real en reposo (`rgba(42,39,35,...)`, nunca negra pura) y crecen al hover. No es decorativo: cada tarjeta debe leerse como un objeto elevado sobre la página, no un contorno dibujado. La ficha DIAN y el mockup de chat del hero van más lejos — flotan con una leve rotación (±1–3°) además de la sombra, el gesto más dramático reservado a los dos elementos que literalmente "flotan" sobre un fondo oscuro/saturado.

## Shapes

Escala de radios de tres pasos — 8px (botones, inputs, chips de ícono), 14px (tarjetas de contenido estándar: features, verticales), 20px (superficies grandes: tarjetas de plan, mockup de chat). Insignias, tags y el chip de canal usan radio 999px (píldora completa). Sin bordes duros ni esquinas cuadradas en ningún componente interactivo.

**Excepción documentada:** el anillo de foco (`:focus-visible`) usa 4px, no la escala de 8/14/20 — es un contorno de accesibilidad, no una superficie, y sigue su propia convención minimalista.

## Components

### Buttons
- **Shape:** radio 8px (`--radius-sm`) en todos los botones.
- **Primary:** fondo `--brand`, texto blanco, halo azul propio (`brand glow`), padding `14px 26px` (`16px 30px` en `.btn-lg`).
- **Hover / Focus:** primary oscurece a `--brand-strong` + `translateY(-1px)`; el anillo de foco (`:focus-visible`) es `2px solid var(--brand)` con `outline-offset: 3px` en todo elemento interactivo del sitio.
- **Secondary:** fondo `--paper`, borde `--line`, texto `--ink`; hover oscurece el borde y tiñe el fondo con `--paper-tint`.
- **Ghost:** solo texto `--ink`, hover pasa a `--brand-strong`.

### Chips
- **Channel chip:** píldora con fondo `--paper-tint`, borde `--line`, ícono en su color de marca real (WhatsApp `#25D366`, Instagram `#E4405F`, Messenger `#0084FF`, Telegram `#229ED9`) — la única excepción documentada a "un solo azul": los logos de canal externos conservan su color oficial porque son identidad ajena, no acento propio.
- **DIAN tag:** píldora sobre fondo oscuro, texto y borde en `--brand-soft` al 16–35% de opacidad — el único lugar donde el azul claro del logo lleva texto legible.

### Cards / Containers
- **Corner Style:** 14px (feature/vertical) o 20px (plan, chat-demo).
- **Background:** `--paper` sobre fondo de página `--paper-tint`, o al revés — siempre hay contraste de un paso entre tarjeta y fondo.
- **Shadow Strategy:** ver Elevation — plano en reposo, `--shadow` al hover.
- **Border:** `1px solid var(--line)`; el plan destacado sube a `2px solid var(--brand)`.
- **Internal Padding:** 28–32px.

### Navigation
- **Style:** header sticky con blur (`backdrop-filter: blur(10px)`) sobre `rgba(251,248,242,0.86)` — el mismo papel cálido, solo translúcido. Enlaces en `--ink-soft`, hover a `--ink`. En mobile (≤860px) la navegación de texto se oculta, solo quedan logo + CTA primario + botón de menú.

### DIAN Receipt (signature component)
Única superficie de la página con fondo `--ink` completo (sección "Facturación DIAN"). Sobre ese fondo flota una ficha blanca (`.dian-receipt`) con líneas tipo recibo (`border-bottom: 1px dashed`) y un sello verde rotado -2° ("AL DÍA") — el único lugar del sitio donde el verde se permite un borde propio, no solo un ícono.

### Inbox Preview (excepción documentada a la paleta cálida, agregada 2026-08-27)
Sección `#inbox-preview` (entre Verticals y DIAN, fondo `--paper-tint`): una recreación autoría del inbox real de Chatwoot (`.inbox-mockup`), no una captura de pantalla real — todos los nombres, mensajes y contadores son inventados, sin datos reales de clientes. Es la única superficie del sitio que **no** usa la paleta papel/tinta — usa un set de tokens local (`--iv-bg`, `--iv-surface`, `--iv-text`, `--iv-brand: #2781f6`, etc., con prefijo `--iv-` para no colisionar con `:root`) que reproduce el tema oscuro real del producto (el mismo `#2781f6` que gobierna `subscriptions/base.html`, la plataforma autenticada). La lógica es la misma ya documentada para los íconos de canal: es identidad prestada de un software real, no un acento de marca propio de la landing, así que no se fuerza al papel cálido. Layout de 3 columnas (nav icon-rail 68px / lista de conversaciones 296px / hilo de chat) que colapsa a solo el hilo en ≤860px (`.inbox-mockup__nav` y `.inbox-mockup__list` se ocultan). Texto secundario usa `--iv-text-muted` (6.1:1 sobre `--iv-bg`), nunca `--iv-text-faint` (3.4:1, insuficiente para texto real — reservado a íconos decorativos donde el umbral AA no aplica).

## Do's and Don'ts

### Do:
- **Do** usar `--brand` (`#3A5FDB`) para toda acción primaria e interactiva destacada; es el único color con permiso de cubrir superficies grandes.
- **Do** mantener todos los neutros cálidos (arena/marrón), nunca gris frío puro.
- **Do** limitar `--ok` (verde) a checkmarks, estados "activo/en línea" y el sello DIAN — nunca fondos ni botones.
- **Do** usar `font-variant-numeric: tabular-nums` en cualquier cifra (precios, conteos, comparaciones).
- **Do** dejar que los logos de canal (WhatsApp, Instagram, Messenger, Telegram) conserven su color oficial — es la única excepción a "un solo azul".

### Don't:
- **Don't** introducir un segundo color saturado de marca (ni morado, ni coral/naranja — ya se probó y se descartó explícitamente).
- **Don't** usar gradientes en texto, fondos o botones en ningún punto del sitio.
- **Don't** repetir patrones decorativos de íconos flotantes de fondo (el sistema anterior lo hacía; quedó descartado junto con el resto del mundo visual viejo).
- **Don't** usar un eyebrow/kicker sobre ningún `h2` — el título lleva su propio peso.
- **Don't** inventar métricas o testimonios sin evidencia real (principio ya fijado en `PRODUCT.md`: solo existen 4 logos de cliente reales, ningún dato de resultado).
