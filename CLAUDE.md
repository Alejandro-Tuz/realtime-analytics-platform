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
- Redis (puerto 6379) — corriendo en WSL (Ubuntu). Arrancar con
  `sudo service redis-server start`; verificar con `redis-cli ping` → PONG.
```

## Arquitectura del código

```
app/
  config.py    — Lee DATABASE_URL, REDIS_HOST y REDIS_PORT desde .env vía pydantic-settings.
  database.py  — Crea el engine SQLAlchemy, SessionLocal y la clase Base para los modelos.
  models.py    — Modelo ORM Event; define la tabla `events` con sus columnas e índices.
  schemas.py   — Schema Pydantic EventCreate; valida el body JSON que llega al endpoint.
  queue.py     — Crea el cliente Redis vía get_redis(); redis-py maneja el pool interno.
  main.py      — App FastAPI: GET /health y POST /events (encola en Redis con lpush, devuelve 202).

alembic/
  env.py       — Configura Alembic para usar settings.database_url y detectar Base.metadata.
  versions/    — Migraciones versionadas; la primera crea la tabla events con sus índices.

test_db.py     — Script one-shot para verificar conectividad con la DB (no es suite de tests).
```

El flujo actual (etapa 3 en curso): `POST /events` → validación Pydantic → `redis.lpush("events_queue")` → respuesta 202 → [worker pendiente] → `db.commit()` → PostgreSQL.

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
- Cliente Redis creado por llamada en get_redis(): redis-py maneja un pool
  interno, así que no hace falta un singleton en este caso síncrono.
- POST /events responde 202 Accepted: la ingesta es asíncrona; el evento se
  acepta pero se procesa después (lo persiste el worker, no el endpoint).
- Cola FIFO con Redis: el endpoint empuja con lpush (izquierda) y el worker
  sacará con rpop/brpop (derecha) → el evento más viejo se procesa primero.
- Configuración por variables de entorno; secretos en .env (en .gitignore).
  redis_host/redis_port llevan defaults (localhost/6379) por ser estándar;
  database_url NO lleva default a propósito (es secreto y debe fallar si falta).

## Estado actual (retomar aquí)
Etapa 3 en curso. Avance:
- Redis corriendo en WSL (Ubuntu). Verificado con `redis-cli ping` → PONG.
- app/queue.py escrito y verificado: `get_redis().ping()` → True.
- config.py: agregados redis_host (default localhost) y redis_port (default 6379).
- POST /events refactorizado: ya NO escribe a DB; encola en Redis con
  lpush("events_queue") y devuelve 202. Ya no recibe db: Session.
- requirements.txt actualizado con redis.

PENDIENTE INMEDIATO:
- Probar el endpoint (Swagger /docs) y verificar el encolado con
  `redis-cli lrange events_queue 0 -1` (ver el evento como JSON en la cola).
- Escribir el worker: consume con rpop/brpop, deserializa el JSON,
  reconstruye el Event ORM y escribe a PostgreSQL (db.commit()).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.