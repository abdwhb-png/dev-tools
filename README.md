# Development tools

An independent, versioned developer-tool configuration for Ubuntu 24.04 and 26.04 x86_64, including WSL2. It prepares native command-line tools and GitHub access. It does not install application dependencies, containers, databases, web servers, or Pi.

**Status: installation qualification passed on Ubuntu 24.04/26.04 and real WSL2 24.04/26.04 on 2026-11-01.** See the [CI evidence and qualification limits](docs/ci-qualification.md) for the tested commit, job links and covered behavior.

## Installation

Use a regular Ubuntu account with sudo access. The bootstrap uses Ubuntu's `/usr/bin/python3` (3.11 or newer) and Python's standard library. On a minimal image, install the initial prerequisites with the distribution package manager:

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl
```

Install directly from your terminal without keeping a script file:

```sh
curl -fsSL https://github.com/abdwhb-png/dev-tools/releases/latest/download/install.sh | sh
```

The installer reads confirmations from your terminal even when its input is a pipe. For unattended use, append `-s -- --yes` after `sh`. It installs missing Ubuntu prerequisites, then applies the release's exact checkout. Keep that checkout at its installed location.

After installing a release that includes the global command, future updates are simply:

```sh
dev-tools upgrade
```

The command is installed in `~/.local/bin` and works across Bash, Zsh, SSH and ordinary process execution. It checks the latest stable release, skips installer downloads when already current, verifies a downloaded installer's SHA-256 against GitHub release metadata, and delegates to the same installer with `--upgrade`. Temporary files are removed automatically. `dev-tools upgrade --yes` is unattended; `--dry-run` reads release metadata but downloads no installer and changes nothing.

The installer distinguishes a new installation from checking/repairing an existing checkout or updating it. Its confirmation mentions prerequisites only when some are missing. Those prerequisites are distinct from the developer tools and system libraries, which bootstrap checks separately. An already current source release does not imply healthy tools: use `dev-tools check` to verify them, or `dev-tools bootstrap` to repair the installed configuration without keeping or downloading `install.sh`.

For an existing v0.2.0 installation that does not yet have this command, bootstrap it once after the new release is published:

```sh
curl -fsSL https://github.com/abdwhb-png/dev-tools/releases/latest/download/install.sh | sh -s -- --upgrade
```

You can also use a reviewed checkout directly with `sh bootstrap.sh`. Git, system Python and certificates are needed for this route. The global updater requires a checkout managed by the release installer and refuses unrelated locations.

The preview performs no network requests and writes no files. It describes intended packages and configuration, not a complete APT dependency simulation. `--yes` explicitly accepts the same changes without a prompt. Keep the checkout at its installed location: the global fragment links to it as the authoritative source. Moving it requires explicitly updating that link.

The bootstrap downloads the pinned mise executable, verifies its SHA-256, installs declared signed APT packages, registers the native PHP executable with mise, installs locked tools, and enables Bash/Zsh activation using mise's managed file edits. Existing shell content and Ubuntu's `.profile` remain intact. Custom `ZDOTDIR` requires manual activation; automatic edits are refused.

After opening a new terminal:

```sh
dev-tools github
dev-tools check
```

GitHub setup uses the native device/browser login flow, selects HTTPS, and configures Git's credential helper. A valid active account on github.com is reused; expired inactive accounts and other GitHub hosts do not trigger a new login. Login is per machine. gh owns credential storage; on machines without a credential store, its documented fallback is a local plaintext file. No credentials belong in this repository. Cancelling login leaves tools installed.

## Tools and versions

`mise.toml` is authoritative for download-managed tools; `mise.lock` records their URLs and checksums. The pinned baseline, verified on 2026-11-01, is mise 2026.10.25, Node 26.13.0, npm 12.2.1, pnpm 12.16.1, Bun 1.4.4, Python 3.15.2, Go 1.27.3, gh 2.103.3, ripgrep 15.2.0, jq 1.8.2, PHP 8.5.12, Composer 2.11.1 and Git 2.56.0.

Git and PHP are distribution-managed. `mise.noble.toml` and `mise.resolute.toml` pin the actual package revisions for each Ubuntu release. mise's native APT declarations own the Git-core PPA and canonical Sury repository and verify pinned signing-key fingerprints. The system owns those package files; mise links PHP through a dedicated prefix containing only the PHP executable. A system upgrade can change a linked executable: `check` inspects its real version rather than trusting the link label.

Only the native package operation runs through sudo, using `/var/lib/dev-tools/mise` and `/var/cache/dev-tools/mise` for its system state and cache. Its temporary APT policy disables recommended and suggested packages without changing machine-wide APT settings. Runtime installations and shell configuration belong to the regular account.

PHP is precompiled and includes the required modules in `php-modules.txt`. Extensions follow the selected repository's packaged versions; they are not automatically upgraded to independent PECL releases. Composer is installed independently as a checked official PHAR and uses the selected PHP through its native shebang. Local Herd executables and configuration are not copied.

`check --tools-only` checks the repository baseline, regardless of the invoking project, and does not require GitHub credentials. The full check also requires GitHub authentication and the HTTPS credential helper. The checker reports failures instead of accepting a different executable merely because mise printed the requested version in a fallback warning.

## Projects and additional PHP versions

Use native mise project declarations. The global fragment enables native version files for Node, npm, pnpm, Bun and Python, including `packageManager` declarations. Trust project configurations explicitly when mise requests it. Automatic installation before tasks is disabled globally so that checks and setup tasks do not install tools implicitly; use an explicit `mise install` when a project needs tools. A project's tools override the global defaults; scripts can use `mise exec -- COMMAND`.

Additional PHP versions require binary packages first:

```sh
dev-tools php-prepare 8.4.27
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

