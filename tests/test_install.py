from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.py"
VALIDATOR = ROOT / "scripts" / "validate_skill.py"


class InstallerTests(unittest.TestCase):
    def test_custom_install_is_complete_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "skills"
            install = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            skill = base / "treatwell-appointments"
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertTrue((skill / "references" / "tool-contract.md").is_file())
            self.assertTrue((skill / "scripts" / "booking_ledger.py").is_file())
            self.assertEqual(
                (skill / ".treatwell-appointments-install").read_text(encoding="utf-8"),
                "treatwell-appointments\ninstaller-schema=1\n",
            )
            self.assertFalse((skill / "tests").exists())

            validation = subprocess.run(
                [sys.executable, str(VALIDATOR), str(skill)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

            refused = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(refused.returncode, 2)

            preserved = skill / "operator-notes.txt"
            preserved.write_text("keep", encoding="utf-8")
            forced = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base), "--force"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(preserved.read_text(encoding="utf-8"), "keep")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_rejects_top_level_and_script_source_symlinks(self) -> None:
        for relative in (Path("SKILL.md"), Path("scripts") / "booking_ledger.py"):
            with self.subTest(relative=str(relative)), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "source"
                (source / "scripts").mkdir(parents=True)
                (source / "references").mkdir()
                shutil.copy2(INSTALLER, source / "scripts" / "install.py")
                (source / "SKILL.md").write_text("skill", encoding="utf-8")
                (source / "LICENSE").write_text("license", encoding="utf-8")
                (source / "scripts" / "booking_ledger.py").write_text(
                    "runtime", encoding="utf-8"
                )
                (source / "references" / "tool-contract.md").write_text(
                    "reference", encoding="utf-8"
                )
                external = root / "external-secret.txt"
                external.write_text("outside", encoding="utf-8")
                source_path = source / relative
                source_path.unlink()
                source_path.symlink_to(external)

                process = subprocess.run(
                    [
                        sys.executable,
                        str(source / "scripts" / "install.py"),
                        "--target",
                        str(root / "skills"),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(process.returncode, 2)
                self.assertIn("source runtime path contains a symlink", process.stderr)
                destination = root / "skills" / "treatwell-appointments"
                self.assertFalse(destination.exists())
                self.assertEqual(external.read_text(encoding="utf-8"), "outside")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_rejects_symlinked_source_tree_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            (source / "scripts").mkdir(parents=True)
            shutil.copy2(INSTALLER, source / "scripts" / "install.py")
            (source / "scripts" / "booking_ledger.py").write_text(
                "runtime", encoding="utf-8"
            )
            (source / "SKILL.md").write_text("skill", encoding="utf-8")
            (source / "LICENSE").write_text("license", encoding="utf-8")
            external_references = root / "external-references"
            external_references.mkdir()
            (external_references / "secret.md").write_text("outside", encoding="utf-8")
            (source / "references").symlink_to(
                external_references, target_is_directory=True
            )

            process = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "install.py"),
                    "--target",
                    str(root / "skills"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("source runtime path contains a symlink", process.stderr)
            destination = root / "skills" / "treatwell-appointments"
            self.assertFalse(destination.exists())

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_preflight_rejects_nested_source_symlink_without_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            (source / "scripts").mkdir(parents=True)
            (source / "references" / "nested").mkdir(parents=True)
            shutil.copy2(INSTALLER, source / "scripts" / "install.py")
            (source / "scripts" / "booking_ledger.py").write_text(
                "runtime", encoding="utf-8"
            )
            (source / "SKILL.md").write_text("skill", encoding="utf-8")
            (source / "LICENSE").write_text("license", encoding="utf-8")
            (source / "references" / "first.md").write_text("first", encoding="utf-8")
            external = root / "external-secret.md"
            external.write_text("outside", encoding="utf-8")
            (source / "references" / "nested" / "later.md").symlink_to(external)

            destination = root / "skills" / "treatwell-appointments"
            process = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "install.py"),
                    "--target",
                    str(root / "skills"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("source runtime path contains a symlink", process.stderr)
            self.assertFalse(destination.exists())
            self.assertEqual(external.read_text(encoding="utf-8"), "outside")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_invalid_source_preflight_leaves_existing_install_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            (source / "scripts").mkdir(parents=True)
            (source / "references").mkdir()
            shutil.copy2(INSTALLER, source / "scripts" / "install.py")
            (source / "SKILL.md").write_text("new-skill", encoding="utf-8")
            (source / "LICENSE").write_text("new-license", encoding="utf-8")
            (source / "references" / "tool-contract.md").write_text(
                "new-reference", encoding="utf-8"
            )
            external = root / "external-runtime.py"
            external.write_text("outside", encoding="utf-8")
            (source / "scripts" / "booking_ledger.py").symlink_to(external)

            base = root / "skills"
            destination = base / "treatwell-appointments"
            destination.mkdir(parents=True)
            (destination / ".treatwell-appointments-install").write_text(
                "treatwell-appointments\ninstaller-schema=1\n", encoding="utf-8"
            )
            (destination / "SKILL.md").write_text("old-skill", encoding="utf-8")
            sentinel = destination / "operator-notes.txt"
            sentinel.write_text("keep", encoding="utf-8")

            process = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "install.py"),
                    "--target",
                    str(base),
                    "--force",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "old-skill")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertEqual(external.read_text(encoding="utf-8"), "outside")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_refuses_symlink_components_in_destination_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            external = root / "external"
            external.mkdir()
            direct_alias = root / "direct-alias"
            direct_alias.symlink_to(external, target_is_directory=True)
            ancestor_alias = root / "ancestor-alias"
            ancestor_alias.symlink_to(external, target_is_directory=True)

            for base in (direct_alias, ancestor_alias / "nested"):
                with self.subTest(base=str(base)):
                    process = subprocess.run(
                        [sys.executable, str(INSTALLER), "--target", str(base)],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(process.returncode, 2)
                    self.assertIn("destination base with symlink component", process.stderr)

            self.assertFalse((external / "treatwell-appointments").exists())
            self.assertFalse((external / "nested" / "treatwell-appointments").exists())

    def test_refuses_parent_segments_in_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "safe" / ".." / "redirected"
            process = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("target path containing '..'", process.stderr)
            self.assertFalse((Path(temp) / "redirected").exists())

    def test_refuses_source_destination_overlap_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "treatwell-appointments"
            (source / "scripts").mkdir(parents=True)
            (source / "references").mkdir()
            shutil.copy2(INSTALLER, source / "scripts" / "install.py")
            (source / "scripts" / "booking_ledger.py").write_text("runtime", encoding="utf-8")
            (source / "SKILL.md").write_text("skill", encoding="utf-8")
            (source / "LICENSE").write_text("license", encoding="utf-8")
            (source / "references" / "tool-contract.md").write_text("reference", encoding="utf-8")
            marker = source / ".treatwell-appointments-install"
            marker.write_text(
                "treatwell-appointments\ninstaller-schema=1\n", encoding="utf-8"
            )

            process = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "install.py"),
                    "--target",
                    str(source.parent),
                    "--force",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("overlapping source and destination", process.stderr)
            self.assertEqual((source / "SKILL.md").read_text(encoding="utf-8"), "skill")
            self.assertEqual(marker.read_text(encoding="utf-8"), "treatwell-appointments\ninstaller-schema=1\n")

    def test_known_agent_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            hermes_home = Path(temp) / "hermes-home"
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["HERMES_HOME"] = str(hermes_home)
            expected = {
                "hermes": hermes_home / "skills" / "treatwell-appointments",
                "codex": home / ".agents" / "skills" / "treatwell-appointments",
                "claude": home / ".claude" / "skills" / "treatwell-appointments",
                "opencode": home / ".config" / "opencode" / "skills" / "treatwell-appointments",
            }
            for agent, destination in expected.items():
                with self.subTest(agent=agent):
                    process = subprocess.run(
                        [sys.executable, str(INSTALLER), "--agent", agent],
                        text=True,
                        capture_output=True,
                        check=False,
                        env=env,
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertTrue((destination / "SKILL.md").is_file())

    def test_force_refuses_unrecognized_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "skills"
            destination = base / "treatwell-appointments"
            destination.mkdir(parents=True)
            sentinel = destination / "do-not-delete.txt"
            sentinel.write_text("keep", encoding="utf-8")
            (destination / "SKILL.md").write_text(
                "---\nname: treatwell-appointments\ndescription: spoof\n---\n",
                encoding="utf-8",
            )

            process = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base), "--force"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("unrecognized directory", process.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_force_unlinks_symlink_without_deleting_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "skills"
            base.mkdir()
            external = Path(temp) / "external"
            external.mkdir()
            sentinel = external / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            destination = base / "treatwell-appointments"
            destination.symlink_to(external, target_is_directory=True)

            process = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base), "--force"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(destination.is_symlink())
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    @unittest.skipIf(os.name == "nt", "symlink creation may require elevated privileges")
    def test_force_replaces_managed_nested_symlinks_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "skills"
            install = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            skill = base / "treatwell-appointments"

            external_file = Path(temp) / "external-skill.md"
            external_file.write_text("outside", encoding="utf-8")
            (skill / "SKILL.md").unlink()
            (skill / "SKILL.md").symlink_to(external_file)

            external_references = Path(temp) / "external-references"
            external_references.mkdir()
            sentinel = external_references / "keep.txt"
            sentinel.write_text("outside", encoding="utf-8")
            shutil.rmtree(skill / "references")
            (skill / "references").symlink_to(external_references, target_is_directory=True)

            forced = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(base), "--force"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertFalse((skill / "SKILL.md").is_symlink())
            self.assertFalse((skill / "references").is_symlink())
            self.assertEqual(external_file.read_text(encoding="utf-8"), "outside")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "outside")
            self.assertTrue((skill / "references" / "tool-contract.md").is_file())


if __name__ == "__main__":
    unittest.main()
