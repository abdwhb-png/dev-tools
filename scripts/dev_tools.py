#!/usr/bin/python3
"""Prepare developer tools using mise's configuration and Ubuntu's package manager."""

import argparse
import difflib
import time
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OS_RELEASE = Path('/etc/os-release')


def configuration():
    return tomllib.loads((ROOT / 'mise.toml').read_text())


def host():
    values = dict(line.split('=', 1) for line in OS_RELEASE.read_text().splitlines() if '=' in line)
    version = values.get('VERSION_ID', '').strip('"')
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or values.get('ID', '').strip('"') != 'ubuntu' or version not in ('24.04', '26.04'):
        raise RuntimeError('Supported hosts: Ubuntu 24.04/26.04 x86_64, including WSL2.')
    return {'24.04': 'noble', '26.04': 'resolute'}[version]


def home():
    return Path.home()


def fragment():
    return Path(os.environ.get('XDG_CONFIG_HOME', home() / '.config')) / 'mise/conf.d/dev-tools'


def preflight():
    target = fragment()
    if target.is_symlink():
        if target.resolve() != ROOT:
            raise RuntimeError(f'Configuration collision: {target}')
    elif target.exists():
        raise RuntimeError(f'Configuration collision: {target}')
    for name in ('dev-tools-php', 'dev-tools-git'):
        source = Path('/etc/apt/sources.list.d') / f'mise-{name}.sources'
        if source.exists():
            # Only accept an already declared repository with its pinned signing key.
            declaration = configuration()['bootstrap']['apt']['sources'][name]
            expected = declaration.get('uris', 'git-core')
            if expected not in source.read_text():
                raise RuntimeError(f'APT source collision: {source}')


def run(args, **kwargs):
    print('+', ' '.join(str(arg) for arg in args), flush=True)
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def isolated_env(series=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('MISE_')}
    env.update(MISE_GLOBAL_CONFIG_FILE=str(ROOT / 'scripts/empty.toml'), MISE_SYSTEM_CONFIG_FILE=str(ROOT / 'scripts/empty.toml'),
               MISE_CEILING_PATHS=str(ROOT.parent), MISE_TRUSTED_CONFIG_PATHS=str(ROOT),
               MISE_AUTO_INSTALL='0', MISE_SELF_UPDATE_AUTO='0')
    if series:
        env['MISE_ENV'] = series
    return env


def mise_path():
    return Path(os.environ.get('XDG_DATA_HOME', home() / '.local/share')) / 'dev-tools/mise/bin/mise'


def fetch_mise():
    cfg = configuration()['vars']
    binary = mise_path()
    if binary.exists():
        if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg['mise_binary_sha256']:
            raise RuntimeError(f'Existing mise checksum mismatch: {binary}')
        return binary
    url = f'https://github.com/jdx/mise/releases/download/v{cfg["mise_version"]}/mise-v{cfg["mise_version"]}-linux-x64.tar.xz'
    with tempfile.TemporaryDirectory(prefix='dev-tools-download-') as directory:
        archive = Path(directory) / 'mise.tar.xz'
        with urllib.request.urlopen(url, timeout=60) as response:
            archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != cfg['mise_sha256']:
            raise RuntimeError('mise archive checksum mismatch')
        with tarfile.open(archive) as bundle:
            member = bundle.getmember('mise/bin/mise')
            if not member.isfile():
                raise RuntimeError('mise archive does not contain a regular executable')
            with bundle.extractfile(member) as source:
                content = source.read()
        if hashlib.sha256(content).hexdigest() != cfg['mise_binary_sha256']:
            raise RuntimeError('mise executable checksum mismatch')
        binary.parent.mkdir(parents=True, exist_ok=True)
        temporary = binary.with_suffix('.new')
        temporary.write_bytes(content)
        temporary.chmod(0o755)
        temporary.replace(binary)
    return binary


def php_packages(series):
    return tomllib.loads((ROOT / f'mise.{series}.toml').read_text())['bootstrap']['packages']


