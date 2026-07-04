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

### Con Docker (forma actual — levanta TODO junto)
```
docker compose up --build     # construye y levanta api + worker + postgres + redis
docker compose up             # levanta sin reconstruir
docker compose down           # detiene y elimina los contenedores (CONSERVA los datos)
docker compose down -v        # detiene y BORRA también el volumen de datos (¡cuidado!)
docker compose logs -f api    # ver logs de un servicio (api, worker, postgres, redis)
```
Con Docker NO hace falta arrancar nada a mano. Docker corre en WSL; si no está
arrancado: `sudo service docker start`.

### Sin Docker (forma manual antigua, por si se necesita)
```
venv\Scripts\activate                     # activar entorno (Windows)
uvicorn app.main:app --reload             # API
python worker.py                          # worker (otra terminal)
alembic upgrade head                      # aplicar migraciones
alembic revision --autogenerate -m "msg"  # generar migración
python test_db.py                         # probar conexión a la DB
```
Servicios externos (modo manual): PostgreSQL (5432) y Redis (6379 en WSL,
`sudo service redis-server start`). En este modo, REDIS_URL toma su valor por
defecto (redis://localhost:6379) si no se define en el entorno.

## Arquitectura del código

```
app/
  config.py    — Lee DATABASE_URL y REDIS_URL desde el entorno/.env vía pydantic-settings.
                 REDIS_URL tiene default redis://localhost:6379 (funciona sin Docker).
  database.py  — Crea el engine SQLAlchemy, SessionLocal y la clase Base para los modelos.
  models.py    — Modelo ORM Event; define la tabla `events` con sus columnas e índices.
  schemas.py   — Schema Pydantic EventCreate; valida el body JSON que llega al endpoint.
  queue.py     — Crea el cliente Redis vía get_redis() usando redis.Redis.from_url(REDIS_URL);
                 redis-py maneja el pool interno.
  metrics.py   — Consultas SQL agregadas con el ORM. get_summary(): total de eventos,
                 usuarios únicos (distinct) y conteo por tipo (group by + order by).
  main.py      — App FastAPI. Endpoints: GET /health, POST /events (encola en Redis, 202),
                 GET /metrics/summary (métricas), WS /ws/metrics (métricas en vivo).
                 Monta StaticFiles en /static para servir el dashboard.
  static/
    index.html — Dashboard en vivo (HTML/CSS/JS puro, sin frameworks). WebSocket, barras,
                 destello al cambiar, indicador de conexión, auto-reconexión, wss:// automático.

worker.py        — Proceso aparte. Consume events_queue con brpop, deserializa el JSON,
                   reconstruye el Event ORM y lo guarda en PostgreSQL.
Dockerfile       — Imagen de la app (python:3.11-slim). Orden optimizado para caché de capas.
                   CMD ["./entrypoint.sh"].
.dockerignore    — Excluye venv/, __pycache__, .env, .git de la imagen.
entrypoint.sh    — Corre `alembic upgrade head` y luego `exec uvicorn ...`. Lo usa la API.
docker-compose.yml — Orquesta api, worker (misma imagen, command distinto), postgres
                   (con volumen postgres_data) y redis. Pasa DATABASE_URL y
                   REDIS_URL=redis://redis:6379 (el host es el nombre del servicio).
alembic/
  env.py         — Usa settings.database_url y detecta Base.metadata.
  versions/      — Migraciones versionadas; la primera crea la tabla events con sus índices.
test_db.py       — Script one-shot para verificar conectividad con la DB.
```

Flujo de ingesta: POST /events → Pydantic → redis.lpush("events_queue") → 202 →
worker (brpop) → deserializa → Event ORM → db.commit() → PostgreSQL.
Flujo de métricas: GET /metrics/summary o WS /ws/metrics → get_summary() → PostgreSQL →
JSON → dashboard en /static/index.html (el WS empuja cada 3 s).

## Roadmap del proyecto (Plataforma de analítica en tiempo real)

Mini-versión de Mixpanel/Google Analytics. Ingesta de eventos a gran escala con
procesamiento asíncrono y métricas en vivo.
Arquitectura: Cliente → API (FastAPI) → Cola (Redis) → Workers → PostgreSQL → Dashboard (WebSocket)

Etapas:
1. [HECHO] API recibe y valida eventos (FastAPI + Pydantic).
2. [HECHO] Persistencia en PostgreSQL (SQLAlchemy + Alembic, code-first).
3. [HECHO] Redis + workers (ingesta asíncrona con cola).
4. [HECHO] Métricas + dashboard en vivo por WebSocket.
5. [EN CURSO] Docker y despliegue.

## Plan de la etapa 5 (EN CURSO) — Docker y despliegue
- 5.1 [HECHO] Dockerfile + .dockerignore. Caché de capas verificado (build ~50s → ~2s).
- 5.2 [HECHO] docker-compose.yml: api + worker + postgres + redis con un comando.
      Los servicios se hablan por NOMBRE (DATABASE_URL→postgres, REDIS_URL→redis://redis:6379),
      no localhost. Volumen postgres_data para persistir. depends_on para el orden.
- 5.3 [HECHO] entrypoint.sh: corre `alembic upgrade head` antes de uvicorn. Usa CMD (no
      ENTRYPOINT) para que el worker sobreescriba con `command: python worker.py`.
      #!/bin/sh (la slim no trae bash) y `exec uvicorn` para recibir bien las señales.
- 5.3b [HECHO] Refactor Redis a una sola URL: config.py y queue.py ahora usan REDIS_URL
      (con redis.Redis.from_url), no REDIS_HOST/REDIS_PORT. Motivo: Render entrega el Redis
      como URL combinada (redis://host:6379), no como campos separados. Queda consistente
      con DATABASE_URL. default redis://localhost:6379 para correr sin Docker.
      docker-compose.yml actualizado a REDIS_URL. Probado en local con docker compose up.
- 5.4 [EN CURSO] Despliegue en Render:
      * [HECHO] PostgreSQL administrado creado (Oregon, free). Su URL empieza con
        postgresql:// (compatible con SQLAlchemy, no hay que reescribir el esquema).
      * [HECHO] Redis/Key Value administrado creado (Oregon, free). Internal URL:
        redis://red-d94nnavaqgkc73e5op50:6379 (external bloqueado = más seguro).
        Persistence Off (Redis es cola de paso; el almacén real es PostgreSQL).
      * [PENDIENTE] Crear el Web Service (API) desde el Dockerfile, con variables de
        entorno DATABASE_URL (la Internal de Postgres) y REDIS_URL (la Internal del Redis).
        MISMA región (Oregon) para que se comuniquen por red privada.
      * [PENDIENTE] Crear el Background Worker (misma imagen, command: python worker.py).
      * [PENDIENTE] CORS: revisar si hace falta (probablemente no, porque el dashboard se
        sirve desde el mismo origen que la API). Confirmar cuando la API esté viva.
      * [PENDIENTE] Probar la URL pública y actualizar CV/README con el link de la demo.
      * Nota: el plan free de Render "duerme" los servicios; la primera visita tarda unos
        segundos en despertar (normal, no es error).

Errores/decisiones de la etapa 5 (para defender en entrevista):
- ENTRYPOINT vs CMD: con ENTRYPOINT el `command:` del compose se vuelve ARGUMENTO (no
  reemplaza), así que el worker corría uvicorn. Se volvió a CMD.
- Race condition en migraciones: API y worker corrían alembic a la vez y chocaban al crear
  alembic_version (duplicate key). Con CMD, solo la API migra; el worker no compite.
- Puertos: DBeaver se conecta al 5433 (mapeado) que Docker reenvía al 5432 interno.
- YAML: la indentación es sintaxis (como Python).
- redis.Redis.from_url + decode_responses=False: devuelve bytes, que json.loads acepta;
  mantiene el worker funcionando igual que antes.

Decisiones de diseño ya tomadas (y su porqué):
- Code-first con ORM y migraciones; esquema en git, reproducible con `alembic upgrade head`.
- `properties` como JSONB: flexible por tipo de evento; campos fijos indexados.
- SQLAlchemy SÍNCRONO a propósito; endpoints de DB en `def` para no bloquear el event loop.
- get_redis() crea el cliente por llamada con from_url(REDIS_URL); redis-py maneja el pool.
- POST /events responde 202 Accepted (ingesta asíncrona; persiste el worker).
- Cola FIFO: lpush (izq) en la API, brpop (der) en el worker → el más viejo primero.
- Worker usa brpop bloqueante (no rpop) + timeout=5 + try/except TimeoutError (race del
  socket Windows→WSL). Maneja la sesión a mano (SessionLocal + try/finally).
- WebSocket usa asyncio.to_thread (no bloquear el loop) y asyncio.sleep (no time.sleep).
- Dashboard sin dependencias; URL del WS derivada de location; barras con textContent
  (anti-XSS); auto-reconexión.
- Dockerfile ordenado para caché de capas; .dockerignore excluye el .env (secretos NUNCA
  en la imagen; en producción se inyectan por variables de entorno).
- Config por variables de entorno; secretos en .env (en .gitignore). REDIS_URL con default
  (estándar); DATABASE_URL sin default a propósito (secreto, debe fallar si falta).

## Estado actual (retomar aquí)
ETAPA 5 en la recta final. Contenerización COMPLETA y refactor de Redis a REDIS_URL HECHO
y probado en local (docker compose up --build funciona: evento → cola → worker → Postgres).
En Render ya están creados el PostgreSQL y el Redis (ambos en Oregon, free).

PENDIENTE INMEDIATO (pieza 5.4, paso 2):
1. Crear el Web Service (API) en Render desde el repo/Dockerfile:
   - Variables de entorno: DATABASE_URL = (Internal URL del Postgres de Render),
     REDIS_URL = redis://red-d94nnavaqgkc73e5op50:6379 (Internal del Redis).
   - Misma región: Oregon.
2. Crear el Background Worker (misma imagen, command: python worker.py, mismas variables).
3. Revisar CORS si hace falta. Probar la URL pública.
4. Agregar el link de la DEMO EN VIVO al CV y al README (el repo ya está enlazado).

Tareas de portafolio pendientes (tras el despliegue):
- README con GIF del dashboard en vivo, arquitectura, stack y cómo correrlo.
- Documento de "decisiones de diseño y su porqué" (guion de defensa para entrevista).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.