import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from test_commands import app


class UpgradeCommand(unittest.TestCase):
    def invoke(self, directory, revision, script, digest=None, options=('--yes',)):
        root = Path(directory) / 'dev-tools/source'
        root.mkdir(parents=True)
        payload = {'tag_name':'v0.3.0', 'target_commitish':revision, 'draft':False, 'prerelease':False,
                   'assets':[{'name':'install.sh', 'browser_download_url':'https://github.com/abdwhb-png/dev-tools/releases/download/v0.3.0/install.sh',
                              'digest':digest or 'sha256:'+hashlib.sha256(script).hexdigest()}]}
        with patch.dict(os.environ, {'XDG_DATA_HOME':directory}), patch.object(app,'ROOT',root), patch('subprocess.check_output',return_value='a'*40+'\n'), patch('urllib.request.urlopen',side_effect=[io.BytesIO(json.dumps(payload).encode()),io.BytesIO(script)]) as network, patch.object(app,'run') as command:
            code = app.main(['upgrade',*options])
            return code, network.call_count, command.call_args_list

    def test_current_release_does_not_download_or_execute_installer(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(output):
            code, requests, calls = self.invoke(directory,'a'*40,b'#!/bin/sh\nexit 0\n')
        self.assertEqual(code,0)
        self.assertEqual(requests,1)
        self.assertEqual(calls,[])
        self.assertIn('Source already up to date:', output.getvalue())
        self.assertIn('dev-tools check', output.getvalue())
        self.assertIn('dev-tools bootstrap', output.getvalue())

    def test_upgrade_uses_verified_installer_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            code, requests, calls = self.invoke(directory,'b'*40,b'#!/bin/sh\nexit 0\n')
        self.assertEqual(code,0)
        self.assertEqual(requests,2)
        argv=calls[0].args[0]
        self.assertEqual(argv[0],'sh')
        self.assertEqual(argv[2:],['--upgrade','--yes'])
        self.assertFalse(Path(argv[1]).exists())

    def test_bad_checksum_never_executes_download(self):
        with tempfile.TemporaryDirectory() as directory:
            code, _, calls = self.invoke(directory,'b'*40,b'corrupt','sha256:'+'0'*64)
        self.assertEqual(code,1)
        self.assertEqual(calls,[])

    def test_bootstrap_publishes_a_shell_independent_command_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app,'home',return_value=Path(directory)):
                app.publish_launchers(Path(directory)/'mise')
                target=Path(directory)/'.local/bin/dev-tools'
                self.assertTrue(target.is_symlink())
                before=target.lstat().st_mtime_ns
                app.publish_launchers(Path(directory)/'mise')
                self.assertEqual(target.lstat().st_mtime_ns,before)
                self.assertEqual(target.resolve(),app.ROOT/'scripts/dev_tools.py')
                self.assertIn('upgrade', subprocess.check_output([str(target),'--help'],text=True))

    def test_preview_only_reads_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            code, requests, calls = self.invoke(directory,'b'*40,b'not downloaded',options=('--dry-run',))
        self.assertEqual((code,requests,calls),(0,1,[]))

    def test_unpinned_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            code, requests, calls = self.invoke(directory,'main',b'not downloaded')
        self.assertEqual((code,requests,calls),(1,1,[]))

    def test_preflight_preserves_an_existing_user_command(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'.local/bin/dev-tools'
            target.parent.mkdir(parents=True)
            target.write_text('personal command')
            with patch.object(app,'home',return_value=Path(directory)):
                with self.assertRaisesRegex(RuntimeError,'collision'):
                    app.publish_launchers(Path(directory)/'mise',dry_run=True)
            self.assertEqual(target.read_text(),'personal command')
            self.assertFalse((target.parent/'mise').exists())
