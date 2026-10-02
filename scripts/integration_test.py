"""Black-box acceptance tests for both implementations and real infrastructure."""
import base64
import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contract_check import validate_response

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [("csharp", os.environ.get("BASE_CSHARP", "http://127.0.0.1:19081")),
    ("java", os.environ.get("BASE_JAVA", "http://127.0.0.1:19082"))]
ENV = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line)
RESULTS = []

def request(base, method, path, token=None, body=None, key=None):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    if key: headers["Idempotency-Key"] = key
    data = None if body is None else json.dumps(body).encode()
    start = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers, method=method), timeout=30) as response:
            raw = response.read()
            content = json.loads(raw) if raw else None
            validate_response(method, path, response.status, content)
            return response.status, content, time.monotonic() - start
    except urllib.error.HTTPError as error:
        raw = error.read()
        try: content = json.loads(raw)
        except json.JSONDecodeError: content = raw.decode()
        return error.code, content, time.monotonic() - start

def token_for(username):
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": "banking-lab",
        "username": username, "password": ENV["LAB_USER_PASSWORD"]}).encode()
    with urllib.request.urlopen("http://127.0.0.1:18180/realms/banking-lab/protocol/openid-connect/token", data, timeout=10) as response:
        return json.load(response)["access_token"]

def subject(token):
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]

def sql(database, statement, check=True):
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", database, "-At", "-c", statement],
        cwd=ROOT, capture_output=True, text=True)
    if check and process.returncode: raise AssertionError(process.stderr)
    return process

def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)

