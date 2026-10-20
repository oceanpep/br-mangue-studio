#!/bin/sh
set -eu

application_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
chmod u+x "$application_dir/BRMANGUE_Studio_Linux_x86_64"
exec "$application_dir/BRMANGUE_Studio_Linux_x86_64" --install-shortcuts
