"""Check drift and balanced postings using stored data, without mutating it."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
queries = {
    "projection_drift": """SELECT count(*) FROM accounts a WHERE
      a.balance_minor<>(SELECT coalesce(sum(delta),0) FROM account_events e WHERE e.account_id=a.id)
      OR a.version<>(SELECT max(version) FROM account_events e WHERE e.account_id=a.id)""",
    "unbalanced_postings": """SELECT count(*) FROM (
      SELECT transfer_id FROM account_events WHERE transfer_id IS NOT NULL
      GROUP BY transfer_id HAVING count(*)<>2 OR sum(delta)<>0) violations""",
}
for database in ("ledger_csharp", "ledger_java"):
    for name, query in queries.items():
        result = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", database,
            "-At", "-c", query], cwd=root, check=True, capture_output=True, text=True)
        assert result.stdout.strip() == "0", (database, name, result.stdout)
        print(f"{database}: {name}=0")
