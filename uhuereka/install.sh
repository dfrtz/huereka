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
  mpremote_bin="echo ${mpremote_bin}"
  rshell_bin="echo ${rshell_bin}"
fi

if [ "${install_dependencies}" == "true" ]; then
  $mpremote_bin connect /dev/cu.usbmodem14201 mip install logging
  $mpremote_bin connect /dev/cu.usbmodem14201 mip install pathlib
  $mpremote_bin connect /dev/cu.usbmodem14201 mip install time
  $mpremote_bin connect /dev/cu.usbmodem14201 mip install github:miguelgrinberg/microdot/src/microdot.py
fi

if [ "${install_src}" == "true" ]; then
  $rshell_bin --port /dev/cu.usbmodem14201 rsync ${script_root}/src/ /pyboard/
  # Rsync with folders only works to existing folders, must create tree manually first for nested sync.
  $rshell_bin --port /dev/cu.usbmodem14201 mkdir /pyboard/huereka
  $rshell_bin --port /dev/cu.usbmodem14201 mkdir /pyboard/huereka/shared
  $rshell_bin --port /dev/cu.usbmodem14201 rsync ${project_root}/huereka/shared/ /pyboard/huereka/shared/
fi
