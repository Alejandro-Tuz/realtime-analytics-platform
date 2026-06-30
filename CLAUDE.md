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
  main.py      — App FastAPI. Endpoints: GET /health, POST /events (encola en Redis, 202),
                 GET /metrics/summary (métricas), WS /ws/metrics (métricas en vivo).

worker.py      — Proceso aparte (NO es la API). Consume events_queue con brpop, deserializa
                 el JSON, reconstruye el Event ORM y lo guarda en PostgreSQL. Se corre solo.
alembic/
  env.py       — Configura Alembic para usar settings.database_url y detectar Base.metadata.
  versions/    — Migraciones versionadas; la primera crea la tabla events con sus índices.

test_db.py     — Script one-shot para verificar conectividad con la DB (no es suite de tests).
```

El flujo de ingesta (etapa 3): `POST /events` → validación Pydantic → `redis.lpush("events_queue")` → respuesta 202 → `worker.py` consume con `brpop` → deserializa JSON → reconstruye Event ORM → `db.commit()` → PostgreSQL.

El flujo de métricas (etapa 4): `GET /metrics/summary` o `WS /ws/metrics` → `get_summary()` (SQL agregado) → PostgreSQL → JSON al cliente. El WebSocket lo empuja cada 3 s.

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
- 4.1 [HECHO] app/metrics.py — get_summary() con SQL agregado.
- 4.2 [HECHO] GET /metrics/summary en app/main.py — expone get_summary() por HTTP.
      Endpoint `def` (síncrono): FastAPI lo manda a un threadpool y no bloquea el loop.
- 4.3 [HECHO] WS /ws/metrics en app/main.py — WebSocket que empuja las métricas
      cada 3 s. async def + await asyncio.to_thread(get_summary) + await asyncio.sleep(3).
- 4.4 [PENDIENTE] Dashboard HTML en app/static/index.html — página que se conecta
      al WebSocket y muestra las métricas actualizándose solas.

Concepto clave de la etapa (ya aplicado en 4.3):
- Un endpoint WebSocket OBLIGA a `async def`: la conexión queda abierta mucho
  tiempo; el event loop sostiene miles de conexiones sin un thread por cada una.
- PERO SQLAlchemy es síncrono/bloqueante. Llamarlo directo dentro de un async def
  bloquea el event loop y nadie más puede conectarse mientras corre la query.
- Solución: `data = await asyncio.to_thread(get_summary)` → manda la query a un
  thread del SO y deja el event loop libre. Puente sync↔async.
- OJO con sleep: dentro de async se usa `await asyncio.sleep(3)` (NO time.sleep),
  porque cede el control al event loop en vez de congelar todo.
- Frase de entrevista: "El WebSocket requiere async por las conexiones de larga
  duración; como SQLAlchemy es síncrono, usé asyncio.to_thread para correr las
  queries en un thread sin bloquear el event loop, y así soportar miles de
  clientes en el dashboard a la vez."

Decisiones de diseño ya tomadas (y su porqué):
- Code-first con ORM y migraciones: el esquema vive en código y en git,
  reproducible con `alembic upgrade head`.
- `properties` como JSONB: datos flexibles por tipo de evento; campos fijos
  (event_name, user_id, timestamp) como columnas indexadas.
- SQLAlchemy SÍNCRONO a propósito: los workers (síncronos) son los que
  escriben; los endpoints HTTP de DB usan `def` para no bloquear el event loop.
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
- metrics.py usa SessionLocal + try/finally (igual que el worker), no
  Depends(get_db), para ser reutilizable fuera del contexto HTTP.
- WebSocket usa asyncio.to_thread para no bloquear el event loop con la query
  síncrona, y asyncio.sleep (no time.sleep) para la espera entre envíos.
- Configuración por variables de entorno; secretos en .env (en .gitignore).
  redis_host/redis_port llevan defaults (localhost/6379) por ser estándar;
  database_url NO lleva default a propósito (es secreto y debe fallar si falta).

## Estado actual (retomar aquí)
Etapa 4 casi lista. Hechas las piezas 4.1, 4.2 y 4.3:
- app/metrics.py: get_summary() probado, devuelve {total_events, unique_users,
  events_by_type}.
- GET /metrics/summary: probado en /docs, devuelve el JSON de métricas.
- WS /ws/metrics: probado desde la consola del navegador (DevTools → Console)
  con:
    const ws = new WebSocket("ws://localhost:8000/ws/metrics");
    ws.onmessage = (e) => console.log(JSON.parse(e.data));
  Llegan los datos cada 3 segundos. Funciona.
- Limpieza hecha en main.py: se quitaron los imports huérfanos
  (from app.database import get_db; from app.models import Event).

PENDIENTE — pieza 4.4 (retomar aquí mañana): el dashboard HTML.
- Crear app/static/index.html: una página que se conecta a ws://.../ws/metrics
  por JavaScript y muestra las métricas actualizándose solas
  (document.getElementById(...).textContent = ...).
- Servir archivos estáticos en main.py:
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
  Luego el dashboard queda en http://localhost:8000/static/index.html
- Conceptos nuevos de esta pieza: (a) StaticFiles para servir HTML (FastAPI no
  sirve HTML por defecto); (b) el mismo WebSocket de la prueba de consola, pero
  dentro del HTML, actualizando el DOM cuando llega cada mensaje.
- Con esto se cierra la ETAPA 4 completa.

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.