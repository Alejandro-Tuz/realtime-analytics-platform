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
                 Monta StaticFiles en /static para servir el dashboard.
  static/
    index.html — Dashboard en vivo (HTML/CSS/JS puro, sin frameworks). Se conecta al
                 WebSocket, muestra total/usuarios únicos/eventos por tipo con barras,
                 destella los números al cambiar, indicador de conexión y auto-reconexión.
                 La URL del WS se deriva de location.host (sirve en local y en prod).

worker.py      — Proceso aparte (NO es la API). Consume events_queue con brpop, deserializa
                 el JSON, reconstruye el Event ORM y lo guarda en PostgreSQL. Se corre solo.
alembic/
  env.py       — Configura Alembic para usar settings.database_url y detectar Base.metadata.
  versions/    — Migraciones versionadas; la primera crea la tabla events con sus índices.

test_db.py     — Script one-shot para verificar conectividad con la DB (no es suite de tests).
```

El flujo de ingesta (etapa 3): `POST /events` → validación Pydantic → `redis.lpush("events_queue")` → respuesta 202 → `worker.py` consume con `brpop` → deserializa JSON → reconstruye Event ORM → `db.commit()` → PostgreSQL.

El flujo de métricas (etapa 4): `GET /metrics/summary` o `WS /ws/metrics` → `get_summary()` (SQL agregado) → PostgreSQL → JSON al cliente → dashboard en /static/index.html. El WebSocket lo empuja cada 3 s.

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
4. [HECHO] Endpoints de métricas + dashboard en vivo por WebSocket.
5. [EN CURSO] Empaquetado con Docker y despliegue (Render/Railway/Fly.io).

## Plan de la etapa 5 (EN CURSO) — Docker y despliegue
Objetivo: pasar de "corre en mi máquina" a un LINK EN VIVO en internet.
Piezas previstas (a confirmar/ajustar cuando arranquemos):
- 5.1 Dockerfile de la app (API + worker comparten imagen; se corren como
      procesos/servicios distintos con el mismo código).
- 5.2 docker-compose.yml para levantar TODO junto en local: api, worker,
      postgres, redis. Reemplaza el arranque manual de cada servicio.
      Ojo: dentro de compose, los hosts ya NO son localhost sino los nombres
      de servicio (p. ej. DATABASE_URL apunta a "postgres", REDIS_HOST="redis").
- 5.3 Ajustes para producción: variables de entorno en el proveedor (no .env),
      aplicar migraciones en el arranque (alembic upgrade head), CORS si aplica.
- 5.4 Despliegue en Render (u otro): crear los servicios (web = API, worker,
      Postgres y Redis gestionados), conectar el repo, configurar variables,
      obtener la URL pública. El dashboard ya usa wss:// automático por
      derivar la URL de location, así que debería funcionar sin tocar el HTML.

Conceptos nuevos de esta etapa (explicar antes de escribir):
- Imagen vs contenedor; Dockerfile (receta) vs docker-compose (orquesta varios).
- Capas de la imagen y caché (orden de COPY/RUN para builds rápidos).
- Redes de docker-compose: los servicios se hablan por nombre de servicio.
- Volúmenes para que los datos de Postgres persistan.
- Diferencia entre el entorno local (WSL/Windows) y el de producción.

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
- Dashboard: HTML/CSS/JS puro, cero dependencias externas (mantiene el mensaje
  "esto es backend"). La URL del WS se deriva de location.host para servir en
  local y en producción sin cambios. Barras construidas con createElement +
  textContent (no innerHTML) para evitar XSS. Auto-reconexión si cae el server.
- Configuración por variables de entorno; secretos en .env (en .gitignore).
  redis_host/redis_port llevan defaults (localhost/6379) por ser estándar;
  database_url NO lleva default a propósito (es secreto y debe fallar si falta).

## Estado actual (retomar aquí)
ETAPA 4 COMPLETA. El sistema funciona de punta a punta y con dashboard pulido:
- POST /events → Redis → worker.py → PostgreSQL → get_summary() → WebSocket →
  dashboard en /static/index.html actualizándose en vivo.
- Dashboard rediseñado (tema oscuro tipo consola de telemetría, tarjetas,
  barras por tipo, indicador de conexión, auto-reconexión, wss:// automático).
- Todo probado con eventos reales; los números y barras se actualizan solos.

SIGUIENTE — ETAPA 5 (retomar aquí): Docker y despliegue. Ver "Plan de la etapa 5".
Empezar por el concepto de Docker (imagen vs contenedor) antes de escribir el
Dockerfile. Luego docker-compose para levantar api+worker+postgres+redis juntos,
y finalmente el despliegue en Render para obtener la URL pública.

Tareas de portafolio pendientes (además del despliegue):
- README con GIF del dashboard en vivo, descripción, arquitectura y cómo correrlo.
- Documento de "decisiones de diseño y su porqué" (guion de defensa para entrevista).

## Limpieza pendiente
- El proyecto quedó anidado (analytics-realtime/analytics-realtime). Trabajar
  siempre en la carpeta interna.