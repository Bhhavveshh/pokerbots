import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardTests(unittest.TestCase):
    def test_guard_blocks_filesystem_writes_and_network_creation(self):
        operations = ["open('must_not_be_created.txt', 'w')", "import socket; socket.socket()"]
        for operation in operations:
            result = subprocess.run(
                [sys.executable, "-B", "-c", "import tools.guarded_bot; " + operation],
                input=b"", capture_output=True, cwd=ROOT, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"PermissionError", result.stderr)
        self.assertFalse((ROOT / "must_not_be_created.txt").exists())


if __name__ == "__main__":
    unittest.main()
