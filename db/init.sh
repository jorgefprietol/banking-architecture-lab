#!/bin/sh
set -eu
for database in ledger_csharp ledger_java audit_csharp audit_java; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE $database"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -v app_password="$POSTGRES_PASSWORD" -v app_role="$database" <<'SQL'
CREATE ROLE :"app_role" LOGIN PASSWORD :'app_password';
REVOKE CONNECT ON DATABASE :"app_role" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"app_role" TO :"app_role";
SQL
done
for database in ledger_csharp ledger_java; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -f /lab/ledger.sql
  for migration in /lab/migrations/*.sql; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -f "$migration"
  done
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -v app_role="$database" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT, UPDATE ON accounts, outbox, products, reservations TO :"app_role";
GRANT SELECT, INSERT ON account_events, transfers TO :"app_role";
GRANT SELECT ON schema_migrations TO :"app_role";
SQL
done
for database in audit_csharp audit_java; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -f /lab/audit.sql
  for migration in /lab/audit-migrations/*.sql; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -f "$migration"
  done
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" -v app_role="$database" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT ON inbox TO :"app_role";
GRANT SELECT ON schema_migrations TO :"app_role";
SQL
done
