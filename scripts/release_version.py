"""Calculate release metadata from published stable tags and conventional commits."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

STABLE = re.compile(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')


def next_version(last, messages):
    if last is None:
        return 'v0.1.0'
    major, minor, patch = map(int, STABLE.fullmatch(last).groups())
    if re.search(r'^[a-z]+(?:\([^\n)]*\))?!:|^BREAKING[ -]CHANGE:', messages, re.MULTILINE):
        return f'v{major + 1}.0.0'
    if re.search(r'^feat(?:\([^\n)]*\))?:', messages, re.MULTILINE):
        return f'v{major}.{minor + 1}.0'
    return f'v{major}.{minor}.{patch + 1}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.revision):
        parser.error('Expected a full Git SHA')
    releases = json.loads(subprocess.check_output(['gh', 'release', 'list', '--repo', args.repository,
                        '--limit', '100', '--json', 'tagName,isDraft,isPrerelease'], text=True))
    stable = [r['tagName'] for r in releases if not r['isDraft'] and not r['isPrerelease'] and STABLE.fullmatch(r['tagName'])]
    last = max(stable, key=lambda tag: tuple(map(int, STABLE.fullmatch(tag).groups()))) if stable else None
    needed = True
    if last:
        commit = subprocess.check_output(['git', 'rev-parse', last + '^{commit}'], text=True).strip()
        subprocess.run(['git', 'merge-base', '--is-ancestor', commit, args.revision], check=True)
        if commit == args.revision:
            version, needed = last, False
        else:
            messages = subprocess.check_output(['git', 'log', '--format=%B', f'{last}..{args.revision}'], text=True)
            version = next_version(last, messages)
    else:
        version = next_version(None, '')
    print(f'{"Next release" if needed else "Already published"}: {version}')
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write(f'version={version}\nneeded={str(needed).lower()}\n')


if __name__ == '__main__':
    main()
