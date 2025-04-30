#! /bin/bash

# Install uHuereka source and dependencies.

set -e

script_root="$(dirname $(readlink -f "$0"))"
project_root="$(dirname ${script_root})"

device=""
mpremote_bin="mpremote"
install_shared="false"
install_src="false"
install_dependencies="false"
compile="true"
no_ssl="false"
dry_run="false"
cmd_prefix=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --device)
      if [ -z "$2" ]; then echo "Must provide a device port. Example: --device /dev/ttyUSB0"; exit 1; fi
      device=$2
      shift
    ;;
    --shared)
      install_shared="true"
    ;;
    --src)
      install_src="true"
    ;;
    --deps)
      install_dependencies="true"
    ;;
    --no-compile)
      compile="false"
    ;;
    --no-ssl)
      no_ssl="true"
    ;;
    --dry-run)
      dry_run="true"
    ;;
    *)  echo "Try '-h' for more information"
        exit 0
    ;;
  esac
  shift
done

if [ "${no_ssl}" == "true" ]; then
  echo "Disabling SSL verification during installation."
  mpremote_bin="${script_root}/mpremote_no_ssl.py"
fi

if [ "${dry_run}" == "true" ]; then
  echo "Dry running commands without executing."
  cmd_prefix="echo"
fi

if [ "${install_dependencies}" == "true" ]; then
  if [ -z "${device}" ]; then
    echo 'No device specified. Please provide a device to connect to with "--device".'
    echo 'For help finding devices, here is the output of "mpremote devs":'
    mpremote devs
    exit 1
  fi

  microdot_src="uhuereka/src/lib/microdot.py"
  microdot_compiled="uhuereka/compiled/lib/microdot.mpy"
  if [ ! -f "$microdot_src" ]; then
    curl 'https://raw.githubusercontent.com/miguelgrinberg/microdot/refs/tags/v2.1.0/src/microdot/microdot.py' -o "$microdot_src"
    mpy-cross "$microdot_src" -o "$microdot_compiled" -O3
  fi
  $cmd_prefix $mpremote_bin mkdir lib || true
  $cmd_prefix $mpremote_bin cp "$microdot_compiled" :lib/microdot.mpy
  $cmd_prefix $mpremote_bin connect ${device} mip install logging
  $cmd_prefix $mpremote_bin connect ${device} mip install pathlib
  $cmd_prefix $mpremote_bin connect ${device} mip install time
fi

if [ "${install_shared}" == "true" ]; then
  # Cleanup any CPython files from the shared location before pushing in case project was run locally.
  $cmd_prefix rm -r ${project_root}/huereka/shared/__pycache__ || true
  # Sync with folders only works to existing folders, must create tree manually first for nested sync.
  $cmd_prefix $mpremote_bin mkdir huereka || true
  $cmd_prefix $mpremote_bin mkdir huereka/shared || true
  if [ "${compile}" == "true" ]; then
    mkdir -vp uhuereka/compiled/huereka/shared
    find huereka/shared -regex ".*.py" | while read file; do
      mpy-cross $file -o uhuereka/compiled/${file/.py/.mpy}
    done
    $cmd_prefix $mpremote_bin cp -r uhuereka/compiled/huereka/shared/. :huereka/shared
  else
    $cmd_prefix $mpremote_bin cp -r huereka/shared/. :huereka/shared
  fi
fi

if [ "${install_src}" == "true" ]; then
  # Sync with folders only works to existing folders, must create tree manually first for nested sync.
  $cmd_prefix $mpremote_bin mkdir lib || true
  $cmd_prefix $mpremote_bin mkdir uhuereka || true
  $cmd_prefix $mpremote_bin mkdir uhuereka/static || true
  if [ "${compile}" == "true" ]; then
    mkdir -vp uhuereka/compiled/uhuereka || true
    find uhuereka/src/uhuereka -regex ".*.py" -exec basename {} \; | while read file; do
      mpy-cross uhuereka/src/uhuereka/$file -o uhuereka/compiled/uhuereka/${file/.py/.mpy}
    done
    $cmd_prefix $mpremote_bin cp -r uhuereka/compiled/lib/. :lib
    $cmd_prefix $mpremote_bin cp -r uhuereka/compiled/uhuereka/. :uhuereka
  else
    $cmd_prefix $mpremote_bin cp -r uhuereka/src/lib/. :lib
    $cmd_prefix $mpremote_bin cp -r uhuereka/src/uhuereka/. :uhuereka
  fi
  $cmd_prefix $mpremote_bin cp -r uhuereka/src/uhuereka/static/. :uhuereka/static
fi
