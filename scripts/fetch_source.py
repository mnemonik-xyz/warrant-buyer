#!/usr/bin/env python3
"""Fetch the pinned buyer source from warrant-showcases.

The warrant-buyer wheel is built from showcases/ionet_arc in the warrant-showcases repository.
That code is shared with the seller, so it stays there. source.lock names the exact commit.

    python scripts/fetch_source.py fetch        # check out the pinned commit into .src/
    python scripts/fetch_source.py pin main     # write source.lock from a branch or tag

`fetch` checks out the commit and then confirms that HEAD is that commit. A Git commit id covers
the whole tree, so no second checksum is needed. `pin` trusts the remote once: review the
source.lock diff before you commit it.

Environment: WARRANT_SOURCE_DIR sets the target directory (default .src in the repository root),
WARRANT_SOURCE_BASE_URL replaces https://github.com (used by the tests).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "source.lock"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
MARKER = Path("showcases") / "ionet_arc" / "buyer_mcp_server.py"


class SourceError(Exception):
    pass


def source_dir() -> Path:
    override = os.environ.get("WARRANT_SOURCE_DIR")
    return Path(override).expanduser() if override else ROOT / ".src"


def base_url() -> str:
    return os.environ.get("WARRANT_SOURCE_BASE_URL", "https://github.com").rstrip("/")


def remote_url(repo: str) -> str:
    return f"{base_url()}/{repo}"


def git(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise SourceError(f"git {' '.join(args)} failed: {exc.stderr.strip() or exc.stdout.strip()}") from exc
    except FileNotFoundError as exc:
        raise SourceError("git is not installed") from exc
    return result.stdout.strip()


def read_lock() -> dict:
    if not LOCK.is_file():
        raise SourceError("source.lock does not exist. Run: python scripts/fetch_source.py pin main")
    lock = json.loads(LOCK.read_text())
    if not REPO_RE.match(lock.get("repo", "")):
        raise SourceError(f"source.lock has an invalid repo: {lock.get('repo')!r}")
    if not COMMIT_RE.match(lock.get("commit", "")):
        raise SourceError(f"source.lock has an invalid commit: {lock.get('commit')!r}")
    return lock


def fetch(args: argparse.Namespace) -> int:
    lock = read_lock()
    dest = source_dir()
    if (dest / ".git").is_dir():
        try:
            if git("rev-parse", "HEAD", cwd=dest) == lock["commit"] and (dest / MARKER).is_file():
                print(f"Source {lock['repo']}@{lock['commit'][:7]} is already in {dest}")
                return 0
        except SourceError:
            pass
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    git("init", "-q", cwd=dest)
    git("remote", "add", "origin", remote_url(lock["repo"]), cwd=dest)
    git("fetch", "-q", "--depth", "1", "origin", lock["commit"], cwd=dest)
    git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=dest)
    head = git("rev-parse", "HEAD", cwd=dest)
    if head != lock["commit"]:
        shutil.rmtree(dest)
        raise SourceError(f"Fetched {head}, but source.lock pins {lock['commit']}")
    if not (dest / MARKER).is_file():
        shutil.rmtree(dest)
        raise SourceError(f"The pinned commit has no {MARKER}")
    print(f"Source {lock['repo']}@{lock['commit'][:7]} is in {dest}")
    return 0


def pin(args: argparse.Namespace) -> int:
    if not REPO_RE.match(args.repo) or not REF_RE.match(args.ref):
        raise SourceError("Invalid repo or ref")
    out = git("ls-remote", remote_url(args.repo), f"refs/heads/{args.ref}", f"refs/tags/{args.ref}")
    lines = [line.split() for line in out.splitlines() if line]
    if not lines or not COMMIT_RE.match(lines[0][0]):
        raise SourceError(f"{args.ref!r} not found in {args.repo}")
    LOCK.write_text(json.dumps({"repo": args.repo, "commit": lines[0][0]}, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {LOCK.name}: {args.repo}@{lines[0][0][:7]}. Review it before you commit.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="check out the pinned commit into .src/").set_defaults(func=fetch)
    pin_p = sub.add_parser("pin", help="write source.lock from a branch or tag")
    pin_p.add_argument("ref", help="branch or tag, for example main")
    pin_p.add_argument("--repo", default="mnemonik-xyz/warrant-showcases")
    pin_p.set_defaults(func=pin)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
