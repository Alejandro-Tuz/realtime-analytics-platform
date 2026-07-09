import random
from datetime import datetime, timezone

EVENTOS_CON_PESO = [
    ("page_view", 60),
    ("click", 20),
    ("signup", 10),
    ("purchase", 10),
]

PAGINAS = ["/", "/pricing", "/docs", "/blog", "/about"]


def random_event() -> dict:
    nombres = [nombre for nombre, _ in EVENTOS_CON_PESO]
    pesos = [peso for _, peso in EVENTOS_CON_PESO]
    event_name = random.choices(nombres, weights=pesos, k=1)[0]

    if event_name == "page_view":
        properties = {"page": random.choice(PAGINAS)}
    elif event_name == "purchase":
        properties = {"amount": round(random.uniform(5, 200), 2)}
    else:
        properties = {}

    return {
        "event_name": event_name,
        "user_id": f"u{random.randint(1, 60)}",
        "properties": properties,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }