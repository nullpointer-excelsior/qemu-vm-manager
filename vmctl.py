#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12.0",
#   "rich>=13.7.0",
#   "pyyaml>=6.0",
# ]
# ///
"""vmctl — QEMU Virtual Machine Manager."""
from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

# ── Constants ──────────────────────────────────────────────────────────────────

VERSION = "0.1.0"

EFI_CODE_PATH = Path(
    os.environ.get("VMCTL_EFI_SOURCE", "/opt/homebrew/share/qemu/edk2-aarch64-code.fd")
)

DEFAULT_RAM = "2G"
DEFAULT_CORES = 4
DEFAULT_DISK_SIZE = "20G"
DEFAULT_SSH_PORT = 2222
DEFAULT_DISPLAY = "default"
DEFAULT_NETWORK = "vmnet-shared"

FIRMWARE_SIZE = 64 * 1024 * 1024  # 64 MiB


def _detect_accelerator() -> str:
    accelerators = {
        "Darwin": "hvf",
        "Linux": "kvm",
        "Windows": "whpx",
    }
    try:
        return accelerators[platform.system()]
    except KeyError:
        raise RuntimeError(f"Unsupported host operating system: {platform.system()}")


def _detect_architecture() -> str:
    architectures = {
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "x86_64": "x86_64",
        "AMD64": "x86_64",
    }
    try:
        return architectures[platform.machine()]
    except KeyError:
        raise RuntimeError(f"Unsupported host architecture: {platform.machine()}")

# ── Console ────────────────────────────────────────────────────────────────────

console = Console()
err_console = Console(stderr=True)

# ── Config dataclasses ────────────────────────────────────────────────────────


@dataclass
class NetworkConfig:
    type: str = DEFAULT_NETWORK
    ssh_port: int = DEFAULT_SSH_PORT


@dataclass
class AudioConfig:
    enabled: bool = True
    backend: str = "coreaudio"


@dataclass
class SharedFolder:
    host_path: str
    mount_tag: str


