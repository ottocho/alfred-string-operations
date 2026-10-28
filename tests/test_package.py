import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.build import build

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS = (
    "json.pretty", "camelCase", "snake_case", "underscore_case",
    "kebab-case", "lowercase", "uppercase",
)


class WorkflowDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.metadata = plistlib.loads((ROOT / "workflow/info.plist").read_bytes())

    def test_metadata_identifies_ottos_string_operations(self):
        self.assertEqual(self.metadata["name"], "String Operations")
        self.assertEqual(self.metadata["bundleid"], "ottocho.alfred.string-operations")
        self.assertEqual(self.metadata["webaddress"], "https://github.com/ottocho/alfred-string-operations")
        self.assertRegex(self.metadata["version"], r"^[0-9]+[.][0-9]+[.][0-9]+(?:[-+].+)?$")
        self.assertFalse(self.metadata["disabled"])

    def test_only_requested_keywords_are_connected_to_their_matching_actions(self):
        objects = self.metadata["objects"]
        inputs = [obj for obj in objects if obj["type"] == "alfred.workflow.input.keyword"]
        actions = {obj["uid"]: obj for obj in objects if obj["type"] == "alfred.workflow.action.script"}
        self.assertEqual(tuple(obj["config"]["keyword"] for obj in inputs), KEYWORDS)
        self.assertEqual(len(objects), 14)
        self.assertEqual(len({obj["uid"] for obj in objects}), 14)
        self.assertEqual(set(self.metadata["connections"]), {obj["uid"] for obj in inputs})
        self.assertEqual(set(self.metadata["uidata"]), {obj["uid"] for obj in objects})
        connected_actions = set()
        for obj in inputs:
            with self.subTest(keyword=obj["config"]["keyword"]):
                self.assertEqual(obj["config"]["argumenttype"], 2)
                links = self.metadata["connections"][obj["uid"]]
                self.assertEqual(len(links), 1)
                action_id = links[0]["destinationuid"]
                connected_actions.add(action_id)
                config = actions[action_id]["config"]
                self.assertEqual(config["script"], "exec /bin/bash ./run.sh " + obj["config"]["keyword"])
                self.assertFalse(config["concurrently"])
        self.assertEqual(connected_actions, set(actions))


class PackageTests(unittest.TestCase):
    def test_archive_contains_only_runtime_files_at_its_root(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested/String-Operations.alfredworkflow"
            self.assertEqual(build(target), target)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.namelist(), ["info.plist", "icon.png", "run.sh", "string_operations.py"])
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    with self.subTest(name=name):
                        self.assertEqual(archive.read(name), (ROOT / "workflow" / name).read_bytes())
                self.assertEqual(archive.getinfo("run.sh").external_attr >> 16, 0o100755)

    def test_rebuilding_replaces_stale_archive_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "String-Operations.alfredworkflow"
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("removed-command.py", "old")
            build(target)
            first_build = target.read_bytes()
            with zipfile.ZipFile(target) as archive:
                self.assertNotIn("removed-command.py", archive.namelist())
            build(target)
            self.assertEqual(target.read_bytes(), first_build)

    def test_extracted_package_runs_all_commands_outside_the_source_directory(self):
        examples = {
            "json.pretty": ('{"b":2,"a":1}', '{\n    "a": 1,\n    "b": 2\n}'),
            "camelCase": ("HTTP response-code", "httpResponseCode"),
            "snake_case": ("HTTP response-code", "http_response_code"),
            "underscore_case": ("HTTP response-code", "http_response_code"),
            "kebab-case": ("HTTP response-code", "http-response-code"),
            "lowercase": (" HeLLo\nWORLD ", " hello\nworld "),
            "uppercase": (" HeLLo\nworld ", " HELLO\nWORLD "),
        }
        with tempfile.TemporaryDirectory(prefix="alfred package ") as directory:
            root = Path(directory)
            with zipfile.ZipFile(build(root / "workflow.alfredworkflow")) as archive:
                archive.extractall(root / "installed workflow")
            uv = root / ".local/bin/uv"
            uv.parent.mkdir(parents=True)
            uv.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(sys.executable) + "\n")
            uv.chmod(0o755)
            environment = {**os.environ, "HOME": directory, "PATH": "/usr/bin:/bin"}
            for keyword, (source, expected) in examples.items():
                with self.subTest(keyword=keyword):
                    result = subprocess.run(
                        ["/bin/bash", str(root / "installed workflow/run.sh"), keyword, "--stdin"],
                        input=source, capture_output=True, text=True, encoding="utf-8",
                        env=environment, cwd=root, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)
                    self.assertEqual(result.stderr, "")
            self.assertEqual(list(root.rglob(".venv")), [])
            self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_missing_python_reports_setup_command_without_running_transform(self):
        with tempfile.TemporaryDirectory() as directory:
            uv = Path(directory) / ".local/bin/uv"
            uv.parent.mkdir(parents=True)
            uv.write_text("#!/bin/sh\nexit 1\n")
            uv.chmod(0o755)
            result = subprocess.run(
                ["/bin/bash", str(ROOT / "workflow/run.sh"), "uppercase", "--stdin"],
                input="unchanged", capture_output=True, text=True,
                env={**os.environ, "HOME": directory, "PATH": "/usr/bin:/bin"}, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("uv python install 3.12", result.stderr)


if __name__ == "__main__":
    unittest.main()