The workflow runs on pull requests or explicit manual dispatch, without an automatic repeat on main pushes. Superseded runs of the same PR are canceled. It qualifies fresh Ubuntu 24.04/26.04 containers and actual WSL2 24.04/26.04 distributions, repeated installation, Bash/Zsh startup, PHP functionality, compilation, project overrides, and GitHub HTTPS access. Its real-install script refuses ordinary workstation execution. CI uses GitHub's temporary repository token with read-only contents permission to configure gh's native helper and exercise Git’s credential protocol without exposing credentials. An independent anonymous clone verifies public access. Personal browser/device login and credential storage still require per-machine qualification. Provider calls are not part of qualification. Preserve logs, actual paths and package inventories as evidence. A failed or unrun job is not qualification. Markdown-only changes skip the installation matrix; runtime, test and workflow changes rerun it.

For updates, query live official vendor release APIs, npm registry metadata/engines, PHP advisories and repository package indexes. Choose stable releases, inspect applicable security advisories, update the native declarations, regenerate the lockfile with `mise lock` for the download-managed tools, and rerun qualification. Do not install unpinned `latest` tools during ordinary preparation. Use Socket Firewall for supported networked application dependency commands; this repository itself has no such dependency install.

Sources: [mise](https://mise.jdx.dev/), [Sury installation](https://packages.sury.org/php/README.txt), [Git on Ubuntu](https://git-scm.com/install/linux), [PHP security release](https://news-web.php.net/php.announce/513), [Python security release](https://www.python.org/downloads/release/python-3152/), [Composer](https://getcomposer.org/download/), [gh authentication](https://cli.github.com/manual/gh_auth_login).

## Publishing a release

Run `Publish qualified installer` from `main` without inputs. It calculates the next version from published stable releases and commits since the last tag: `feat:` increments the minor number, `!`/`BREAKING CHANGE:` increments the major number, and other changes increment the patch. Drafts/prereleases are excluded. Repeating publication for the same already released commit is a no-op. Only clicking the publication button authorizes publication; merging does not publish automatically.

The workflow requires complete installation evidence for identical runtime files. Markdown and the explicitly listed publication/qualification control files are excluded from that fingerprint; they always receive isolated checks. All other tracked paths, file modes and object IDs must match, including installer, bootstrap, configuration, lockfile, runtime tests and real-install qualification script. PRs reuse matching complete evidence instead of repeating the four installations. A manual dispatch of `qualification.yml` deliberately forces a full matrix. A skipped/partial matrix never becomes complete evidence.

Publication only runs isolated tests and syntax checks, renders the versioned wrapper and compares its public downloads. It never launches an installation matrix as a fallback. Missing or expired complete evidence blocks publication. Release notes link the reused run; immutability remains enabled, and only the publishing job has contents write permission. Existing drafts are not overwritten automatically. Merging and publishing remain separate actions.

## Agentic tools

The configuration includes agent-browser 0.41.1, Chrome for Testing 156.0.8078.80 and Herdr 0.9.5 as locked native downloads. Zsh and browser system libraries come from Ubuntu. No agent CLI, API credentials, browser profile, SSH configuration or running session is copied.

The reviewed Herdr profile in `config/herdr.toml` reproduces the local terminal theme, Ctrl+B bindings, UI preferences and Zsh login shell. It is copied to a regular file, preserving existing personal preferences. To explicitly review, back up and replace them, use `dev-tools herdr-config --apply`. Rerunning with identical contents does not create another backup or rewrite the file. Existing Herdr servers are never restarted by bootstrap.

Use `dev-tools upgrade` to move a clean managed checkout to the latest stable release; older installations use the one-time pipe command above. It still refuses foreign origins, modified checkouts and unrequested version changes. A same-version upgrade does not fetch Git again; matching APT packages skip sudo/APT, locked tool installs reuse existing installations, and identical Herdr preferences are left alone. No system rollback is promised after a partial failure; rerun the same installer to repair it. The streamed installer preview remains offline; the global upgrade preview only reads release metadata.

GitHub login now presents the native gh device code in a separate text frame with its URL. Authorization happens on your own computer, without trying to open a browser on the VPS. gh still owns OAuth and credential storage. Already valid authentication is reused.

For browser observation on the VPS, run `agent-browser dashboard start`. From your local computer, run `ssh -N -L 4848:127.0.0.1:4848 USER@VPS` and visit `http://localhost:4848`. The dashboard is loopback-only and starts on demand. Stop it with `agent-browser dashboard stop`. Keep agent work in named sessions; no dashboard AI provider is enabled by this utility.
