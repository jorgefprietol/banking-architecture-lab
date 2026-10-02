"""Restore fresh snapshots into disposable databases and compare core records."""
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parents[1]
def run(*command):
    return subprocess.run(["docker", "compose", "exec", "-T", "postgres", *command], cwd=root,
        check=True, capture_output=True, text=True).stdout.strip()
checks = {
    "ledger": "SELECT (SELECT count(*) FROM accounts),(SELECT coalesce(sum(balance_minor),0) FROM accounts),(SELECT count(*) FROM account_events),(SELECT count(*) FROM transfers),(SELECT max(version) FROM schema_migrations)",
    "audit": "SELECT count(*) FROM inbox",
}
for source in ("ledger_csharp", "ledger_java", "audit_csharp", "audit_java"):
    temporary = "restore_verify_" + uuid.uuid4().hex
    dump = "/tmp/" + temporary + ".dump"
    run("psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE " + temporary)
    try:
        run("pg_dump", "-U", "postgres", "-d", source, "--format=custom", "--file", dump)
        run("pg_restore", "-U", "postgres", "-d", temporary, "--no-owner", "--no-privileges", dump)
        query = checks[source.split("_")[0]]
        original = run("psql", "-U", "postgres", "-d", source, "-At", "-c", query)
        restored = run("psql", "-U", "postgres", "-d", temporary, "-At", "-c", query)
        assert original == restored, (source, original, restored)
        print(source + ": backup restored and core counts/balances matched")
    finally:
        # This name was generated and created by this invocation; no existing DB is touched.
        run("psql", "-U", "postgres", "-d", "postgres", "-c", "DROP DATABASE " + temporary)
        run("rm", "--", dump)