def preview(series):
    print(f'Ubuntu {series}; tools declared by {ROOT}')
    for name, value in configuration()['tools'].items():
        print(f'{name}: {value["version"] if isinstance(value, dict) else value}')
    for name, value in php_packages(series).items():
        print(f'{name}: {value}')
    for command in tool_versions():
        print(f'Existing path {command}: {shutil.which(command) or "not found"}')
    print('APT sources: https://packages.sury.org/php/ and git-core/ppa')
    print(f'Global mise configuration: {fragment()} -> {ROOT}')
    print('Shell activation: managed blocks for installed Bash/Zsh shells.')
    print('Herdr Core: official installer if absent; existing versions preserved. TUI is optional: dev-tools install herdr-tui.')
    print('APT applies changes incrementally; completed package changes are not rolled back.')


def php_prefix(version):
    return Path(os.environ.get('XDG_DATA_HOME', home() / '.local/share')) / f'dev-tools/php/{version}'


def link_php(mise, version, env):
    branch = '.'.join(version.split('.')[:2])
    executable = Path(f'/usr/bin/php{branch}')
    actual = subprocess.run([str(executable), '-r', 'echo PHP_VERSION;'], check=True, capture_output=True, text=True).stdout
    if actual != version:
        raise RuntimeError(f'PHP package mismatch: expected {version}, found {actual}')
    prefix = php_prefix(version)
    target = prefix / 'bin/php'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == executable:
        pass
    elif target.exists() or target.is_symlink():
        raise RuntimeError(f'PHP executable collision: {target}')
    else:
        target.symlink_to(executable)
    # Linking a system runtime must not regenerate the reviewed download lockfile.
    run([mise, 'link', f'php@{version}', prefix], env=env | {'MISE_LOCKFILE': '0'}, cwd=ROOT)


def install_shells(mise, env):
    # Generate only a temporary native config for the user's installed shells.
    with tempfile.TemporaryDirectory(prefix='dev-tools-shell-') as directory:
        path = Path(directory)
        activation, edits = [], []
        path_line = 'export PATH="$HOME/.local/bin:$PATH"'
        if shutil.which('bash'):
            activation.append('bashrc = true')
            login = '.bash_profile' if (home() / '.bash_profile').exists() else '.profile'
            edits.append(f'"~/{login}/dev-tools-shims" = {{ block = \'eval "$(mise activate bash --shims)"\' }}')
            for file in (login, '.bashrc'):
                edits.append(f'"~/{file}/dev-tools-path" = {{ line = {path_line!r}, position = "prepend" }}')
        if shutil.which('zsh'):
            if os.environ.get('ZDOTDIR'):
                raise RuntimeError('Custom ZDOTDIR requires explicit shell configuration; no shell files were edited.')
            activation.append('zsh = true')
            edits.append(f'"~/.zshenv/dev-tools-path" = {{ line = {path_line!r}, position = "prepend" }}')
        (path / 'mise.toml').write_text('[bootstrap.mise_shell_activate]\n' + '\n'.join(activation) + '\n[dotfiles]\n' + '\n'.join(edits) + '\n')
        shell_env = env | {'MISE_CEILING_PATHS': str(path.parent), 'MISE_TRUSTED_CONFIG_PATHS': str(path)}
        # Startup blocks invoke mise by name, so publish its dedicated launcher first.
        run([mise, 'bootstrap', '--only', 'dotfiles,mise-shell-activate', '--yes'], cwd=path, env=shell_env)


def publish_launchers(mise, *, dry_run=False):
    for name, source in (('mise', mise), ('dev-tools', ROOT / 'scripts/dev_tools.py')):
        target = home() / '.local/bin' / name
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if target.exists() or target.is_symlink():
            raise RuntimeError(f'Launcher collision: {target}; keep it or move it explicitly before retrying.')
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)


