"""Offline managed-path contracts on native Windows and POSIX."""

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2 import _paths
from harness2.core import runmark, tree

SURFACE = tree.SurfaceSpec(
    name="portable-test",
    always_on=("AGENTS.md",),
    always_on_max=8000,
    always_on_cap_reason="test",
    skill_dir=".agents/skills",
    skill_name_rule="overrides_dir",
    trigger_hint="test",
    autotrigger_file="AGENTS.md",
    trigger_line="test",
    subagent_requires_mode=False,
    plugin_dir=None,
    hooks_file=None,
    stubs=((".agents/skills/README.md", "stub"),),
)


class PortablePathsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="경로 테스트 ", dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_normalize_preserves_korean_spaces_and_canonicalizes_separators(self):
        self.assertEqual(_paths.normalize_rel(r".\한글 폴더\파일.txt"), "한글 폴더/파일.txt")
        self.assertEqual(_paths.normalize_rel("./a//./b.txt"), "a/b.txt")
        self.assertEqual(_paths.normalize_rel("."), "")
        self.assertEqual(_paths.normalize_rel(" leading.txt"), " leading.txt")

    def test_rejects_unsafe_or_nonportable_paths_on_every_os(self):
        invalid = (
            "../out", "a/../out", "/root", r"\root", r"C:\root", "C:relative",
            r"\\server\share\file", r"\\?\C:\file", "file:stream", "NUL",
            "con.txt", "CON .txt", "NUL .py", "COM1 .txt", "AUX .log",
            "a/COM1.py", "LPT².log", "a/CONOUT$", "name.", "name ",
            "a/name./file", 'a/ba\"d', "a/b?d", "a/b*d", "a/\x00file",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _paths.normalize_rel(value)

    def test_rejects_aliases_case_collisions_and_file_directory_conflicts(self):
        for paths in (
            ["a/b", r"a\b"], ["AGENTS.md", "agents.md"],
            ["Folder/a", "folder/b"], ["a", "a/b"], ["."],
        ):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                _paths.validate_relative_paths(paths)

    def test_tree_roundtrip_uses_posix_keys_and_excludes_nested_stubs(self):
        expected = {
            "AGENTS.md": "한글 지침\n",
            ".agents/skills/work/SKILL.md": "---\ndescription: Work\n---\nBody\n",
        }
        windows_keys = {key.replace("/", "\\"): body for key, body in expected.items()}
        (self.root / "unmanaged.txt").write_bytes(b"keep\r\n")
        tree.write_tree(SURFACE, windows_keys, self.root)
        self.assertEqual(tree.read_tree(SURFACE, self.root), expected)
        self.assertEqual(tree.skill_names(SURFACE, tree.read_tree(SURFACE, self.root)), ["work"])
        self.assertEqual((self.root / "unmanaged.txt").read_bytes(), b"keep\r\n")
        self.assertTrue((self.root / ".agents/skills/README.md").is_file())

    def test_invalid_write_is_rejected_before_deleting_existing_files(self):
        (self.root / "AGENTS.md").write_bytes(b"original\r\n")
        for bad_tree in (
            {"AGENTS.md": "new", "../outside": "bad"},
            {"AGENTS.md": "new", "agents.md": "alias"},
            {"AGENTS.md": "new", "folder": "file", "folder/file": "child"},
        ):
            with self.subTest(tree=bad_tree), self.assertRaises(ValueError):
                tree.write_tree(SURFACE, bad_tree, self.root)
            self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"original\r\n")

    def test_existing_directory_and_parent_file_conflicts_preserve_managed_files(self):
        (self.root / "AGENTS.md").write_bytes(b"original\r\n")
        (self.root / "directory").mkdir()
        (self.root / "parent-file").write_bytes(b"keep")
        for rel in ("directory", "parent-file/child.txt"):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                tree.write_tree(SURFACE, {"AGENTS.md": "new", rel: "bad"}, self.root)
            self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"original\r\n")

    def test_stub_directory_conflict_is_preflighted_before_deleting_managed_files(self):
        (self.root / "AGENTS.md").write_bytes(b"original\r\n")
        (self.root / ".agents/skills/README.md").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "existing directory"):
            tree.write_tree(SURFACE, {"AGENTS.md": "new"}, self.root)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"original\r\n")

    def test_checked_path_detects_junction_components_without_following_them(self):
        redirected = self.root / ".agents"
        with patch.object(Path, "is_junction", lambda path: path == redirected):
            with self.assertRaisesRegex(ValueError, "junction"):
                _paths.checked_path(self.root, ".agents/skills/work/SKILL.md")
        with patch.object(Path, "is_junction", lambda path: path == self.root):
            with self.assertRaisesRegex(ValueError, "root"):
                tree.read_tree(SURFACE, self.root)

    def test_existing_case_aliases_are_rejected_without_overwriting_user_files(self):
        original = self.root / "Agents.md"
        original.write_bytes(b"user instructions\r\n")
        with self.assertRaisesRegex(ValueError, "aliases"):
            _paths.checked_path(self.root, "AGENTS.md")
        with self.assertRaisesRegex(ValueError, "aliases"):
            tree.write_tree(SURFACE, {"AGENTS.md": "overwrite"}, self.root)
        self.assertEqual(original.read_bytes(), b"user instructions\r\n")

    @unittest.skipUnless(os.name == "nt", "native Windows junction test")
    def test_real_junction_is_rejected_before_read_write_and_delete(self):
        outside = self.root / "외부 보존"
        outside.mkdir()
        sentinel = outside / "SKILL.md"
        sentinel.write_bytes(b"preserve\r\n")
        managed = self.root / "managed"
        (managed / ".agents/skills").mkdir(parents=True)
        link = managed / ".agents/skills/work"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode:
            detail = (result.stdout + result.stderr).decode("mbcs", errors="replace").strip()
            self.skipTest(f"junction creation unavailable (exit {result.returncode}): {detail}")
        try:
            self.assertTrue(link.is_junction())
            with self.assertRaisesRegex(ValueError, "junction"):
                tree.read_tree(SURFACE, managed)
            with self.assertRaisesRegex(ValueError, "junction"):
                tree.write_tree(SURFACE, {"AGENTS.md": "new"}, managed)
            with self.assertRaisesRegex(ValueError, "junction"):
                _paths.checked_path(managed, ".agents/skills/work/SKILL.md")
            self.assertEqual(sentinel.read_bytes(), b"preserve\r\n")
            self.assertFalse((managed / "AGENTS.md").exists())
        finally:
            link.rmdir()

    def test_symlink_root_is_rejected_and_target_preserved(self):
        target = self.root / "target"
        target.mkdir()
        (target / "AGENTS.md").write_text("keep", encoding="utf-8")
        link = self.root / "root-link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "root"):
            tree.write_tree(SURFACE, {"AGENTS.md": "overwrite"}, link)
        self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "keep")

    def test_fingerprint_uses_portable_paths_and_bytes(self):
        nested = self.root / "한글 폴더"
        nested.mkdir()
        (nested / "file.txt").write_bytes(b"text\r\n")
        digest = hashlib.sha1("한글 폴더/file.txt".encode("utf-8") + b"\0text\r\n\0")
        self.assertEqual(runmark.fingerprint(self.root), digest.hexdigest()[:16])

    def test_relative_persistence_and_legacy_windows_separators(self):
        nested = self.root / "한글 폴더/file.txt"
        self.assertEqual(runmark.relative_path(nested, self.root), "한글 폴더/file.txt")
        self.assertEqual(runmark.resolve_path(r"한글 폴더\file.txt", self.root), nested)
        self.assertEqual(runmark.resolve_path(nested, self.root), nested)
        with self.assertRaises(ValueError):
            runmark.resolve_path("../outside", self.root)


if __name__ == "__main__":
    unittest.main()
