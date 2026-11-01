# Development tools

An independent, versioned developer-tool configuration for Ubuntu 24.04 and 26.04 x86_64, including WSL2. It prepares native command-line tools and GitHub access. It does not install application dependencies, containers, databases, web servers, or Pi.

**Status: implemented locally; real installation qualification has not run. Do not treat the supplied CI workflow as a passing result.**

## Installation

Use a regular Ubuntu account with sudo access. The bootstrap uses Ubuntu's `/usr/bin/python3` (3.11 or newer) and Python's standard library. On a minimal image, install the initial prerequisites with the distribution package manager:

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3
```

Obtain a reviewed checkout of this repository, enter it, then preview and apply:

```sh
bash bootstrap.sh --dry-run
bash bootstrap.sh
```

The preview performs no network requests and writes no files. It describes intended packages and configuration, not a complete APT dependency simulation. `--yes` explicitly accepts the same changes without a prompt. Keep the checkout at its installed location: the global fragment links to it as the authoritative source. Moving it requires explicitly updating that link.

The bootstrap downloads the pinned mise executable, verifies its SHA-256, installs declared signed APT packages, registers the native PHP executable with mise, installs locked tools, and enables Bash/Zsh activation using mise's managed file edits. Existing shell content and Ubuntu's `.profile` remain intact. Custom `ZDOTDIR` requires manual activation; automatic edits are refused.

After opening a new terminal:

```sh
mise run dev-tools:github
mise run dev-tools:check
```

GitHub setup uses the native device/browser login flow, selects HTTPS, and configures Git's credential helper. Login is per machine. gh owns credential storage; on machines without a credential store, its documented fallback is a local plaintext file. No credentials belong in this repository. Cancelling login leaves tools installed.

## Tools and versions

`mise.toml` is authoritative for download-managed tools; `mise.lock` records their URLs and checksums. The pinned baseline, verified on 2026-11-01, is mise 2026.10.25, Node 26.13.0, npm 12.2.1, pnpm 12.16.1, Bun 1.4.4, Python 3.15.2, Go 1.27.3, gh 2.103.3, ripgrep 15.2.0, jq 1.8.2, PHP 8.5.12, Composer 2.11.1 and Git 2.56.0.

Git and PHP are distribution-managed. `mise.noble.toml` and `mise.resolute.toml` pin the actual package revisions for each Ubuntu release. mise's native APT declarations own the Git-core PPA and canonical Sury repository and verify pinned signing-key fingerprints. The system owns those package files; mise links PHP through a dedicated prefix containing only the PHP executable. A system upgrade can change a linked executable: `check` inspects its real version rather than trusting the link label.

PHP is precompiled and includes the required modules in `php-modules.txt`. Extensions follow the selected repository's packaged versions; they are not automatically upgraded to independent PECL releases. Composer is installed independently as a checked official PHAR and uses the selected PHP through its native shebang. Local Herd executables and configuration are not copied.

`check --tools-only` checks the repository baseline, regardless of the invoking project, and does not require GitHub credentials. The full check also requires GitHub authentication and the HTTPS credential helper. The checker reports failures instead of accepting a different executable merely because mise printed the requested version in a fallback warning.

## Projects and additional PHP versions

Use native mise project declarations. The global fragment enables native version files for Node, npm, pnpm, Bun and Python, including `packageManager` declarations. Trust project configurations explicitly when mise requests it. Automatic installation before tasks is disabled globally so that checks and setup tasks do not install tools implicitly; use an explicit `mise install` when a project needs tools. A project's tools override the global defaults; scripts can use `mise exec -- COMMAND`.

Additional PHP versions require binary packages first:

```sh
mise run dev-tools:php-prepare -- 8.4.27
```

The task resolves the exact PHP release from the configured Sury binary repository, displays its package pins, asks before installing, and registers it with `mise link`. It never compiles PHP. If the repository no longer offers the requested release, it fails rather than selecting another release. Package indexes may need refreshing with `sudo apt-get update`.

Automatic PHP source installation is disabled. Native mise may warn and use another PATH executable when explicitly invoking `mise exec` for an unprepared version; prepare that version before running a project. A warning is not proof of the requested runtime. The baseline checker detects a different real version. Normal shims disable system fallback.

## Failure and recovery

Operations are incremental. APT changes and completed downloads remain after an error; there is no machine-wide rollback. Correct the reported cause and rerun the bootstrap. An unrelated global fragment or user launcher is a collision and is never overwritten automatically. No whole-system upgrade, automatic tool update, forced removal, or service activation is performed.

The bootstrap applies only this checkout's configuration, excluding unrelated global/system mise settings and parent project configuration. Personal configurations with higher precedence can still override the installed global fragment in everyday shells; inspect `mise config ls` and `mise current` if that is intentional. Never infer readiness from the presence of a symlink alone.

APT pins describe installation requests, not permanent package holds. Keep Ubuntu security maintenance enabled. If a vendor removes a pinned package, update the reviewed declarations rather than silently falling back. Removing the global fragment removes these defaults, but does not uninstall APT packages or erase personal data.

## Validation and maintenance

```sh
python3 -m unittest discover -s tests -v
bash -n bootstrap.sh scripts/qualify.sh
```

Tests import the production command module. Native mise characterization tests additionally run when `DEV_TOOLS_MISE` names a verified executable; they operate only on temporary fixtures. No package install or GitHub login runs in the local test suite.

The workflow qualifies fresh Ubuntu 24.04/26.04 and actual WSL2 24.04/26.04 distributions, repeated installation, shell startup, PHP functionality, and project overrides. Its real-install script refuses ordinary workstation execution. Credentials are not needed in CI and provider calls are not part of qualification. Preserve logs, actual paths and package inventories as evidence. A failed or unrun job is not qualification.

For updates, query live official vendor release APIs, npm registry metadata/engines, PHP advisories and repository package indexes. Choose stable releases, inspect applicable security advisories, update the native declarations, regenerate the lockfile with `mise lock` for the download-managed tools, and rerun qualification. Do not install unpinned `latest` tools during ordinary preparation. Use Socket Firewall for supported networked application dependency commands; this repository itself has no such dependency install.

Sources: [mise](https://mise.jdx.dev/), [Sury installation](https://packages.sury.org/php/README.txt), [Git on Ubuntu](https://git-scm.com/install/linux), [PHP security release](https://news-web.php.net/php.announce/513), [Python security release](https://www.python.org/downloads/release/python-3152/), [Composer](https://getcomposer.org/download/), [gh authentication](https://cli.github.com/manual/gh_auth_login).
