"""Mirror-safe SHA256: hash both raw bytes and CRLF-normalized bytes.

Phase 5 Stage A1. Companion to `_codex_rollout.py` and `_session_jsonl.py`:
pure stdlib, no Pydantic, no <prior-iteration> imports, ASCII source.

Background
----------
Phase 4 Stage 6 e2e on `2026-05-22-example-erp-02` failed mirror byte-identity
because git's `core.autocrlf=true` rewrote LF to CRLF on checkout. The
implementer wrote the mirror file as LF locally (5851 bytes), committed
it (autocrlf kept it LF in the git object), but when the auditor later
checked it out on the same Windows machine, the working-tree copy came
back as CRLF (5881 bytes, 30 extra `\r` bytes for 30 line endings).
Raw SHA256 differed; semantic content was identical.

`hash_pair(path)` returns BOTH hashes:
    raw_sha256        sha256 of raw bytes as read from disk
    normalized_sha256 sha256 after replacing every CRLF with LF

The auditor (and implementer) compares mirrors via `normalized_sha256`.
`raw_sha256` is kept for diagnostics so the operator can see at a glance
whether the drift is a pure autocrlf artefact (raw differs + normalized
matches) or a real semantic mismatch (both differ).

Normalization scope is intentionally NARROW (LF/CRLF only):
- BOM is preserved -- it can be semantic in 1C XML metadata.
- Trailing whitespace is preserved -- can be semantic in markdown.
- Final newline is preserved -- can be semantic in some formats.
The only autocrlf artefact we immunize against is the
b"\r\n" -> b"\n" rewrite. Anything else is a real difference.

CLI
---
    python _hash_normalized.py <file>
        Prints:
            raw_sha256=<hex>
            normalized_sha256=<hex>
            raw_bytes=<int>
            normalized_bytes=<int>
        Exit 0 on success, 1 on file-not-found.

    python _hash_normalized.py --compare <file_a> <file_b>
        Prints both pairs plus a final EQUAL or DIFFER line.
        Exit 0 if normalized hashes match.
        Exit 2 if normalized hashes differ.
        Exit 1 if either file is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def _read_bytes(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_file():
        raise IsADirectoryError(str(path))
    return path.read_bytes()


def normalize_eol(raw: bytes) -> bytes:
    """Replace CRLF with LF. Lone CR is left alone (rare and usually intentional)."""
    return raw.replace(b"\r\n", b"\n")


def hash_pair(path: str | Path) -> dict:
    """Return raw + normalized SHA256 and byte counts for the file at `path`.

    Returns
    -------
    dict with keys:
        path                str  -- absolute path
        raw_sha256          str  -- hex digest of raw bytes
        normalized_sha256   str  -- hex digest after CRLF -> LF
        raw_bytes           int
        normalized_bytes    int
    """
    p = Path(path).resolve()
    raw = _read_bytes(p)
    norm = normalize_eol(raw)
    return {
        "path": str(p),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_sha256": hashlib.sha256(norm).hexdigest(),
        "raw_bytes": len(raw),
        "normalized_bytes": len(norm),
    }


def compare(path_a: str | Path, path_b: str | Path) -> dict:
    """Hash both files and return a compare result.

    Returns
    -------
    dict with keys:
        a, b                 dict from hash_pair()
        raw_match            bool
        normalized_match     bool
        eol_artefact_only    bool  -- raw differs but normalized matches
    """
    a = hash_pair(path_a)
    b = hash_pair(path_b)
    raw_match = a["raw_sha256"] == b["raw_sha256"]
    norm_match = a["normalized_sha256"] == b["normalized_sha256"]
    return {
        "a": a,
        "b": b,
        "raw_match": raw_match,
        "normalized_match": norm_match,
        "eol_artefact_only": (not raw_match) and norm_match,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="_hash_normalized",
        description="Mirror-safe SHA256 with CRLF/LF normalization.",
    )
    parser.add_argument("path", nargs="?", help="file to hash (single-file mode)")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("FILE_A", "FILE_B"),
        help="compare two files; exit 0 if normalized hashes match else exit 2",
    )
    args = parser.parse_args()

    if args.compare and args.path:
        sys.stderr.write("error: pass either <path> or --compare, not both\n")
        return 1

    if args.compare:
        try:
            res = compare(args.compare[0], args.compare[1])
        except FileNotFoundError as ex:
            sys.stderr.write("error: file not found: %s\n" % ex)
            return 1
        for side in ("a", "b"):
            d = res[side]
            sys.stdout.write("%s.path=%s\n" % (side, d["path"]))
            sys.stdout.write("%s.raw_sha256=%s\n" % (side, d["raw_sha256"]))
            sys.stdout.write("%s.normalized_sha256=%s\n" % (side, d["normalized_sha256"]))
            sys.stdout.write("%s.raw_bytes=%d\n" % (side, d["raw_bytes"]))
            sys.stdout.write("%s.normalized_bytes=%d\n" % (side, d["normalized_bytes"]))
        sys.stdout.write("raw_match=%s\n" % str(res["raw_match"]).lower())
        sys.stdout.write("normalized_match=%s\n" % str(res["normalized_match"]).lower())
        sys.stdout.write("eol_artefact_only=%s\n" % str(res["eol_artefact_only"]).lower())
        if res["normalized_match"]:
            sys.stdout.write("RESULT=EQUAL\n")
            return 0
        sys.stdout.write("RESULT=DIFFER\n")
        return 2

    if not args.path:
        parser.print_usage(sys.stderr)
        return 1

    try:
        d = hash_pair(args.path)
    except FileNotFoundError as ex:
        sys.stderr.write("error: file not found: %s\n" % ex)
        return 1
    sys.stdout.write("raw_sha256=%s\n" % d["raw_sha256"])
    sys.stdout.write("normalized_sha256=%s\n" % d["normalized_sha256"])
    sys.stdout.write("raw_bytes=%d\n" % d["raw_bytes"])
    sys.stdout.write("normalized_bytes=%d\n" % d["normalized_bytes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
