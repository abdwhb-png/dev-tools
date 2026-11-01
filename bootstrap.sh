#!/bin/sh
set -eu
root=$(cd -- "$(dirname -- "$0")" && pwd -P)
if [ ! -x /usr/bin/python3 ]; then
  echo 'Python 3.11+ from Ubuntu is required: sudo apt-get install python3' >&2
  exit 1
fi
exec /usr/bin/python3 "$root/scripts/dev_tools.py" bootstrap "$@"
