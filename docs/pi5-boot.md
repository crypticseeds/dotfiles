# Raspberry Pi 5 boot and nono

nono needs Landlock to enforce its Linux filesystem sandbox. The stock Raspberry Pi `2712` kernels checked on this host (`6.18.50` and `6.18.60`) have `CONFIG_SECURITY_LANDLOCK` unset. A boot parameter cannot add support that the kernel lacks. Canonical’s prebuilt Pi kernel `7.0.0-1023-raspi` includes Landlock and enables it by default. It successfully booted the existing Debian installation from the same SD card. A nono test read an allowed file and received `Permission denied` for a file outside the sandbox. [nono Landlock requirements](https://nono.sh/docs/cli/internals/landlock#enabling-landlock)

## Boot files

- `/boot/firmware/config.txt` selects `landlock-trial/kernel-landlock.img` for normal boots. `auto_initramfs=1` selects the matching `initramfs-landlock`.
- `/boot/firmware/tryboot.txt` includes `config.stock.txt` for a one-shot Trixie boot. The stock `kernel_2712.img` and `initramfs_2712` remain in `/boot/firmware`. The previous Ubuntu trial configuration is saved as `tryboot.ubuntu-trial.txt`.
- `/usr/lib/modules/7.0.0-1023-raspi/` contains the matching Ubuntu modules. The kernel and modules came from Ubuntu `linux-raspi` packages version `7.0.0-1023.23`, extracted manually. Debian APT updates the stock kernel. Ubuntu trial files and their security updates need separate maintenance. [Ubuntu kernel release](https://launchpad.net/ubuntu/+source/linux-raspi/7.0.0-1023.23)

## Test, keep, or roll back

With physical reset access, run `sudo reboot '0 tryboot'` for a one-shot Trixie fallback. A subsequent normal reboot uses `config.txt` and selects the Ubuntu kernel. If a boot fails, reset the Pi locally. [Raspberry Pi tryboot](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#fail-safe-os-updates-tryboot)

The installed normal-boot selection is:

```ini
[all]
os_prefix=landlock-trial/
kernel=kernel-landlock.img
cmdline=/cmdline.txt
```

To roll back a permanent change, restore `config.stock.txt` over `config.txt` and reboot. If the Pi cannot boot, restore the file on the SD card from another computer. This restores the stock boot path. Both kernels use the same live filesystem, so a kernel rollback does not roll back changes to app data.

The saved `config.stock.txt` and `tryboot.ubuntu-trial.txt` were verified against the original files after installation. The new normal and fallback configurations have not yet been tested by rebooting.

After any boot change, check the running kernel and nono startup:

```sh
uname -r
cat /sys/kernel/security/lsm
nono wrap --profile default --block-net -- /usr/bin/true
```

On the Ubuntu entry, expect `7.0.0-1023-raspi`, `landlock` in the LSM list, and a successful nono launch. Also check SSH and the services you rely on, including Docker, k3s, Tailscale, and Herdr Core.
