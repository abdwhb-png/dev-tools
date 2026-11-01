# Local validation — 2026-11-01

## Scope

The repository was created locally. No host package installation, shell activation, provider request, GitHub authentication, remote repository creation, push, or workflow dispatch was performed. The existing daily tool installations remain in place.

A mise 2026.10.25 executable was downloaded to a temporary directory and verified against the SHA-256 returned by its official release API. It was used for native configuration characterization and lockfile generation, with temporary HOME/config/data/cache directories. Lock generation fetched upstream metadata and artifacts for provenance verification; it did not install the declared tools. PHP registration tests used a fictitious executable in a temporary prefix, not a new PHP installation.

## Executed evidence

- The initial public preview test failed because no planned versions were reported, then passed after implementation.
- A native configuration test reproduced the rejection of `/dev/null` as a mise configuration filename. Isolated operations now use an actual empty TOML file.
- A native shell fixture reproduced `.bash_profile` creation shadowing the Ubuntu `.profile`. Shell preparation now preserves the profile selection and puts the mise launcher on PATH before activation.
- A regression test reproduced acceptance of the desired PHP version mentioned only in a fallback warning. Verification now checks the version actually reported first by the executable.
- A native task dry run reproduced automatic tool installation before `check`. Task auto-install is now explicitly disabled.
- Four native characterization tests plus ten isolated command tests passed together: 14 tests total, using Python's standard unittest runner and an explicitly supplied verified mise executable. The linked-PHP/locked-install characterization took approximately 52 seconds in the complete run because native backend metadata can require network access.
- Bash syntax checks passed for the bootstrap and qualification scripts. Python compilation checks passed. Workflow YAML and all TOML files, including the generated lockfile, parsed successfully.
- An additional isolated regression verified that an existing mise executable is checked by SHA-256 before execution; the final isolated run passed 11 tests (the four opt-in native tests were not repeated after this download-verification-only change).
- The actual public `bootstrap.sh --dry-run` completed without installing anything.
- The real-install qualification script refused ordinary workstation execution before performing installation work.

## Not established

The GitHub Actions workflow has not run. Real APT installation, full PHP extension equivalence and functionality, additional PHP preparation, all tool downloads/installations, default/project runtime switching, repeat installation, and real WSL2 behavior remain CI qualification gates. GitHub login and credential storage remain per-machine manual qualification. Passing local fixtures is not a successful Ubuntu/WSL installation result.

The workflow prepares four disposable targets: Ubuntu 24.04 and 26.04, plus WSL2 distributions of both releases. It retains logs, selected paths, PHP module output and package inventories. No configured model provider or paid API is needed.
