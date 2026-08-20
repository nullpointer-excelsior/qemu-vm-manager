# AGENTS.md

## Project Overview

`virtual-machines` is a QEMU-based virtual machine manager for Apple Silicon Macs (aarch64, HVF acceleration). Its core is `vmctl.py`, a Python CLI (Typer + Rich) that creates and runs VMs defined by per-VM `config.yaml` files under `vms/<name>/`.

Legacy shell scripts (`install-iso.sh`, `run-debian.sh`, `install-debian-base.sh`) predate `vmctl.py` and hardcode a single Debian VM (`debian_m1.qcow2`). Treat them as reference/legacy only — new VM workflows go through `vmctl.py`.

## Tech Stack

- **Language**: Python 3.11+
- **Runtime execution**: `uv run` (PEP 723 inline script metadata at the top of `vmctl.py` — no separate `pyproject.toml`/`requirements.txt`)
- **Dependencies**: `typer`, `rich`, `pyyaml` (declared inline in `vmctl.py`, resolved automatically by `uv`)
- **Virtualization**: QEMU (`qemu-system-aarch64`), HVF accelerator, EDK2/UEFI firmware

## Repository Structure

```
vmctl.py              # Main CLI: create/run VMs
isos/                  # Installer ISOs (gitignored)
vms/<name>/
  config.yaml          # Per-VM configuration (arch, ram, cores, disk, network, audio...)
  disk.qcow2            # VM disk image (gitignored)
  firmware.fd            # EFI NVRAM (gitignored)
artifacts/             # AI-generated docs (gitignored)
EDK2_CODE.fd / EDK2_VARS.fd  # Legacy shared EFI firmware (used only by legacy scripts)
```

## Running the CLI

```bash
./vmctl.py --help
./vmctl.py create <name>      # interactive prompts for ram, cores, disk size, iso, etc.
./vmctl.py run [<name>]       # boots from ISO if installed=false in config.yaml, else boots the installed disk
```

`vmctl.py` has a shebang (`#!/usr/bin/env -S uv run`) with inline PEP 723 metadata, so it must be run directly (`./vmctl.py`) or via `uv run vmctl.py` — do NOT run it with a bare `python3 vmctl.py` unless dependencies are already installed in the active environment.

## Conventions for Agents

- **Single source of truth for VM state** is `vms/<name>/config.yaml`. Never hand-edit disk images or firmware directly; regenerate them via `vmctl.py create` if corrupted.
- **`installed` flag** in `config.yaml` controls boot mode: `false` boots from the ISO (install mode), `true` boots the installed disk directly. `vmctl.py` flips this automatically after a confirmed install — don't flip it manually unless recovering from a broken state.
- Large binary artifacts (`*.qcow2`, `*.fd`, ISOs) are gitignored (`isos/` is ignored; disk/firmware files live inside `vms/` — verify `.gitignore` before assuming disk images are tracked). Never attempt to open, diff, or "read" `.qcow2`/`.fd` files as text.
- Keep all new code in `vmctl.py` consistent with existing style: dataclasses for config models, Typer commands, Rich console for output, `_private` helper functions.
- Function parameters in new/edited Python code go on a single line per project-wide style rules (see global AGENTS.md), except where existing Typer command signatures already split parameters per line — match the surrounding code's existing pattern in that case.
- Do not commit `isos/`, `*.qcow2`, or `*.fd` files.
</content>
