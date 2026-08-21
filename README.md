# virtual-machines

Gestor de máquinas virtuales QEMU para Macs con Apple Silicon (aarch64, aceleración HVF).

## Requisitos

- macOS con Apple Silicon
- [Homebrew](https://brew.sh/)
- QEMU: `brew install qemu`
- [uv](https://docs.astral.sh/uv/): `brew install uv`

`vmctl.py` tiene shebang con metadatos PEP 723, por lo que resuelve sus dependencias
(`typer`, `rich`, `pyyaml`) automáticamente al ejecutarse con `uv run`. No requiere
instalar nada manualmente en un entorno Python.

## Estructura

```
vmctl.py              # CLI principal: crear y arrancar VMs
isos/                  # ISOs de instalación (gitignored)
vms/<name>/
  config.yaml          # Configuración de la VM
  disk.qcow2            # Disco de la VM (gitignored)
  firmware.fd            # NVRAM EFI (gitignored)
```

## Uso

```bash
./vmctl.py --help
./vmctl.py create <nombre>      # crea una VM (interactivo)
./vmctl.py run [<nombre>]       # arranca una VM (instala si aún no está instalada)
```

`vmctl.py` debe ejecutarse directamente (`./vmctl.py`) o con `uv run vmctl.py`. No lo
ejecutes con `python3 vmctl.py` a menos que ya tengas las dependencias instaladas en el
entorno activo.

**El script debe ejecutarse con permisos de root (`sudo`)**:

```bash
sudo ./vmctl.py <comando>
```

### Crear una VM

```bash
./vmctl.py create debian
```

El comando pide de forma interactiva: ISO, RAM, cores, tamaño de disco, arquitectura,
acelerador, tipo de red, puerto SSH y audio. Todos los valores también se pueden pasar
como flags (`--iso`, `--ram`, `--cores`, `--disk-size`, `--arch`, `--accel`, `--network`,
`--ssh-port`, `--display`).

### Arrancar una VM

```bash
./vmctl.py run debian
```

Si `installed: false` en `config.yaml`, arranca desde el ISO (modo instalación). Al
terminar la instalación, confirma cuando se te pregunte y `vmctl.py` marcará
`installed: true` automáticamente. En arranques posteriores bootea directo desde el
disco instalado.

## Red

`network.type` en `config.yaml` controla el modo de red de la VM:

### `user` (NAT, por defecto histórico)

```yaml
network:
  type: user
  ssh_port: 2222
```

- **Host → VM**: solo a través de puertos reenviados explícitamente.
  ```bash
  ssh -p 2222 usuario@localhost
  ```
- **VM → Host**: a través de la puerta de enlace `10.0.2.2`.
- **VM → red local**: la VM no es visible en la red del host; solo tiene salida a
  Internet vía NAT.
- No requiere privilegios especiales.

### `vmnet-shared` (recomendado, VM visible en la red del host)

```yaml
network:
  type: vmnet-shared
  ssh_port: 2222
```

- La VM obtiene su propia IP en la red compartida del host (visible con `ip addr` dentro
  de la VM).
- Host y VM pueden comunicarse directamente por IP, sin necesidad de `hostfwd`:
  ```bash
  ssh usuario@<IP_DE_LA_VM>
  ```
- **Requiere el entitlement `com.apple.vm.networking`**, que macOS no concede al binario
  de QEMU de Homebrew por defecto. Sin él, QEMU falla con:
  ```
  qemu-system-aarch64: -netdev vmnet-shared,id=net0: cannot create vmnet interface: general failure (possibly not enough privileges)
  ```

  Solución: ejecutar con `sudo`:
  ```bash
  sudo ./vmctl.py run <nombre>
  ```

## Troubleshooting

### zsh se ve raro por SSH (caracteres duplicados, backspace no funciona)

Si usas [Ghostty](https://ghostty.org) como terminal del host, este envía `TERM=xterm-ghostty`,
un terminfo que la mayoría de VMs no tienen instalado. Esto provoca que zsh/oh-my-zsh
redibuje mal la línea (caracteres duplicados/desordenados) y que teclas como Backspace
se interpreten incorrectamente.

Solución rápida: forzar un `TERM` estándar solo para la sesión SSH.

```bash
TERM=xterm-256color ssh usuario@<IP_DE_LA_VM>
```

Alternativa (instala el terminfo real de Ghostty en la VM, evita tener que setear `TERM`
cada vez):

```bash
infocmp -x xterm-ghostty | ssh usuario@<IP_DE_LA_VM> -- tic -x -o \$HOME/.terminfo /dev/stdin
```

## Scripts legacy

`install-iso.sh`, `run-debian.sh` e `install-debian-base.sh` son anteriores a
`vmctl.py` y asumen una única VM Debian (`debian_m1.qcow2`). Se mantienen solo como
referencia; los flujos nuevos de VMs deben usar `vmctl.py`.
</content>
