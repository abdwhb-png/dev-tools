#!/usr/bin/env bash
# Real installations are restricted to disposable GitHub Actions machines.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'Qualification requires a disposable GitHub Actions runner.' >&2; exit 1; }
[[ $(id -u) != 0 ]] || { echo 'Use the unprivileged qualifier account.' >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$root"
mkdir -p evidence
exec > >(tee evidence/qualification.log) 2>&1
uname -a
if [[ ${1:?platform required} == wsl2 ]]; then
  uname -r | grep -i microsoft-standard-WSL2
fi
sh .ci-installer --dry-run
curl -fsSL https://github.com/abdwhb-png/dev-tools/releases/download/v0.1.0/install.sh -o evidence/v0.1.0-install.sh
printf '90f2ac14eafadb20760df7cecafa80df9645195dcae832af7d68c2df2ec7e87b  evidence/v0.1.0-install.sh\n' | sha256sum -c -
sh evidence/v0.1.0-install.sh --yes
sh .ci-installer --yes --upgrade
export PATH="$HOME/.local/bin:$PATH"
export DEV_TOOLS_MISE="$HOME/.local/bin/mise"
python3 -m unittest discover -s "${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/source/tests" -v
dev-tools check --tools-only
python3 - <<'STATE' > evidence/before-replay.json
import json,os
from pathlib import Path
home=Path.home()
paths=[home/p for p in ('.profile','.bashrc','.zshrc','.zshenv','.zprofile','.local/bin/herdr-core','.local/bin/hc','.local/bin/mise','.local/bin/dev-tools','.config/mise/conf.d/dev-tools','.local/share/dev-tools/browser/chrome')]
print(json.dumps({str(p):[p.lstat().st_mtime_ns,p.readlink().as_posix() if p.is_symlink() else (__import__('hashlib').sha256(p.read_bytes()).hexdigest() if p.name == 'herdr-core' else p.read_text())] for p in paths if p.exists()},sort_keys=True))
STATE
cat .ci-installer | sh -s -- --yes --upgrade | tee evidence/replay.log
python3 - <<'STATE'
import json,re
from pathlib import Path
before=json.loads(Path('evidence/before-replay.json').read_text())
for name, expected in before.items():
    p=Path(name)
    actual=[p.lstat().st_mtime_ns,p.readlink().as_posix() if p.is_symlink() else (__import__('hashlib').sha256(p.read_bytes()).hexdigest() if p.name == 'herdr-core' else p.read_text())]
    assert actual==expected, 'Replay changed '+name
text=Path('evidence/replay.log').read_text()
assert not re.search(r'\bDownloading\b|bootstrap packages apply|apt-get',text,re.I), 'Replay repeated an installation operation'
print('Replay configuration, links and installation operations verified.')
STATE
# Every real command is evaluated through the installed environment.
mise exec -- php -r 'if ((new PDO("sqlite::memory:"))->query("select 1")->fetchColumn() != 1) exit(1); $i = new Imagick(); $i->newImage(1, 1, "white"); if (!class_exists("Redis") || !class_exists("MongoDB\\Driver\\Manager")) exit(1);'
mise exec -- python3 -c 'import ssl, sqlite3; print(ssl.OPENSSL_VERSION)'
mise exec -- bun -e 'if (1+1 !== 2) process.exit(1)'
export DEV_TOOLS_NODE_VERSION
export DEV_TOOLS_PHP_VERSION
DEV_TOOLS_NODE_VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("mise.toml", "rb"))["tools"]["node"])')
DEV_TOOLS_PHP_VERSION=$(python3 -c 'import tomllib; print(tomllib.load(open("mise.toml", "rb"))["tools"]["php"])')
bash -lic 'set -e; [[ $(node --version) == "v$DEV_TOOLS_NODE_VERSION" ]]; [[ $(php -r "echo PHP_VERSION;") == "$DEV_TOOLS_PHP_VERSION" ]]'
zsh -lic 'set -e; [[ $(node --version) == "v$DEV_TOOLS_NODE_VERSION" ]]; [[ $(php -r "echo PHP_VERSION;") == "$DEV_TOOLS_PHP_VERSION" ]]'
# A project must override the default and leaving it must restore the default.
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
printf 'package main\nimport "fmt"\nfunc main() { fmt.Print("compiled") }\n' > "$fixture/main.go"
[[ $(GOTOOLCHAIN=local mise exec -- go run "$fixture/main.go") == compiled ]]
printf '{"name":"fixture/tools","description":"Qualification fixture","license":"MIT","require":{}}\n' > "$fixture/composer.json"
mise exec -- composer --no-plugins --no-scripts validate --strict --no-check-publish "$fixture/composer.json"
[[ -n ${GH_TOKEN:-} && -n ${GITHUB_REPOSITORY:-} ]] || { echo 'CI repository token is required for HTTPS qualification.' >&2; exit 1; }
mise run dev-tools:github
git config --get-all credential.https://github.com.helper > evidence/github-helper.txt
python3 scripts/dev_tools.py check
# Public cloning proves installation does not depend on GitHub credentials.
GIT_TERMINAL_PROMPT=0 mise -C "$fixture" exec -- git -c credential.helper= -c http.https://github.com/.extraheader= clone --quiet --depth 1 "https://github.com/${GITHUB_REPOSITORY}.git" "$fixture/anonymous-clone"
# Exercise the native Git credential protocol without printing or storing its token.
mise exec -- python3 - <<'CREDENTIAL'
import os, subprocess
request = 'protocol=https\nhost=github.com\n\n'
result = subprocess.run(['git', 'credential', 'fill'], input=request, capture_output=True, text=True, check=True)
fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
if fields.get('password') != os.environ['GH_TOKEN']:
    raise SystemExit('Git credential helper did not supply the CI credential')
