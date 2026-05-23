"""Unit tests for `_hash_normalized.py`. Phase 5 Stage A1.

Coverage:
    - normalize_eol pure function (LF identity, CRLF -> LF, mixed,
      lone CR preserved, empty bytes, no trailing newline).
    - hash_pair single-file (pure LF, pure CRLF, mixed, BOM preserved,
      missing file raises).
    - compare two-file (LF vs LF identical, LF vs CRLF eol-artefact,
      true mismatch, both empty).
    - CLI single-file mode (success + missing file).
    - CLI --compare mode (equal + differ + missing).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _hash_normalized as hn  # noqa: E402


class NormalizeEolTests(unittest.TestCase):
    def test_pure_lf_identity(self):
        self.assertEqual(hn.normalize_eol(b"line1\nline2\n"), b"line1\nline2\n")

    def test_pure_crlf_collapses_to_lf(self):
        self.assertEqual(hn.normalize_eol(b"line1\r\nline2\r\n"), b"line1\nline2\n")

    def test_mixed_lf_and_crlf(self):
        self.assertEqual(hn.normalize_eol(b"a\r\nb\nc\r\n"), b"a\nb\nc\n")

    def test_lone_cr_preserved(self):
        # Lone CR (old MacOS line ending; rare) is intentional content; do not strip.
        self.assertEqual(hn.normalize_eol(b"a\rb\rc"), b"a\rb\rc")

    def test_empty_bytes(self):
        self.assertEqual(hn.normalize_eol(b""), b"")

    def test_no_trailing_newline(self):
        self.assertEqual(hn.normalize_eol(b"no trailing nl"), b"no trailing nl")


class HashPairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hnpair-")

    def tearDown(self):
        for f in Path(self.tmp).iterdir():
            f.unlink()
        os.rmdir(self.tmp)

    def _write(self, name: str, data: bytes) -> Path:
        p = Path(self.tmp) / name
        p.write_bytes(data)
        return p

    def test_pure_lf_file(self):
        p = self._write("lf.txt", b"alpha\nbeta\n")
        d = hn.hash_pair(p)
        # For a pure-LF file, raw and normalized hashes are identical
        # and byte counts equal.
        self.assertEqual(d["raw_sha256"], d["normalized_sha256"])
        self.assertEqual(d["raw_bytes"], d["normalized_bytes"])
        self.assertEqual(d["raw_bytes"], len(b"alpha\nbeta\n"))

    def test_pure_crlf_file(self):
        p = self._write("crlf.txt", b"alpha\r\nbeta\r\n")
        d = hn.hash_pair(p)
        # Raw and normalized differ; normalized byte count is smaller by
        # exactly the number of CR bytes removed.
        self.assertNotEqual(d["raw_sha256"], d["normalized_sha256"])
        self.assertEqual(d["raw_bytes"], 13)
        self.assertEqual(d["normalized_bytes"], 11)
        # Normalized hash of pure-CRLF must equal raw hash of pure-LF
        # for the same logical content.
        lf = self._write("lf-same.txt", b"alpha\nbeta\n")
        self.assertEqual(d["normalized_sha256"], hn.hash_pair(lf)["raw_sha256"])

    def test_mixed_eol_file(self):
        p = self._write("mix.txt", b"a\r\nb\nc\r\n")
        d = hn.hash_pair(p)
        self.assertEqual(d["raw_bytes"], 8)
        self.assertEqual(d["normalized_bytes"], 6)

    def test_bom_preserved(self):
        # BOM is semantic and must NOT be stripped by normalize_eol.
        bom_lf = self._write("bom_lf.txt", b"\xef\xbb\xbfhello\n")
        bom_crlf = self._write("bom_crlf.txt", b"\xef\xbb\xbfhello\r\n")
        d_lf = hn.hash_pair(bom_lf)
        d_crlf = hn.hash_pair(bom_crlf)
        # Different raw (autocrlf artefact) but same normalized (real content equal).
        self.assertNotEqual(d_lf["raw_sha256"], d_crlf["raw_sha256"])
        self.assertEqual(d_lf["normalized_sha256"], d_crlf["normalized_sha256"])

    def test_missing_file_raises(self):
        p = Path(self.tmp) / "missing.txt"
        with self.assertRaises(FileNotFoundError):
            hn.hash_pair(p)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hncmp-")

    def tearDown(self):
        for f in Path(self.tmp).iterdir():
            f.unlink()
        os.rmdir(self.tmp)

    def _write(self, name: str, data: bytes) -> Path:
        p = Path(self.tmp) / name
        p.write_bytes(data)
        return p

    def test_lf_vs_lf_identical(self):
        a = self._write("a.txt", b"hello\nworld\n")
        b = self._write("b.txt", b"hello\nworld\n")
        r = hn.compare(a, b)
        self.assertTrue(r["raw_match"])
        self.assertTrue(r["normalized_match"])
        self.assertFalse(r["eol_artefact_only"])

    def test_lf_vs_crlf_eol_artefact_only(self):
        # The exact scenario from Phase 4 Stage 6 example-erp-02 e2e.
        a = self._write("local_lf.md", b"# title\nline 1\nline 2\n")
        b = self._write("checkout_crlf.md", b"# title\r\nline 1\r\nline 2\r\n")
        r = hn.compare(a, b)
        self.assertFalse(r["raw_match"])
        self.assertTrue(r["normalized_match"])
        self.assertTrue(r["eol_artefact_only"])

    def test_true_mismatch(self):
        a = self._write("a.txt", b"alpha\nbeta\n")
        b = self._write("b.txt", b"alpha\nGAMMA\n")
        r = hn.compare(a, b)
        self.assertFalse(r["raw_match"])
        self.assertFalse(r["normalized_match"])
        self.assertFalse(r["eol_artefact_only"])

    def test_both_empty(self):
        a = self._write("a.txt", b"")
        b = self._write("b.txt", b"")
        r = hn.compare(a, b)
        self.assertTrue(r["raw_match"])
        self.assertTrue(r["normalized_match"])
        self.assertFalse(r["eol_artefact_only"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hncli-")
        self.module = HERE / "_hash_normalized.py"

    def tearDown(self):
        for f in Path(self.tmp).iterdir():
            f.unlink()
        os.rmdir(self.tmp)

    def _write(self, name: str, data: bytes) -> Path:
        p = Path(self.tmp) / name
        p.write_bytes(data)
        return p

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.module), *args],
            capture_output=True,
            text=True,
        )

    def test_single_file_success(self):
        p = self._write("a.txt", b"hello\n")
        r = self._run(str(p))
        self.assertEqual(r.returncode, 0)
        self.assertIn("raw_sha256=", r.stdout)
        self.assertIn("normalized_sha256=", r.stdout)
        self.assertIn("raw_bytes=6", r.stdout)
        self.assertIn("normalized_bytes=6", r.stdout)

    def test_single_file_missing(self):
        r = self._run(str(Path(self.tmp) / "nope.txt"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("file not found", r.stderr)

    def test_compare_equal_eol_artefact(self):
        a = self._write("lf.md", b"x\ny\n")
        b = self._write("crlf.md", b"x\r\ny\r\n")
        r = self._run("--compare", str(a), str(b))
        self.assertEqual(r.returncode, 0)
        self.assertIn("RESULT=EQUAL", r.stdout)
        self.assertIn("eol_artefact_only=true", r.stdout)

    def test_compare_differ(self):
        a = self._write("a.txt", b"alpha\n")
        b = self._write("b.txt", b"beta\n")
        r = self._run("--compare", str(a), str(b))
        self.assertEqual(r.returncode, 2)
        self.assertIn("RESULT=DIFFER", r.stdout)

    def test_compare_missing(self):
        a = self._write("a.txt", b"x")
        r = self._run("--compare", str(a), str(Path(self.tmp) / "nope.txt"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("file not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
