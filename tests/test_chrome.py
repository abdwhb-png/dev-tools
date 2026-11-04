from test_commands import app
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class Chrome(unittest.TestCase):
    def test_official_package_is_installed_through_apt(self):
        calls = []
        def external(argv, **kwargs):
            calls.append(argv)
            if argv[0] == 'dpkg-query':
                return subprocess.CompletedProcess(argv, 1, '', '')
            return subprocess.CompletedProcess(argv, 0)
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'CHROME', Path(directory) / 'chrome', create=True), patch('subprocess.run', side_effect=external):
            app.install_chrome()
        self.assertEqual(calls[1][-1], 'https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb')
        self.assertEqual(calls[2][:5], ['sudo', 'apt-get', 'install', '--yes', '--no-install-recommends'])
        self.assertFalse(Path(calls[2][-1]).exists())

    def test_existing_official_package_skips_download_and_apt(self):
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'install ok installed', '')) as command:
            app.install_chrome()
        self.assertEqual(command.call_count, 1)

    def test_failed_download_never_runs_apt(self):
        def external(argv, **kwargs):
            if argv[0] == 'dpkg-query':
                return subprocess.CompletedProcess(argv, 1, '', '')
            raise subprocess.CalledProcessError(22, argv)
        with patch('subprocess.run', side_effect=external) as command:
            with self.assertRaises(subprocess.CalledProcessError):
                app.install_chrome()
        self.assertEqual(command.call_count, 2)

    def test_sandbox_qualification_refuses_ci_bypass_before_launch(self):
        with patch.dict('os.environ', {'CI': 'true'}), patch('subprocess.run') as command:
            with self.assertRaisesRegex(RuntimeError, 'CI'):
                app.check_browser_sandbox(Path('/mise'), app.isolated_env())
        command.assert_not_called()

    def sandbox_probe(self, command_line, sandbox):
        import os
        import json
        responses = iter([command_line, sandbox])
        def external(argv, **kwargs):
            result = json.dumps({'success': True, 'data': {'result': next(responses)}}) if 'eval' in argv else ''
            return subprocess.CompletedProcess(argv, 0, result, '')
        env = {k: v for k, v in os.environ.items() if k != 'CI'}
        with patch.dict(os.environ, env, clear=True), patch('subprocess.run', side_effect=external) as command:
            app.check_browser_sandbox(Path('/mise'), app.isolated_env())
        self.assertEqual(command.call_args.args[0][-1], 'close')

    def test_real_sandbox_status_and_launch_flags_are_required(self):
        self.sandbox_probe('/opt/google/chrome/chrome --headless', 'Seccomp-BPF sandbox\tYes\nYou are adequately sandboxed.')

    def test_no_sandbox_flag_fails_even_if_page_claims_safe(self):
        with self.assertRaisesRegex(RuntimeError, 'disabling'):
            self.sandbox_probe('/opt/google/chrome/chrome --no-sandbox', 'Seccomp-BPF sandbox\tYes\nYou are adequately sandboxed.')

    def test_negative_sandbox_status_is_not_accepted(self):
        with self.assertRaisesRegex(RuntimeError, 'adequate sandbox'):
            self.sandbox_probe('/opt/google/chrome/chrome --headless', 'Seccomp-BPF sandbox\tNo\nYou are NOT adequately sandboxed.')
