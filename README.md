# 🍌 BananaPay

Fintech ecuatoriana 100% vía WhatsApp. Permite a los usuarios enviar dinero, depositar y retirar (fiat y USDT TRC-20) sin necesidad de descargar ninguna app — todo desde WhatsApp.

## Stack

| Capa | Tecnología |
|---|---|
| Backend API | Python 3.11 + FastAPI |
| Base de datos | Supabase (PostgreSQL) |
| Cache / sesiones | Redis (Upstash) |
| Blockchain | USDT TRC-20 via TronGrid |
| Verificación IA | Claude Vision (Anthropic) |
| Panel admin | HTML/CSS/JS vanilla |
| App mobile | React Native + Expo (en desarrollo) |
| Deploy backend | Railway |
| Deploy mobile | EAS Build (Expo) |

## Estructura

```
BananaPay/
├── app/
│   ├── api/            # Routers FastAPI (webhook, admin, app mobile)
│   ├── modules/        # Lógica de negocio (auth, fiat, crypto, ai)
│   ├── integrations/   # Clientes externos (Supabase, Redis, WhatsApp, Tron)
│   ├── core/           # Bot router, command dispatcher
│   └── config.py       # Settings via pydantic-settings
├── panel/              # Panel admin (HTML estático, servido en /panel)
├── BananaPayApp/       # App React Native / Expo
├── tests/
│   ├── integration/    # pytest — bot router, módulos
│   └── e2e/            # Playwright — panel admin
├── main.py             # Entry point FastAPI
├── worker.py           # Worker independiente (deposit listener USDT)
├── nixpacks.toml       # Build config Railway
└── railway.toml        # Deploy config Railway
```

## Desarrollo local

### Requisitos
- Python 3.11+
- Node 20+
- Redis corriendo en `localhost:6379`

### Backend

```bash
# 1. Entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# → edita .env con tus valores

# 4. Arrancar
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API disponible en `http://localhost:8000`
Docs en `http://localhost:8000/docs`
Panel admin en `http://localhost:8000/panel/index.html`

### App mobile

```bash
cd BananaPayApp
npm install
cp .env.example .env          # ajusta EXPO_PUBLIC_API_URL con tu IP local
npx expo start
```

### Tests

```bash
# Python
pytest --tb=short -q

# Jest (mobile)
cd BananaPayApp && npm test

# Playwright (panel admin)
npx playwright test
```

## Deploy

Ver [PASO A PASO](#) — Railway (backend) + EAS Build (mobile).

### Variables de entorno Railway
Ver `.env.example` para la lista completa de variables requeridas.

## Licencia

Propietario y confidencial — ver [LICENSE](LICENSE).
