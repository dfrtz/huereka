#! /bin/bash

# Install uHuereka source and dependencies.

set -e

script_root="$(dirname $(readlink -f "$0"))"
project_root="$(dirname ${script_root})"

device=""
rshell_bin="rshell"
mpremote_bin="mpremote"
install_src="false"
install_dependencies="false"
no_ssl="false"
dry_run="false"
cmd_prefix=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --device)
      if [ -z "$2" ]; then echo "Must provide a device port. Example: --device /dev/ttyACM0"; exit 1; fi
      device=$2
      shift
    ;;
    --src)
      install_src="true"
    ;;
    --deps)
      install_dependencies="true"
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

if [ -z "${device}" ]; then
  echo 'No device specified. Please provide a device to connect to with "--device".'
  echo 'For help finding devices, try "esptool.py chip_id" or "rshell boards" depending on the microcontroller.'
  exit 1
fi

if [ "${no_ssl}" == "true" ]; then
  echo "Disabling SSL verification during installation."
  mpremote_bin="${script_root}/mpremote_no_ssl.py"
fi

if [ "${dry_run}" == "true" ]; then
  echo "Dry running commands without executing."
  cmd_prefix="echo"
fi

if [ "${install_dependencies}" == "true" ]; then
  $cmd_prefix $mpremote_bin connect ${device} mip install logging
  $cmd_prefix $mpremote_bin connect ${device} mip install pathlib
  $cmd_prefix $mpremote_bin connect ${device} mip install time
  $cmd_prefix $mpremote_bin connect ${device} mip install github:miguelgrinberg/microdot/src/microdot.py
fi

if [ "${install_src}" == "true" ]; then
  $cmd_prefix $rshell_bin --port ${device} rsync ${script_root}/src/ /pyboard/

  # Cleanup any CPython files from the shared location before pushing in case project was run locally.
  $cmd_prefix rm -r ${project_root}/huereka/shared/__pycache__ || true
  # Rsync with folders only works to existing folders, must create tree manually first for nested sync.
  $cmd_prefix $rshell_bin --port ${device} mkdir /pyboard/huereka
  $cmd_prefix $rshell_bin --port ${device} mkdir /pyboard/huereka/shared
  $cmd_prefix $rshell_bin --port ${device} rsync ${project_root}/huereka/shared/ /pyboard/huereka/shared/
fi
