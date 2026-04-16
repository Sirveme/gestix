"""
Runner de migraciones SQL sin Alembic.
Lee archivos .sql de app/migrations/sql/ en orden (v001_, v002_, ...)
y ejecuta solo los que no han sido aplicados aún.
"""
import os
from pathlib import Path
from sqlalchemy import text
from app.database import engine

SQL_DIR = Path(__file__).parent / "sql"
TABLA_CONTROL = "erp_migraciones"


async def ejecutar_migraciones_pendientes():
    async with engine.begin() as conn:
        # Crear tabla de control si no existe
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLA_CONTROL} (
                version VARCHAR(20) PRIMARY KEY,
                nombre VARCHAR(200),
                aplicada_en TIMESTAMP DEFAULT NOW()
            )
        """))

        # Leer versiones ya aplicadas
        result = await conn.execute(text(f"SELECT version FROM {TABLA_CONTROL}"))
        aplicadas = {row[0] for row in result.fetchall()}

        # Leer archivos .sql ordenados
        archivos = sorted([
            f for f in os.listdir(SQL_DIR)
            if f.endswith(".sql")
        ])

        for archivo in archivos:
            version = archivo.split("_")[0]  # v001, v002, ...
            if version in aplicadas:
                continue

            sql_path = SQL_DIR / archivo
            sql = sql_path.read_text(encoding="utf-8")

            print(f"[migrations] Aplicando {archivo}...")

            # asyncpg no acepta múltiples sentencias en una sola llamada
            # — ejecutar una por una, ignorando líneas de comentarios
            sentencias = [
                s.strip() for s in sql.split(";")
                if s.strip() and not all(
                    line.startswith("--") for line in s.strip().splitlines() if line.strip()
                )
            ]
            for sentencia in sentencias:
                await conn.execute(text(sentencia))

            await conn.execute(text(
                f"INSERT INTO {TABLA_CONTROL} (version, nombre) VALUES (:v, :n)"
            ), {"v": version, "n": archivo})
            print(f"[migrations] ✓ {archivo} aplicado")