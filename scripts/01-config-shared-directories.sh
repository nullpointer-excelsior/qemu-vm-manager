#!/bin/bash

mkdir /mnt/hostshare

FSTAB_LINE="hostshare /mnt/hostshare 9p trans=virtio,version=9p2000.L,rw,_netdev,nofail 0 0"

if ! grep -qF "$FSTAB_LINE" /etc/fstab; then
    echo "$FSTAB_LINE" | sudo tee -a /etc/fstab > /dev/null
fi