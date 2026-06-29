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

Levantar el worker (en otra terminal, con el venv activo y Redis corriendo):
```
python worker.py
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
  metrics.py   — Consultas SQL agregadas con el ORM. get_summary(): total de eventos,
                 usuarios únicos (distinct) y conteo por tipo (group by + order by).
  main.py      — App FastAPI: GET /health y POST /events (encola en Redis con lpush, devuelve 202).

worker.py      — Proceso aparte (NO es la API). Consume events_queue con brpop, deserializa
                 el JSON, reconstruye el Event ORM y lo guarda en PostgreSQL. Se corre solo.
alembic/
  env.py       — Configura Alembic para usar settings.database_url y detectar Base.metadata.
  versions/    — Migraciones versionadas; la primera crea la tabla events con sus índices.

test_db.py     — Script one-shot para verificar conectividad con la DB (no es suite de tests).
```

El flujo completo (etapa 3 lista): `POST /events` → validación Pydantic → `redis.lpush("events_queue")` → respuesta 202 → `worker.py` consume con `brpop` → deserializa JSON → reconstruye Event ORM → `db.commit()` → PostgreSQL.

## Roadmap del proyecto (Plataforma de analítica en tiempo real)

Mini-versión de Mixpanel/Google Analytics. Objetivo: ingesta de eventos a
gran escala con procesamiento asíncrono y métricas en vivo.

Arquitectura objetivo:
Cliente → API (FastAPI) → Cola (Redis) → Workers → PostgreSQL → Dashboard (WebSocket)

Etapas:
1. [HECHO] API recibe y valida eventos (FastAPI + Pydantic).
2. [HECHO] Persistencia en PostgreSQL (SQLAlchemy + Alembic, code-first).
3. [HECHO] Redis + workers: la API encola eventos en vez de escribir
   directo; los workers consumen la cola y guardan en PostgreSQL.
4. [EN CURSO] Endpoints de métricas + dashboard en vivo por WebSocket.
5. [PENDIENTE] Empaquetado con Docker y despliegue (Render/Railway/Fly.io).

## Plan de la etapa 4 (EN CURSO) — métricas + dashboard en vivo
Cuatro piezas, en este orden:
- 4.1 [HECHO] app/metrics.py — funciones de consulta SQL agregado (get_summary()).
- 4.2 [PENDIENTE] Endpoints REST de métricas en app/main.py — exponen get_summary()
      por HTTP con un GET (p. ej. GET /metrics/summary).
- 4.3 [PENDIENTE] Endpoint WebSocket en app/main.py — conexión abierta que empuja
      las métricas al dashboard en vivo (cada pocos segundos), sin recargar.
- 4.4 [PENDIENTE] Dashboard HTML en app/static/index.html — la página que muestra
      las métricas y se conecta al WebSocket.

Concepto clave de la etapa (importa para la pieza 4.3):
- Un endpoint WebSocket OBLIGA a usar `async def`: mantiene la conexión abierta
  mucho tiempo, y eso lo maneja bien el modelo asíncrono (el event loop).
- PERO SQLAlchemy es síncrono/bloqueante. Si se llama directo dentro de un
  `async def`, bloquea el event loop y nadie más puede conectarse mientras
  corre la query.
- Solución: `resultado = await asyncio.to_thread(funcion_sincrona, args)`.
  Manda la función síncrona a un thread aparte y deja el event loop libre.
  Es el puente entre el mundo sync (SQLAlchemy) y el async (WebSocket).
- Frase de entrevista: "Usé asyncio.to_thread para correr las queries síncronas
  de SQLAlchemy desde el handler async del WebSocket sin bloquear el event loop."

Decisiones de diseño ya tomadas (y su porqué):
- Code-first con ORM y migraciones: el esquema vive en código y en git,
  reproducible con `alembic upgrade head`.
- `properties` como JSONB: datos flexibles por tipo de evento; campos fijos
  (event_name, user_id, timestamp) como columnas indexadas.
- SQLAlchemy SÍNCRONO a propósito: los workers (síncronos) son los que
  escriben; el endpoint usa `def` (no async) para no bloquear el event loop.
- Cliente Redis creado por llamada en get_redis(): redis-py maneja un pool
  interno, así que no hace falta un singleton en este caso síncrono.
- POST /events responde 202 Accepted: la ingesta es asíncrona; el evento se
  acepta pero se procesa después (lo persiste el worker, no el endpoint).
- Cola FIFO con Redis: el endpoint empuja con lpush (izquierda) y el worker
  saca con brpop (derecha) → el evento más viejo se procesa primero.
- Worker usa brpop (no rpop): bloquea/duerme cuando la cola está vacía en vez
  de quemar CPU en espera activa. timeout=5 permite atender Ctrl+C limpiamente.
- Worker maneja la sesión a mano (SessionLocal + try/finally) porque no hay
  FastAPI que gestione el ciclo de vida con Depends(get_db).
- Worker envuelve brpop en try/except redis.exceptions.TimeoutError: en el
  puente de red Windows→WSL, el timeout del socket puede dispararse justo antes
  de que Redis responda (condición de carrera). Se trata como "cola vacía"
  (continue). Lección: en producción los workers SIEMPRE manejan errores de red.
- worker.py va en la raíz (no en app/): es un proceso hermano, no parte de la API.
- metrics.py usa el patrón SessionLocal + try/finally (igual que el worker),
  no Depends(get_db), porque las consultas pueden llamarse fuera de un request.
- Configuración por variables de entorno; secretos en .env (en .gitignore).
  redis_host/redis_port llevan defaults (localhost/6379) por ser estándar;
  database_url NO lleva default a propósito (es secreto y debe fallar si falta).

## Estado actual (retomar aquí)
Etapa 4 en curso. Pieza 4.1 HECHA y probada:
- app/metrics.py escrito con get_summary() → devuelve un dict con
  {total_events, unique_users, events_by_type}.
  * total_events: func.count(Event.id)
  * unique_users: func.count(func.distinct(Event.user_id))
  * events_by_type: group_by(event_name) + order_by(count desc), pasado a dict.
- Probado en python interactivo:
  `from app.metrics import get_summary; print(get_summary())` → muestra los
  conteos reales desde PostgreSQL (los eventos guardados por el worker).
- Nota: el import `text` en metrics.py está puesto pero AÚN no se usa; lo
  reservó para una posible query de métricas por rango de tiempo. No es error.

SIGUIENTE (retomar aquí con Claude Code):
- Pieza 4.2: crear los endpoints REST de métricas en app/main.py que exponen
  get_summary() por HTTP (un GET, p. ej. GET /metrics/summary). Probar en /docs.
- Luego 4.3 (WebSocket, recordar asyncio.to_thread) y 4.4 (dashboard HTML).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.