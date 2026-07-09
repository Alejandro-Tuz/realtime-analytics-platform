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

### Sin Docker (forma manual antigua)
```
venv\Scripts\activate                     # activar entorno (Windows)
uvicorn app.main:app --reload             # API
python worker.py                          # worker (otra terminal)
alembic upgrade head                      # aplicar migraciones
python test_db.py                         # probar conexión a la DB
```

## Arquitectura del código

```
app/
  config.py    — Lee DATABASE_URL y REDIS_URL desde el entorno/.env vía pydantic-settings.
                 REDIS_URL default redis://localhost:6379.
  database.py  — engine SQLAlchemy, SessionLocal y Base.
  models.py    — Modelo ORM Event; tabla `events` con columnas e índices.
  schemas.py   — Schema Pydantic EventCreate.
  queue.py     — get_redis() con redis.Redis.from_url(REDIS_URL).
  metrics.py   — get_summary(): total, usuarios únicos (distinct), conteo por tipo (group by).
  main.py      — FastAPI. Endpoints: GET /health, POST /events (encola, 202),
                 GET /metrics/summary, WS /ws/metrics. Monta StaticFiles en /static.
  static/
    index.html — Dashboard en vivo (HTML/CSS/JS puro). WebSocket, gráfico de throughput en
                 vivo (SVG), número hero, métricas, barras por tipo, indicador de conexión,
                 auto-reconexión, wss:// automático. Consume solo total_events, unique_users
                 y events_by_type del WS (sin cambios de backend).

worker.py        — Proceso aparte. Consume events_queue con brpop, deserializa, guarda en PostgreSQL.
Dockerfile       — Imagen python:3.11-slim, caché de capas, CMD ["./entrypoint.sh"].
.dockerignore    — Excluye venv/, __pycache__, .env, .git.
entrypoint.sh    — Corre `alembic upgrade head` y luego `exec uvicorn ...`. Lo usa la API.
docker-compose.yml — api, worker (misma imagen, command distinto), postgres (volumen), redis.
                 DATABASE_URL→postgres, REDIS_URL=redis://redis:6379.
alembic/         — env.py + versions/ (migraciones).
```

Flujo de ingesta: POST /events → Pydantic → lpush("events_queue") → 202 →
worker (brpop) → Event ORM → commit → PostgreSQL.
Flujo de métricas: GET /metrics/summary o WS /ws/metrics → get_summary() → dashboard.

## Roadmap del proyecto (Plataforma de analítica en tiempo real)
1. [HECHO] API recibe y valida eventos (FastAPI + Pydantic).
2. [HECHO] Persistencia en PostgreSQL (SQLAlchemy + Alembic).
3. [HECHO] Redis + workers (ingesta asíncrona con cola).
4. [HECHO] Métricas + dashboard en vivo por WebSocket.
5. [EN CURSO] Docker y despliegue.

## Etapa 5 — Docker y despliegue
- 5.1 [HECHO] Dockerfile + .dockerignore.
- 5.2 [HECHO] docker-compose.yml (4 servicios; se hablan por nombre, no localhost).
- 5.3 [HECHO] entrypoint.sh (migra y arranca; CMD no ENTRYPOINT para que el worker sobreescriba).
- 5.3b [HECHO] Refactor Redis a REDIS_URL (from_url). Probado en local.
- 5.4 [CASI HECHO] Despliegue en Render:
  * [HECHO] PostgreSQL administrado (Oregon, free). URL postgresql:// (compatible).
  * [HECHO] Redis/Key Value administrado (Oregon, free). Internal URL combinada.
  * [HECHO] Web Service (API) desplegado y VIVO:
    https://realtime-analytics-platform.onrender.com  (Docker, master, Oregon, free).
    Migraciones corrieron, uvicorn arrancó. (Los 404 en / y el "buildcache not found"
    eran ruido inofensivo, no errores.)
  * [DECISIÓN] El Background Worker NO se despliega en Render (los workers ya no son gratis,
    ~7 USD/mes). En su lugar → ver "DEMO_MODE" abajo. La arquitectura separada (API + worker)
    SE MANTIENE INTACTA en el código y en docker-compose; DEMO_MODE es solo un truco para la
    demo pública gratuita, no un cambio de arquitectura.
  * [PENDIENTE] Ruta raíz: agregar GET "/" en main.py que redirija a /static/index.html
    (RedirectResponse), para que el link limpio muestre el dashboard y desaparezca el 404.
  * [PENDIENTE] Datos de demo: con DEMO_MODE el simulador llena la base solo (ya no hace falta
    sembrar a mano). Alternativa manual: INSERT vía DBeaver en la base de Render.

