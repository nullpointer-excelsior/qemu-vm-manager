# virtual-machines

Gestor de máquinas virtuales QEMU para Macs con Apple Silicon (aarch64, aceleración HVF).

## Requisitos

- macOS con Apple Silicon
- [Homebrew](https://brew.sh/)
- QEMU: `brew install qemu`
- [uv](https://docs.astral.sh/uv/): `brew install uv`

`vmctl.py` resuelve automáticamente sus dependencias (`typer`, `rich`, `pyyaml`) con
`uv run`.

## Estructura

```
vmctl.py              # CLI principal
.vmctl/config.yml     # Opciones por defecto de QEMU
isos/                 # ISOs de instalación (gitignored)
vms/<name>/
  config.yaml         # Configuración de la VM
  disk.qcow2          # Disco de la VM (gitignored)
  firmware.fd         # NVRAM EFI (gitignored)
```

## Uso

```bash
./vmctl.py --help
./vmctl.py create <nombre>
./vmctl.py run [<nombre>]
```

Ejecuta el script directamente o con `uv run vmctl.py`; no uses `python3 vmctl.py` salvo
que las dependencias ya estén instaladas.

### Crear una VM

```bash
./vmctl.py create debian
```

El comando solicita ISO, RAM, cores, disco, tipo de red, pantalla y audio. También acepta
`--iso`, `--ram`, `--cores`, `--disk-size`, `--network` y `--display`.

### Arrancar una VM

```bash
./vmctl.py run debian
```

Si `installed: false`, arranca desde el ISO. Después de confirmar la instalación,
`vmctl.py` cambia automáticamente el valor a `installed: true`.

## Red

`vms/<nombre>/config.yaml` solo selecciona el tipo de red. Los argumentos de QEMU se
definen centralmente en `.vmctl/config.yml`:

```yaml
template-options:
  network:
    - bridge: "-netdev vmnet-bridged,id=net0,ifname=en0 -device virtio-net-pci,netdev=net0"
    - nat: "-netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=net0"
```

La VM selecciona una opción:

```yaml
network:
  type: nat
```

### `nat`

Usa la red `user` de QEMU con NAT. La VM tiene salida a Internet, pero no es visible
directamente en la red local. El puerto `2222` del host se reenvía al SSH de la VM:

```bash
ssh -p 2222 usuario@localhost
```

El puerto se cambia editando `hostfwd` en `.vmctl/config.yml`.

### `bridge`

Usa `vmnet-bridged` y conecta la VM a una interfaz física del host. La VM obtiene su
propia IP en la red local y se accede directamente:

```bash
ssh usuario@<IP_DE_LA_VM>
```

`ifname=en0` normalmente corresponde a Wi-Fi. Consulta las interfaces disponibles con:

```bash
networksetup -listallhardwareports
```

Si la interfaz activa es diferente, cambia `ifname=en0` en `.vmctl/config.yml`. El modo
bridge no usa `hostfwd`.

## Carpetas compartidas

```bash
./vmctl.py share add /ruta/en/el/host hostshare --vm debian
./vmctl.py share list --vm debian
./vmctl.py share remove hostshare --vm debian
```

Dentro de la VM:

```bash
sudo mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/hostshare
```

## Scripts legacy

`install-iso.sh`, `run-debian.sh` e `install-debian-base.sh` son scripts antiguos y se
mantienen solo como referencia. Los nuevos flujos deben usar `vmctl.py`.
