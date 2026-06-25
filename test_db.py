from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    resultado = conn.execute(text("SELECT 1"))
    print("Conexión exitosa:", resultado.scalar())