## TAREA ACTUAL (retomar aquí) — Parte 1: DEMO_MODE (simulador de tráfico)
Objetivo: que la demo pública muestre datos entrando en vivo 24/7 sin worker pago y sin
meter datos a mano. Se hace DENTRO de la API (gratis), activado solo por variable de entorno
DEMO_MODE=true (se pone SOLO en Render; en local queda apagado porque ya hay worker real).

Implementar (en plan mode, explicando cada pieza y su porqué):
1. Crear app/simulator.py con una función random_event() -> dict que genere eventos realistas
   y variados (event_name con pesos: page_view el más común; user_id tipo f"u{random 1..60}"
   para que unique_users sea realista; properties según el tipo). Que el ritmo/cantidad sea
   algo aleatorio/bursty para que el gráfico de throughput del dashboard tenga variación.
2. En main.py, usar el lifespan de FastAPI para que, SOLO si os.getenv("DEMO_MODE") == "true":
   a) Arranque el worker en un hilo daemon:  threading.Thread(target=worker.run, daemon=True).start()
      (revive el pipeline real en prod y hace que POST /events también funcione en la demo).
   b) Lance una tarea async que cada 1-2 s genere eventos con random_event() y los encole
      con lpush en Redis (mismo camino que POST /events): asyncio.create_task(generar_trafico()).
   Ojo: worker.run() es un bucle bloqueante con brpop → por eso va en un HILO, no en async.
3. En Render, en el Web Service (API), agregar la variable de entorno DEMO_MODE=true.
   NO ponerla en local (local sigue usando el worker real de docker-compose).
4. Probar en local que con DEMO_MODE apagado NO cambia nada (worker normal), y opcionalmente
   con DEMO_MODE=true un momento para ver que genera y procesa.

HONESTIDAD (importante): esto es un SIMULADOR DE TRÁFICO para la demo, no usuarios reales.
Debe mencionarse en el README ("incluye un generador de eventos para alimentar la demo en vivo").

## Errores/decisiones de la etapa 5 (para defender en entrevista)
- ENTRYPOINT vs CMD: con ENTRYPOINT el command del compose se vuelve ARGUMENTO; se usó CMD.
- Race condition en migraciones: solo la API migra (con CMD); el worker no compite.
- Puertos: DBeaver al 5433 (mapeado) que Docker reenvía al 5432 interno.
- redis.Redis.from_url + decode_responses=False: devuelve bytes que json.loads acepta.
- Servicios administrados (Render) vs contenedores propios (local/compose).
- DEMO_MODE: el diseño separa API y worker (ver docker-compose); en la demo gratuita se
  integra el worker vía bandera de entorno, manteniendo el desacople en el código. Es navegar
  el trade-off entre el diseño ideal y las restricciones reales de presupuesto.
- Plan free de Render: la API "duerme" tras inactividad (~15 min); la 1ª visita tarda ~30-60s
  en despertar. En producción real se usan planes always-on.

## Decisiones de diseño (y su porqué)
- Code-first con ORM y migraciones (esquema en git, reproducible).
- properties como JSONB (flexible por evento); campos fijos indexados.
- SQLAlchemy síncrono a propósito; endpoints de DB en def para no bloquear el event loop.
- POST /events responde 202 (ingesta asíncrona; persiste el worker).
- Cola FIFO: lpush en la API, brpop en el worker.
- Worker: brpop bloqueante + timeout=5 + try/except TimeoutError (race del socket Win→WSL);
  sesión a mano (SessionLocal + try/finally).
- WebSocket: asyncio.to_thread (no bloquear el loop) + asyncio.sleep.
- Dashboard sin dependencias; URL del WS derivada de location; barras con textContent (anti-XSS);
  auto-reconexión; gráfico de throughput calculado en el cliente (sin cambios de backend).
- .dockerignore excluye .env (secretos nunca en la imagen; se inyectan por variables de entorno).

## Estado actual (retomar aquí)
API VIVA en https://realtime-analytics-platform.onrender.com (falta pulir).
PENDIENTES para cerrar el proyecto (meta: dejarlo full hoy):
1. Implementar DEMO_MODE (ver "TAREA ACTUAL" arriba) → dashboard con datos en vivo.
2. Reemplazar app/static/index.html por la versión nueva del dashboard (gráfico de throughput
   en vivo). Es drop-in: usa los mismos datos del WS, no cambia backend.
3. Agregar GET "/" → RedirectResponse a /static/index.html (link limpio).
4. Commit + push (Render redespliega solo). Poner DEMO_MODE=true en el Web Service de Render.
5. Probar el link público y agregar la DEMO EN VIVO al CV, README y LinkedIn.
6. SEGURIDAD: rotar/resetear la contraseña de la base de Render (quedó expuesta en una captura).

Tareas de portafolio (tras cerrar):
- README con GIF del dashboard, arquitectura, stack, cómo correrlo, y mención del simulador.
- Documento de "decisiones de diseño y su porqué" (guion de defensa para entrevista).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar en la carpeta interna.