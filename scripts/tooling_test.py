"""Security and reproducibility checks for the release handoff and load generator."""
import json
from pathlib import Path
import tempfile
import unittest
from image_bundle import IMAGES, sha256, validate
from load_test import workload, percentile

class ToolingTests(unittest.TestCase):
    def bundle(self, directory):
        names = ["banking-images.tar", *(name+".cdx.json" for name in IMAGES)]
        for name in names: (directory/name).write_text(json.dumps({"bomFormat": "CycloneDX"}) if name.endswith("json") else "example archive")
        manifest = {"commit": "a"*40, "runId": "42", "repository": "owner/repo",
            "images": [{"name": name, "image": image, "imageId": "sha256:"+"b"*64} for name, image in IMAGES.items()],
            "files": [{"name": name, "sha256": sha256(directory/name)} for name in names]}
        (directory/"manifest.json").write_text(json.dumps(manifest)); return manifest
    def test_changed_archive_is_rejected_before_docker_load(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); self.bundle(directory)
            validate(directory, "a"*40, "42", "owner/repo")
            (directory/"banking-images.tar").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "checksum"): validate(directory, "a"*40, "42", "owner/repo")
    def test_foreign_commit_and_run_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); self.bundle(directory)
            for commit, run_id in [("c"*40, "42"), ("a"*40, "43")]:
                with self.assertRaisesRegex(ValueError, "another commit"): validate(directory, commit, run_id, "owner/repo")
    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); manifest = self.bundle(directory); manifest["files"][0]["name"] = "../outside"
            (directory/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "path"): validate(directory, "a"*40, "42", "owner/repo")
    def test_incomplete_image_set_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); manifest = self.bundle(directory); manifest["images"].pop()
            (directory/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "image set"): validate(directory, "a"*40, "42", "owner/repo")
    def test_seed_controls_workload_and_retries_reuse_operation(self):
        operations = workload(42, 80, 4)
        self.assertEqual(operations, workload(42, 80, 4)); self.assertNotEqual(operations, workload(43, 80, 4))
        unique = {}
        for index, pair, amount in operations:
            if index in unique: self.assertEqual(unique[index], (pair, amount))
            unique[index] = (pair, amount)
        self.assertEqual(80, len(unique)); self.assertEqual(88, len(operations))
    def test_percentiles_use_nearest_rank(self):
        self.assertEqual(50, percentile(list(range(100, 0, -1)), .5))
        self.assertEqual(95, percentile(list(range(1, 101)), .95))
        self.assertEqual(22, percentile(list(range(1, 23)), .99))

if __name__ == "__main__": unittest.main()
