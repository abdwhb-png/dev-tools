from test_commands import app
import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

class Agentic(unittest.TestCase):
    def test_matching_packages_do_not_run_sudo(self):
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as command:
            app.install_system_packages(Path('/mise'), app.isolated_env('noble'))
        self.assertFalse(any(call.args[0][0] == 'sudo' for call in command.call_args_list))

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
            with patch.dict('os.environ', {'XDG_CONFIG_HOME': directory}), patch('subprocess.run') as command:
                code = app.main(['herdr-config'])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(), 'theme = "personal"\n')
            command.assert_not_called()

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