print('Git credential protocol verified; credential value withheld.')
CREDENTIAL
printf '[tools]\nnode = "24.18.0"\n' > "$fixture/mise.toml"
mise trust "$fixture/mise.toml"
mise -C "$fixture" install node
[[ $(mise -C "$fixture" exec -- node --version) == v24.18.0 ]]
[[ $(mise exec -- node --version) == v26.13.0 ]]
mkdir "$fixture/package-manager"
printf '{"packageManager":"pnpm@12.8.1"}\n' > "$fixture/package-manager/package.json"
printf '[tools]\nnode="26.13.0"\n' > "$fixture/package-manager/mise.toml"
mise trust "$fixture/package-manager/mise.toml"
mise -C "$fixture/package-manager" install pnpm
[[ $(mise -C "$fixture/package-manager" exec -- pnpm --version) == 12.8.1 ]]
# Existing-host preparation shares the production code, including version confirmation.
printf 'yes\n' | script -qec 'python3 scripts/dev_tools.py php-prepare 8.4.27' /dev/null
printf '[tools]\nphp="8.4.27"\n' > "$fixture/mise.toml"
[[ $(mise -C "$fixture" exec -- php -r 'echo PHP_VERSION;') == 8.4.27 ]]
mise -C "$fixture" exec -- composer --version 2>&1 | grep 'PHP version 8.4.27'
mise ls --json > evidence/tools.json
mise exec -- php -m > evidence/php-modules.txt
mise which php > evidence/php-path.txt
mise which composer > evidence/composer-path.txt
dpkg-query -W 'php*' git > evidence/packages.txt
dev-tools check --tools-only

# Agentic runtime: only local fixture content and owned sessions, no agent/provider calls.
printf '<html><body><button>Fixture button</button></body></html>' > "$fixture/browser.html"
cleanup_agentic() {
  mise exec -- agent-browser --session dev-tools-ci close || true
  mise exec -- agent-browser dashboard stop || true
  HC_SESSION=dev-tools-ci herdr-core server stop || true
  rm -rf "$fixture"
}
trap cleanup_agentic EXIT
mise exec -- agent-browser --session dev-tools-ci open "file://$fixture/browser.html"
mise exec -- agent-browser --session dev-tools-ci snapshot -i | grep 'Fixture button'
mise exec -- agent-browser --session dev-tools-ci screenshot "$root/evidence/browser.png"
mise exec -- agent-browser dashboard start
curl -fsS http://127.0.0.1:4848/ > evidence/dashboard.html
HC_SESSION=dev-tools-ci herdr-core run --bg --name fixture sh -c 'printf core-fixture; sleep 30' > evidence/herdr-core-run.txt
for attempt in $(seq 1 30); do
  HC_SESSION=dev-tools-ci herdr-core read fixture --lines 20 > evidence/herdr-core-read.txt
  if grep -q core-fixture evidence/herdr-core-read.txt; then break; fi
  sleep 1
done
grep -q core-fixture evidence/herdr-core-read.txt
HC_SESSION=dev-tools-ci herdr-core ls > evidence/herdr-core-status.txt
herdr-core --version > evidence/herdr-core-version.txt
cleanup_agentic
trap 'rm -rf "$fixture"' EXIT
# Fresh user configuration, sharing only immutable download caches.
fresh_home=$(mktemp -d)
env HOME="$fresh_home" XDG_CONFIG_HOME="$fresh_home/.config" XDG_DATA_HOME="$fresh_home/.local/share" XDG_CACHE_HOME="$HOME/.cache" sh .ci-installer --yes
test ! -e "$fresh_home/.local/bin/herdr"
test ! -e "$fresh_home/.config/herdr/config.toml"
env HOME="$fresh_home" PATH="$fresh_home/.local/bin:$PATH" dev-tools install herdr-tui
herdr_stamp=$(stat -c %Y "$fresh_home/.local/bin/herdr")
env HOME="$fresh_home" PATH="$fresh_home/.local/bin:$PATH" dev-tools install herdr-tui
[[ $(stat -c %Y "$fresh_home/.local/bin/herdr") == "$herdr_stamp" ]]
"$fresh_home/.local/bin/herdr" --version > evidence/herdr-tui-version.txt
rm -rf "$fresh_home"
