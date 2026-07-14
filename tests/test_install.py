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
