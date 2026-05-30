# BananaPay Landing Page — Design Document

> Documento de referencia para diseñadores, desarrolladores y cualquier persona que trabaje sobre el landing de BananaPay. Cubre cada decisión visual, de copy y de experiencia de usuario.

---

## 1. Filosofía de diseño

### Principio central
**Velocidad y simplicidad.** El usuario ecuatoriano promedio está acostumbrado a webs financieras lentas, confusas y llenas de letra pequeña. BananaPay rompe ese patrón: el landing debe comunicar en los primeros 3 segundos que esto es diferente, rápido y para ellos.

### Tres pilares visuales
| Pilar | Descripción |
|---|---|
| **Bold** | Tipografía extra-bold, titulares grandes. No hay timidez visual. |
| **Clean** | Fondo blanco, mucho espacio en blanco. La información respira. |
| **Warm** | El amarillo banana es el acento emocional. Genera confianza sin frialdad corporativa. |

### Referentes
- **Ugly Cash** — tono disruptivo vs. bancos tradicionales, lenguaje directo
- **Stripe** — limpieza visual, tipografía bold, mockups flotantes
- **Revolut** — progresión de secciones, stats prominentes
- **Nubank** — calidez + finanzas, color de marca dominante

---

## 2. Paleta de colores

```
Primarios
─────────────────────────────────────────────────
--yellow:       #facc15   → Amarillo banana — acento principal
--yellow-dark:  #b45309   → Para texto sobre fondo amarillo claro
--yellow-light: #fef9c3   → Fondos de badges, pills, highlights
--black:        #0a0a0a   → Negro casi puro — titulares y texto principal

Grises (sistema)
─────────────────────────────────────────────────
--gray-900:     #111827   → Footer background
--gray-700:     #374151   → Texto secundario, nav links
--gray-500:     #6b7280   → Subtítulos, descripciones
--gray-300:     #d1d5db   → Bordes sutiles, separadores
--gray-100:     #f3f4f6   → Fondo de tarjetas alternativas
--gray-50:      #f9fafb   → Fondo de secciones alternadas
--white:        #ffffff   → Base de la página

Especiales
─────────────────────────────────────────────────
--wa-green:     #25d366   → Verde WhatsApp — solo para CTAs de WhatsApp
--green:        #16a34a   → Verde sistema (éxito, badges)
```

