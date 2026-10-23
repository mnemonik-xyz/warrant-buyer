"""Tests for scripts/fetch_source.py. A throwaway local Git repository plays the part of GitHub."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_source.py"
spec = importlib.util.spec_from_file_location("fetch_source", SCRIPT)
fetch_source = importlib.util.module_from_spec(spec)
sys.modules["fetch_source"] = fetch_source
spec.loader.exec_module(fetch_source)

REPO = "owner/showcases"


def git(*args: str, cwd: Path) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


class FetchSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.remote = tmp / "web" / REPO
        self.remote.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.remote)
        git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=self.remote)
        marker = self.remote / "showcases" / "ionet_arc" / "buyer_mcp_server.py"
        marker.parent.mkdir(parents=True)
        marker.write_text("# buyer\n")
        git("add", "-A", cwd=self.remote)
        git("commit", "-q", "-m", "buyer", cwd=self.remote)
        self.good = git("rev-parse", "HEAD", cwd=self.remote)
        (self.remote / "other.txt").write_text("x\n")
        git("add", "-A", cwd=self.remote)
        git("commit", "-q", "-m", "other", cwd=self.remote)
        self.tip = git("rev-parse", "HEAD", cwd=self.remote)

        self.lock_path = tmp / "source.lock"
        self.dest = tmp / "src"
        env = {
            "WARRANT_SOURCE_BASE_URL": f"file://{tmp / 'web'}",
            "WARRANT_SOURCE_DIR": str(self.dest),
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        lock_patch = mock.patch.object(fetch_source, "LOCK", self.lock_path)
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

    def write_lock(self, commit: str, repo: str = REPO) -> None:
        self.lock_path.write_text(json.dumps({"repo": repo, "commit": commit}))

    def test_fetch_checks_out_the_pinned_commit_not_the_branch_tip(self):
        self.write_lock(self.good)
        self.assertEqual(fetch_source.main(["fetch"]), 0)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.dest), self.good)
        self.assertTrue((self.dest / "showcases" / "ionet_arc" / "buyer_mcp_server.py").is_file())
        self.assertFalse((self.dest / "other.txt").exists())

    def test_a_second_fetch_keeps_the_checkout(self):
        self.write_lock(self.good)
        fetch_source.main(["fetch"])
        (self.dest / "stamp").write_text("kept")
        self.assertEqual(fetch_source.main(["fetch"]), 0)
        self.assertTrue((self.dest / "stamp").exists())

    def test_a_changed_pin_replaces_the_checkout(self):
        self.write_lock(self.good)
        fetch_source.main(["fetch"])
        self.write_lock(self.tip)
        self.assertEqual(fetch_source.main(["fetch"]), 0)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.dest), self.tip)
        self.assertTrue((self.dest / "other.txt").exists())

    def test_an_unknown_commit_fails(self):
        self.write_lock("0" * 40)
        self.assertEqual(fetch_source.main(["fetch"]), 1)

    def test_a_commit_without_the_buyer_source_fails_and_leaves_nothing(self):
        git("checkout", "-q", "--orphan", "empty", cwd=self.remote)
        git("rm", "-rfq", ".", cwd=self.remote)
        (self.remote / "readme").write_text("no buyer\n")
        git("add", "-A", cwd=self.remote)
        git("commit", "-q", "-m", "empty", cwd=self.remote)
        self.write_lock(git("rev-parse", "HEAD", cwd=self.remote))
        self.assertEqual(fetch_source.main(["fetch"]), 1)
        self.assertFalse(self.dest.exists())

    def test_an_invalid_lock_is_rejected(self):
        for bad in ("main", "abc", "g" * 40):
            self.write_lock(bad)
            self.assertEqual(fetch_source.main(["fetch"]), 1, bad)
        self.write_lock(self.good, repo="not a repo; rm -rf /")
        self.assertEqual(fetch_source.main(["fetch"]), 1)

    def test_pin_writes_the_branch_tip(self):
        self.assertEqual(fetch_source.main(["pin", "main", "--repo", REPO]), 0)
        self.assertEqual(json.loads(self.lock_path.read_text()), {"repo": REPO, "commit": self.tip})

    def test_pin_refuses_an_unknown_ref_and_a_hostile_one(self):
        self.assertEqual(fetch_source.main(["pin", "nope", "--repo", REPO]), 1)
        self.assertEqual(fetch_source.main(["pin", "main; touch x", "--repo", REPO]), 1)


if __name__ == "__main__":
    unittest.main()
