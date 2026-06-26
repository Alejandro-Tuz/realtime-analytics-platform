# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cómo trabajar conmigo (IMPORTANTE)

Soy estudiante de últimos semestres de ingeniería de sistemas, construyendo
este proyecto para mi portafolio y para aprender a fondo, no solo para que
funcione. Mi meta es poder DEFENDER cada decisión en una entrevista técnica.

Reglas de interacción:
- Usa SIEMPRE plan mode: propón cambios y explícalos, pero NO los apliques tú.
  Yo escribo todo el código manualmente.
- Explica el PORQUÉ de cada decisión: qué hace, qué alternativas había, qué
  pasa por debajo, y cómo lo defendería ante un reclutador.
- Cuando aparezca un concepto nuevo, explícamelo a detalle antes de usarlo.
- Avanza paso a paso. No me des la etapa entera de golpe; una pieza, la
  entiendo, la escribo, la pruebo, y seguimos.
- Si cometo un error o algo falla, ayúdame a leer el error y entenderlo,
  no solo a arreglarlo.
- Responde en español.

## Comandos de desarrollo

Activar el entorno virtual (Windows):
```
venv\Scripts\activate
```

Levantar el servidor de desarrollo:
```
uvicorn app.main:app --reload
```

Verificar la conexión a la base de datos:
```
python test_db.py
```

Migraciones con Alembic:
```
alembic upgrade head                              # aplicar todas las migraciones pendientes
alembic revision --autogenerate -m "descripcion" # generar migración desde los modelos
alembic downgrade -1                              # revertir la última migración
alembic history                                   # ver historial de migraciones

```

Instalar dependencias:
```
pip install -r requirements.txt
```

```
Servicios externos que deben estar corriendo:
- PostgreSQL (base `analytics`, puerto 5432).
- Redis (puerto 6379) — pendiente de levantar; ver "Estado actual".
```

## Arquitectura del código

```
app/
  config.py    — Lee DATABASE_URL (y futuras vars) desde .env vía pydantic-settings.
  database.py  — Crea el engine SQLAlchemy, SessionLocal y la clase Base para los modelos.
  models.py    — Modelo ORM Event; define la tabla `events` con sus columnas e índices.
  schemas.py   — Schema Pydantic EventCreate; valida el body JSON que llega al endpoint.
  main.py      — App FastAPI: GET /health y POST /events (escribe directo a DB por ahora).

alembic/
  env.py       — Configura Alembic para usar settings.database_url y detectar Base.metadata.
  versions/    — Migraciones versionadas; la primera crea la tabla events con sus índices.

test_db.py     — Script one-shot para verificar conectividad con la DB (no es suite de tests).
```

El flujo actual de un evento: `POST /events` → validación Pydantic → `Event()` ORM → `db.commit()` → PostgreSQL.

El flujo objetivo (etapa 3): `POST /events` → validación Pydantic → `redis.lpush()` → respuesta 202 → worker consume → `db.commit()` → PostgreSQL.

## Roadmap del proyecto (Plataforma de analítica en tiempo real)

Mini-versión de Mixpanel/Google Analytics. Objetivo: ingesta de eventos a
gran escala con procesamiento asíncrono y métricas en vivo.

Arquitectura objetivo:
Cliente → API (FastAPI) → Cola (Redis) → Workers → PostgreSQL → Dashboard (WebSocket)

Etapas:
1. [HECHO] API recibe y valida eventos (FastAPI + Pydantic).
2. [HECHO] Persistencia en PostgreSQL (SQLAlchemy + Alembic, code-first).
3. [EN CURSO] Redis + workers: la API encola eventos en vez de escribir
   directo; los workers consumen la cola y guardan en PostgreSQL.
4. [PENDIENTE] Endpoints de métricas + dashboard en vivo por WebSocket.
5. [PENDIENTE] Empaquetado con Docker y despliegue (Render/Railway/Fly.io).

Decisiones de diseño ya tomadas (y su porqué):
- Code-first con ORM y migraciones: el esquema vive en código y en git,
  reproducible con `alembic upgrade head`.
- `properties` como JSONB: datos flexibles por tipo de evento; campos fijos
  (event_name, user_id, timestamp) como columnas indexadas.
- SQLAlchemy SÍNCRONO a propósito: los workers (síncronos) serán los que
  escriban; el endpoint usa `def` (no async) para no bloquear el event loop.
- Configuración por variables de entorno; secretos en .env (en .gitignore).

## Estado actual (retomar aquí)
Etapa 3 en curso. Avance y bloqueo:
- Ya se discutió el diseño del cliente Redis (módulo `app/queue.py` con una
  función `get_redis()`; se decidió crear el cliente por llamada porque
  redis-py ya maneja un pool de conexiones interno; un singleton no aporta
  en este caso síncrono).
- BLOQUEO: falta levantar Redis. Docker Desktop NO se pudo instalar (versión
  de Windows incompatible: pide 22H2 / build 19045 o superior).
- Opciones para desbloquear, en orden de preferencia:
  A) Actualizar Windows a 22H2 desde Windows Update, luego reintentar Docker.
  B) Instalar Redis directo en WSL (`wsl --install` → Ubuntu →
     `sudo apt install redis-server` → `sudo service redis-server start`).
     Conectar desde la API en localhost:6379. ← opción recomendada.
  C) Redis en la nube (Redis Cloud / Upstash); URL en .env. Red de seguridad.
- PENDIENTE tras desbloquear: escribir `app/queue.py`, verificar con
  `get_redis().ping()` → True, y luego refactorizar `POST /events` para que
  encole en vez de escribir directo a la DB.

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.