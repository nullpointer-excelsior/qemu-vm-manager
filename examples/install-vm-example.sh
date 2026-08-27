#!/bin/bash

# --- Configuración ---
ISO_PATH="debian-13.3.0-arm64-netinst.iso" # Cambia esto a tu ruta real
DISK_NAME="debian_m1.qcow2"
DISK_SIZE="20G"
RAM="2G"
CORES="4"

# 1. Crear el disco si no existe
if [ ! -f "$DISK_NAME" ]; then
    echo "--- Creando disco virtual de $DISK_SIZE... ---"
    qemu-img create -f qcow2 "$DISK_NAME" "$DISK_SIZE"
else
    echo "--- El disco ya existe, saltando creación. ---"
fi

# 2. Descargar Firmware EFI (Necesario para ARM en QEMU)
# Instalamos qemu-virfw vía brew si no está para obtener los archivos pflash
if [ ! -f "EDK2_CODE.fd" ]; then
    echo "--- Configurando Firmware EFI ---"
    # Copiamos el firmware que viene con QEMU a la carpeta local
    cp /opt/homebrew/share/qemu/edk2-aarch64-code.fd ./EDK2_CODE.fd
    truncate -s 64M EDK2_CODE.fd
    # Creamos un archivo para las variables de la NVRAM
    truncate -s 64M EDK2_VARS.fd
fi

# 3. Ejecutar QEMU
echo "--- Iniciando Máquina Virtual ---"
qemu-system-aarch64 \
  -m 2G \
  -cpu host \
  -smp 4 \
  -accel hvf \
  -M virt,highmem=off \
  -drive if=pflash,format=raw,readonly=on,file=EDK2_CODE.fd \
  -drive if=pflash,format=raw,file=EDK2_VARS.fd \
  -drive file="debian_m1.qcow2",if=virtio \
  -drive file="debian-13.3.0-arm64-netinst.iso",id=cdrom,if=none,media=cdrom \
  -device virtio-scsi-pci  d\
  -device scsi-cd,drive=cdrom \
  -device virtio-gpu-pci \
  -display default,show-cursor=on \
  -device qemu-xhci,id=usb \
  -device usb-kbd \
  -device usb-tablet \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0
