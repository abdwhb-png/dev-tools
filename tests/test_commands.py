import contextlib
import importlib.util
import io
import os
import re
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dev_tools", ROOT / "scripts/dev_tools.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class Commands(unittest.TestCase):
    def test_package_policy_is_scoped_and_survives_sudo(self):
        commands = []
        def external(argv, **kwargs):
            if 'status' in argv:
                return subprocess.CompletedProcess(argv, 1)
            commands.append(argv)
            settings = dict(arg.split('=', 1) for arg in argv if '=' in arg)
            self.assertIn('APT_CONFIG', settings, 'mise must receive an explicit per-invocation APT policy')
            policy = Path(settings['APT_CONFIG'])
            self.assertIn('APT::Install-Recommends "false"', policy.read_text())
            self.assertEqual(argv[:2], ['sudo', 'env'])
            self.assertNotIn('USER_SECRET', settings)
            return subprocess.CompletedProcess(argv, 0)
        with patch('subprocess.run', side_effect=external):
            app.install_system_packages(Path('/verified/mise'), app.isolated_env('noble') | {'USER_SECRET': 'not-forwarded'})
        self.assertEqual(len(commands), 1)
        settings = dict(arg.split('=', 1) for arg in commands[0] if '=' in arg)
        self.assertFalse(Path(settings['APT_CONFIG']).exists(), 'temporary policy must be removed')

    def invoke(self, args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = app.main(args)
        return code, output.getvalue(), error.getvalue()

    def test_preview_reports_pinned_tools_without_installing(self):
        with patch("subprocess.run", side_effect=AssertionError("preview executed a command")):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = app.main(["bootstrap", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("8.5.12", output.getvalue())
        self.assertIn("packages.sury.org", output.getvalue())

    def test_foreign_global_fragment_blocks_preview_before_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'dev-tools'
            target.mkdir()
            with patch.object(app, 'fragment', return_value=target), patch('subprocess.run') as command:
                code, _, error = self.invoke(['bootstrap', '--dry-run'])
            self.assertEqual(code, 1)
            self.assertIn('collision', error)
            self.assertNotIn('Completed APT changes', error)
            command.assert_not_called()

    def test_interrupt_reports_cancellation_without_a_traceback(self):
        with patch('subprocess.run', side_effect=KeyboardInterrupt):
            code, _, error = self.invoke(['github'])
        self.assertEqual(code, 130)
        self.assertIn('Cancelled', error)
        self.assertNotIn('Completed APT changes', error)

    def test_unsupported_host_is_rejected_without_commands(self):
        with patch('platform.machine', return_value='aarch64'), patch('subprocess.run') as command:
            code, _, error = self.invoke(['bootstrap', '--yes'])
        self.assertEqual(code, 1)
        self.assertIn('Supported hosts', error)
        command.assert_not_called()

    def test_cancellation_does_not_fetch_or_activate_tools(self):
        with patch('sys.stdin.isatty', return_value=False), patch('os.geteuid', return_value=1000), patch.object(app, 'fetch_mise') as fetch:
            code, _, _ = self.invoke(['bootstrap'])
        self.assertEqual(code, 1)
        fetch.assert_not_called()

    def test_machine_context_does_not_inherit_arbitrary_mise_settings(self):
        with patch.dict('os.environ', {'MISE_ENV': 'personal', 'MISE_GLOBAL_CONFIG_FILE': '/personal/config.toml', 'MISE_AUTO_INSTALL': '1'}):
            env = app.isolated_env('noble')
        self.assertEqual(env['MISE_ENV'], 'noble')
        self.assertNotEqual(env['MISE_GLOBAL_CONFIG_FILE'], '/personal/config.toml')
        self.assertEqual(env['MISE_AUTO_INSTALL'], '0')

    def test_additional_php_rejects_prereleases_without_package_operations(self):
        with patch('subprocess.run') as command:
            code, _, _ = self.invoke(['php-prepare', '8.6.0RC1'])
        self.assertEqual(code, 1)
        command.assert_not_called()

    def test_php_validation_does_not_run_for_a_different_package_version(self):
        import subprocess
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, '8.5.0', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                app.link_php(Path('/unused/mise'), '8.5.12', {})
        self.assertEqual(command.call_count, 1)

    def test_bad_download_never_creates_a_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'bin/mise'
            with patch.object(app, 'mise_path', return_value=binary), patch('urllib.request.urlopen', return_value=io.BytesIO(b'corrupt archive')):
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    app.fetch_mise()
            self.assertFalse(binary.exists())

    def test_existing_mise_is_verified_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'mise'
            binary.write_bytes(b'unrelated executable')
            with patch.object(app, 'mise_path', return_value=binary), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, '2026.10.25 linux-x64', '')) as command:
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    app.fetch_mise()
            command.assert_not_called()

    def test_failed_login_does_not_configure_git(self):
        calls = []
        def external(argv, **kwargs):
            calls.append(argv)
            if 'status' in argv:
                return subprocess.CompletedProcess(argv, 1, b'', b'')
            raise subprocess.CalledProcessError(1, argv)
        with patch('subprocess.run', side_effect=external), patch.object(app, 'login_github', side_effect=RuntimeError('login cancelled')), patch('sys.stdin.isatty', return_value=True):
            code, _, _ = self.invoke(['github'])
        self.assertEqual(code, 1)
        self.assertFalse(any('setup-git' in call for call in calls))

    def test_fallback_warning_does_not_count_as_the_requested_php_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mise.toml').write_text('[tools]\nphp="8.5.12"\n')
            (root / 'php-modules.txt').write_text('Core\n')
            for series in ('noble', 'resolute'):
                (root / f'mise.{series}.toml').write_text('[bootstrap.packages]\n"apt:git"="1:2.56.0-0ppa1~ubuntu24.04.2"\n')
            binary = root / 'mise'
            binary.touch()
            def external(argv, **kwargs):
                if str(argv[0]).endswith('/herdr-core'):
                    return subprocess.CompletedProcess(argv, 0, 'hc 0.1.16', '')
                if any(str(arg).endswith('/sfw') for arg in argv):
                    return subprocess.CompletedProcess(argv, 0, 'Socket Firewall Free, version 1.16.0', '')
                if str(argv[0]).endswith('/chrome'):
                    return subprocess.CompletedProcess(argv, 0, 'Google Chrome 157.0.8103.38', '')
                if 'php' in argv and '--version' in argv:
                    return subprocess.CompletedProcess(argv, 0, 'PHP 8.5.0', 'mise WARN php@8.5.12 is missing')
                if 'git' in argv:
                    return subprocess.CompletedProcess(argv, 0, 'git version 2.56.0', '')
                if '-r' in argv:
                    return subprocess.CompletedProcess(argv, 0, '["Core"]', '')
                return subprocess.CompletedProcess(argv, 0, '/fixture/bin', '')
            with patch.object(app, 'ROOT', root), patch.object(app, 'mise_path', return_value=binary), patch('subprocess.run', side_effect=external):
                code, _, error = self.invoke(['check', '--tools-only'])
            self.assertEqual(code, 1)
            self.assertIn('php', error)
            self.assertNotIn('chrome', error)

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires an explicitly supplied verified mise binary')
    def test_native_mise_loads_the_isolated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            env = app.isolated_env() | {'HOME': directory, 'XDG_CONFIG_HOME': directory + '/config', 'XDG_DATA_HOME': directory + '/data', 'XDG_CACHE_HOME': directory + '/cache'}
            result = subprocess.run([os.environ['DEV_TOOLS_MISE'], 'config', 'ls'], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('mise.toml', result.stdout)

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_check_task_does_not_automatically_install_missing_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            env = app.isolated_env() | {'HOME': directory, 'XDG_CONFIG_HOME': directory + '/config', 'XDG_DATA_HOME': directory + '/data', 'XDG_CACHE_HOME': directory + '/cache'}
            env.pop('MISE_AUTO_INSTALL')
            result = subprocess.run([os.environ['DEV_TOOLS_MISE'], 'run', '--dry-run', 'dev-tools:check', '--tools-only'], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('would install', result.stdout + result.stderr)

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_global_task_uses_its_source_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config/mise/conf.d'
            config.mkdir(parents=True)
            (config / 'dev-tools').symlink_to(ROOT, target_is_directory=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith('MISE_')}
            env.update(HOME=directory, XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'), XDG_CACHE_HOME=str(root / 'cache'), MISE_TRUSTED_CONFIG_PATHS=str(ROOT), MISE_CEILING_PATHS=str(ROOT.parent))
            for cwd in (ROOT, root):
                with self.subTest(cwd=cwd):
                    result = subprocess.run([os.environ['DEV_TOOLS_MISE'], 'run', '--dry-run', 'dev-tools:check', '--tools-only'], cwd=cwd, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    script = re.search(r'"([^"]+/scripts/dev_tools.py)"', result.stdout + result.stderr)
                    self.assertIsNotNone(script, result.stdout + result.stderr)
                    self.assertEqual(Path(script.group(1)).resolve(), ROOT / 'scripts/dev_tools.py')

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_shell_setup_preserves_ubuntu_profile_and_sets_launcher_path(self):
        mise = Path(os.environ['DEV_TOOLS_MISE'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.profile').write_text('# existing profile\n')
            env = app.isolated_env() | {'HOME': directory, 'XDG_CONFIG_HOME': directory + '/config', 'XDG_DATA_HOME': directory + '/data', 'XDG_CACHE_HOME': directory + '/cache'}
            with patch.dict(os.environ, env, clear=True), patch('shutil.which', side_effect=lambda name: '/usr/bin/bash' if name == 'bash' else None):
                app.install_shells(mise, env)
            self.assertFalse((root / '.bash_profile').exists(), 'must not shadow the existing .profile')
            self.assertIn('# existing profile', (root / '.profile').read_text())
            self.assertIn('.local/bin', (root / '.bashrc').read_text())

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_linked_php_is_not_source_built_during_locked_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            for name in ('mise.toml', 'mise.lock'):
                (project / name).write_bytes((ROOT / name).read_bytes())
            prefix = root / 'php'
            (prefix / 'bin').mkdir(parents=True)
            actual = root / 'php-binary'
            actual.write_text('#!/bin/sh\nprintf "8.5.12"\n')
            actual.chmod(0o755)
            php = prefix / 'bin/php'
            env = app.isolated_env() | {'HOME': str(root), 'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'), 'MISE_CEILING_PATHS': str(root), 'MISE_TRUSTED_CONFIG_PATHS': str(project)}
            mise = os.environ['DEV_TOOLS_MISE']
            original_lock = (project / 'mise.lock').read_bytes()
            def system_path(value):
                return actual if value == '/usr/bin/php8.5' else Path(value)
            with patch.object(app, 'ROOT', project), patch.object(app, 'php_prefix', return_value=prefix), patch.object(app, 'Path', side_effect=system_path):
                app.link_php(mise, '8.5.12', env)
            self.assertEqual((project / 'mise.lock').read_bytes(), original_lock, 'PHP registration must preserve the reviewed lockfile')
            selected = subprocess.run([mise, 'which', 'php'], cwd=project, env=env, capture_output=True, text=True)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(Path(selected.stdout.strip()).resolve(), actual)
            result = subprocess.run([mise, 'install', '--locked', '--dry-run', 'node'], cwd=project, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('php@8.5.12', result.stderr)


if __name__ == "__main__":
    unittest.main()
