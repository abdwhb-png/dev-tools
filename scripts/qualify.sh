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
python3 -m unittest discover -s tests -v
bash bootstrap.sh --dry-run
bash bootstrap.sh --yes
export PATH="$HOME/.local/bin:$PATH"
export DEV_TOOLS_MISE="$HOME/.local/bin/mise"
python3 -m unittest discover -s tests -v
python3 scripts/dev_tools.py check --tools-only
bash bootstrap.sh --yes
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
GIT_TERMINAL_PROMPT=0 mise exec -- git clone --quiet --depth 1 "https://github.com/${GITHUB_REPOSITORY}.git" "$fixture/authenticated-clone"
[[ -f "$fixture/authenticated-clone/README.md" ]]
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
python3 scripts/dev_tools.py check --tools-only
