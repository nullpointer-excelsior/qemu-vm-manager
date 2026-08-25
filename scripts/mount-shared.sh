#!/usr/bin/env bash

set -u

MOUNT_BASE="/mnt"
MOUNT_OPTIONS="trans=virtio,version=9p2000.L,rw,nofail"
VIRTIO_9P_DRIVER="/sys/bus/virtio/drivers/9pnet_virtio"

modprobe 9pnet_virtio 2>/dev/null || true

shopt -s nullglob
devices=("${VIRTIO_9P_DRIVER}"/virtio*)

if [[ ${#devices[@]} -eq 0 ]]; then
    printf 'No Virtio 9p devices found.\n' >&2
    exit 0
fi

for device in "${devices[@]}"; do
    tag_file="${device}/mount_tag"
    [[ -r "$tag_file" ]] || continue

    tag="$(<"$tag_file")"
    if [[ ! "$tag" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        printf 'Invalid mount tag: %s\n' "$tag" >&2
        continue
    fi

    mount_point="${MOUNT_BASE}/${tag}"
    mkdir -p "$mount_point"

    if mountpoint -q "$mount_point"; then
        printf 'Already mounted: %s\n' "$mount_point"
        continue
    fi

    if mount -t 9p -o "$MOUNT_OPTIONS" "$tag" "$mount_point"; then
        printf 'Mounted %s at %s\n' "$tag" "$mount_point"
    else
        printf 'Failed to mount %s\n' "$tag" >&2
    fi
done
