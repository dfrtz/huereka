# READ THIS NOTICE

**CAUTION: Improper grounding, voltage, and other interactions with electricity, can cause personal injury or
damage to your surroundings. By using this guide you agree to take proper precautions and assume full responsibility.**

**CAUTION: Improper use of 'dd' can overwrite any partition on your system. Do not proceed with any
commands without absolute certainty they are targeting the correct partition.**

This guide was written and tested on Raspberry Pi OS Lite (2022-09-22), however
the same steps (should) work in any Debian based environment with minimal modification. Other
Linux distros will require medium to heavy modification of the commands such as installing
dependencies. Your mileage may vary.


#### Table Of Contents

* [Download Raspberry Pi OS](#download-raspberry-pi-os-raspbian-image)
* [Installing OS](#installing-the-operating-system)
* [Prepare OS Headless Boot](#prepare-operating-system-for-headless-boot)
* [Prepare OS For User Access](#prepare-operating-system-for-user-access)
* [Build And Install Python](#build-and-install-python39)
* [Set up Python Dev Environment](#set-up-python-development-environment)
* [Set up Huereka Dev Environment](#set-up-huereka-development-environment)
* [Set up Huereka LED Test Hardware](#set-up-huereka-testing-hardware)
* [Set up Serial Hardware Alias](#set-up-serial-hardware-alias)
* [Set up Huereka Service to Start on Boot](#set-up-huereka-service-to-start-on-boot)
* [Improve Raspberry Pi Boot Time](#improve-raspberry-pi-boot-time)


### Download Raspberry Pi OS (Raspbian) Image

Find and download an image from Raspbian Official:  
https://www.raspberrypi.org/downloads/


### Installing the Operating System

**CAUTION: Improper use of 'dd' can overwrite any partition on your system. Do not proceed with any
commands without absolute certainty they are targeting the correct partition.**

In order to install the Raspberry Pi OS you will need a separate computer from the Raspberry Pi itself.
The following procedure outlines installing the image from a Linux based OS.

1. List the current devices and their mount points:
    ```
    lsblk
    ```

2. Insert the SD card into an SD card slot, or an external adapter.

3. Check for the new device and location (/dev/sdX):
    ```
    lsblk
    ```

4. If the device was mounted automatically, unmount it from the system:
    ```
    umount /dev/sdX
    ```

5. Copy the image to the SD card using 'dd':
    ```
    dd if=2022-09-22-raspios-bullseye-armhf-lite.img of=/dev/sdX conv=fsync status=progress
    ```


### Prepare Operating System for Headless Boot

1. Make two new directories to mount the SD card boot and system partitions:
    ```
    mkdir -vp /mnt/rpi/boot /mnt/rpi/system
    ```

2. List the devices to find the boot and system partitions on the SD card. The SD card device should
be split into two parts after installing the OS, similar to `/dev/sdb1` and `/dev/sdb2`.
    ```
    lsblk
    ```

3. Mount the boot partition. This should be the smallest of the 2 partitions found in Step 2, usually `/dev/sdX1`:
    ```
    mount /dev/sdXx /mnt/rpi/boot
    ```

4. Add an 'ssh' file to the boot directory. This will enable SSH on first boot of the Raspberry Pi
to allow login and configuration. The file will be deleted after first boot.
    ```
    touch /mnt/rpi/boot/ssh
    ```

5. Add a 'userconf' file to the boot partition. This will set up the initial user and prevent displaying the
prompt on first boot that would otherwise block a headless setup. This is required on Bullseye+.

    * To generate an encrypted password:
        ```
        echo 'mypassword' | openssl passwd -6 -stdin
        ```
    * Open the `/mnt/rpi/boot/userconf` configuration file using a text editor.
    * The file must contain 1 line with `<username>:<encryptd password>`.
    * Save file and exit text editor.

6. If using a wired connection, skip this step. Edit the WPA supplicant file to add one or more network(s).

    * Open the `/mnt/rpi/boot/wpa_supplicant.conf` configuration file using a text editor.
    * Add everything after <Begin> and before <End> tags, replacing county, wpa-ssid, and wpa-psk as
    appropriate for your network:
    ```
    ### Begin ###
    country=US
    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    update_config=1

    # For a standard network:
    network={
      ssid="My network name"
      psk="My network password"
      scan_ssid=1
    }

    # For a RADIUS network:
    network={
      ssid="My network name"
      key_mgmt=WPA-EAP
      eap=PEAP
      identity="My User Name"
      password="My network password"
      id_str="My network name"
    }
    ### End ###
    ```
    * Save file and exit text editor.

7. Unmount boot partition:
    ```
    umount /mnt/rpi/boot
    ```

8. Recommended: Change the default hostname. If not changing the name, skip this step.

   * Mount system partition: `mount /dev/sdXx /mnt/rpi/system`
   * Change the name in: `/mnt/rpi/system/etc/hostname`
   * Change the name in: `/mnt/rpi/system/etc/hosts`
   * Add the name to the `127.0.0.1` and `::1` lines in: `/mnt/rpi/system/etc/hosts`
   * Unmount system partition: `umount /mnt/rpi/system`

9. Recommended: Consider additional changes from [Improve Raspberry Pi Boot Time](#improve-raspberry-pi-boot-time).
These can also be performed at a later time.

10. Ensure device is completely unmounted, and remove from SD card slot or external adapter:
     ```
     lsblk
     ```


### Prepare Operating System for User Access

1. Install SD card into Raspberry Pi.

2. Power on device.

3. If using DHCP, you will need to find the IP address of the Raspberry Pi. Examples:
    ```
    arp -a
    ping -c1 raspberrypi # Or hostname specified during setup.
    ```

4. SSH into the Raspberry Pi as the user/password set in the OS preparation phase via hostname or IP:
    ```
    ssh <myuser>@raspberrypi # Or hostname specified during setup.
    # OR:
    ssh <myuser>@<IP address>
    ```

5. Enter configuration tool and update hostname of device on network (if not performed with OS set up) and ensure SSH is
enabled:
    ```
    sudo raspi-config
    ```
    * Navigation Breadcrumbs:  
    ```
    Main Menu > System Options > Hostname
    Main Menu > Interface Options > SSH
    ```

6. Exit configuration tool by selecting "Finish". Do not reboot yet.

7. If using OS earlier that Bullseye, change 'root' password to further secure system:
    ```
    sudo passwd root
    ```

8. Update packages:
    ```
    sudo apt update
    sudo apt upgrade
    ```

9. Reboot:
    ```
    sudo reboot
    ```

10. After it reboots, set up your local SSH key on the new user to simplify future logins:
    ```
    ssh-copy-id -i ~/.ssh/id_rsa.pub <username>@<ip>
    ```


### Build and Install Python3.9

As of Raspberry Pi OS Bullseye this step is no longer required, however it is left here for posterity or for this
wishing to build a version newer than 3.9.2 (latest as of 2021-10-30 Raspberry Pi OS Lite).

1. Install dependencies to build python from source. This builds a fairly minimal python. If you wish to expand
the code further, python may need to be rebuilt later after more packages are installed:  
    ```
    sudo apt install -y \
        build-essential \
        tk-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libffi-dev \
        libreadline6-dev \
        libdb5.3-dev \
        libgdbm-dev \
        libsqlite3-dev \
        libssl-dev \
        libbz2-dev
    sudo ldconfig
    ```

2. Create directory for source code to compile:
    ```
    mkdir ~/python
    cd ~/python
    ```

3. Pull down the tarball and extract the source:
    ```
    wget https://www.python.org/ftp/python/3.9.9/Python-3.9.9.tar.xz
    tar -xf Python-3.9.9.tar.xz
    ```

4. Configure the source and build:
    ```
    cd Python-3.9.9/
    ./configure
    make -j4
    ```

5. Install:
    ```
    sudo make altinstall
    ```

6. Cleanup source:
    ```
    cd ..
    rm -r Python-3.9.9/
    rm Python-3.9.9.tar.xz
    ```


### Set Up Python Development Environment

1. Install Python package manager, development, and virtual environment libraries:
    ```
    sudo apt update && sudo apt install -y python3-dev python3-pip python3-venv
    ```


### Set Up Huereka Development Environment

1. Set up OS requirements:
    ```shell
    sudo apt install -y git vim libgpiod2
    ```

2. Create development folder:
    ```shell
    mkdir -v ~/Development
    ```

3. Clone repo and update location:
    ```shell
    cd ~/Development
    git clone <remote repo location>
    cd huereka
    ```

4. Set up hooks:
    ```shell
    make setup
    ```

5. Make virtual environment to isolate packages:
    ```shell
    make venv
    source .venv/bin/activate
    ```

6. Install python project:
    ```shell
    export CFLAGS=-fcommon  # Needs to be set before calling pip install or it will fail on RPi.GPIO
    pip install -r requirements-dev.txt
    pip install -r requirements.txt
    unset CFLAGS
    ```

7. Generate HTTPS certificate:
    ```shell
    openssl req -newkey rsa:4096 -nodes -keyout huereka.key -x509 -days 365 -out huereka.crt
    ```


### Set Up Huereka Testing Hardware

**CAUTION: Improper grounding, voltage, and other interactions with electricity, can cause personal injury or
damage to your surroundings. By using this guide you agree to take proper precautions and assume full responsibility.**

After setting up the OS and software it is recommended to perform a basic test using a standalone LED.
This is optional, but can help provide assurance that the setup is ready to continue into production.

**Requirements**

- 1x LED (Any basic 2 prong LED, max 5V)
- Jumper wires
  - Without breadboard: 3x female to female
  - If using breadboard: 4x male to female
- 1x 330 Ohm resistor
- Breadboard (Optional)

1. Print the pinout of the GPIO pins for reference:
   ```
   pinout
   ```

2. Set up the circuit. This is not a tutorial on jumpers or breadboards, refer to public guides if more detailed
steps on setting up circuits are needed. Basic overview:
   1. If not using breadboard:
      1. Connect GND (pin 14) from Pi to LED.
      2. Connect GPIO18 (pin 12) power line from Pi to 330 resistor.
      3. Connect 330 resistor to LED.
   2. If using breadboard:
      1. Connect GND (pin 14) from Pi to breadboard.
      2. Connect breadboard GND to LED.
      3. Connect GPIO18 (pin 12) power line from Pi to breadboard.
      4. Connect power line from breadboard to 330 resister.
      5. Connect 330 resistor to LED.

3. Run the tester. Expected behavior is to blink for 1 second intervals. If not working, verify hardware setup.
   ```
   huereka/utils/gpio_tester.py
   ```


### Set Up Serial Hardware Alias

If using a serial device to control lighting, such as connecting an Arduino to a Raspberry Pi, it is worth
configuring static device aliases to bypass possible tty changes. For example, rapid connect/disconnect of
serial devices from a Raspberry Pi may result in `/dev/ttyACM0` becoming `/dev/ttyACM1`. This can cause
LED managers to fail due to device no longer existing. The following steps outline how to set up a
static `/dev/arduino` alias on a Raspberry Pi, however they can be used for any device.

1. Grab the `idVendor`, `idProduct`, and `serial` for a connected serial device. Example commands:
   ```bash
   # Use udevadm to list device connected via USB serial to default ACM:
   udevadm info -a -n /dev/ttyACM0 |grep -E "idVendor|idProduct|{serial}" |head -3

   # Or check recently connected device logs:
   less /var/log/messages
   ```

2. Add a new `/etc/udev/rules.d/99-usb-serial.rules` file with the following contents, filling in the placeholders.
   ```
   # Template:
   SUBSYSTEM=="tty", ATTRS{idVendor}=="<your device idVendor>", ATTRS{idProduct}=="<your device idProduct>", ATTRS{serial}=="<your device serial>", SYMLINK+="<your alias>"

   # Example:
   SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0058", ATTRS{serial}=="045B78B2515146", SYMLINK+="arduino"
   ```

3. Reconnect device, or reboot system, for alias to take effect.


### Set Up Huereka Service to Start on Boot

1. Ensure Huereka development environment is set up, or library is installed on to core system.

2. Create a basic bash script which can be called by the service, such as `~/Development/huereka/huereka.sh`:
    ```bash
    #!/bin/bash
    cd /home/huereka/Development/huereka
    source .venv/bin/activate
    PYTHONPATH=. ./huereka/server.py \
        -k ./huereka.key \
        -c ./huereka.crt
    ```

3. Add extra arguments if needed.

4. Make the script executable:
    ```
    chmod 755 ~/Development/huereka/huereka.sh
    ```

5. Create a new service file under `/etc/systemd/system/huereka.service`:
    ```
    [Unit]
    Description=GPIO LED manager software

    [Service]
    ExecStart=/home/huereka/huereka.sh

    [Install]
    WantedBy=multi-user.target
    ```

6. Test the new service:
    ```
    sudo systemctl start huereka.service
    ```

7. Check the status and logs for the service:
    ```
    sudo service huereka status
    sudo journalctl -u huereka.service
    ```

8. If the service is working as expected, enable it permanently to start on boot:
    ```
    sudo systemctl enable huereka.service
    ```


### Improve Raspberry Pi Boot Time

**CAUTION: Before applying any optimizations, understand the risks. These may lead to an un-bootable system
if applied improperly. Not all settings are appropriate for all use cases either.**

Huereka is not restricted to running only on Raspberry Pi, however this is a common hardware type to use due to
availability and hardware features. To help with this common use case, a few tips have been collected to help.
The following are common for standalone servers dedicated to single tasks, such as running Huereka.

- Modify `/boot/config.txt` (each value on new line):
  - Disable splash screen: `disable_splash=1`
  - Disable bluetooth: `dtoverlay=disable-bt`
  - Disable initial boot delay: `boot_delay=0`

- Modify `/boot/cmdline.txt` (each value in place, do not add newlines):
  - To disable splash screen, remove: `splash`
  - To disable logging output to screen, add: `quiet`
  - To disable loading and displaying logo, add: `logo.nologo`

- Disable network wait at boot (Equivalent to "Wait for Network at Boot" from raspi-config):
  - `rm /etc/systemd/system/dhcpcd.service.d/wait.conf`

- Disable unneeded services before first boot:
  - `rm /etc/systemd/system/sysinit.target.wants/keyboard-setup.service`
  - `rm /etc/systemd/system/dbus-org.freedesktop.ModemManager1.service`
  - `rm /etc/systemd/system/multi-user.target.wants/ModemManager.service`

- Disable unnecessary services after first boot:
  - Disable initial config service: `systemctl disable raspi-config.service`
  - Disable physical swap services for low memory services: `systemctl disable dphys-swapfile.service`
  - Disable device auto discovery on network: `systemctl disable avahi-daemon.service`

- Analyze and disable possibly other unused services:
  - To show overall boot time: `systemd-analyze`
  - To show individual service boot time: `systemd-analyze blame`
  - To disable a service (use with caution): `systemctl disable <service>`
