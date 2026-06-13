# Alembic — migraciones versionadas

Reemplaza al `infra/init-db.sql` manual. A partir de aquí, **cada cambio de
esquema vive como un archivo en `versions/`** y se aplica con un comando.

## Primer arranque (BD existente creada por init-db.sql)

Si la BD ya tiene las tablas porque las creó `init-db.sql` la primera vez:

```bash
docker exec recruitai-backend alembic stamp head
```

Esto crea la tabla `alembic_version` y la marca al día. **No toca el resto del
schema**. A partir de aquí los cambios van por migración.

## Primer arranque (BD vacía)

Si la BD está limpia:

```bash
docker exec recruitai-backend alembic upgrade head
```

Aplica todas las migraciones en orden. La primera migración recreará el schema
completo (equivalente a init-db.sql).

## Workflow día a día

1. **Cambias un modelo** en `backend/app/db/models.py`.
2. Generas la migración automáticamente:
   ```bash
   docker exec recruitai-backend alembic revision --autogenerate -m "agregar columna X a candidates"
   ```
3. **Revisas el archivo generado** en `versions/`. Alembic acierta el 90% de
   los casos; los renames de columna y los `ALTER TYPE` enum a veces los
   detecta mal — corrígelos a mano.
4. Aplicas:
   ```bash
   docker exec recruitai-backend alembic upgrade head
   ```
5. Commit del archivo `versions/...py`.

## Comandos útiles

```bash
# Ver la revisión actual de la BD
docker exec recruitai-backend alembic current

# Ver el historial
docker exec recruitai-backend alembic history

# Bajar una revisión (rollback)
docker exec recruitai-backend alembic downgrade -1

# Generar SQL sin aplicarlo (para revisión humana o CI)
docker exec recruitai-backend alembic upgrade head --sql
```

## Reglas

- **Nunca editar una migración ya aplicada en producción.** Si tienes que
  corregir algo, crea una nueva migración encima.
- **Probar siempre el downgrade** antes de commit en cambios destructivos
  (DROP, ALTER que pierde datos).
- **No mezclar cambios de schema con cambios de datos** en la misma migración
  cuando sea posible — facilita el rollback.
