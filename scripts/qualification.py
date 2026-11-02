"""Find complete CI evidence for identical tracked non-Markdown files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

# These control publication/qualification, not the installed environment.
# Their changes always run isolated checks; only a full matrix supplies evidence.
CONTROL_FILES = {b'.github/workflows/release.yml', b'.github/workflows/qualification.yml',
                 b'scripts/release_version.py', b'tests/test_release_version.py',
                 b'scripts/qualification.py', b'tests/test_qualification.py'}

REQUIRED_JOBS = {'build', 'isolated', 'ubuntu (24.04)', 'ubuntu (26.04)', 'wsl2 (24.04)', 'wsl2 (26.04)'}


def fingerprint(revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full Git revision')
    exists = subprocess.run(['git', 'cat-file', '-e', revision + '^{commit}'], capture_output=True)
    if exists.returncode:
        subprocess.run(['git', 'fetch', '--no-tags', 'origin', revision], check=True)
    tree = subprocess.check_output(['git', 'ls-tree', '-rz', revision])
    entries = [entry for entry in tree.split(b'\0') if entry and not entry.split(b'\t', 1)[1].endswith(b'.md') and entry.split(b'\t', 1)[1] not in CONTROL_FILES]
    return hashlib.sha256(b'\0'.join(entries)).hexdigest()


def api(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', endpoint], text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--allow-missing', action='store_true', help='Report reused=false instead of failing when no complete evidence exists')
    args = parser.parse_args()
    target = fingerprint(args.revision)
    runs = api(f'repos/{args.repository}/actions/workflows/qualification.yml/runs?status=success&per_page=100')['workflow_runs']
    for run in runs:
        if run['conclusion'] != 'success' or run['head_repository']['full_name'] != args.repository:
            continue
        if fingerprint(run['head_sha']) != target:
            continue
        jobs = api(f"repos/{args.repository}/actions/runs/{run['id']}/jobs?per_page=100")['jobs']
        passed = {job['name'] for job in jobs if job['conclusion'] == 'success'}
        if not REQUIRED_JOBS.issubset(passed):
            continue
        # PR run metadata names the head commit; the installer records the merge
        # revision actually exercised by all four installation jobs.
        with tempfile.TemporaryDirectory(prefix='dev-tools-evidence-') as directory:
            download = subprocess.run(['gh', 'run', 'download', str(run['id']), '--repo', args.repository,
                                       '--name', 'installer-candidate', '--dir', directory], capture_output=True)
            if download.returncode:
                print(f"Evidence artifact unavailable for run {run['id']} (exit {download.returncode}); cannot reuse it.", file=sys.stderr)
                continue
            candidate = Path(directory) / '.ci-installer'
            if not candidate.is_file():
                print(f"Missing installer evidence for run {run['id']}; cannot reuse it.", file=sys.stderr)
                continue
            source = re.search(r"^    revision='([0-9a-f]{40})'$", candidate.read_text(), re.MULTILINE)
            if not source or fingerprint(source.group(1)) != target:
                continue
        print(f"Reusing complete qualification: {run['html_url']} (fingerprint {target})")
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
                output.write(f"run_url={run['html_url']}\nreused=true\n")
        return 0
    if args.allow_missing:
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
                output.write('reused=false\n')
        print('No matching complete qualification; the installation matrix is required.')
        return 0
    print('No matching complete qualification. Run qualification.yml manually for this revision before publication.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
