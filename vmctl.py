#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12.0",
#   "rich>=13.7.0",
#   "pyyaml>=6.0",
# ]
# ///
"""vmctl — QEMU Virtual Machine Manager for Apple Silicon Macs."""
from __future__ import annotations

import os
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
DEFAULT_ARCH = "aarch64"
DEFAULT_ACCEL = "hvf"
DEFAULT_SSH_PORT = 2222
DEFAULT_DISPLAY = "default"

FIRMWARE_SIZE = 64 * 1024 * 1024  # 64 MiB

# ── Console ────────────────────────────────────────────────────────────────────

console = Console()
err_console = Console(stderr=True)

# ── Config dataclasses ────────────────────────────────────────────────────────


@dataclass
class NetworkConfig:
    type: str = "user"
    ssh_port: int = DEFAULT_SSH_PORT


@dataclass
class AudioConfig:
    enabled: bool = True
    backend: str = "coreaudio"


@dataclass
class VMConfig:
    name: str
    arch: str = DEFAULT_ARCH
    ram: str = DEFAULT_RAM
    cores: int = DEFAULT_CORES
    disk_size: str = DEFAULT_DISK_SIZE
    disk: str = ""
    iso: str = ""
    installed: bool = False
    accelerator: str = DEFAULT_ACCEL
    display: str = DEFAULT_DISPLAY
    network: NetworkConfig = field(default_factory=NetworkConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)


# ── Config serialization ──────────────────────────────────────────────────────


def _to_dict(cfg: VMConfig) -> dict:
    return {
        "name": cfg.name,
        "arch": cfg.arch,
        "ram": cfg.ram,
        "cores": cfg.cores,
        "disk_size": cfg.disk_size,
        "disk": cfg.disk,
        "iso": cfg.iso,
        "installed": cfg.installed,
        "accelerator": cfg.accelerator,
        "display": cfg.display,
        "network": {"type": cfg.network.type, "ssh_port": cfg.network.ssh_port},
        "audio": {"enabled": cfg.audio.enabled, "backend": cfg.audio.backend},
    }


def _from_dict(data: dict) -> VMConfig:
    net = data.get("network", {})
    audio = data.get("audio", {})
    return VMConfig(
        name=data["name"],
        arch=data.get("arch", DEFAULT_ARCH),
        ram=data.get("ram", DEFAULT_RAM),
        cores=int(data.get("cores", DEFAULT_CORES)),
        disk_size=data.get("disk_size", DEFAULT_DISK_SIZE),
        disk=data.get("disk", ""),
        iso=data.get("iso", ""),
        installed=bool(data.get("installed", False)),
        accelerator=data.get("accelerator", DEFAULT_ACCEL),
        display=data.get("display", DEFAULT_DISPLAY),
        network=NetworkConfig(
            type=net.get("type", "user"),
            ssh_port=int(net.get("ssh_port", DEFAULT_SSH_PORT)),
        ),
        audio=AudioConfig(
            enabled=bool(audio.get("enabled", True)),
            backend=audio.get("backend", "coreaudio"),
        ),
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


def _print_summary(cfg: VMConfig) -> None:
    table = Table(title=f"VM: {cfg.name}", show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Name", cfg.name)
    table.add_row("Architecture", cfg.arch)
    table.add_row("RAM", cfg.ram)
    table.add_row("Cores", str(cfg.cores))
    table.add_row("Disk Size", cfg.disk_size)
    table.add_row("Disk", cfg.disk)
    table.add_row("ISO", cfg.iso or "(none)")
    table.add_row("Installed", str(cfg.installed))
    table.add_row("Accelerator", cfg.accelerator)
    table.add_row("Display", cfg.display)
    table.add_row("SSH Port", f"{cfg.network.ssh_port} → guest:22")
    table.add_row("Audio", f"{'enabled' if cfg.audio.enabled else 'disabled'} ({cfg.audio.backend})")
    console.print(table)


def _error(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")


# ── QEMU command builder ──────────────────────────────────────────────────────


def _build_qemu_cmd(cfg: VMConfig, project_root: Path, *, install_mode: bool) -> list[str]:
    vm_dir = project_root / "vms" / cfg.name
    display_args = ["-display", "none"] if cfg.display == "none" else ["-display", f"{cfg.display},show-cursor=on"]
    audio_args = (
        ["-audiodev", f"{cfg.audio.backend},id=audio0", "-device", "intel-hda", "-device", "hda-duplex,audiodev=audio0"]
        if cfg.audio.enabled
        else []
    )

    cmd = [
        f"qemu-system-{cfg.arch}",
        "-m", cfg.ram,
        "-cpu", "host",
        "-smp", str(cfg.cores),
        "-accel", cfg.accelerator,
        "-M", "virt,highmem=off",
        "-drive", f"if=pflash,format=raw,readonly=on,file={EFI_CODE_PATH}",
        "-drive", f"if=pflash,format=raw,file={vm_dir / 'firmware.fd'}",
        "-drive", f"file={project_root / cfg.disk},if=virtio",
    ]

    if install_mode:
        cmd += [
            "-drive", f"file={project_root / cfg.iso},id=cdrom,if=none,media=cdrom,readonly=on",
            "-device", "virtio-scsi-pci",
            "-device", "scsi-cd,drive=cdrom",
        ]
    else:
        cmd += ["-device", "virtio-scsi-pci"]

    cmd += [
        "-device", "virtio-gpu-pci",
        *display_args,
        "-device", "qemu-xhci,id=usb",
        "-device", "usb-kbd",
        "-device", "usb-tablet",
        "-device", "virtio-net-pci,netdev=net0",
        "-netdev", f"user,id=net0,hostfwd=tcp::{cfg.network.ssh_port}-:22",
        *audio_args,
    ]
    return cmd


# ── Shared boot logic ─────────────────────────────────────────────────────────


def _boot(cfg: VMConfig, project_root: Path) -> None:
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

    cmd = _build_qemu_cmd(cfg, project_root, install_mode=install_mode)
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
    arch: Optional[str] = typer.Option(None, "--arch", help="QEMU architecture (aarch64)"),
    accel: Optional[str] = typer.Option(None, "--accel", help="Accelerator (hvf)"),
    ssh_port: Optional[int] = typer.Option(None, "--ssh-port", help="Host port forwarded to guest SSH (22)"),
    display: Optional[str] = typer.Option(None, "--display", help="Display backend: default | none"),
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
    if arch is None:
        arch = Prompt.ask("Architecture", default=DEFAULT_ARCH, console=console)
    if accel is None:
        accel = Prompt.ask("Accelerator", default=DEFAULT_ACCEL, console=console)
    if ssh_port is None:
        ssh_port = IntPrompt.ask("SSH port (host → guest:22)", default=DEFAULT_SSH_PORT, console=console)
    if display is None:
        display = Prompt.ask("Display", default=DEFAULT_DISPLAY, console=console)
    audio_enabled = Confirm.ask("Enable audio?", default=True, console=console)

    cfg = VMConfig(
        name=name,
        arch=arch,
        ram=ram,
        cores=cores,
        disk_size=disk_size,
        disk=f"vms/{name}/disk.qcow2",
        iso=f"isos/{iso}",
        installed=False,
        accelerator=accel,
        display=display,
        network=NetworkConfig(type="user", ssh_port=ssh_port),
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


if __name__ == "__main__":
    app()
