#!/bin/bash

set -e

if [ ! -f address ]; then
    echo "No address file found, setting permissions for /dev/usb/lp0"
    chmod 666 /dev/usb/lp0
else
    address="$(cat address)"
    address=${address//"file://"/}
    echo "address file found, setting permissions for $address"
    chmod 666 "$address"
fi

echo "Permissions set successfully."
