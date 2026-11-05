import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dev_tools', ROOT / 'scripts/dev_tools.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class ZshProfile(unittest.TestCase):
    def test_existing_configuration_is_preserved_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rc = root / '.zshrc'
            rc.write_text('export PRIVATE_VALUE=keep\n')
            with patch.object(app, 'home', return_value=root), patch.dict(os.environ, {'XDG_DATA_HOME': directory + '/data'}), patch.object(app, 'run') as external:
                self.assertEqual(app.main(['zsh-config']), 0)
            self.assertEqual(rc.read_text(), 'export PRIVATE_VALUE=keep\n')
            external.assert_not_called()

    def test_noninteractive_adoption_refuses_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rc = root / '.zshrc'
            rc.write_text('# personal\n')
            with patch.object(app, 'home', return_value=root), patch('sys.stdin.isatty', return_value=False):
                self.assertEqual(app.main(['zsh-config', '--apply']), 1)
            self.assertEqual(rc.read_text(), '# personal\n')
            self.assertEqual(list(root.glob('*.backup-*')), [])

    @unittest.skipUnless(os.environ.get('DEV_TOOLS_MISE'), 'requires verified mise')
    def test_install_repeat_and_adoption_preserve_personal_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {'HOME': directory, 'XDG_DATA_HOME': directory + '/data', 'XDG_CONFIG_HOME': directory + '/config', 'XDG_CACHE_HOME': directory + '/cache'}
            with patch.object(app, 'home', return_value=root), patch.dict(os.environ, env), patch.object(app, 'mise_path', return_value=Path(os.environ['DEV_TOOLS_MISE'])), patch.object(app, 'install_zsh_components'), patch.object(app, 'validate_zsh_profile'):
                self.assertTrue(app.install_zsh_profile())
                rc = root / '.zshrc'
                initial = rc.read_bytes()
                self.assertTrue(app.install_zsh_profile())
                self.assertEqual(rc.read_bytes(), initial)
                self.assertEqual(rc.read_text().count('mise activate zsh'), 1)
                self.assertEqual(rc.read_text().count('/zsh/profile.zsh'), 1)
                rc.write_text(rc.read_text() + '# personal addition\n')
                personal = rc.read_bytes()
                self.assertFalse(app.install_zsh_profile())
                self.assertEqual(rc.read_bytes(), personal)
                with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='yes'):
                    self.assertEqual(app.main(['zsh-config', '--apply']), 0)
                backups = list(app.zsh_directory().glob('backup-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0] / '.zshrc').read_bytes(), personal)
                self.assertEqual((backups[0].stat().st_mode & 0o777), 0o700)
                self.assertEqual((backups[0] / '.zshrc').stat().st_mode & 0o777, 0o600)
                self.assertNotIn('personal addition', rc.read_text())
                prompt = app.zsh_directory() / 'p10k.zsh'
                prompt.write_text('# customized prompt\n')
                self.assertFalse(app.install_zsh_profile())
                self.assertEqual(prompt.read_text(), '# customized prompt\n')

    def test_failed_dependencies_do_not_replace_personal_rc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rc = root / '.zshrc'
            rc.write_text('# personal\n')
            with patch.object(app, 'home', return_value=root), patch.dict(os.environ, {'XDG_DATA_HOME': directory + '/data'}), patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='yes'), patch.object(app, 'install_zsh_components', side_effect=RuntimeError('download failed')):
                self.assertEqual(app.main(['zsh-config', '--apply']), 1)
            self.assertEqual(rc.read_text(), '# personal\n')

    def test_zdotdir_refused_before_network(self):
        with patch.dict(os.environ, {'ZDOTDIR': '/custom'}), patch.object(app, 'run') as external:
            self.assertEqual(app.main(['zsh-config', '--apply']), 1)
            external.assert_not_called()

    def test_login_shell_change_uses_account_database(self):
        import types
        before = types.SimpleNamespace(pw_name='fixture', pw_shell='/bin/bash')
        after = types.SimpleNamespace(pw_name='fixture', pw_shell='/usr/bin/zsh')
        with patch.object(app.pwd, 'getpwuid', side_effect=[before, after]), patch.object(app, 'run') as external:
            app.set_zsh_login()
            external.assert_called_once_with(['sudo', 'chsh', '-s', '/usr/bin/zsh', 'fixture'])
        with patch.object(app.pwd, 'getpwuid', return_value=after), patch.object(app, 'run') as external:
            app.set_zsh_login()
            external.assert_not_called()

    def test_invalid_profile_does_not_replace_personal_rc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rc = root / '.zshrc'
            rc.write_text('# personal\n')
            with patch.object(app, 'home', return_value=root), patch.dict(os.environ, {'XDG_DATA_HOME': directory + '/data'}), patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='yes'), patch.object(app, 'install_zsh_components'), patch.object(app, 'validate_zsh_profile', side_effect=RuntimeError('invalid profile')):
                self.assertEqual(app.main(['zsh-config', '--apply']), 1)
            self.assertEqual(rc.read_text(), '# personal\n')
