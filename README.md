# virtual-machines

QEMU virtual machine manager for Apple Silicon Macs, using aarch64 architecture and
HVF acceleration.

## Requirements

- macOS on Apple Silicon
- [Homebrew](https://brew.sh/)
- QEMU: `brew install qemu`
- [uv](https://docs.astral.sh/uv/): `brew install uv`

QEMU must provide the `edk2-aarch64-code.fd` firmware. By default, `vmctl.py` looks for
it at `/opt/homebrew/share/qemu/edk2-aarch64-code.fd`. Override this location with the
`VMCTL_EFI_SOURCE` environment variable.

The Python dependencies (`typer`, `rich`, and `pyyaml`) are resolved automatically by
`uv run`.

## Structure

```text
vmctl.py                  # Main CLI
.vmctl/config.yml         # QEMU configuration templates
isos/                     # Installation ISOs (not versioned)
vms/<name>/
  config.yaml             # VM configuration
  disk.qcow2              # Virtual disk (not versioned)
  firmware.fd             # EFI NVRAM (not versioned)
examples/                 # Legacy reference scripts
```

## Usage

```bash
./vmctl.py --help
./vmctl.py --version
./vmctl.py create <name>
./vmctl.py run [<name>]
```

You can also run the CLI with `uv run vmctl.py`. Do not use `python3 vmctl.py` unless
the dependencies are already installed in the active environment.

### Create a VM

Place an installation ISO in `isos/`, then run:

```bash
./vmctl.py create debian
```

The command prompts for the ISO, RAM, CPU cores, disk size, network, display, audio,
and serial number. These options can also be provided on the command line:

```bash
./vmctl.py create debian \
  --iso debian-13.3.0-arm64-netinst.iso \
  --ram 4G --cores 4 --disk-size 20G \
  --network nat --display default
```

### Run a VM

```bash
./vmctl.py run debian
```

Without a name, `run` displays an interactive VM selection. If `installed: false` is
set in `vms/<name>/config.yaml`, the VM boots from the ISO. After you confirm that the
installation is complete, `vmctl.py` automatically changes the value to `true` for
future boots.

## Networking

Network types are defined in `.vmctl/config.yml`, and each VM selects one in its
configuration:

```yaml
network:
  type: nat
```

### NAT

The `nat` mode provides Internet access through QEMU's `user` network and forwards host
port `2222` to the VM's SSH port:

```bash
ssh -p 2222 user@localhost
```

Change the forwarded port by editing the `hostfwd` value in `.vmctl/config.yml`.

### Bridge

The `bridge` mode connects the VM to a physical network interface and gives it an IP on
the local network:

```bash
ssh user@<VM_IP>
```

The default interface is `en0`. List available interfaces with:

```bash
networksetup -listallhardwareports
```

If necessary, change `ifname` in `.vmctl/config.yml`. Bridge mode does not use
`hostfwd`.

## Shared folders

Add, list, or remove shared folders using virtio-9p:

```bash
./vmctl.py share add /path/on/host hostshare --vm debian
./vmctl.py share list --vm debian
./vmctl.py share remove hostshare --vm debian
```

Inside the VM, mount a configured folder with:

```bash
sudo mkdir -p /mnt/hostshare
sudo mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/hostshare
```

## Reference scripts

The scripts in `examples/` belong to the previous workflow and are kept for reference
only. New VM workflows should use `vmctl.py`.
