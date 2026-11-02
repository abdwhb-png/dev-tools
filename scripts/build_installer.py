"""Render a standalone installer pinned to one Git revision."""
import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
        parser.error('revision must be a full lowercase Git SHA')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-ci)?', args.version):
        parser.error('version must be vMAJOR.MINOR.PATCH, optionally suffixed -ci')
    template = Path(__file__).with_name('install.sh.in').read_text()
    args.output.write_text(template.replace('@REVISION@', args.revision).replace('@VERSION@', args.version))
    args.output.chmod(0o755)


if __name__ == '__main__':
    main()
