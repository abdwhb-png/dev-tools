# CI qualification — 2026-11-01

Real installation qualification passed for runtime commit `abaa7756d3289a4810be4ff9429d5120cf377e89` in [GitHub Actions run 41348117131](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131). All five jobs completed successfully. This report and the README status are documentation-only descendants of that commit; the workflow deliberately skips Markdown-only changes.

## Qualified environments

| Target | Execution environment | Result |
| --- | --- | --- |
| Ubuntu 24.04 x86_64 | Fresh Ubuntu container on a Linux runner | [Passed](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131/job/124972217052) |
| Ubuntu 26.04 x86_64 | Fresh Ubuntu container on a Linux runner | [Passed](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131/job/124972216871) |
| Ubuntu 24.04 under WSL2 x86_64 | Actual distribution on Windows Server 2025 | [Passed](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131/job/124972216953) |
| Ubuntu 26.04 under WSL2 x86_64 | Actual distribution on Windows Server 2025 | [Passed](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131/job/124972216670) |
| Isolated tests and Bash syntax | Ubuntu runner, no tool installation | [Passed](https://github.com/abdwhb-png/dev-tools/actions/runs/41348117131/job/124972217007) |

Both WSL logs record kernel `6.18.54.1-microsoft-standard-WSL2`. The Linux container jobs establish Ubuntu userspace behavior; they do not constitute deployment to a particular VPS or qualification of its kernel and hosting configuration.

## Executed coverage

Each of the four installation jobs ran the public bootstrap preview, installed the declared packages and locked tools as an unprivileged account with sudo, checked actual tool versions and PHP modules, and successfully repeated the bootstrap. After installation, all 17 tests passed, including five tests against the installed native mise executable; before installation, the 12 isolated tests passed with those five native tests explicitly skipped.

The jobs also verified:

- Bash and Zsh interactive login shells resolve the configured Node and PHP versions.
- PHP can query an in-memory SQLite database and create an Imagick image; Redis and MongoDB extension classes load.
- Python loads SSL and SQLite, Bun evaluates a program, and Go compiles and executes a program using the installed toolchain.
- Composer validates a minimal project without installing application dependencies.
- A project switches to Node 24.18.0 and leaving it restores Node 26.13.0; a `packageManager` declaration selects pnpm 12.8.1.
- Additional binary PHP 8.4.27 can be prepared without a source build, selected by a project, and used by Composer; the final baseline check still verifies PHP 8.5.12.
- The global `dev-tools:github` task runs through native mise, configures gh's HTTPS helper, and passes the full tools/GitHub check. Git clones this private repository from an independent temporary directory. A control clone with credential helpers and authentication headers disabled fails, establishing that checkout credentials did not supply the successful clone.
- Global task entrypoints resolve their declaring checkout both from that checkout and an unrelated working directory. Existing shell profile content is preserved in native fixture tests.

The GitHub setup test uses the temporary Actions token with repository contents read permission. No personal credentials are included in fixtures or artifacts. Checkout credential persistence is disabled. Real installation jobs are guarded against ordinary workstation execution.

## Retained evidence

The successful run publishes `ubuntu-24.04-evidence`, `ubuntu-26.04-evidence`, `wsl2-24.04-evidence` and `wsl2-26.04-evidence` artifacts. Each contains the installation log, native mise tool inventory, PHP module list, selected PHP/Composer paths, package inventory, configured GitHub helper and the expected unauthenticated-clone failure. All four artifact sets were downloaded and checked when preparing this report. GitHub's artifact retention policy applies; the committed report records the result after artifacts expire.

## Failures found and corrected

The [initial installation run](https://github.com/abdwhb-png/dev-tools/actions/runs/41346250445) failed. Ubuntu 24.04 needed `libatomic1` for Node; Ubuntu 26.04 lacked the required SOAP extension; Windows checkout line endings prevented WSL Bash execution. The native declarations now include those packages, and `.gitattributes` enforces LF endings. A scoped APT policy disables optional recommended/suggested packages, avoiding unrelated service packages on minimal installations. A regression verifies that this policy reaches the elevated package operation, does not forward arbitrary environment variables, and is removed afterward. The [next base matrix](https://github.com/abdwhb-png/dev-tools/actions/runs/41346804302) passed all four installations.

Expanded coverage then [found a global-task path failure](https://github.com/abdwhb-png/dev-tools/actions/runs/41347111085): native mise's global `config_root` resolved to the user's home instead of this checkout. Task entrypoints now use a configuration variable derived from the declaring `config_source`. A subsequent [regression-test run](https://github.com/abdwhb-png/dev-tools/actions/runs/41347544544) rejected a valid symlink spelling; the test now compares resolved executable identity. These failures remain historical evidence. Runs [41347697365](https://github.com/abdwhb-png/dev-tools/actions/runs/41347697365) and [41347990534](https://github.com/abdwhb-png/dev-tools/actions/runs/41347990534) were canceled after being superseded and are not passing qualification results. The final successful run covers all resulting runtime, workflow and test changes together.

## Remaining limits

Personal `gh auth login` device/browser interaction, credential-store availability, and persistence across sessions require validation on each real machine. CI establishes token-based authentication and the native Git credential helper, not the personal OAuth interaction. No developer tools or packages were installed on the current workstation, and no VPS was provisioned. Application dependency compatibility, project test suites, database services, remote Redis/MongoDB connectivity, and model providers are outside this qualification. No claim is made for other architectures, Ubuntu releases, or shells.

Pins and upstream package availability can change. Rerun the matrix after runtime/configuration updates and keep ordinary Ubuntu security maintenance enabled. A passing run is dated installation evidence, not a continuing vulnerability audit.

## Public installer qualification

The report above preserves the original private-repository qualification. The public installer changes are tracked in [PR #1](https://github.com/abdwhb-png/dev-tools/pull/1), whose checks link the exact candidate commit and installation evidence for each run. The repository is now public, and immutable releases are enabled. A targeted scan found no known private-key/GitHub-token/AWS-key signatures in eight historical commits and eight Actions logs before the visibility change; this was not an exhaustive secret detector.

The current matrix builds one standalone POSIX installer with the run's exact source SHA and passes the same artifact to all four installation targets. Git is deliberately removed before installation so the installer must restore the missing prerequisite through sudo. The first install uses a script file; the repeat install pipes the same artifact into sh. Tests run from the installed checkout, and all previous runtime checks remain. Public cloning now succeeds without credentials. Separately, Git's credential protocol must retrieve the CI credential through gh's configured helper, without printing or saving the credential value. The earlier private-clone negative control remains historical evidence, not a current public-repository assertion.

The manual publication workflow reuses this matrix and only publishes the candidate bytes after every job passes. It cannot be dispatched from this PR branch: it requires main. No release has been published, and the latest release URL is unavailable until the separately authorized PR merge and first publication. Actual publication, release download comparison and personal browser login remain unexecuted checks.

## First release and avoiding duplicate qualification

[v0.1.0](https://github.com/abdwhb-png/dev-tools/releases/tag/v0.1.0) was published as an immutable release from merge commit `4233a913478c8ff4210e0bb76b3f8d64769180db`. Its tree and the fully qualified source `2b139de0ee6e55a3e003033dd9d7c9e028b65a32` are identical: `01b78828e8c0b640c4cfd6abc8aee7ac41a87135`. Qualification run [41353978416](https://github.com/abdwhb-png/dev-tools/actions/runs/41353978416) supplies the four-platform runtime evidence. The release installer generated by run 41401114027 was compared byte-for-byte with a fresh render for the release SHA/version; isolated tests and shell syntax passed. Versioned and latest public downloads were verified against those bytes. Its SHA-256 is `90f2ac14eafadb20760df7cecafa80df9645195dcae832af7d68c2df2ec7e87b`.

The redundant merge run 41401029104 and release matrix 41401114027 were canceled on the user's instruction to avoid repeating identical installation work. Subsequent workflow changes remove main push qualification and make publication reuse complete same-content evidence. The lookup excludes Markdown exactly as the qualification path filter does; all other tracked paths, object IDs and modes must match. No matching complete evidence means an explicit failure, not an automatic expensive fallback.
