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


class HerdrInstall(unittest.TestCase):
    def test_existing_core_is_preserved_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'herdr-core'
            binary.write_text('#!/bin/sh\necho "hc 0.1.99"\n')
            binary.chmod(0o755)
            with patch.dict(os.environ, {'PATH': directory}), patch('subprocess.run', wraps=subprocess.run) as command:
                app.install_herdr('core')
            self.assertEqual(command.call_count, 1)

    def test_preview_does_not_execute_or_fetch(self):
        with patch('subprocess.run') as command:
            self.assertEqual(app.main(['install', 'herdr-tui', '--dry-run']), 0)
        command.assert_not_called()

    def test_failed_download_never_executes_installer(self):
        calls = []
        def external(argv, **kwargs):
            calls.append(argv)
            raise subprocess.CalledProcessError(22, argv)
        with patch('shutil.which', return_value=None), patch('subprocess.run', side_effect=external):
            with self.assertRaises(subprocess.CalledProcessError):
                app.install_herdr('core')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'curl')

    def test_official_installer_is_used_and_temporary_file_removed(self):
        paths = []
        def external(argv, **kwargs):
            if argv[0] == 'curl':
                self.assertEqual(argv[-1], 'https://releases.herdr.dev/core/install.sh')
                path = Path(argv[argv.index('--output') + 1])
                path.write_text('official fixture')
                paths.append(path)
            elif argv[0] == 'sh':
                self.assertEqual(Path(argv[1]).read_text(), 'official fixture')
            else:
                return subprocess.CompletedProcess(argv, 0, 'hc 0.1.16\n', '')
            return subprocess.CompletedProcess(argv, 0)
        with patch('shutil.which', side_effect=lambda name: '/fixture/herdr-core' if paths else None), patch('subprocess.run', side_effect=external):
            app.install_herdr('core')
        self.assertFalse(paths[0].exists())

    def test_tui_uses_its_official_installer(self):
        calls = []
        def external(argv, **kwargs):
            calls.append(argv)
            if argv[0] == 'curl':
                Path(argv[argv.index('--output') + 1]).write_text('official tui fixture')
            return subprocess.CompletedProcess(argv, 0, 'herdr 0.9.5', '')
        with patch('shutil.which', side_effect=lambda name: '/fixture/herdr' if len(calls) >= 2 else None), patch('subprocess.run', side_effect=external):
            app.install_herdr('tui')
        self.assertEqual(calls[0][-1], 'https://herdr.dev/install.sh')
        self.assertEqual(calls[1][0], 'sh')
        self.assertFalse(Path(calls[1][1]).exists())

    def test_invalid_existing_binary_is_not_overwritten(self):
        with patch('shutil.which', return_value='/foreign/herdr-core'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'another program', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'collision'):
                app.install_herdr('core')
        self.assertEqual(command.call_count, 1)