def install_system_packages(mise, env):
    status = subprocess.run([str(mise), 'bootstrap', 'packages', 'status', '--missing'], cwd=ROOT, env=env)
    if status.returncode == 0:
        print('System packages already conform; APT skipped.')
        return
    if status.returncode != 1:
        raise RuntimeError('Unable to inspect system packages')
    # mise's pinned APT backend has no install-recommends option and sudo drops
    # APT_CONFIG. Elevate only the native package operation, with explicit inputs.
    with tempfile.TemporaryDirectory(prefix='dev-tools-apt-') as directory:
        policy = Path(directory) / 'apt.conf'
        policy.write_text('APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n')
        names = ('MISE_GLOBAL_CONFIG_FILE', 'MISE_SYSTEM_CONFIG_FILE', 'MISE_CEILING_PATHS',
                 'MISE_TRUSTED_CONFIG_PATHS', 'MISE_AUTO_INSTALL', 'MISE_SELF_UPDATE_AUTO', 'MISE_ENV')
        settings = [f'{name}={env[name]}' for name in names if name in env]
        run(['sudo', 'env', f'APT_CONFIG={policy}', 'MISE_DATA_DIR=/var/lib/dev-tools/mise',
             'MISE_CACHE_DIR=/var/cache/dev-tools/mise', *settings,
             mise, 'bootstrap', 'packages', 'apply', '--manager', 'apt', '--yes'], cwd=ROOT)


def herdr_binary(component):
    names = ('herdr-core', 'hc') if component == 'core' else ('herdr',)
    for name in names:
        path = shutil.which(name)
        if path:
            result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=10)
            prefix = 'hc' if component == 'core' else 'herdr'
            if result.returncode == 0 and re.fullmatch(prefix + r' \d+\.\d+\.\d+[^\s]*', result.stdout.strip()):
                return path, result.stdout.strip()
            raise RuntimeError(f'Herdr executable collision: {path}; inspect it before retrying.')
    return None


def install_herdr(component):
    existing = herdr_binary(component)
    if existing:
        print(f'{existing[1]} already installed at {existing[0]}; installer skipped. Use ' + ('hc update.' if component == 'core' else 'herdr update.'))
        return
    url = 'https://releases.herdr.dev/core/install.sh' if component == 'core' else 'https://herdr.dev/install.sh'
    with tempfile.TemporaryDirectory(prefix='dev-tools-herdr-install-') as directory:
        script = Path(directory) / 'install.sh'
        run(['curl', '-fsSL', '--output', script, url])
        run(['sh', script])
    if not herdr_binary(component):
        raise RuntimeError(f'Official Herdr {component} installer completed but its command is absent from PATH.')


def install_optional(args):
    if args.dry_run:
        print('Install Herdr TUI using https://herdr.dev/install.sh if absent; preserve existing versions and preferences.')
        return 0
    if os.geteuid() == 0:
        raise RuntimeError('Run as a regular user, not root.')
    install_herdr('tui')
    herdr_config(argparse.Namespace(apply=False))
    return 0


def bootstrap(args):
    series = host()
    preflight()
    preview(series)
    if args.dry_run:
        return 0
    if os.geteuid() == 0:
        raise RuntimeError('Run as a regular user with sudo privileges, not root.')
    publish_launchers(mise_path(), dry_run=True)
    if not args.yes and (not sys.stdin.isatty() or input('Apply these changes? [y/N] ').lower() not in ('y', 'yes')):
        print('Cancelled; no changes applied.')
        return 1
    mise = fetch_mise()
    env = isolated_env(series)
    install_system_packages(mise, env)
    link_php(mise, configuration()['tools']['php'], env)
    # Install only download-managed tools: PHP is supplied by APT and linked above.
    tools = [name for name in configuration()['tools'] if name != 'php']
    run([mise, 'install', '--locked', *tools], env=env, cwd=ROOT)
    target = fragment()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_symlink():
        target.symlink_to(ROOT, target_is_directory=True)
    publish_launchers(mise)
    install_shells(mise, env)
    install_browser_link(mise, env)
    os.environ['PATH'] = str(home() / '.local/bin') + os.pathsep + os.environ.get('PATH', '')
    install_herdr('core')
    check(argparse.Namespace(tools_only=True))
    print('Tools ready. Open a new terminal, then run: dev-tools github; dev-tools check. Future updates: dev-tools upgrade.')
    return 0


