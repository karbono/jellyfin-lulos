"""Static invariants for the GitHub Actions workflows (no network, no secrets)."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

WF_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOWS = sorted(WF_DIR.glob("*.yml"))
SECRET_RE = re.compile(r"secrets\.RELEASE_")
TAG_RE = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$")


def steps(doc):
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            yield step


class WorkflowTests(unittest.TestCase):
    def load(self, path):
        # PyYAML parses `on:` as True; irrelevant here.
        return yaml.safe_load(path.read_text())

    def test_found_workflows(self):
        self.assertGreaterEqual(len(WORKFLOWS), 2)

    def test_no_expression_in_run(self):
        for p in WORKFLOWS:
            for s in steps(self.load(p)):
                run = s.get("run", "")
                self.assertNotIn("${{", run, f"{p.name}: {s.get('name')}")

    def test_actions_pinned_to_sha(self):
        for p in WORKFLOWS:
            for s in steps(self.load(p)):
                if "uses" in s:
                    self.assertRegex(s["uses"], r"@[0-9a-f]{40}$", f"{p.name}: {s['uses']}")
            for line in p.read_text().splitlines():
                if "uses:" in line:
                    self.assertRegex(line, r"@[0-9a-f]{40} # v\S+$")

    def test_signing_secrets_only_in_sign_step(self):
        for p in WORKFLOWS:
            doc = self.load(p)
            self.assertFalse(SECRET_RE.search(str(doc.get("env", ""))))
            holders = [s for s in steps(doc) if SECRET_RE.search(str(s.get("env", "")) + str(s.get("with", "")))]
            self.assertEqual(len(holders), 1, p.name)
            self.assertIn("Sign", holders[0]["name"])
            self.assertIn("apksigner", holders[0]["run"])
            self.assertNotIn("gradlew", holders[0]["run"])
            for s in steps(doc):
                if "gradlew" in s.get("run", ""):
                    self.assertNotIn("secrets", str(s))
                    self.assertNotIn("keystore", s["run"])

    def test_tag_validated_before_use(self):
        for p in WORKFLOWS:
            check = next(s for s in steps(self.load(p)) if s.get("id") == "compare")
            self.assertIn("INPUT_TAG", check["env"])
            run = check["run"]
            self.assertLess(run.index("=~"), run.index('echo "tag=$TAG"'))

    def test_tag_regex_semantics(self):
        for ok in ("v2.7.3", "0.20.0", "v1.2.3-rc.1"):
            self.assertRegex(ok, TAG_RE)
        for bad in ("$(id)", "v1.2.3;rm -rf /", "v1.2", "", "v1.2.3 x", "-x"):
            self.assertNotRegex(bad, TAG_RE)

    def test_published_asset_names_unchanged(self):
        expect = {"build-custom.yml": "jellyfin-lulos.apk", "build-tv.yml": "jellyfin-lulos-tv.apk"}
        for name, apk in expect.items():
            text = (WF_DIR / name).read_text()
            self.assertIn(f"dist/{apk}", text)

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
    def test_shellcheck_run_blocks(self):
        for p in WORKFLOWS:
            for i, s in enumerate(steps(self.load(p))):
                if "run" not in s:
                    continue
                with tempfile.NamedTemporaryFile("w", suffix=".sh") as f:
                    f.write("#!/usr/bin/env bash\n" + s["run"])
                    f.flush()
                    r = subprocess.run(["shellcheck", "-S", "warning", f.name], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, f"{p.name} step {i}\n{r.stdout}")


if __name__ == "__main__":
    unittest.main()
