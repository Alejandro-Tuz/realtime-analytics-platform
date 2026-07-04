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
docker compose up --build     # construye (si hace falta) y levanta api + worker + postgres + redis
docker compose up             # levanta sin reconstruir
docker compose down           # detiene y elimina los contenedores (CONSERVA los datos)
docker compose down -v        # detiene y BORRA también el volumen de datos (¡cuidado!)
docker compose logs -f api    # ver logs de un servicio (api, worker, postgres, redis)
```
Con Docker NO hace falta arrancar nada a mano (ni Redis en WSL, ni uvicorn, ni el worker):
`docker compose up` reemplaza todo ese arranque manual. Docker corre en WSL; si no está
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
`sudo service redis-server start`).

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
                 Monta StaticFiles en /static para servir el dashboard.
  static/
    index.html — Dashboard en vivo (HTML/CSS/JS puro, sin frameworks). WebSocket, barras,
                 destello al cambiar, indicador de conexión, auto-reconexión, wss:// automático.

worker.py        — Proceso aparte. Consume events_queue con brpop, deserializa el JSON,
                   reconstruye el Event ORM y lo guarda en PostgreSQL.
Dockerfile       — Imagen de la app (python:3.11-slim). Orden optimizado para caché de capas
                   (COPY requirements → install → COPY resto). CMD ["./entrypoint.sh"].
.dockerignore    — Excluye venv/, __pycache__, .env, .git de la imagen (más liviana y segura).
entrypoint.sh    — Corre `alembic upgrade head` y luego `exec uvicorn ...`. Lo usa la API.
docker-compose.yml — Orquesta 4 servicios: api, worker (misma imagen, command distinto),
                   postgres (con volumen postgres_data) y redis. Red interna por nombre.
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
- 5.1 [HECHO] Dockerfile + .dockerignore. Imagen construida; caché de capas verificado
      (build de ~50s → ~2s; contexto 66MB → 1.5KB al ignorar venv/).
- 5.2 [HECHO] docker-compose.yml: api + worker + postgres + redis con un solo comando.
      Los servicios se hablan por NOMBRE (DATABASE_URL→postgres, REDIS_HOST→redis), no
      localhost. Volumen postgres_data para persistir. depends_on para el orden de arranque.
- 5.3 [HECHO] entrypoint.sh: corre `alembic upgrade head` antes de uvicorn, para crear el
      esquema en cualquier entorno nuevo. Usa CMD (no ENTRYPOINT) para que el worker pueda
      sobreescribir con `command: python worker.py`. #!/bin/sh (la slim no trae bash) y
      `exec uvicorn` para que reciba bien las señales de apagado.
- 5.4 [PENDIENTE] Despliegue en Render:
      * Web Service (API, desde el Dockerfile) + Background Worker (python worker.py) +
        PostgreSQL gestionado + Redis gestionado (servicios administrados por Render, no
        contenedores propios).
      * Conectar todo por variables de entorno (DATABASE_URL, REDIS_HOST/PORT) en Render.
      * Revisar CORS (pendiente que dejó Claude Code) si el dashboard lo necesita.
      * Nota: el plan free de Render "duerme" los servicios; la primera visita tarda unos
        segundos en despertar (es normal, no es error).
      * REQUISITO: el repo debe estar ACTUALIZADO en GitHub (Render se alimenta del repo).

Errores resueltos en la etapa 5 (para defender en entrevista):
- ENTRYPOINT vs CMD: con ENTRYPOINT el `command:` del compose se vuelve ARGUMENTO (no
  reemplaza), así que el worker corría uvicorn. Se volvió a CMD y el worker ya sobreescribe bien.
- Race condition en migraciones: API y worker corrían alembic a la vez y chocaban al crear
  alembic_version (duplicate key). Con CMD, solo la API migra; el worker ya no compite.
- Puertos: DBeaver se conecta al 5433 (mapeado) que Docker reenvía al 5432 interno de postgres.
- YAML: indentación es sintaxis (como Python); un bloque mal sangrado rompía el compose.

Decisiones de diseño ya tomadas (y su porqué):
- Code-first con ORM y migraciones; esquema en git, reproducible con `alembic upgrade head`.
- `properties` como JSONB: flexible por tipo de evento; campos fijos indexados.
- SQLAlchemy SÍNCRONO a propósito; endpoints de DB en `def` para no bloquear el event loop.
- get_redis() crea el cliente por llamada (redis-py maneja pool interno; no hace falta singleton).
- POST /events responde 202 Accepted (ingesta asíncrona; persiste el worker).
- Cola FIFO: lpush (izq) en la API, brpop (der) en el worker → el más viejo primero.
- Worker usa brpop bloqueante (no rpop) + timeout=5 (atender Ctrl+C) + try/except
  TimeoutError (condición de carrera del socket Windows→WSL).
- Worker maneja la sesión a mano (SessionLocal + try/finally), sin Depends(get_db).
- WebSocket usa asyncio.to_thread (no bloquear el loop con la query síncrona) y asyncio.sleep.
- Dashboard sin dependencias; URL del WS derivada de location; barras con textContent (anti-XSS);
  auto-reconexión.
- Dockerfile ordenado para caché de capas; .dockerignore excluye el .env (secretos NUNCA en la
  imagen). En producción los secretos se inyectan por variables de entorno, no horneados.
- Config por variables de entorno; secretos en .env (en .gitignore). redis_host/redis_port con
  defaults (estándar); database_url sin default a propósito (secreto, debe fallar si falta).

## Estado actual (retomar aquí)
ETAPA 5 casi lista. Contenerización COMPLETA y probada:
- `docker compose up --build` levanta api + worker + postgres + redis con un comando.
- Migraciones automáticas al arrancar (entrypoint.sh); la tabla events se crea sola en la
  base nueva del contenedor. /health y /metrics/summary responden dentro de Docker.
- Datos persisten en el volumen postgres_data; DBeaver se conecta por el 5433.
- Resueltos los líos de ENTRYPOINT/CMD y la race condition de migraciones.

PENDIENTE INMEDIATO:
1. ACTUALIZAR GITHUB: ya se subió el repo antes, pero hay commits nuevos → hacer push para
   ponerlo al día (Render lo necesita). Antes del push, confirmar con `git status --ignored`
   que el .env sigue ignorado (NO subir la contraseña).
2. Pieza 5.4: desplegar en Render (Web Service + Worker + Postgres + Redis gestionados),
   variables de entorno, revisar CORS, obtener la URL pública.
3. Al desplegar: agregar el link de la DEMO EN VIVO al CV (ya tiene el link del repo).

Tareas de portafolio pendientes (tras el despliegue):
- README con GIF del dashboard en vivo, arquitectura, stack y cómo correrlo (docker compose up).
- Documento de "decisiones de diseño y su porqué" (guion de defensa para entrevista).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.