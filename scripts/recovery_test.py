"""Black-box recovery: poison events, immutable quarantine, DLQ retries and outbox age."""
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid
from integration_test import ROOT, TARGETS, Acceptance, request, sql, broker, wait_for, token_for

def kafka(*args, input=None):
    return subprocess.run(["docker", "compose", "exec", "-T", "kafka", *args], cwd=ROOT, input=input,
        capture_output=True, text=True, timeout=180)

def logged(language, code, start, native_offset=0):
    if os.getenv("BANK_NATIVE_LOGS"):
        with (Path(os.environ["BANK_NATIVE_LOGS"])/("ledger-"+language+".log")).open("rb") as stream:
            stream.seek(native_offset)
            return code in stream.read().decode("utf-8", errors="replace")
    result = subprocess.run(["docker", "compose", "logs", "--since", str(start), "ledger-"+language], cwd=ROOT, capture_output=True, text=True)
    return code in result.stdout

class Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Acceptance.setUpClass(); cls.alice = Acceptance.alice; cls.bob = Acceptance.bob

    def test_poison_events_do_not_block_following_records(self):
        for language, _ in TARGETS:
            with self.subTest(language=language):
                marker = str(uuid.uuid4()); event = {"eventId": str(uuid.uuid4()), "type": "TransferCompleted", "schemaVersion": 1,
                    "transferId": str(uuid.uuid4()), "sourceId": str(uuid.uuid4()), "destinationId": str(uuid.uuid4()), "amountMinor": 100, "currency": "USD"}
                raw = json.dumps(event)
                poison = ["{invalid-"+marker, "{}", json.dumps({**event, "amountMinor": "100"}), json.dumps({**event, "amountMinor": 1.5}),
                    json.dumps({**event, "eventId": None}), json.dumps({**event, "schemaVersion": 2}), raw[:-1]+',"currency":"USD"}']
                messages = [*poison, raw, raw, json.dumps({**event, "amountMinor": 101})]
                result = kafka("/opt/kafka/bin/kafka-console-producer.sh", "--bootstrap-server", "localhost:29092", "--topic", "transfers."+language+".v1",
                    "--property", "parse.key=true", "--property", "key.separator=|", input="\n".join(marker+"|"+message for message in messages)+"\n")
                self.assertEqual(0, result.returncode, result.stderr[-500:])
                database = "audit_"+language
                query = "SELECT coalesce(json_agg(json_build_object('id',id,'code',error_code,'raw',raw_payload,'published',published_at IS NOT NULL,'partition',source_partition,'offset',source_offset)),'[]') FROM dead_letters WHERE payload->>'originalKey'='"+marker+"'"
                rows = lambda: json.loads(sql(database, query).stdout)
                wait_for(lambda: len(current := rows()) == 8 and all(item["published"] for item in current), timeout=180)
                rejected = rows()
                self.assertEqual(8, len({(row["partition"], row["offset"]) for row in rejected}))
                self.assertEqual(1, len({row["partition"] for row in rejected}))
                self.assertEqual(set(poison+[messages[-1]]), {row["raw"] for row in rejected})
                self.assertIn("event_identity_conflict", {row["code"] for row in rejected})
                self.assertEqual("1", sql(database, "SELECT count(*) FROM inbox WHERE event_id='"+event["eventId"]+"'").stdout.strip())
                denied = sql(database, "SET ROLE "+database+"; UPDATE dead_letters SET raw_payload='changed' WHERE id='"+rejected[0]["id"]+"'", check=False)
                self.assertNotEqual(0, denied.returncode)
                self.assertIn("permission denied", denied.stderr)
                # Replay delivery after a simulated publish/mark interruption keeps a stable failureId.
                first = rejected[0]["id"]
                sql(database, "UPDATE dead_letters SET published_at=NULL WHERE id='"+first+"'")
                wait_for(lambda: all(item["published"] for item in rows()), timeout=180)
                output = kafka("/opt/kafka/bin/kafka-console-consumer.sh", "--bootstrap-server", "localhost:29092", "--topic", "transfers."+language+".dlq.v1",
                    "--from-beginning", "--timeout-ms", "15000")
                envelopes = [json.loads(line) for line in output.stdout.splitlines() if line.startswith("{")]
                delivered = [item for item in envelopes if item.get("originalKey") == marker]
                schema = json.loads((ROOT/"contracts"/"audit-event-rejected.v1.schema.json").read_text())
                for item in delivered:
                    self.assertEqual(set(schema["required"]), set(item))
                    self.assertEqual(1, item["schemaVersion"]); self.assertEqual("AuditEventRejected", item["type"])
                    self.assertEqual("transfers."+language+".v1", item["sourceTopic"])
                    self.assertIn(item["rawPayload"], poison+[messages[-1]])
                self.assertEqual({row["id"] for row in rejected}, {item["failureId"] for item in delivered})
                self.assertGreaterEqual(sum(item["failureId"] == first for item in delivered), 2)
                self.assertEqual(8, len(rows()))

    def test_outbox_age_alert_and_recovery(self):
        fixture = Acceptance(); fixture.alice = self.alice
        for _, base in TARGETS:
            self.assertEqual(401, request(base, "GET", "/api/operations/outbox")[0])
            self.assertEqual(403, request(base, "GET", "/api/operations/outbox", self.bob)[0])
            wait_for(lambda: request(base, "GET", "/api/operations/outbox", self.alice)[1]["pending"] == 0, timeout=180)
        ids = {language: fixture.accounts(base) for language, base in TARGETS}
        start = int(time.time())
        offsets = {language: (Path(os.environ["BANK_NATIVE_LOGS"])/("ledger-"+language+".log")).stat().st_size
            if os.getenv("BANK_NATIVE_LOGS") else 0 for language, _ in TARGETS}
        broker("stop")
        try:
            for language, base in TARGETS:
                self.assertEqual(201, fixture.transfer(base, ids[language])[0])
                # Age only this test's new record; no wall-clock delay or old fixture mutation.
                sql("ledger_"+language, "UPDATE outbox SET created_at=now()-interval '120 seconds' WHERE aggregate_id='"+ids[language][0]+"'")
                status, value, _ = request(base, "GET", "/api/operations/outbox", self.alice)
                self.assertEqual(200, status); self.assertTrue(value["alert"]); self.assertGreaterEqual(value["oldestAgeSeconds"], 120)
                wait_for(lambda: logged(language, "outbox_stale", start, offsets[language]), timeout=60)
        finally: broker("start")
        for language, base in TARGETS:
            wait_for(lambda: request(base, "GET", "/api/operations/outbox", self.alice)[1]["pending"] == 0, timeout=180)
            self.assertFalse(request(base, "GET", "/api/operations/outbox", self.alice)[1]["alert"])
            wait_for(lambda: logged(language, "outbox_recovered", start, offsets[language]), timeout=60)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Recovery)
    start = time.monotonic(); result = unittest.TextTestRunner(verbosity=2).run(suite)
    destination = ROOT/"artifacts"/"integration"; destination.mkdir(parents=True, exist_ok=True)
    (destination/"recovery.json").write_text(json.dumps({"tests": result.testsRun, "successful": result.wasSuccessful(),
        "languages": [language for language, _ in TARGETS], "durationSeconds": round(time.monotonic()-start, 3)}, indent=2)+"\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