def tool_versions():
    result = {}
    aliases = {'node': 'node', 'python': 'python3', 'github-cli': 'gh', 'ripgrep': 'rg', 'http:composer': 'composer'}
    for name, value in configuration()['tools'].items():
        result[aliases.get(name, name.removeprefix('http:'))] = value['version'] if isinstance(value, dict) else value
    package = php_packages(host())['apt:git']
    result['git'] = package.split(':')[-1].split('-')[0]
    return result


def check(args):
    mise = mise_path()
    if not mise.is_file():
        raise RuntimeError('Managed mise is absent; run dev-tools bootstrap first.')
    env = isolated_env()
    failures = []
    for command, expected in tool_versions().items():
        argv = ['version'] if command == 'go' else ['--version']
        result = subprocess.run([str(mise), 'exec', '--', command, *argv], cwd=ROOT, env=env, capture_output=True, text=True)
        text = result.stdout + result.stderr
        versions = re.findall(r'(?<![\d.])v?(\d+\.\d+(?:\.\d+){0,2}(?:RC\d+|[ab]\d+)?)', text)
        valid = result.returncode == 0 and bool(versions) and versions[0] == expected
        print(f'{command}: {"OK" if valid else "MISMATCH"} (expected {expected})')
        if not valid:
            failures.append(command)
    result = subprocess.run([str(mise), 'exec', '--', 'php', '-r', 'echo json_encode(get_loaded_extensions());'], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    modules = {name.lower().replace(' ', '_') for name in json.loads(result.stdout)}
    required = set((ROOT / 'php-modules.txt').read_text().lower().split())
    missing = required - modules
    if missing:
        failures.append('PHP modules: ' + ', '.join(sorted(missing)))
    # Report the actual command paths without reading credentials or environment files.
    run([mise, 'which', 'php'], cwd=ROOT, env=env)
    run([mise, 'which', 'composer'], cwd=ROOT, env=env)
    core = herdr_binary('core')
    if core:
        print(f'Herdr Core: {core[1]} ({core[0]}); updates: hc update')
    else:
        failures.append('Herdr Core absent: run dev-tools bootstrap')
    if not args.tools_only:
        status = subprocess.run([str(mise), 'exec', '--', 'gh', 'auth', 'status', '--hostname', 'github.com', '--active'], cwd=ROOT, env=env, capture_output=True)
        if status.returncode:
            failures.append('GitHub authentication: run dev-tools github')
        else:
            helper = subprocess.run(['git', 'config', '--get', 'credential.https://github.com.helper'], capture_output=True, text=True)
            if helper.returncode or 'gh auth git-credential' not in helper.stdout:
                failures.append('GitHub HTTPS credential helper: run dev-tools github')
    if failures:
        raise RuntimeError('Not ready: ' + '; '.join(failures))
    print('Tools verified.' if args.tools_only else 'Tools and GitHub verified.')
    return 0


def github(args):
    mise = mise_path()
    env = isolated_env()
    prefix = [mise, 'exec', '--', 'gh']
    status = subprocess.run([str(p) for p in prefix + ['auth', 'status', '--hostname', 'github.com', '--active']], cwd=ROOT, env=env, capture_output=True)
    if status.returncode:
        if not sys.stdin.isatty():
            raise RuntimeError('GitHub login requires an interactive terminal; tools remain installed.')
        login_github(prefix, env)
    protocol = subprocess.run([str(p) for p in prefix + ['config', 'get', 'git_protocol', '--host', 'github.com']], cwd=ROOT, env=env, capture_output=True, text=True)
    if protocol.returncode or protocol.stdout.strip() != 'https':
        run(prefix + ['config', 'set', 'git_protocol', 'https', '--host', 'github.com'], cwd=ROOT, env=env)
    helper = subprocess.run(['git', 'config', '--get', 'credential.https://github.com.helper'], capture_output=True, text=True)
    if helper.returncode or 'gh auth git-credential' not in helper.stdout:
        run(prefix + ['auth', 'setup-git', '--hostname', 'github.com'], cwd=ROOT, env=env)
    print('GitHub HTTPS access configured.')
    return 0


def login_github(prefix, env):
    print('\nGITHUB SIGN-IN — ACTION REQUIRED\nOpen the address below on your own computer.\n', flush=True)
    login_env = {k: v for k, v in env.items() if k not in ('GH_DEBUG', 'GH_FORCE_TTY')}
    login_env.update(GH_PROMPT_DISABLED='1', NO_COLOR='1')
    command = [str(p) for p in prefix + ['auth', 'login', '--hostname', 'github.com', '--git-protocol', 'https', '--web', '--clipboard=false']]
    process = subprocess.Popen(command, cwd=ROOT, env=login_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in process.stdout:
            code = re.search(r'First copy your one-time code: ([A-Z0-9-]+)', line)
            if code:
                print('\n' + '=' * 48 + '\nCODE: ' + code.group(1) + '\nhttps://github.com/login/device\n' + '=' * 48 + '\nWaiting for authorization…', flush=True)
            else:
                print(line.rstrip(), flush=True)
        if process.wait():
            raise RuntimeError('GitHub login failed or expired; rerun dev-tools github.')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()


def install_browser_link(mise, env):
    source = Path(subprocess.check_output([str(mise), 'which', 'chrome'], cwd=ROOT, env=env, text=True).strip())
    target = Path(os.environ.get('XDG_DATA_HOME', home() / '.local/share')) / 'dev-tools/browser/chrome'
    if target.is_symlink() and target.resolve() == source.resolve():
        return
    if target.exists() or target.is_symlink():
        data = Path(env.get('XDG_DATA_HOME', home() / '.local/share'))
        installs = Path(env.get('MISE_DATA_DIR', data / 'mise')) / 'installs/http-chrome'
        if not target.is_symlink() or not target.resolve().is_relative_to(installs.resolve()):
            raise RuntimeError(f'Browser launcher collision: {target}')
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def herdr_config(args):
    source = ROOT / 'config/herdr.toml'
    target = Path(os.environ.get('XDG_CONFIG_HOME', home() / '.config')) / 'herdr/config.toml'
    if target.exists():
        if target.read_bytes() == source.read_bytes():
            print('Herdr preferences already conform.')
            return 0
        if not args.apply:
            print('Personal Herdr preferences preserved. To review/apply the profile: dev-tools herdr-config --apply')
            return 0
        print(''.join(difflib.unified_diff(target.read_text().splitlines(True), source.read_text().splitlines(True), fromfile='current', tofile='profile')))
        if not sys.stdin.isatty() or input('Back up and replace Herdr preferences? [y/N] ').lower() not in ('y', 'yes'):
            raise RuntimeError('Herdr preferences unchanged.')
        backup = target.with_name(f'config.toml.backup-{time.time_ns()}')
        shutil.copy2(target, backup)
        print(f'Backup: {backup}')
    with tempfile.TemporaryDirectory(prefix='dev-tools-herdr-') as directory:
        config = Path(directory)
        (config / 'mise.toml').write_text('[dotfiles]\n' + json.dumps(str(target)) + ' = { source = ' + json.dumps(str(source)) + ', mode = "copy" }\n')
        env = isolated_env() | {'MISE_CEILING_PATHS': str(config.parent), 'MISE_TRUSTED_CONFIG_PATHS': str(config)}
        run([mise_path(), 'dot', 'apply', '--yes'], cwd=config, env=env)
    return 0


def upgrade(args):
    managed = Path(os.environ.get('XDG_DATA_HOME', home() / '.local/share')) / 'dev-tools/source'
    if ROOT.resolve() != managed.resolve():
        raise RuntimeError('Upgrade requires the checkout managed by the release installer.')
    current = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    with urllib.request.urlopen('https://api.github.com/repos/abdwhb-png/dev-tools/releases/latest', timeout=30) as response:
        release = json.load(response)
    version = release.get('tag_name', '')
    revision = release.get('target_commitish', '')
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v\d+\.\d+\.\d+', version) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise RuntimeError('Latest release metadata does not identify a stable pinned source.')
    if current == revision:
        print(f'Source already up to date: {version}.')
        print('Tools were not checked. Run dev-tools check to verify them, or dev-tools bootstrap to repair this installation.')
        return 0
    print(f'Upgrade to {version} ({revision}).')
    if args.dry_run:
        print('Preview only; no installer downloaded or changes applied.')
        return 0
    url = f'https://github.com/abdwhb-png/dev-tools/releases/download/{version}/install.sh'
    asset = next((item for item in release.get('assets', []) if item.get('name') == 'install.sh'), {})
    digest = asset.get('digest', '')
    if asset.get('browser_download_url') != url or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise RuntimeError('Published installer URL or SHA-256 is missing or invalid.')
    with tempfile.TemporaryDirectory(prefix='dev-tools-upgrade-') as directory:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        if 'sha256:' + hashlib.sha256(content).hexdigest() != digest:
            raise RuntimeError('Published installer checksum mismatch; nothing executed.')
        installer = Path(directory) / 'install.sh'
        installer.write_bytes(content)
        command = ['sh', str(installer), '--upgrade']
        if args.yes:
            command.append('--yes')
        run(command)
    return 0


def prepare_php(args):
    host()
    if not re.fullmatch(r'8\.[2-9]\.\d+', args.version):
        raise RuntimeError('Supply an exact stable PHP 8.x version, for example 8.4.27.')
    # Resolve exact upstream version against the signed binary repository, never source-build.
    branch = '.'.join(args.version.split('.')[:2])
    baseline = php_packages(host())
    desired = [name.removeprefix('apt:').replace('php' + '.'.join(configuration()['tools']['php'].split('.')[:2]) + '-', f'php{branch}-') for name in baseline if name.startswith('apt:php')]
    pins = []
    for package in desired:
        result = subprocess.run(['apt-cache', 'madison', package], capture_output=True, text=True, check=True)
        versions = [line.split('|')[1].strip() for line in result.stdout.splitlines() if '|' in line and 'packages.sury.org/php' in line]
        if package.endswith(('-redis', '-imagick', '-mongodb', '-imap', '-zstd')):
            candidate = versions[0] if versions else None
        else:
            candidate = next((v for v in versions if v.split(':')[-1].startswith(args.version + '-')), None)
        if not candidate:
            raise RuntimeError(f'Binary package unavailable: {package} for PHP {args.version}; no fallback performed.')
        pins.append(f'{package}={candidate}')
    print('Prepare PHP binary packages:', ' '.join(pins))
    if not sys.stdin.isatty() or input('Install these packages with sudo? [y/N] ').lower() not in ('y', 'yes'):
        raise RuntimeError('PHP preparation cancelled.')
    run(['sudo', 'apt-get', 'install', '--yes', '--no-install-recommends', *pins])
    link_php(mise_path(), args.version, isolated_env())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    boot = commands.add_parser('bootstrap')
    boot.add_argument('--dry-run', action='store_true')
    boot.add_argument('--yes', action='store_true')
    verify = commands.add_parser('check')
    verify.add_argument('--tools-only', action='store_true')
    commands.add_parser('github')
    update = commands.add_parser('upgrade')
    update.add_argument('--yes', action='store_true')
    update.add_argument('--dry-run', action='store_true')
    install = commands.add_parser('install')
    install.add_argument('tool', choices=['herdr-tui'])
    install.add_argument('--dry-run', action='store_true')
    profile = commands.add_parser('herdr-config')
    profile.add_argument('--apply', action='store_true')
    php = commands.add_parser('php-prepare')
    php.add_argument('version')
    args = parser.parse_args(argv)
    try:
        return {'install': install_optional, 'bootstrap': bootstrap, 'check': check, 'github': github, 'upgrade': upgrade, 'herdr-config': herdr_config, 'php-prepare': prepare_php}[args.command](args)
    except KeyboardInterrupt:
        print('Cancelled. Any completed changes are retained.', file=sys.stderr)
        return 130
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'{args.command} failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
