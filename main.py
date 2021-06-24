import os
import logging
import subprocess
from configobj import ConfigObj


REQUIRED_ATTRS = {"keyboard": ["layout", "locale"], "time": ["timezone", "ntp"], "partitions": ["root", "boot", "swap"]}
PARSER = None


def check_config():
    global PARSER
    try:
        PARSER = ConfigObj('conf.ini', list_values=True, unrepr=True)
        attrs = REQUIRED_ATTRS.keys()
        for attr in attrs:
            if attr not in PARSER.sections:
                logging.warning("'%s' section is missing in conf.ini" % (attr))
                exit()
            else:
                tmp_section = PARSER[attr]
                for attr1 in REQUIRED_ATTRS[attr]:
                    if attr1 not in tmp_section:
                        logging.warning("'%s' of '%s' section is missing in conf.ini" % (attr1, attr))
                        exit()
        logging.info("'conf.ini' file check completed.")
    except Exception as e:
        logging.error(e)
        raise e


def quit(msg):
    logging.warning(msg)
    exit()


def run(cmd, bool_results=True):
    logging.info("Cmd: %s" % cmd)
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    logging.info(out, err)
    if err == b'':
        if bool_results:
            return True
        else:
            return out
    else:
        if bool_results:
            return False
        else:
            return err


def pre_pacstrap(): # Steps to follow before running pacstrap command
    # Setting up the keyboard
    # Check if the keyboard layout specified exists!
    layout = PARSER['keyboard']['layout']
    cmd = "ls /usr/share/kbd/keymaps/**/*.map.gz | grep %s" % layout
    if not run(cmd):
        quit("Keyboard layout specified doesn't exists! Choose a different one.")
    else:
        cmd = "loadkeys %s" % layout
        run(cmd)

    # Verifying the boot mode
    cmd = "ls /sys/firmware/efi/efivars"
    if run(cmd):
        logging.info("System has booted into UEFI mode.")
    else:
        logging.info("System has booted into MBR mode.")

    # Check internet connectivity
    cmd = "ping -c 1 google.com"
    if not run(cmd):
        quit("No internet access!")
    else:
        logging.info("Internet working fine.")

    # Setting up time
    timezone = PARSER['time']['timezone']
    ntp = PARSER['time']['ntp']
    cmd = "timedatectl set-timezone %s" % timezone
    run(cmd)
    cmd = "timedatectl set-ntp %s" % ntp
    run(cmd)

    # Setup partitions (UEFI only for now)
    root_fs = PARSER['partitions']['root']
    boot_fs = PARSER['partitions']['boot']
    swap_fs = PARSER['partitions']['swap']
    cmd = "mkswap %s" % swap_fs
    run(cmd)
    cmd = "swapon %s" % swap_fs
    run(cmd)
    cmd = "mkfs.ext4 %s" % root_fs
    run(cmd)
    cmd = "mount %s /mnt" % root_fs
    run(cmd)
    cmd = "mkdir /mnt/boot/EFI"
    run(cmd)
    cmd = "mount %s /mnt/boot/EFI" % boot_fs
    run(cmd)


def main():
    logging.info("Starting ArchLinux installer...")
    logging.info("This script uses 'conf.ini' to set preferences. Modify it before running this script!")
    check_config()
    pre_pacstrap()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
