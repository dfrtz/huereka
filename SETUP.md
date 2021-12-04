# READ THIS NOTICE

This guide was written and tested on Raspberry Pi OS Lite (2021-10-30), however
the same steps (should) work in any Debian based environment with minimal to no modification. Other
Linux distros will require medium to heavy modification of the commands such as installing
dependencies. Your mileage may vary.

**CAUTION: Improper use of 'dd' can overwrite any partition on your system. Do not proceed with any
commands without absolute certainty they are targeting the correct partition.**


#### Table Of Contents

* [Download Raspberry Pi OS](#download-raspberry-pi-os-raspbian-image)
* [Installing OS](#installing-the-operating-system)
* [Prepare OS Headless Boot](#prepare-operating-system-for-headless-boot)
* [Prepare OS For User Access](#prepare-operating-system-for-user-access)
* [Build And Install Python](#build-and-install-python36)
* [Setup Python Dev Environment](#setup-python-development-environment)
* [Setup Huereka Dev Environment](#setup-huereka-development-environment)
* [Setup Huereka LED Test Hardware](#setup-huereka-led-test-hardware)


### Download Raspberry Pi OS (Raspbian) Image

Find and download an image from Raspbian Official:  
https://www.raspberrypi.org/downloads/


### Installing the Operating System

**CAUTION: Improper use of 'dd' can overwrite any partition on your system. Do not proceed with any
commands without absolute certainty they are targeting the correct partition.**

1. List the current devices and their mount points:
    ```
    lsblk
    ```

2. Insert the SD card into the SD card slot, or an external adapter.

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
    dd if=2021-10-30-raspios-bullseye-armhf-lite.img of=/dev/sdc conv=fsync status=progress
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

3. Mount the boot partition. This should be the smaller of the 2 partitions found in Step 2, usually `/dev/sdX1`:
    ```
    mount /dev/sdXx /mnt/rpi/boot
    ```

4. Add an 'ssh' file to the boot directory. This will enable SSH on first boot of the Raspberry Pi
to allow login and configuration. The file will be deleted after first boot.
    ```
    touch /mnt/rpi/boot/ssh
    ```

5. Unmount boot partition:
    ```
    umount /mnt/rpi/boot
    ```

6. Mount the system partition. This should be the larger of the two partitions found in step 2:
    ```
    mount /dev/sdXx /mnt/rpi/system
    ```

7. If using wired connection, skip this step and go to step 8. Edit the WPA supplicant file to add one
or more network(s).

    * Open the wpa_supplicant configuration file using a text editor. Examples:
    ```
    vi /etc/wpa_supplicant/wpa_supplicant.conf
    # OR:
    nano /etc/wpa_supplicant/wpa_supplicant.conf
    ```

    * Add everything after <Begin> and before <End> tags, replacing wpa-ssid and wpa-psk as
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

    * Save file and exit text editor. Examples:
    ```
    If using vi: ESC > Shift + : > wq > Enter
    If using nano: `CTRL + X > Enter
    ```

8. Unmount system partition:
     ```
     umount /mnt/rpi/system
     ```

9. Ensure device is completely unmounted, and remove from SD card slot or external adapter:
   ```
   lsblk
   ```


### Prepare Operating System for User Access

1. Install SD card into Raspberry Pi.

2. Power on device.

3. If using DHCP, you will need to find the IP address of the Raspberry Pi. Examples:
    ```
    arp -a
    ping -c1 raspberrypi
    ```

4. SSH into the Raspberry Pi as user 'pi' and password 'raspberry' via hostname or IP:
    ```
    ssh pi@raspberrypi
    # OR:
    ssh pi@<IP address>
    ```

5. Change 'pi' passwd to remove popup about default password on future logins:
    ```
    passwd
    ```

6. Enter configuration tool and update hostname of device on network and enable SSH:
    ```
    sudo raspi-config
    ```
    * Navigation Breadcrumbs:  
    ```
    Main Menu > System Options > Hostname
    Main Menu > Interface Options > SSH
    ```

7. Exit configuration tool by selecting "Finish". Do not reboot yet.

8. Create a new administrator user:
    ```
    sudo adduser <username>
    ```

9. Add the new user to sudo group:
   ```
   sudo usermod -aG sudo <username>
   ```

10. Logout of Raspberry Pi, and reconnect as new user:
    ```
    exit
    ssh <username>@<IP address>
    ```

11. Delete 'pi' user:
    ```
    sudo deluser pi
    ```

12. Change 'root' password to further secure system:
    ```
    sudo passwd root
    ```

13. Update packages:  
    ```
    sudo apt update
    sudo apt upgrade
    ```

14. Reboot:
    ```
    sudo reboot
    ```

15. After it reboots, setup your local SSH key on the new user to simplify future logins:
    ```
    ssh-copy-id -i ~/.ssh/id_rsa.pub <username>@<ip>
    ```


### Build and Install Python3.9

As of Raspberry Pi OS Bullseye this step is no longer required, however it is left here for posterity or wishing
to build a version newer than 3.9.2 (latest as of 2021-10-30 Raspberry Pi OS Lite).

1. Install dependencies to build python from source. This builds a fairly minimal python. If you wish to expand
  the code further, python may need to be rebuilt later after more packages are installed:  
    ```
    sudo apt install \
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


### Setup Python Development Environment

1. Install 'pip' Python Package Manager and Development Library:
    ```
    sudo apt install python3-pip python3-dev
    ```

2. Install virtual environment:
    ```
    sudo pip3 install virtualenv virtualenvwrapper
    ```

3. Update user profile with virtual environment wrapper for additional commands and to show
currently active workspace:
    ```
    echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> ~/.profile
    echo "export WORKON_HOME=$HOME/.virtualenvs" >> ~/.profile
    echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.profile
    ```


### Setup Huereka Development Environment

1. Setup OS requirements:
    ```
    sudo apt install git vim libgpiod2
    ```

2. Create development folder:
    ```
    mkdir -v ~/Development
    ```

3. Clone repo and update location:
    ```
    cd ~/Development
    git clone <remote repo location>
    ```

4. Setup the hooks:
   ```
   hooks/setup_hooks.sh
   ```

5. Make virtual environment to isolate packages:
    ```
    mkvirtualenv huereka -p $(which python3.9)
    echo "export PYTHONPATH=~/Development/huereka" >> ~/.virtualenvs/huereka/bin/activate

    # If the venv does not automatically activate (and used on future logins):
    workon huereka
    ```

6. Install python project:
    ```
    cd huereka
    export CFLAGS=-fcommon  # Needs to be set before calling pip install or it will fail on RPi.GPIO
    pip install -r requirements-dev.txt
    pip install -r requirements.txt
    unset CFLAGS
    ```

7. Generate HTTPS certificate:
    ```
    openssl req -newkey rsa:4096 -nodes -keyout huereka.key -x509 -days 365 -out huereka.crt
    ```

8. Setup libgpiod per adafruit instructions:
    ```
    cd ~
    wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/libgpiod.sh
    chmod +x libgpiod.sh
    ./libgpiod.sh
    rm ./libgpiod.sh
    ```


### Setup Huereka Testing Hardware

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

2. Setup the circuit. This is not a tutorial on jumpers or breadboards, refer to public guides if more detailed
steps on setting up circuits is needed. Basic overview:
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
