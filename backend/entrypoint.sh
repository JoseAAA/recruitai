#!/bin/sh
# Entrypoint del backend RecruitAI.
#
# Aplica las migraciones de base de datos ANTES de arrancar la API. Esto evita
# el fallo "column github does not exist" / "relation llm_usage does not exist"
# en una instalación NUEVA en el cliente.
#
# Contexto:
#   - El schema base lo crea infra/init-db.sql en el primer arranque de Postgres
#     (volumen vacío). Pero las migraciones Alembic posteriores (columna
#     candidates.github, tabla llm_usage, y las que vengan) NO se aplican solas.
#   - La migración baseline (3e09fb20a612) es un no-op: representa lo que ya
#     creó init-db.sql. Por eso `alembic upgrade head` sobre una BD recién creada
#     por init-db.sql aplica EXACTAMENTE las migraciones nuevas, sin intentar
#     recrear las tablas base. Sobre una BD ya gestionada, es un no-op seguro.
#
# Resultado: el cliente solo corre el script de arranque; el schema queda
# siempre al día sin pasos manuales.
set -e

echo "[entrypoint] Esperando a la base de datos y aplicando migraciones (alembic upgrade head)..."

# El backend arranca con depends_on Postgres en condition: service_started (no
# service_healthy), así que Postgres puede tardar unos segundos en aceptar
# conexiones. Reintentamos para no morir por una carrera de arranque.
attempt=0
max_attempts=15
until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "[entrypoint] ERROR: no se pudieron aplicar las migraciones tras ${max_attempts} intentos. Abortando." >&2
        exit 1
    fi
    echo "[entrypoint] Base de datos no lista todavia (intento ${attempt}/${max_attempts}); reintento en 3s..."
    sleep 3
done

echo "[entrypoint] Migraciones al dia. Arrancando la API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
