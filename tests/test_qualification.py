import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Qualification(unittest.TestCase):
    def test_documentation_change_reuses_complete_success(self):
        self.check_reuse(documentation=True, complete=True, succeeds=True)

    def test_runtime_change_cannot_reuse_old_success(self):
        self.check_reuse(documentation=False, complete=True, succeeds=False)

    def test_incomplete_matrix_is_not_a_qualification(self):
        self.check_reuse(documentation=True, complete=False, succeeds=False)

    def test_declared_run_head_is_insufficient_if_installed_source_differs(self):
        self.check_reuse(documentation=True, complete=True, succeeds=False, source_matches=False)

    def test_release_workflow_change_reuses_runtime_evidence(self):
        self.check_reuse(documentation=False, complete=True, succeeds=True, control=True)

    def check_reuse(self, documentation, complete, succeeds, source_matches=True, control=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'repo'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (repo / 'bootstrap.sh').write_text('first')
            git('add', '.')
            git('commit', '-qm', 'qualified')
            qualified = git('rev-parse', 'HEAD')
            changed = repo / ('.github/workflows/release.yml' if control else ('README.md' if documentation else 'bootstrap.sh'))
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_text('changed')
            git('add', '.')
            git('commit', '-qm', 'candidate')
            candidate = git('rev-parse', 'HEAD')
            installed = qualified
            if not source_matches:
                (repo / 'bootstrap.sh').write_text('different installed source')
                git('add', '.')
                git('commit', '-qm', 'other source')
                installed = git('rev-parse', 'HEAD')
            binary = root / 'gh'
            binary.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
if sys.argv[1:3] == ['run', 'download']:
    destination = Path(sys.argv[sys.argv.index('--dir') + 1])
    destination.joinpath('.ci-installer').write_text("    revision='" + os.environ['INSTALLED_SHA'] + "'\\n")
    sys.exit(0)
if '/jobs' in sys.argv[-1]:
    names = ['build', 'isolated', 'ubuntu (24.04)', 'ubuntu (26.04)', 'wsl2 (24.04)', 'wsl2 (26.04)']
    if not os.environ.get('COMPLETE'): names.pop()
    print(json.dumps({'jobs':[{'name':n,'conclusion':'success'} for n in names]}))
else:
    print(json.dumps({'workflow_runs':[{'id':7,'head_sha':os.environ['QUALIFIED_SHA'],'conclusion':'success','html_url':'https://example.invalid/run/7','head_repository':{'full_name':'owner/repo'}}]}))
''')
            binary.chmod(0o755)
            env = os.environ | {'PATH': str(root) + ':' + os.environ['PATH'], 'QUALIFIED_SHA': qualified, 'COMPLETE': '1' if complete else '', 'INSTALLED_SHA': installed, 'GITHUB_OUTPUT': str(root / 'outputs')}
            result = subprocess.run(['python3', str(ROOT / 'scripts/qualification.py'), '--repository', 'owner/repo', '--revision', candidate], cwd=repo, env=env, capture_output=True, text=True)
            if succeeds:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('https://example.invalid/run/7', result.stdout)
            else:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('No matching complete qualification', result.stderr)
