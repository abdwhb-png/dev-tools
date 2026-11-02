from test_commands import app
import argparse
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

class Agentic(unittest.TestCase):
    def test_github_reuses_valid_github_com_login_despite_other_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'mise'
            binary.write_text('#!/bin/sh\ncase "$*" in *"auth status --hostname github.com --active") exit 0;; *"config get git_protocol --host github.com") echo https;; *) exit 99;; esac\n')
            binary.chmod(0o755)
            git = Path(directory) / 'git'
            git.write_text('#!/bin/sh\necho "!gh auth git-credential"\n')
            git.chmod(0o755)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(app, 'mise_path', return_value=binary), patch.dict(os.environ, {'PATH': directory + ':' + os.environ['PATH']}), patch('sys.stdin.isatty', return_value=False), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                code = app.main(['github'])
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn('GitHub HTTPS access configured.', output.getvalue())
            self.assertNotIn('SIGN-IN', output.getvalue())

    def test_check_points_to_the_global_github_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mise.toml').write_text('[tools]\n')
            (root / 'php-modules.txt').write_text('Core\n')
            for series in ('noble', 'resolute'):
                (root / f'mise.{series}.toml').write_text('[bootstrap.packages]\n"apt:git"="1:2.56.0-0ppa1"\n')
            binary = root / 'mise'
            binary.write_text('#!/bin/sh\ncase "$*" in *"git --version") echo "git version 2.56.0";; *"php -r"*) echo \'["Core"]\';; "which "*) echo /fixture;; *"auth status --hostname github.com --active") exit 1;; *) exit 99;; esac\n')
            binary.chmod(0o755)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(app, 'ROOT', root), patch.object(app, 'mise_path', return_value=binary), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                code = app.main(['check'])
            self.assertEqual(code, 1)
            self.assertIn('GitHub authentication: run dev-tools github', error.getvalue())
            self.assertNotIn('MISMATCH', output.getvalue())

    def test_matching_packages_do_not_run_sudo(self):
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as command:
            app.install_system_packages(Path('/mise'), app.isolated_env('noble'))
        self.assertFalse(any(call.args[0][0] == 'sudo' for call in command.call_args_list))

    def test_browser_upgrade_respects_the_isolated_xdg_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / 'data'
            old = data / 'mise/installs/http-chrome/155/chrome'
            new = data / 'mise/installs/http-chrome/156/chrome'
            for binary in (old, new):
                binary.parent.mkdir(parents=True)
                binary.touch()
            target = data / 'dev-tools/browser/chrome'
            target.parent.mkdir(parents=True)
            target.symlink_to(old)
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(data), 'MISE_DATA_DIR': directory + '/unrelated'}), patch('subprocess.check_output', return_value=str(new)):
                app.install_browser_link(Path('/mise'), app.isolated_env())
            self.assertEqual(target.resolve(), new)

    def test_browser_upgrade_preserves_a_personal_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            personal = data / 'personal-chrome'
            personal.touch()
            target = data / 'dev-tools/browser/chrome'
            target.parent.mkdir(parents=True)
            target.symlink_to(personal)
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(data)}), patch('subprocess.check_output', return_value=str(data / 'mise/installs/http-chrome/156/chrome')):
                with self.assertRaisesRegex(RuntimeError, 'collision'):
                    app.install_browser_link(Path('/mise'), app.isolated_env())
            self.assertEqual(target.resolve(), personal)

    def test_github_code_is_prominent_and_failed_login_does_not_configure_git(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'mise'
            binary.write_text('#!/bin/sh\ncase "$*" in *"auth status"*) exit 1;; *"auth login"*) echo "! First copy your one-time code: ABCD-EFGH"; echo "Open this URL to continue in your web browser: https://github.com/login/device"; exit 1;; *) exit 99;; esac\n')
            binary.chmod(0o755)
            output = io.StringIO()
            with patch.object(app, 'mise_path', return_value=binary), patch('sys.stdin.isatty', return_value=True), contextlib.redirect_stdout(output):
                code = app.main(['github'])
            self.assertEqual(code, 1)
            self.assertIn('CODE: ABCD-EFGH', output.getvalue())
            self.assertIn('https://github.com/login/device', output.getvalue())

    def test_existing_herdr_preferences_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'herdr/config.toml'
            target.parent.mkdir()
            target.write_text('theme = "personal"\n')
            output = io.StringIO()
            with patch.dict('os.environ', {'XDG_CONFIG_HOME': directory}), patch('subprocess.run') as command, contextlib.redirect_stdout(output):
                code = app.main(['herdr-config'])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(), 'theme = "personal"\n')
            command.assert_not_called()
            self.assertIn('dev-tools herdr-config --apply', output.getvalue())

    @unittest.skipUnless(__import__('os').environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_native_herdr_copy_and_repeat_do_not_rewrite(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            env = {'HOME': directory, 'XDG_CONFIG_HOME': directory + '/config', 'XDG_DATA_HOME': directory + '/data', 'XDG_CACHE_HOME': directory + '/cache'}
            with patch.dict(os.environ, env), patch.object(app, 'mise_path', return_value=Path(os.environ['DEV_TOOLS_MISE'])):
                self.assertEqual(app.main(['herdr-config']), 0)
                target = Path(directory) / 'config/herdr/config.toml'
                before = target.stat().st_mtime_ns
                self.assertEqual(app.main(['herdr-config']), 0)
                self.assertEqual(target.stat().st_mtime_ns, before)
