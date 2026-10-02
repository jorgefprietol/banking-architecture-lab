"""Apply only pending additive migrations without deleting local data."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
for database in ("ledger_csharp", "ledger_java"):
    for migration in sorted((root / "db" / "migrations").glob("*.sql")):
        version = int(migration.name.split("-")[0])
        result = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", database,
            "-At", "-c", f"SELECT count(*) FROM schema_migrations WHERE version={version}"], cwd=root, check=True, capture_output=True, text=True)
        if result.stdout.strip() == "0":
            subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres",
                "-d", database, "-f", "/lab/migrations/" + migration.name], cwd=root, check=True)
            print(database + ": applied " + migration.name)
