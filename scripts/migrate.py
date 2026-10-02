"""Apply pending additive migrations in one psql session without deleting local data."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
commands = []
for database in ("ledger_csharp", "ledger_java", "audit_csharp", "audit_java"):
    folder = "audit-migrations" if database.startswith("audit_") else "migrations"
    commands.append("\\connect " + database)
    for migration in sorted((root / "db" / folder).glob("*.sql")):
        version = int(migration.name.split("-")[0])
        commands.extend([
            f"SELECT NOT EXISTS(SELECT 1 FROM schema_migrations WHERE version={version}) AS pending",
            "\\gset", "\\if :pending", "\\i /lab/"+folder+"/"+migration.name,
            "\\echo " + database + ": applied " + migration.name, "\\endif",
        ])
subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
    cwd=root, input="\n".join(commands)+"\n", text=True, check=True)
