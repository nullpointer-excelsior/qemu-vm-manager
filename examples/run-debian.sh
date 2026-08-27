#!/bin/bash

# --- Configuración ---
ISO_PATH="debian-13.3.0-arm64-netinst.iso" # Cambia esto a tu ruta real
DISK_NAME="debian_m1.qcow2"
DISK_SIZE="20G"
RAM="2G"
CORES="4"


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
  -device virtio-scsi-pci \
  -device virtio-gpu-pci \
  -display default,show-cursor=on \
  -device qemu-xhci,id=usb \
  -device usb-kbd \
  -device usb-tablet \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -audiodev coreaudio,id=audio0 \
  -device intel-hda \
  -device hda-duplex,audiodev=audio0