def wait_for(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate(): return
        except (OSError, AssertionError): pass
        time.sleep(0.5)
    raise AssertionError("Timed out waiting for observable state")

class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for _, base in TARGETS:
            wait_for(lambda: request(base, "GET", "/health/ready")[0] == 200, timeout=600)
        wait_for(lambda: urllib.request.urlopen("http://127.0.0.1:18180/realms/banking-lab/.well-known/openid-configuration", timeout=3).status == 200)
        cls.alice = token_for("alice"); cls.bob = token_for("bob"); cls.guest = token_for("guest")

    def accounts(self, base, amount=1000, owner=None, destination_amount=0, destination_currency="USD"):
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for account_id, minor, currency in [(ids[0], amount, "USD"), (ids[1], destination_amount, destination_currency)]:
            status, _, _ = request(base, "POST", "/api/accounts", self.alice, {
                "id": account_id, "ownerId": owner or subject(self.alice), "openingMinor": minor, "currency": currency})
            self.assertEqual(201, status)
        return ids

    def transfer(self, base, ids, amount=100, key=None, token=None, currency="USD"):
        return request(base, "POST", "/api/transfers", token or self.alice, {
            "sourceId": ids[0], "destinationId": ids[1], "amountMinor": amount, "currency": currency}, key or str(uuid.uuid4()))

    def balance(self, base, account_id):
        status, view, _ = request(base, "GET", "/api/accounts/" + account_id, self.alice)
        self.assertEqual(200, status)
        return view["balanceMinor"]

    def test_01_authentication_and_roles(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                self.assertEqual(401, request(base, "POST", "/api/accounts", body={})[0])
                self.assertEqual(401, request(base, "GET", "/api/accounts/" + str(uuid.uuid4()), "not-a-token")[0])
                self.assertEqual(403, request(base, "POST", "/api/accounts", self.bob, {})[0])
                self.assertEqual(403, request(base, "POST", "/api/transfers", self.guest, {})[0])

    def test_02_owner_authorization(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base)
                self.assertEqual(403, request(base, "GET", "/api/accounts/" + ids[0], self.bob)[0])
                self.assertEqual(403, self.transfer(base, ids, token=self.bob)[0])
                self.assertEqual(1000, self.balance(base, ids[0]))

    def test_03_double_entry_and_replay(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base)
                self.assertEqual(201, self.transfer(base, ids)[0])
                self.assertEqual([900, 100], [self.balance(base, item) for item in ids])
                for item in ids:
                    status, events, _ = request(base, "GET", f"/api/accounts/{item}/events", self.alice)
                    self.assertEqual(200, status)
                    self.assertEqual([1, 2], [event["version"] for event in events])
                    self.assertEqual(self.balance(base, item), sum(event["delta"] for event in events))

    def test_04_exact_retry_and_payload_conflict(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base); key = str(uuid.uuid4())
                first = self.transfer(base, ids, key=key); second = self.transfer(base, ids, key=key)
                self.assertEqual((201, first[1]), second[:2])
                conflict = self.transfer(base, ids, amount=101, key=key)
                self.assertEqual(409, conflict[0]); self.assertEqual("idempotency_conflict", conflict[1]["code"])
                self.assertEqual(900, self.balance(base, ids[0]))

    def test_05_concurrent_duplicate_requests(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base); key = str(uuid.uuid4())
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    results = list(pool.map(lambda _: self.transfer(base, ids, key=key), range(24)))
                self.assertTrue(all(result[0] == 201 for result in results))
                self.assertEqual(1, len({result[1]["id"] for result in results}))
                self.assertEqual(900, self.balance(base, ids[0]))

    def test_06_concurrent_distinct_requests_conserve_money(self):
        for name, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base, amount=100_000)
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    results = list(pool.map(lambda _: self.transfer(base, ids, amount=100), range(40)))
                self.assertTrue(all(result[0] == 201 for result in results))
                self.assertEqual([96_000, 4000], [self.balance(base, item) for item in ids])
                latencies = sorted(result[2] * 1000 for result in results)
                RESULTS.append({"implementation": name, "requests": 40, "concurrency": 12,
                    "p50_ms": round(statistics.median(latencies), 2), "p95_ms": round(latencies[int(len(latencies) * .95) - 1], 2)})

    def test_07_concurrent_overdraft(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base, amount=100)
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                    results = list(pool.map(lambda _: self.transfer(base, ids, amount=30), range(10)))
                self.assertEqual(3, sum(result[0] == 201 for result in results))
                self.assertEqual(7, sum(result[0] == 422 for result in results))
                self.assertEqual([10, 90], [self.balance(base, item) for item in ids])

    def test_08_invalid_transfers_leave_no_effect(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base)
                for amount in [0, -1, 1001, 9_000_000_000_001]:
                    self.assertEqual(422, self.transfer(base, ids, amount=amount)[0])
                self.assertEqual(422, self.transfer(base, [ids[0], ids[0]])[0])
                self.assertEqual(404, self.transfer(base, [ids[0], str(uuid.uuid4())])[0])
                self.assertEqual(422, self.transfer(base, ids, currency="EUR")[0])
                self.assertEqual(1000, self.balance(base, ids[0])); self.assertEqual(0, self.balance(base, ids[1]))

    def test_09_strict_contract(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base)
                for amount in [1.5, None, "100"]:
                    self.assertEqual(400, self.transfer(base, ids, amount=amount)[0])
                self.assertEqual(400, request(base, "POST", "/api/transfers", self.alice, {}, str(uuid.uuid4()))[0])
                self.assertEqual(422, self.transfer(base, ids, key="invalid")[0])

    def test_10_transaction_rolls_back_when_outbox_insert_fails(self):
        for name, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base); database = "ledger_" + name
                sql(database, f"""CREATE FUNCTION lab_outbox_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.payload->>'sourceId' = '{ids[0]}' THEN RAISE EXCEPTION 'synthetic_outbox_failure'; END IF; RETURN NEW; END $$;
                CREATE TRIGGER lab_outbox_failure BEFORE INSERT ON outbox FOR EACH ROW EXECUTE FUNCTION lab_outbox_failure();""")
                try:
                    key = str(uuid.uuid4())
                    self.assertEqual(500, self.transfer(base, ids, key=key)[0])
                    self.assertEqual([1000, 0], [self.balance(base, item) for item in ids])
                    self.assertEqual("0", sql(database, f"SELECT count(*) FROM transfers WHERE request_key='{key}'").stdout.strip())
                    self.assertEqual("2", sql(database, f"SELECT count(*) FROM account_events WHERE account_id IN ('{ids[0]}','{ids[1]}')").stdout.strip())
                finally:
                    sql(database, "DROP TRIGGER lab_outbox_failure ON outbox; DROP FUNCTION lab_outbox_failure();")

    def test_11_risk_plugins_and_reconciliation(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                status, findings, _ = request(base, "POST", "/api/risk/evaluate", self.alice,
                    {"amountMinor": 1_000_001, "recentTransfers": 5, "sanctionsMatch": True})
                self.assertEqual(200, status)
                self.assertEqual(["amount", "sanctions", "velocity"], [item["rule"] for item in findings])
                self.assertTrue(all(item["blocked"] for item in findings))
                status, rows, _ = request(base, "POST", "/api/reconciliation", self.alice, {
                    "internalRows": [{"reference": "a", "minor": 10}], "providerRows": [{"reference": "a", "minor": 11}]})
                self.assertEqual(200, status); self.assertEqual([{"reference": "a", "kind": "amount_mismatch"}], rows)

    def test_12_delivery_and_duplicate_recovery(self):
        for name, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base); transfer_id = self.transfer(base, ids)[1]["id"]
                count = lambda: int(sql("audit_" + name, f"SELECT count(*) FROM inbox WHERE transfer_id='{transfer_id}'").stdout.strip())
                wait_for(lambda: count() == 1)
                sql("ledger_" + name, f"UPDATE outbox SET published_at=NULL WHERE payload->>'transferId'='{transfer_id}'")
                wait_for(lambda: sql("ledger_" + name, f"SELECT count(*) FROM outbox WHERE payload->>'transferId'='{transfer_id}' AND published_at IS NULL").stdout.strip() == "0")
                time.sleep(2); self.assertEqual(1, count())

    def test_13_broker_outage_keeps_transfer_durable(self):
        compose("stop", "kafka"); transfers = []
        try:
            for name, base in TARGETS:
                ids = self.accounts(base); result = self.transfer(base, ids)
                self.assertEqual(201, result[0]); self.assertEqual(900, self.balance(base, ids[0]))
                transfers.append((name, result[1]["id"]))
                self.assertEqual("1", sql("ledger_" + name,
                    f"SELECT count(*) FROM outbox WHERE payload->>'transferId'='{result[1]['id']}' AND published_at IS NULL").stdout.strip())
        finally:
            compose("start", "kafka")
        for name, transfer_id in transfers:
            wait_for(lambda: sql("audit_" + name, f"SELECT count(*) FROM inbox WHERE transfer_id='{transfer_id}'").stdout.strip() == "1", timeout=180)

    def test_14_event_store_is_append_only_for_runtime_role(self):
        for name, _ in TARGETS:
            with self.subTest(implementation=name):
                result = sql("ledger_" + name, f"SET ROLE ledger_{name}; UPDATE account_events SET delta=0", check=False)
                self.assertNotEqual(0, result.returncode); self.assertIn("permission denied", result.stderr)

    def test_15_inventory_retry_cancel_and_owner(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                product = str(uuid.uuid4()); reservation = str(uuid.uuid4())
                self.assertEqual(201, request(base, "POST", "/api/products", self.alice, {"id": product, "stock": 10})[0])
                path = f"/api/products/{product}/reservations"
                body = {"reservationId": reservation, "quantity": 3, "expectedVersion": 0}
                first = request(base, "POST", path, self.alice, body)
                self.assertEqual(201, first[0]); self.assertEqual(7, first[1]["available"])
                self.assertEqual(first[:2], request(base, "POST", path, self.alice, body)[:2])
                self.assertEqual(403, request(base, "DELETE", path + f"/{reservation}?expectedVersion=1", self.bob)[0])
                cancelled = request(base, "DELETE", path + f"/{reservation}?expectedVersion=1", self.alice)
                self.assertEqual(200, cancelled[0]); self.assertEqual(10, cancelled[1]["available"])
                self.assertEqual(cancelled[:2], request(base, "DELETE", path + f"/{reservation}?expectedVersion=1", self.alice)[:2])
                self.assertEqual(409, request(base, "POST", path, self.alice, body)[0])

    def test_16_inventory_concurrent_versions_and_oversell(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                product = str(uuid.uuid4())
                self.assertEqual(201, request(base, "POST", "/api/products", self.alice, {"id": product, "stock": 10})[0])
                path = f"/api/products/{product}/reservations"
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                    results = list(pool.map(lambda _: request(base, "POST", path, self.alice,
                        {"reservationId": str(uuid.uuid4()), "quantity": 3, "expectedVersion": 0}), range(10)))
                self.assertEqual(1, sum(item[0] == 201 for item in results))
                self.assertEqual(9, sum(item[0] == 409 for item in results))
                self.assertEqual(422, request(base, "POST", path, self.alice,
                    {"reservationId": str(uuid.uuid4()), "quantity": 8, "expectedVersion": 1})[0])
                self.assertEqual(7, request(base, "GET", f"/api/products/{product}", self.alice)[1]["available"])

    def test_17_onboarding_eligibility_and_atomic_opening(self):
        for name, base in TARGETS:
            with self.subTest(base=base):
                key = str(uuid.uuid4())
                status, rejected, _ = request(base, "POST", "/api/onboarding", self.bob,
                    {"applicantReference": "pending:" + str(uuid.uuid4()), "currency": "USD"}, key)
                self.assertEqual(201, status)
                self.assertEqual({"state": "Rejected", "accountId": None}, rejected)
                key = str(uuid.uuid4())
                body = {"applicantReference": "verified:" + str(uuid.uuid4()), "currency": "USD"}
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                    results = list(pool.map(lambda _: request(base, "POST", "/api/onboarding", self.bob, body, key), range(6)))
                self.assertTrue(all(item[0] == 201 for item in results))
                account_ids = {item[1]["accountId"] for item in results}
                self.assertEqual(1, len(account_ids))
                account_id = account_ids.pop()
                self.assertEqual("Opened", results[0][1]["state"])
                self.assertEqual(0, request(base, "GET", "/api/accounts/" + account_id, self.bob)[1]["balanceMinor"])
                self.assertEqual(409, request(base, "POST", "/api/onboarding", self.bob,
                    {"applicantReference": "verified:different", "currency": "USD"}, key)[0])
                self.assertEqual("1", sql("ledger_" + name, f"SELECT count(*) FROM onboarding WHERE request_id='{key}'").stdout.strip())

    def test_18_database_rejects_unbalanced_postings(self):
        for name, base in TARGETS:
            with self.subTest(implementation=name):
                ids = self.accounts(base)
                transfer_id = str(uuid.uuid4())
                result = sql("ledger_" + name, f"""INSERT INTO transfers(id,actor,request_key,fingerprint,source_id,destination_id,amount_minor,currency)
                    VALUES('{transfer_id}','database-guard','{uuid.uuid4()}','synthetic','{ids[0]}','{ids[1]}',1,'USD')""", check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("unbalanced_transfer", result.stderr)
                self.assertEqual("0", sql("ledger_" + name, f"SELECT count(*) FROM transfers WHERE id='{transfer_id}'").stdout.strip())

    def test_19_opposite_transfers_do_not_deadlock(self):
        for _, base in TARGETS:
            with self.subTest(base=base):
                ids = self.accounts(base, amount=10_000, destination_amount=10_000)
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    results = list(pool.map(lambda i: self.transfer(base, ids if i % 2 == 0 else list(reversed(ids)), amount=100), range(40)))
                self.assertTrue(all(item[0] == 201 for item in results))
                self.assertEqual([10_000, 10_000], [self.balance(base, item) for item in ids])

    def test_20_database_rejects_late_extra_posting(self):
        for name, base in TARGETS:
            with self.subTest(implementation=name):
                ids = self.accounts(base)
                receipt = self.transfer(base, ids)[1]
                third_account = self.accounts(base)[0]
                event_id = str(uuid.uuid4())
                result = sql("ledger_" + name, f"""SET ROLE ledger_{name};
                    INSERT INTO account_events(event_id,account_id,version,delta,currency,transfer_id)
                    VALUES('{event_id}','{third_account}',2,100,'USD','{receipt['id']}')""", check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("unbalanced_transfer", result.stderr)
                self.assertEqual("0", sql("ledger_" + name, f"SELECT count(*) FROM account_events WHERE event_id='{event_id}'").stdout.strip())
                self.assertEqual(1000, self.balance(base, third_account))

if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
    output = ROOT / "artifacts" / "integration"; output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps({
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "targets": dict(TARGETS), "latency_samples": RESULTS,
        "note": "Local contention sample, not a production capacity benchmark."}, indent=2), encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