### Reglas de uso de color
- **Amarillo**: nunca como fondo de texto largo. Solo en accents, badges, stats, CTA final y el botón principal.
- **Verde WhatsApp (`#25d366`)**: exclusivo para botones de "Empieza por WhatsApp". No mezclar con el amarillo en el mismo CTA.
- **Negro sobre amarillo**: siempre `--black` (#0a0a0a), nunca blanco. El amarillo es demasiado claro para texto blanco.
- **Secciones alternas**: blanco → gris-50 → negro → blanco. Evita monotonía vertical.

---

## 3. Tipografía

### Fuente
**Inter** (Google Fonts) — cargada en pesos 400, 500, 600, 700, 800, 900.

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
```

Fallback: `system-ui, sans-serif` — garantiza que en caso de fallo de red la tipografía siga siendo limpia.

### Escala tipográfica

| Elemento | Tamaño | Peso | Letter-spacing | Uso |
|---|---|---|---|---|
| Hero H1 | `clamp(48px, 8vw, 88px)` | 900 | -3px | Titular principal del hero |
| Section title | `clamp(32px, 5vw, 52px)` | 900 | -2px | Títulos de cada sección |
| WA section title | `clamp(32px, 4.5vw, 52px)` | 900 | -2px | Título sección oscura |
| Step title | 20px | 800 | -0.3px | Títulos de pasos |
| Feature title | 18px | 800 | -0.3px | Títulos de features |
| Body / Sub | `clamp(17px, 2.5vw, 21px)` | 400 | — | Hero subtitle |
| Section sub | 18px | 400 | — | Subtítulos de sección |
| Nav links | 15px | 500 | — | Menú de navegación |
| Badges / Tags | 13px | 700 | — | Section tags, pills |
| Footer links | 14px | 400 | — | Links del footer |
| Captions | 12px | 500-600 | 0.3-0.8px | Labels, uppercase tags |

### Principios tipográficos
- `letter-spacing: -2px` a `-3px` en titulares grandes → sensación premium, moderno
- `line-height: 1.02` a `1.1` en H1 → titulares muy compactos y poderosos
- `clamp()` en todos los titulares → escala fluida entre mobile y desktop
- `-webkit-font-smoothing: antialiased` → suavizado consistente en Mac/iOS

---

## 4. Animaciones

### Catálogo de keyframes

#### `fadeUp` — Entrada de elementos al cargar
```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(28px); }
  to   { opacity: 1; transform: translateY(0); }
}
```
- **Uso**: badge del hero, H1, subtítulo, CTAs, mockup del teléfono
- **Duración**: 0.7s — suficientemente rápido para no aburrir
- **Delays escalonados**: 0s → 0.1s → 0.2s → 0.3s → 0.45s — cada elemento entra ligeramente después del anterior, creando sensación de "cascade"

#### `float` — Levitación continua
```css
@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50%       { transform: translateY(-10px); }
}
```
- **Uso**: teléfono principal + 4 tarjetas flotantes
- **Duraciones variadas**: 3.5s, 4.2s, 4.5s, 3.8s — evita que todo se mueva sincronizado (se vería mecánico)
- **Delays variados**: 0.3s, 0.6s, 0.9s, 1.2s — asincronía visual natural

#### `pulse-ring` — Pulso del botón WhatsApp principal
```css
@keyframes pulse-ring {
  0%   { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250,204,21,0.5); }
  70%  { transform: scale(1);    box-shadow: 0 0 0 16px rgba(250,204,21,0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250,204,21,0); }
}
```
- **Uso**: único botón "Empieza por WhatsApp" en el hero
- **Duración**: 2.5s infinito
- **Propósito**: atrae la atención al CTA principal sin ser agresivo
- **Se cancela al hover** — el usuario ve que respondió a su interacción

#### `marquee` — Ticker horizontal continuo
```css
@keyframes marquee {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
```
- **Duración**: 24s — velocidad legible sin ser lenta
- **Técnica**: el contenido se duplica exactamente al 50% — el loop es imperceptible
- **Propósito**: llena el espacio entre hero y stats con mensajes de valor, da sensación de actividad

#### `scroll reveal` — Reveal al hacer scroll
- Implementado con **IntersectionObserver** (JavaScript nativo, sin librerías)
- Clase `.reveal` → `opacity: 0; transform: translateY(24px)`
- Al entrar al viewport → añade clase `.visible` → `opacity: 1; transform: translateY(0)`
- `transition: 0.65s ease` — más lento que fadeUp para dar peso a las secciones
- `rootMargin: '0px 0px -40px 0px'` — se activa 40px antes del borde inferior

### Reglas de animación
- **Hover siempre**: toda tarjeta y botón tiene `transform: translateY(-4px)` en hover + sombra aumentada
- **Transición estándar**: `0.2s` para hovers simples, `0.3s` para hover de tarjetas grandes
- **Sin `animation: all`** — siempre animar propiedades específicas para rendimiento

---

## 5. Layout y estructura

### Contenedor
```css
.container { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
```
- Ancho máximo 1120px — ni tan estrecho (960px) ni tan ancho (1280px)
- Padding lateral 24px en todos los breakpoints

### Espaciado de secciones
Todas las secciones usan `padding: 100px 0` — consistencia vertical en desktop. En mobile se reduce a ~64px automáticamente por el tamaño menor del contenido.

### Sistema de grid
| Uso | Columnas |
|---|---|
| Steps (cómo funciona) | `repeat(3, 1fr)` |
| Features | `repeat(3, 1fr)` |
| WhatsApp section | `1fr 1fr` |
| Security section | `1fr 1fr` |
| Testimoniales | `repeat(3, 1fr)` |
| Stats | `repeat(3, 1fr)` |
| Footer | `2fr 1fr 1fr 1fr` |

---

## 6. Secciones — detalle completo

### 6.1 NAV
- **Sticky** — sigue al usuario al hacer scroll
- **Glassmorphism**: `background: rgba(255,255,255,0.88)` + `backdrop-filter: blur(14px)`
- **Altura**: 64px
- **Contenido**: Logo (imagen real) + wordmark | Links de ancla | CTA botón amarillo
- **Mobile**: links y CTA desktop se ocultan, aparece botón "Empieza" compacto

### 6.2 HERO
**Propósito**: Comunicar la propuesta de valor en <5 segundos y empujar al primer CTA.

**Estructura visual**:
```
[Badge: 🇪🇨 Hecho para Ecuador]
[H1: Tu plata, / donde la necesitas. / En segundos.]  ← "En segundos" subrayado amarillo
[Subtítulo: sin banco, sin filas, 0% comisión]
[CTA WhatsApp] [CTA App]
[Mockup teléfono flotando]
  ↖ Tarjeta: ⚡ 2 segundos     Tarjeta: 💸 $0.00 ↗
  ↙ Tarjeta: 🔐 PIN+Biometría  Tarjeta: 🍌 Sin banco ↘
```

**Background**: `radial-gradient(ellipse 80% 50% at 50% -10%, rgba(250,204,21,0.15), transparent)` — halo amarillo sutil que emerge desde arriba, da contexto de marca sin abrumar.

**El subrayado del H1**:
```css
.hero h1 em::after {
  content: '';
  position: absolute; left: 0; bottom: -4px;
  width: 100%; height: 6px;
  background: var(--yellow); border-radius: 100px; opacity: 0.7;
}
```
Elemento decorativo que enfatiza "En segundos" — el beneficio clave.

**Mockup de teléfono**:
- Frame negro con `border-radius: 40px` — simula iPhone
- Pantalla interior: header verde WhatsApp real (`#075e54`)
- Fondo del chat: patrón SVG similar al fondo de WhatsApp
- Conversación simulada muestra el flujo real de BananaPay
- Animación `float` continua — da vida sin distraer

**Tarjetas flotantes**:
- 4 tarjetas, 2 por lado, esquinas del teléfono
- Cada una con animación `float` de duración y delay diferente
- `box-shadow: 0 10px 40px rgba(0,0,0,0.12)` — profundidad sin exagerar
- Se ocultan en tablet/mobile (< 1024px)

### 6.3 MARQUEE
**Propósito**: Transición visual entre hero y stats. Mantiene el ritmo de lectura.

- 7 mensajes de valor, duplicados para loop infinito
- Separador: emoji 🍌 amarillo — refuerza la marca
- Fondo: `--gray-50` — sutil separación del hero
- Velocidad: 24s — legible cómodamente

### 6.4 STATS
**Propósito**: Establecer credibilidad con números concretos.

| Stat | Valor | Significado |
|---|---|---|
| Tiempo | `< 3s` | Velocidad de transferencia — el diferenciador #1 |
| Comisión | `$0` | Entre usuarios BananaPay — 0% |
| Digital | `100%` | Sin banco, sin papeleos |

- **Fondo**: amarillo banana — la única sección con este fondo, crea momento de pausa visual
- **Tipografía**: `clamp(36px, 5vw, 56px)` weight 900 — los números son el protagonista
- **Separadores**: `border-right: 1px solid rgba(0,0,0,0.1)` entre columnas

### 6.5 CÓMO FUNCIONA
**Propósito**: Reducir la fricción cognitiva. "No es complicado."

3 pasos en tarjetas con:
- Número de paso en círculo amarillo
- Icono emoji grande
- Título bold
- Descripción breve
- Conector `→` entre tarjetas (solo desktop)

Los pasos están deliberadamente redactados para que el usuario vea que **no necesita ir a ningún lugar físico**.

### 6.6 FEATURES
**Propósito**: Mostrar el alcance del producto sin abrumar.

Grid 3×2 con 6 features:
| Feature | Icono | Pill |
|---|---|---|
| Envíos instantáneos | 💸 | "0% comisión" |
| Cobra con QR | ⚡ | "Desde la app" |
| Depósito bancario | 📥 | "Todos los bancos" |
| Retiro express | 📤 | "Mismo día" |
| Cripto incluido | 🪙 | "USDT · USDC" |
| Notificaciones | 🔔 | "Tiempo real" |

Cada tarjeta tiene:
- `border: 1px solid var(--gray-100)` en reposo
- `border-color: var(--yellow)` en hover — detalle sutil de marca
- `transform: translateY(-4px)` en hover

### 6.7 WHATSAPP SECTION (sección oscura)
**Propósito**: El argumento más diferenciador — funciona en WhatsApp. Esta sección tiene peso emocional.

- **Fondo**: `#0a0a0a` — contraste total con el resto de la página
- **Layout**: conversación real a la izquierda, texto + CTA a la derecha
- **Gradientes de fondo**: dos esferas de color con `radial-gradient` — una amarilla (arriba derecha) y una verde WhatsApp (abajo izquierda) — dan profundidad
- **Conversación simulada**: muestra comandos reales de BananaPay — saldo, envío, retiro
- **CTA**: verde WhatsApp sobre fondo oscuro — máximo contraste y reconocimiento

La conversación usa comandos exactamente como el bot los procesa:
```
"saldo"              → respuesta con balances
"enviar 30 a ..."    → confirmación instantánea
"retirar 100 ..."    → confirmación de retiro
```

### 6.8 SEGURIDAD
**Propósito**: Manejar la objeción principal: "¿Es seguro?"

- **Visual izquierda**: caja amarilla con emoji 🔐 grande — lo visual antes que el texto
- **4 items de seguridad**: PIN bcrypt, biometría pura, detección de fraude, HMAC
- **Lenguaje**: técnico pero explicado en lenguaje humano. No "HMAC-SHA256" — "Cada mensaje se verifica criptográficamente"

### 6.9 TESTIMONIALES
**Propósito**: Prueba social. Reduce la barrera de "¿funciona de verdad?"

3 testimoniales de ciudades diferentes de Ecuador (Quito, Guayaquil, Cuenca) — señal de cobertura nacional.

Estructura: estrellas → cita → avatar inicial + nombre + ciudad.

### 6.10 CTA FINAL
**Propósito**: Capturar a los usuarios que llegaron hasta abajo pero aún no hicieron clic.

- **Fondo**: amarillo banana — igual que Stats. Bookends visuales de la página.
- **Emojis decorativos**: dos 🍌 gigantes en las esquinas con `opacity: 0.07` — presencia de marca sin ser ruido
- **Titular**: "Deja de esperar. / Empieza ahora." — urgencia sin ser agresivo
- **Nota de tranquilidad**: "Sin tarjeta · Sin cuenta bancaria · 100% gratis entre usuarios"

### 6.11 FOOTER
- 4 columnas: brand + tagline | Producto | Empresa | Legal
- Logo invertido a blanco con `filter: brightness(0) invert(1)`
- Links desactivados (color `rgba(255,255,255,0.65)`) → amarillo en hover
- Columna brand con `grid-column: 2fr` — más ancho que las demás

---

## 7. Componentes reutilizables

### Section Tag
```html
<span class="section-tag">Texto del tag</span>
```
- Background: `--yellow-light`
- Border: `1px solid rgba(250,204,21,0.4)`
- Color: `--yellow-dark`
- `border-radius: 100px` — pill completa

### Botones

| Variante | Clase | Background | Texto | Uso |
|---|---|---|---|---|
| WhatsApp principal | `.btn-wa` | `#25d366` | blanco | Hero, CTA final |
| WhatsApp oscuro | `.btn-wa-dark` | `#25d366` | blanco | Sección negra |
| App secundario | `.btn-app` | blanco | negro | Junto al WhatsApp |
| Negro | `.btn-black` | `#0a0a0a` | blanco | CTA final secundario |
| Nav | `.nav-cta` | `--yellow` | negro | Navegación |

Todos los botones usan `border-radius: 100px` — pill — estilo moderno y amigable.

### Feature pill
```html
<span class="feature-pill">Texto</span>
```
Mini badge debajo de la descripción de cada feature. Background `--yellow-light`, texto `--yellow-dark`.

---

## 8. Responsive / Breakpoints

### `max-width: 1024px` (tablet)
- Las 4 tarjetas flotantes del hero desaparecen (`display: none`)
- Features grid: `repeat(3, 1fr)` → `repeat(2, 1fr)`
- Footer: `2fr 1fr 1fr 1fr` → `1fr 1fr`

### `max-width: 768px` (mobile)
- Nav: links y CTA desktop ocultos → aparece botón compacto
- Hero CTAs: `flex-direction: column` — apilados verticalmente
- Teléfono mockup: ancho 240px (de 280px)
- Steps: `repeat(3, 1fr)` → `1fr` — apilados, conectores ocultos
- Features: `1fr` — una columna
- Sección WhatsApp: conversación oculta (`display: none`), solo texto
- Security: una columna
- Testimoniales: una columna
- Stats: una columna, border-bottom en lugar de border-right
- Footer: una columna, copyright centrado

---

## 9. SEO y meta tags

```html
<title>BananaPay — Tu plata, en segundos</title>
<meta name="description" content="Envía, recibe y retira dólares en Ecuador sin ir al banco. Solo por WhatsApp o desde la app. Gratis entre usuarios." />

<!-- Open Graph (WhatsApp, Facebook, LinkedIn) -->
<meta property="og:title" content="BananaPay — Tu plata, en segundos" />
<meta property="og:description" content="La billetera digital que funciona por WhatsApp. Envía dinero en segundos, sin filas ni papeleos." />
<meta property="og:image" content="https://bananapay.ec/og.png" />

<!-- Twitter/X -->
<meta name="twitter:card" content="summary_large_image" />
```

### OG Image pendiente
Crear `og.png` de **1200×630px** con:
- Fondo blanco o amarillo
- Logo BananaPay centrado
- Tagline "Tu plata, en segundos"
- Mockup del teléfono o chat de WhatsApp

---

## 10. Rendimiento

| Técnica | Detalle |
|---|---|
| Sin frameworks JS | Cero dependencias JavaScript externas |
| IntersectionObserver | Scroll reveal nativo, sin librerías |
| `font-display: swap` | Inter carga sin bloquear el render |
| `preconnect` | Google Fonts pre-conectado para reducir latencia |
| CSS custom properties | Variables en `:root` — un solo punto de cambio |
| Animaciones GPU | Solo `transform` y `opacity` — no repinta el DOM |
| `will-change` implícito | Las animaciones `float` se ejecutan en el compositor |

---

## 11. Links de WhatsApp

Formato: `https://wa.me/593989006527?text=Hola%2C+quiero+registrarme+en+BananaPay`

- **Número**: `+593 98 900 6527` → formato wa.me: `593989006527`
- **Mensaje pre-escrito**: "Hola, quiero registrarme en BananaPay" — el usuario llega al chat con contexto
- **Ubicaciones en el HTML**: nav CTA, hero botón principal, sección oscura, footer

---

## 12. Archivos del proyecto

```
landing/
├── index.html    → Toda la página (HTML + CSS inline + JS)
├── logo.png      → Logo BananaPay (copia de /static/bananaTradeLogo2.png)
└── DESIGN.md     → Este documento
```

---

## 13. Pendientes para producción

| Item | Prioridad | Detalle |
|---|---|---|
| `og.png` | Alta | Imagen 1200×630px para previews al compartir |
| Link App Store | Alta | Reemplazar `#` en botones "Descarga la app" |
| Dominio | Alta | Conectar `bananapay.ec` en Netlify |
| Analytics | Media | Google Analytics 4 o Plausible (más privado) |
| Testimoniales reales | Media | Reemplazar los 3 testimoniales placeholder por usuarios reales |
| Stats reales | Media | Actualizar `< 3s`, `$0`, `100%` con datos reales cuando haya métricas |
| Términos y Privacidad | Media | Crear páginas `/terminos` y `/privacidad` |
| i18n | Baja | Versión en inglés si se expande fuera de Ecuador |
| Blog | Baja | Sección de contenido para SEO orgánico |

---

## 14. Paleta de copy

### Voz de marca
- **Directa**: sin rodeos, sin "estimado usuario"
- **Cercana**: "tu plata", "listo", "ya está" — como habla un ecuatoriano
- **Confiada**: afirmaciones, no preguntas. "Funciona." no "¿Funciona?"
- **Sin tecnicismos**: "seguridad bancaria" en lugar de "cifrado AES-256"

### Frases clave del landing
| Sección | Frase |
|---|---|
| Hero H1 | "Tu plata, donde la necesitas. En segundos." |
| Hero sub | "Sin filas. Sin papeleos. Sin comisión entre usuarios." |
| WA section | "Tu banco nunca te respondería en segundos." |
| Security | "Tu plata, protegida como debe ser." |
| CTA final | "Deja de esperar. Empieza ahora." |
| CTA note | "Sin tarjeta de crédito · Sin cuenta bancaria requerida · 100% gratis entre usuarios" |

### Palabras que siempre usamos
`plata` · `segundos` · `gratis` · `sin filas` · `digital` · `instantáneo`

### Palabras que evitamos
`blockchain` · `DeFi` · `wallet` (usamos "billetera") · `KYC` · `compliance` · `token`