@dataclass
class VMConfig:
    name: str
    ram: str = DEFAULT_RAM
    cores: int = DEFAULT_CORES
    disk_size: str = DEFAULT_DISK_SIZE
    disk: str = ""
    iso: str = ""
    installed: bool = False
    display: str = DEFAULT_DISPLAY
    serial: str = ""
    network: NetworkConfig = field(default_factory=NetworkConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    shared_folders: list[SharedFolder] = field(default_factory=list)


# ── Config serialization ──────────────────────────────────────────────────────


def _to_dict(cfg: VMConfig) -> dict:
    return {
        "name": cfg.name,
        "ram": cfg.ram,
        "cores": cfg.cores,
        "disk_size": cfg.disk_size,
        "disk": cfg.disk,
        "iso": cfg.iso,
        "installed": cfg.installed,
        "display": cfg.display,
        "serial": cfg.serial,
        "network": {"type": cfg.network.type, "ssh_port": cfg.network.ssh_port},
        "audio": {"enabled": cfg.audio.enabled, "backend": cfg.audio.backend},
        "shared_folders": [
            {"host_path": sf.host_path, "mount_tag": sf.mount_tag} for sf in cfg.shared_folders
        ],
    }


def _from_dict(data: dict) -> VMConfig:
    net = data.get("network", {})
    audio = data.get("audio", {})
    return VMConfig(
        name=data["name"],
        ram=data.get("ram", DEFAULT_RAM),
        cores=int(data.get("cores", DEFAULT_CORES)),
        disk_size=data.get("disk_size", DEFAULT_DISK_SIZE),
        disk=data.get("disk", ""),
        iso=data.get("iso", ""),
        installed=bool(data.get("installed", False)),
        display=data.get("display", DEFAULT_DISPLAY),
        serial=data.get("serial", ""),
        network=NetworkConfig(
            type=net.get("type", DEFAULT_NETWORK),
            ssh_port=int(net.get("ssh_port", DEFAULT_SSH_PORT)),
        ),
        audio=AudioConfig(
            enabled=bool(audio.get("enabled", True)),
            backend=audio.get("backend", "coreaudio"),
        ),
        shared_folders=[
            SharedFolder(host_path=sf["host_path"], mount_tag=sf["mount_tag"])
            for sf in data.get("shared_folders", [])
        ],
    )


def _load_config(vm_dir: Path) -> VMConfig:
    config_path = vm_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(str(config_path))
    with config_path.open() as fh:
        return _from_dict(yaml.safe_load(fh))


def _save_config(cfg: VMConfig, vm_dir: Path) -> None:
    vm_dir.mkdir(parents=True, exist_ok=True)
    with (vm_dir / "config.yaml").open("w") as fh:
        yaml.dump(_to_dict(cfg), fh, default_flow_style=False, sort_keys=False)


# ── TUI helpers ───────────────────────────────────────────────────────────────


def _select_from_list(label: str, options: list[str]) -> str:
    console.print(f"\n[bold]{label}[/bold]")
    for i, opt in enumerate(options, start=1):
        console.print(f"  [cyan]{i}[/cyan]. {opt}")
    while True:
        raw = Prompt.ask("Select number", console=console)
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        console.print("[red]Invalid choice. Enter a number from the list.[/red]")


def _detect_host_serial() -> Optional[str]:
    """Read the host Mac's hardware serial number via ioreg."""
    try:
        result = subprocess.run(
            ["ioreg", "-l"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in result.stdout.splitlines():
        if "IOPlatformSerialNumber" in line:
            return line.split("=", 1)[1].strip().strip('"')
    return None


def _print_summary(cfg: VMConfig) -> None:
    table = Table(title=f"VM: {cfg.name}", show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Name", cfg.name)
    table.add_row("RAM", cfg.ram)
    table.add_row("Cores", str(cfg.cores))
    table.add_row("Disk Size", cfg.disk_size)
    table.add_row("Disk", cfg.disk)
    table.add_row("ISO", cfg.iso or "(none)")
    table.add_row("Installed", str(cfg.installed))
    table.add_row("Display", cfg.display)
    table.add_row("Serial", cfg.serial or "(none)")
    table.add_row("SSH Port", f"{cfg.network.ssh_port} → guest:22")
    table.add_row("Audio", f"{'enabled' if cfg.audio.enabled else 'disabled'} ({cfg.audio.backend})")
    if cfg.shared_folders:
        table.add_row(
            "Shared Folders",
            "\n".join(f"{sf.host_path} → tag:{sf.mount_tag}" for sf in cfg.shared_folders),
        )
    console.print(table)


def _error(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")


# ── QEMU command builder ──────────────────────────────────────────────────────


def _build_qemu_cmd(cfg: VMConfig, project_root: Path, architecture: str, accelerator: str, *, install_mode: bool) -> list[str]:
    vm_dir = project_root / "vms" / cfg.name
    display_args = ["-display", "none"] if cfg.display == "none" else ["-display", f"{cfg.display},show-cursor=on"]
    audio_args = (
        ["-audiodev", f"{cfg.audio.backend},id=audio0", "-device", "intel-hda", "-device", "hda-output,audiodev=audio0"]
        if cfg.audio.enabled
        else []
    )

    cmd = [
        f"qemu-system-{architecture}",
        "-m", cfg.ram,
        "-cpu", "host",
        "-smp", str(cfg.cores),
        "-accel", accelerator,
        "-M", "virt,highmem=on",
        "-drive", f"if=pflash,format=raw,readonly=on,file={EFI_CODE_PATH}",
        "-drive", f"if=pflash,format=raw,file={vm_dir / 'firmware.fd'}",
        "-drive", f"file={project_root / cfg.disk},if=virtio",
    ]

    if cfg.serial:
        cmd += ["-smbios", f"type=1,serial={cfg.serial}"]

    for sf in cfg.shared_folders:
        cmd += [
            "-fsdev", f"local,id=fsdev-{sf.mount_tag},path={sf.host_path},security_model=mapped-xattr",
            "-device", f"virtio-9p-pci,fsdev=fsdev-{sf.mount_tag},mount_tag={sf.mount_tag}",
        ]

    if install_mode:
        cmd += [
            "-drive", f"file={project_root / cfg.iso},id=cdrom,if=none,media=cdrom,readonly=on",
            "-device", "virtio-scsi-pci",
            "-device", "scsi-cd,drive=cdrom",
        ]
    else:
        cmd += ["-device", "virtio-scsi-pci"]

    if cfg.network.type == "user":
        network_args = [
            "-netdev",
            f"user,id=net0,hostfwd=tcp:127.0.0.1:{cfg.network.ssh_port}-:22",
        ]
    elif cfg.network.type == "vmnet-shared":
        network_args = ["-netdev", "vmnet-shared,id=net0"]
    else:
        _error(f"Unsupported network type: {cfg.network.type}. Use 'user' or 'vmnet-shared'.")
        raise typer.Exit(1)

    cmd += [
        "-device", "virtio-gpu-pci",
        "-device", "ramfb",
        *display_args,
        "-device", "qemu-xhci,id=usb",
        "-device", "usb-kbd",
        "-device", "usb-tablet",
        "-device", "virtio-net-pci,netdev=net0",
        *network_args,
        *audio_args,
    ]
    return cmd


# ── Shared boot logic ─────────────────────────────────────────────────────────


def _boot(cfg: VMConfig, project_root: Path) -> None:
    try:
        architecture = _detect_architecture()
        accelerator = _detect_accelerator()
    except RuntimeError as exc:
        _error(str(exc))
        raise typer.Exit(1)
    _print_summary(cfg)
    install_mode = not cfg.installed

    if install_mode:
        if not cfg.iso:
            _error(
                f"VM '{cfg.name}' has installed=false but no ISO configured. "
                "Set iso in config.yaml or recreate the VM."
            )
            raise typer.Exit(1)
        iso_path = project_root / cfg.iso
        if not iso_path.exists():
            _error(f"ISO not found: {iso_path}. Add it to isos/ or update vms/{cfg.name}/config.yaml.")
            raise typer.Exit(1)
        console.print(f"\n[bold yellow]Install mode[/bold yellow] — booting from ISO: {cfg.iso}")
    else:
        console.print("\n[bold green]Run mode[/bold green] — booting installed system")

    cmd = _build_qemu_cmd(cfg, project_root, architecture, accelerator, install_mode=install_mode)
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]\n")
    subprocess.run(cmd)

    if install_mode:
        vm_dir = project_root / "vms" / cfg.name
        if Confirm.ask("Did the installation finish?", default=False, console=console):
            cfg.installed = True
            _save_config(cfg, vm_dir)
            console.print("[green]✓[/green] Marked as installed. Next run will boot the installed system.")


# ── Typer app ─────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="vmctl",
    help="QEMU Virtual Machine Manager for Apple Silicon Macs.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"vmctl {VERSION}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    pass


# ── create ────────────────────────────────────────────────────────────────────


@app.command("create")
def cmd_create(
    name: str = typer.Argument(..., help="Name for the new VM"),
    iso: Optional[str] = typer.Option(None, "--iso", help="ISO filename in isos/"),
    ram: Optional[str] = typer.Option(None, "--ram", help="RAM amount (e.g. 2G)"),
    cores: Optional[int] = typer.Option(None, "--cores", help="Number of CPU cores"),
    disk_size: Optional[str] = typer.Option(None, "--disk-size", help="Disk size (e.g. 20G)"),
    network: Optional[str] = typer.Option(None, "--network", help="Network: vmnet-shared | user"),
    ssh_port: Optional[int] = typer.Option(None, "--ssh-port", help="Host port forwarded to guest SSH (22)"),
    display: Optional[str] = typer.Option(None, "--display", help="Display backend: default | none"),
    serial: Optional[str] = typer.Option(None, "--serial", help="SMBIOS serial number (use 'host' to match this Mac's serial)"),
) -> None:
    """Create a new VM: config, disk image, and EFI NVRAM."""
    project_root = Path.cwd()
    vm_dir = project_root / "vms" / name

    if vm_dir.exists():
        _error(f"vms/{name}/ already exists. Use a different name or delete the existing directory first.")
        raise typer.Exit(1)

    isos_dir = project_root / "isos"
    available_isos = (
        sorted(p.name for p in isos_dir.iterdir() if p.is_file() and p.suffix.lower() == ".iso")
        if isos_dir.exists()
        else []
    )
    if not available_isos:
        _error("No ISO files found in isos/. Add an installer ISO to isos/ before creating a VM.")
        raise typer.Exit(1)

    if iso is not None and iso not in available_isos:
        _error(f"'{iso}' not found in isos/. Available: {', '.join(available_isos)}")
        raise typer.Exit(1)

    if iso is None:
        iso = _select_from_list("Select an ISO from isos/", available_isos)
    if ram is None:
        ram = Prompt.ask("RAM", default=DEFAULT_RAM, console=console)
    if cores is None:
        cores = IntPrompt.ask("CPU cores", default=DEFAULT_CORES, console=console)
    if disk_size is None:
        disk_size = Prompt.ask("Disk size", default=DEFAULT_DISK_SIZE, console=console)
    if network is None:
        network = Prompt.ask("Network", default=DEFAULT_NETWORK, console=console)
    if network not in {"user", "vmnet-shared"}:
        _error("Network must be 'user' or 'vmnet-shared'.")
        raise typer.Exit(1)
    if ssh_port is None:
        ssh_port = IntPrompt.ask("SSH port (host → guest:22)", default=DEFAULT_SSH_PORT, console=console)
    if display is None:
        display = Prompt.ask("Display", default=DEFAULT_DISPLAY, console=console)
    audio_enabled = Confirm.ask("Enable audio?", default=True, console=console)

    if serial is None:
        host_serial = _detect_host_serial()
        default_serial = host_serial or ""
        serial = Prompt.ask(
            "Serial number (empty to skip, 'host' to match this Mac)",
            default=default_serial, console=console,
        )
    if serial is not None and serial.lower() == "host":
        host_serial = _detect_host_serial()
        if not host_serial:
            _error("Could not detect host serial number via ioreg.")
            raise typer.Exit(1)
        serial = host_serial

    cfg = VMConfig(
        name=name,
        ram=ram,
        cores=cores,
        disk_size=disk_size,
        disk=f"vms/{name}/disk.qcow2",
        iso=f"isos/{iso}",
        installed=False,
        display=display,
        serial=serial or "",
        network=NetworkConfig(type=network, ssh_port=ssh_port),
        audio=AudioConfig(enabled=audio_enabled, backend="coreaudio"),
    )

    vm_dir.mkdir(parents=True)

    console.print(f"Creating disk [bold]vms/{name}/disk.qcow2[/bold] ({disk_size})...")
    result = subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", str(vm_dir / "disk.qcow2"), disk_size],
        capture_output=True,
    )
    if result.returncode != 0:
        _error(f"qemu-img failed: {result.stderr.decode().strip()}")
        raise typer.Exit(1)

    console.print(f"Creating EFI NVRAM [bold]vms/{name}/firmware.fd[/bold] (64 MiB)...")
    with (vm_dir / "firmware.fd").open("wb") as fh:
        fh.seek(FIRMWARE_SIZE - 1)
        fh.write(b"\x00")

    _save_config(cfg, vm_dir)
    console.print(f"Config written → [bold]vms/{name}/config.yaml[/bold]\n")
    _print_summary(cfg)

    if Confirm.ask("\nVM created. Start it now?", default=False, console=console):
        _boot(cfg, project_root)


# ── run ───────────────────────────────────────────────────────────────────────


@app.command("run")
def cmd_run(
    name: Optional[str] = typer.Argument(None, help="VM name (omit for interactive selection)"),
) -> None:
    """Run a VM — auto-detects install vs normal boot from config."""
    project_root = Path.cwd()
    vms_dir = project_root / "vms"

    if name is None:
        available = (
            sorted(d.name for d in vms_dir.iterdir() if d.is_dir() and (d / "config.yaml").exists())
            if vms_dir.exists()
            else []
        )
        if not available:
            console.print("[yellow]No VMs found in vms/. Create one with: vmctl create <name>[/yellow]")
            raise typer.Exit(0)
        name = _select_from_list("Select a VM", available)

    vm_dir = vms_dir / name
    if not (vm_dir / "config.yaml").exists():
        _error(f"vms/{name}/config.yaml not found. Create it first with: vmctl create {name}")
        raise typer.Exit(1)

    try:
        cfg = _load_config(vm_dir)
    except Exception as exc:
        _error(f"Failed to read config: {exc}")
        raise typer.Exit(1)

    _boot(cfg, project_root)


# ── share ─────────────────────────────────────────────────────────────────────

share_app = typer.Typer(help="Manage shared folders (virtio-9p) for a VM.")
app.add_typer(share_app, name="share")


def _resolve_vm_dir(name: Optional[str], project_root: Path) -> tuple[str, Path]:
    vms_dir = project_root / "vms"
    if name is None:
        available = (
            sorted(d.name for d in vms_dir.iterdir() if d.is_dir() and (d / "config.yaml").exists())
            if vms_dir.exists()
            else []
        )
        if not available:
            console.print("[yellow]No VMs found in vms/. Create one with: vmctl create <name>[/yellow]")
            raise typer.Exit(0)
        name = _select_from_list("Select a VM", available)
    vm_dir = vms_dir / name
    if not (vm_dir / "config.yaml").exists():
        _error(f"vms/{name}/config.yaml not found. Create it first with: vmctl create {name}")
        raise typer.Exit(1)
    return name, vm_dir


@share_app.command("add")
def cmd_share_add(
    host_path: str = typer.Argument(..., help="Absolute path on the host to share"),
    mount_tag: str = typer.Argument(..., help="Mount tag used in the guest (e.g. 'hostshare')"),
    name: Optional[str] = typer.Option(None, "--vm", help="VM name (omit for interactive selection)"),
) -> None:
    """Add a shared folder (virtio-9p) to a VM's config."""
    project_root = Path.cwd()
    _, vm_dir = _resolve_vm_dir(name, project_root)
    cfg = _load_config(vm_dir)

    resolved_path = str(Path(host_path).expanduser().resolve())
    if not Path(resolved_path).is_dir():
        _error(f"Host path does not exist or is not a directory: {resolved_path}")
        raise typer.Exit(1)
    if any(sf.mount_tag == mount_tag for sf in cfg.shared_folders):
        _error(f"Mount tag '{mount_tag}' already in use for this VM.")
        raise typer.Exit(1)

    cfg.shared_folders.append(SharedFolder(host_path=resolved_path, mount_tag=mount_tag))
    _save_config(cfg, vm_dir)
    console.print(f"[green]✓[/green] Shared folder added: {resolved_path} → tag:{mount_tag}")
    console.print(
        f"[dim]In the guest: sudo mount -t 9p -o trans=virtio,version=9p2000.L {mount_tag} /mnt/{mount_tag}[/dim]"
    )


@share_app.command("remove")
def cmd_share_remove(
    mount_tag: str = typer.Argument(..., help="Mount tag of the shared folder to remove"),
    name: Optional[str] = typer.Option(None, "--vm", help="VM name (omit for interactive selection)"),
) -> None:
    """Remove a shared folder from a VM's config."""
    project_root = Path.cwd()
    _, vm_dir = _resolve_vm_dir(name, project_root)
    cfg = _load_config(vm_dir)

    remaining = [sf for sf in cfg.shared_folders if sf.mount_tag != mount_tag]
    if len(remaining) == len(cfg.shared_folders):
        _error(f"No shared folder found with mount tag '{mount_tag}'.")
        raise typer.Exit(1)

    cfg.shared_folders = remaining
    _save_config(cfg, vm_dir)
    console.print(f"[green]✓[/green] Shared folder removed: tag:{mount_tag}")


@share_app.command("list")
def cmd_share_list(
    name: Optional[str] = typer.Option(None, "--vm", help="VM name (omit for interactive selection)"),
) -> None:
    """List shared folders configured for a VM."""
    project_root = Path.cwd()
    vm_name, vm_dir = _resolve_vm_dir(name, project_root)
    cfg = _load_config(vm_dir)

    if not cfg.shared_folders:
        console.print(f"[yellow]No shared folders configured for '{vm_name}'.[/yellow]")
        return

    table = Table(title=f"Shared Folders: {vm_name}", show_header=True, header_style="bold cyan")
    table.add_column("Host Path", style="bold")
    table.add_column("Mount Tag")
    for sf in cfg.shared_folders:
        table.add_row(sf.host_path, sf.mount_tag)
    console.print(table)


if __name__ == "__main__":
    app()
