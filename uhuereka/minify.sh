#!/usr/bin/env bash

# Create minified uHuereka JavaScript files to improve storage and network transfers.

set -e # Ensure the whole script exits on failures.

# Force execution in docker to ensure reproducibility.
if [ ! -f /.dockerenv ]; then
  echo "Running in docker."
  docker run --rm -it -v "$(pwd)/uhuereka":/mnt/uhuereka node bash -c "/mnt/uhuereka/minify.sh"
  exit 0
fi

set -x # Turn on command echoing to show all commands as they run.

project_root="$(dirname "$(dirname "$(readlink -f "$0")")")"
static_path="/mnt/uhuereka/src/uhuereka/static"
ls -1 "${static_path}"/*.js |grep -v ".min.js" | while read file; do
  minified_file="${file//.js/.min.js}"
  npm config set strict-ssl false
  npm install uglify-js -g
  uglifyjs --mangle -o "${minified_file}" -- "${file}"
done
