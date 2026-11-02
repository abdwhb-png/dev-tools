import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ReleaseVersion(unittest.TestCase):
    def test_rules(self):
        result = __import__('subprocess').run(['python3',str(ROOT/'scripts/release_version.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        spec=importlib.util.spec_from_file_location('release_version',ROOT/'scripts/release_version.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for last,messages,expected in [('v0.1.0','feat: add browser','v0.2.0'),('v0.2.0','fix: repair login','v0.2.1'),('v0.2.0','ci: automatic numbering','v0.2.1'),('v0.2.1','feat!: change interface','v1.0.0'),('v1.2.3','fix: change\n\nBREAKING CHANGE: format','v2.0.0'),(None,'feat: initial','v0.1.0')]:
            with self.subTest(last=last,messages=messages):
                self.assertEqual(module.next_version(last,messages),expected)

    def test_cli_ignores_drafts_and_does_not_republish_same_commit(self):
        import json
        import os
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (root / 'file').write_text('base')
            git('add', '.')
            git('commit', '-qm', 'base')
            git('tag', 'v0.1.0')
            (root / 'file').write_text('feature')
            git('add', 'file')
            git('commit', '-qm', 'feat: agentic tools')
            binary = root / 'gh'
            binary.write_text('#!/usr/bin/python3\nimport os\nprint(os.environ["RELEASE_FIXTURE"])\n')
            binary.chmod(0o755)
            releases = [{'tagName':'v0.1.0','isDraft':False,'isPrerelease':False}, {'tagName':'v9.0.0','isDraft':True,'isPrerelease':False}]
            env = os.environ | {'PATH':str(root)+':'+os.environ['PATH'], 'RELEASE_FIXTURE':json.dumps(releases), 'GITHUB_OUTPUT':str(root/'outputs')}
            command = ['python3',str(ROOT/'scripts/release_version.py'),'--repository','owner/repo','--revision',git('rev-parse','HEAD')]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('version=v0.2.0\nneeded=true', (root/'outputs').read_text())
            git('tag','v0.2.0')
            releases.append({'tagName':'v0.2.0','isDraft':False,'isPrerelease':False})
            env['RELEASE_FIXTURE']=json.dumps(releases)
            (root/'outputs').write_text('')
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('needed=false', (root/'outputs').read_text())
