from test_commands import app
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class SocketFirewall(unittest.TestCase):
    def test_existing_firewall_is_verified_without_installing(self):
        with patch('shutil.which', return_value='/sfw'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'Socket Firewall Free, version 1.16.0\n', '')) as command:
            app.install_sfw(Path('/mise'), app.isolated_env())
        self.assertEqual(command.call_count, 1)
        self.assertIn('--version', command.call_args.args[0])
        self.assertEqual(command.call_args.kwargs['env']['SFW_SKIP_UPDATE_CHECK'], '1')

    def test_missing_firewall_uses_official_npm_install_and_verifies_result(self):
        calls = []
        def external(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, 'Socket Firewall Free, version 1.16.0\n', '')
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'home', return_value=Path(directory)), patch('shutil.which', side_effect=[None, '/sfw']), patch('subprocess.run', side_effect=external):
            app.install_sfw(Path('/mise'), app.isolated_env())
        self.assertEqual(calls[0][:6], ['/mise', 'exec', '--', 'npm', 'install', '--global'])
        self.assertIn('sfw@2.0.6', calls[0])
        self.assertIn('--ignore-scripts', calls[0])
        self.assertIn('--version', calls[1])

    def test_invalid_existing_command_is_preserved(self):
        with patch('shutil.which', return_value='/foreign/sfw'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'unrelated', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'collision'):
                app.install_sfw(Path('/mise'), app.isolated_env())
        self.assertEqual(command.call_count, 1)

    def test_npm_failure_does_not_report_a_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'home', return_value=Path(directory)), patch('shutil.which', return_value=None), patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, ['npm'])) as command:
            with self.assertRaises(subprocess.CalledProcessError):
                app.install_sfw(Path('/mise'), app.isolated_env())
        self.assertEqual(command.call_count, 1)

    def test_failed_verification_preserves_vendor_error(self):
        with patch('shutil.which', return_value='/sfw'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'vendor download refused')):
            with self.assertRaisesRegex(RuntimeError, 'vendor download refused'):
                app.sfw_version(Path('/mise'), app.isolated_env())
