import os
import subprocess

config = {}


def run(cmd, show=False):
    try:
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if err.decode().strip(" ") == '' and out.decode().strip(" ") != '':
            if show:
                return out.decode()
            else:
                return True
        elif err.decode().strip(" ") == '' and out.decode().strip(" ") == '':
            if show:
                return out.decode()
            else:
                return True
        else:
            print("-"*20)
            print("CMD: " + cmd)
            print("**", out.decode().strip(" "), "**")
            print("++", err.decode().strip(" "), "++")
            print("-"*20)
            return False
    except Exception as e:
        print(e)


def quit(msg):
    print(msg)
    exit()


def info(msg):
    print("[+]", msg)


def load_config():
    global config
    with open('./.env') as f:
        lis = [x.strip("\n").split("=") for x in f.readlines()]
        for x, y in lis:
            if y == 'True':
                config[x] = True
            elif y == 'False':
                config[x] = False
            else:
                config[x] = y


def pre_pacstrap():  # steps to do before pacstrapping the os
    global config
    print(config)
    if config["UEFI_CHECK"]:
        if not os.path.exists("/sys/firmware/efi/efivars/"):
            quit("Not in UEFI mode!")
        else:
            info("UEFI mode found!")
    else:
        info("Skipping UEFI check.")

    res = run("ping 1.1.1.1 -c1 -w1", True)
    if res and "64 bytes from" in res:
        info("Internet is working")

    res = run("timedatectl set-ntp true")
    if not res:
        quit("Can't set the time/date to NTP.")
    else:
        info("Time/date set to NTP mode.")

    res = run("fdisk -l", True)
    root = config["DISK_ROOT"]

    if root in res:
        info("Root partition found!")
    else:
        quit("Invalid root partition")

    swap = config["DISK_SWAP"]
    if swap in res:
        info("Swap partition found!")
    else:
        quit("Invalid swap partition")

    boot = config["DISK_BOOT"]
    if boot in res:
        info("Boot partition found!")
    else:
        quit("Invalid boot partition")

    mount_boot = config['MOUNT_BOOT']
    run("umount %s" % mount_boot)
    mount_root = config['MOUNT_ROOT']
    run("umount %s" % mount_root)

    if config["DISK_FORMAT"]:
        info("Disk format enabled!")
        if run("mkfs.ext4 %s 2> /dev/null" % root):
            info("Root partition formatted as 'ext4'.")
        else:
            quit("Couldn't format Root partition as 'ext4'.")

        if run("mkswap %s 2> /dev/null" % swap):
            info("Swap partition formatted.")
        else:
            quit("Couldn't format Swap partition.")

        if run("mkfs.vfat -F32 %s" % boot):
            info("Boot partition formatted.")
        else:
            quit("Couldn't format Boot partition.")
    else:
        info("Skipping disk formatting!")

    if not os.path.exists(mount_root):
        os.makedirs(mount_root, exist_ok=True)
    if run("mount %s %s" % (root, mount_root)):
        info("Root partition(%s) mounted at '%s'." % (root, mount_root))
    else:
        quit("Couldn't mount Root partition.")

    if not os.path.exists(mount_boot):
        os.makedirs(mount_boot, exist_ok=True)
    if run("mount %s %s" % (boot, mount_boot)):
        info("Boot partition(%s) mounted at '%s'." % (boot, mount_boot))
    else:
        quit("Couldn't mount Boot partition.")

    if run("swapon %s 2> /dev/null" % swap):
        info("Swap partition mounted.")
    else:
        quit("Couldn't mount Swap partition.")


def pacstrap():
    global config
    mount_root = config['MOUNT_ROOT']
    info("Pacstrapping...")
    run("pacstrap %s %s" % (mount_root, config['PACSTRAP_PACKAGES']), True)
    info("Pacstrapping finished!")


def post_pacstrap():
    global config
    mount_root = config['MOUNT_ROOT']

    # Generating /etc/fstab file
    if run("genfstab -U %s >> %s/etc/fstab" % (mount_root, mount_root)):
        info("fstab file generated!")
    else:
        quit("Fstab file couldn't be generated!")

    # Generating bash file to execute post-chrooting
    timezone = config['TIMEZONE']
    locale = config['LOCALE']
    hostname = config['HOSTNAME']
    passwd = config['PASSWD']
    user_create = config['USER_CREATE']
    user_name = config['USER_NAME']
    user_passwd = config['USER_PASSWD']
    user_shell = config['USER_SHELL']
    user_system = config['USER_SYSTEM']
    extra_apps = config['EXTRA_APPS']

    user_cmd = ""
    if user_create:
        if user_shell != "/bin/bash":
            user_cmd = "pacman -Sy --noconfirm %s;" % user_shell.split("/")[2]
        user_cmd += "useradd -m -d /home/%s -s %s " % (user_name, user_shell)
        if user_system:
            user_cmd += "-r "
        user_cmd += user_name
        if user_passwd != "":
            user_cmd += "; echo -n '%s\n%s\n' | passwd %s" % (
                user_passwd, user_passwd, user_name)
        user_cmd += ";echo '[+] Extra user created!';"

    bash_file = '''#!/bin/bash
    ln -sf /usr/share/zoneinfo/%s /etc/localtime;
    echo "[+] Timezone set!";
    hwclock --systohc;
    echo "[+] System clock synced!";
    echo "[+] Generating locale..";
    sed -i 's/#%s/%s/g' /etc/locale.gen
    locale-gen
    echo 'LANG=%s' > /etc/locale.conf
    echo "[+] Locale generated!"
    echo '%s' > /etc/hostname
    echo "[+] Hostname set!"
    echo "127.0.0.1     localhost" > /etc/hosts
    echo "::1           localhost" >> /etc/hosts
    echo "[+] Hosts file updated!"
    mkinitcpio -P
    echo "[+] Executed mkinitcpio."
    echo -n "%s\n%s\n" | passwd
    echo "[+] Root passwd updated!"
    %s
    pacman -S grub os-prober efibootmgr --noconfirm
    grub-install --target=x86_64-efi --bootloader-id=grub_uefi --recheck
    grub-mkconfig -o /boot/grub/grub.cfg
    # Extra apps
    pacman -S --noconfirm networkmanager net-tools wpa_supplicant wireless_tools
    pacman -S --noconfirm xorg xorg-xinit ttf-dejavu %s
    exit
    ''' % (timezone, locale, locale, locale, hostname, passwd, passwd, user_cmd, extra_apps)
    with open('%s/mnt/bash_file.sh' % mount_root, 'w') as f:
        f.write(bash_file)

    # Arch-chrooting
    res = run("arch-chroot %s bash /mnt/bash_file.sh" % (mount_root), True)
    print(res)

    run("umount -a;reboot")


load_config()
pre_pacstrap()
pacstrap()
post_pacstrap()
