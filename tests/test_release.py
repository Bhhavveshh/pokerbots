import hashlib
import json
import unittest
import zipfile

from tools.official_match import ROOT, RUNTIME_FILES, snapshot


class ReleaseTests(unittest.TestCase):
    def test_default_runtime_is_exactly_the_selected_tested_baseline(self):
        release = json.loads((ROOT / "experiments/release.json").read_text())
        self.assertEqual(release["version"], "v1")
        self.assertEqual(snapshot(), release["source_sha256"])
        archive = ROOT / release["snapshot"]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), release["snapshot_sha256"])
        with zipfile.ZipFile(archive) as frozen:
            for name in RUNTIME_FILES:
                self.assertEqual((ROOT / name).read_bytes(), frozen.read(name), name)
