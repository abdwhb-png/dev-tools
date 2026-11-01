import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Installer(unittest.TestCase):
    def test_checkout_bootstrap_accepts_sh(self):
        result = subprocess.run(['sh', str(ROOT / 'bootstrap.sh'), '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('8.5.12', result.stdout)

    def test_generated_preview_is_offline_and_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer = root / 'install.sh'
            build = subprocess.run(['python3', str(ROOT / 'scripts/build_installer.py'), '--revision', 'a' * 40, '--version', 'v0.1.0', '--output', str(installer)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            env = os.environ | {'XDG_DATA_HOME': str(root / 'data')}
            result = subprocess.run(['sh', str(installer), '--dry-run'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('a' * 40, result.stdout)
            self.assertFalse((root / 'data').exists())

class InstalledCheckout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        repo = self.root / 'upstream'
        repo.mkdir()
        (repo / 'bootstrap.sh').write_text('#!/bin/sh\nprintf ran >> "$INSTALL_TRACE"\nexit "${BOOTSTRAP_EXIT:-0}"\n')
        for args in (['init', '-q', str(repo)], ['-C', str(repo), 'add', '.'], ['-C', str(repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', *args], check=True)
        self.sha = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        self.installer = self.root / 'install.sh'
        subprocess.run(['python3', str(ROOT / 'scripts/build_installer.py'), '--revision', self.sha, '--version', 'v0.1.0', '--output', str(self.installer)], check=True)
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        git = bin_dir / 'git'
        git.write_text('''#!/usr/bin/python3
import os, subprocess, sys
args = sys.argv[1:]
if 'status' in args and os.environ.get('FAIL_GIT_STATUS'):
    sys.exit(9)
if args[0] == 'clone':
    args[2] = os.environ['FIXTURE_REPO']
    subprocess.run(['/usr/bin/git', *args], check=True)
    sys.exit(subprocess.call(['/usr/bin/git', '-C', args[-1], 'remote', 'set-url', 'origin', 'https://github.com/abdwhb-png/dev-tools.git']))
if len(args) > 3 and args[2] == 'fetch':
    args[4] = os.environ['FIXTURE_REPO']
sys.exit(subprocess.call(['/usr/bin/git', *args]))
''')
        git.chmod(0o755)
        for name, body in [('id', 'echo "${FAKE_UID:-1000}"'), ('sudo', 'echo unexpected-sudo >&2; exit 99')]:
            path = bin_dir / name
            path.write_text('#!/bin/sh\n' + body + '\n')
            path.chmod(0o755)
        self.trace = self.root / 'trace'
        self.env = os.environ | {'PATH': str(bin_dir) + ':' + os.environ['PATH'], 'XDG_DATA_HOME': str(self.root / 'data with spaces'), 'FIXTURE_REPO': str(repo), 'INSTALL_TRACE': str(self.trace)}
        self.destination = self.root / 'data with spaces/dev-tools/source'

    def invoke(self, *args, pipe=False):
        command = ['/bin/sh', '-s', '--', *args] if pipe else ['/bin/sh', str(self.installer), *args]
        return subprocess.run(command, input=self.installer.read_text() if pipe else '', env=self.env, capture_output=True, text=True)

    def test_file_pipe_and_repeat_use_exact_clean_revision(self):
        for pipe in (False, True):
            result = self.invoke('--yes', pipe=pipe)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(), 'ranran')
        self.assertEqual(subprocess.check_output(['git', '-C', str(self.destination), 'rev-parse', 'HEAD'], text=True).strip(), self.sha)

    def test_root_and_unknown_option_do_not_clone(self):
        self.env['FAKE_UID'] = '0'
        for args in [('--yes',), ('--unknown',)]:
            self.assertNotEqual(self.invoke(*args).returncode, 0)
            self.assertFalse(self.destination.exists())

    def test_foreign_directory_is_preserved(self):
        self.destination.mkdir(parents=True)
        (self.destination / 'keep').write_text('original')
        self.assertNotEqual(self.invoke('--yes').returncode, 0)
        self.assertEqual((self.destination / 'keep').read_text(), 'original')

    def test_modified_checkout_is_preserved(self):
        self.assertEqual(self.invoke('--yes').returncode, 0)
        script = self.destination / 'bootstrap.sh'
        script.write_text('personal change')
        self.assertNotEqual(self.invoke('--yes').returncode, 0)
        self.assertEqual(script.read_text(), 'personal change')

    def test_bootstrap_failure_is_not_success(self):
        self.env['BOOTSTRAP_EXIT'] = '7'
        result = self.invoke('--yes')
        self.assertEqual(result.returncode, 7)
        self.assertNotIn('Installed v0.1.0', result.stdout)

    def test_missing_git_apt_failure_never_runs_bootstrap(self):
        bin_dir = self.root / 'bin'
        (bin_dir / 'git').rename(bin_dir / 'git.disabled')
        uname = bin_dir / 'uname'
        uname.write_text('#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo x86_64;; esac\n')
        uname.chmod(0o755)
        self.env['PATH'] = str(bin_dir)
        result = self.invoke('--yes')
        self.assertEqual(result.returncode, 99)
        self.assertIn('unexpected-sudo', result.stderr)
        self.assertFalse(self.trace.exists())

    def test_unavailable_revision_leaves_no_checkout(self):
        self.installer.write_text(self.installer.read_text().replace(self.sha, 'b' * 40))
        result = self.invoke('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.trace.exists())
        self.assertEqual(list(self.destination.parent.glob('.source.*')), [])

    def test_failed_checkout_inspection_is_not_treated_as_clean(self):
        self.assertEqual(self.invoke('--yes').returncode, 0)
        self.env['FAIL_GIT_STATUS'] = '1'
        self.assertNotEqual(self.invoke('--yes').returncode, 0)
        self.assertEqual(self.trace.read_text(), 'ran')
