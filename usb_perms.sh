#!/bin/bash

if [ ! -f address ]; then
    echo "No address file found, setting permissions for /dev/usb/lp0"
    chmod a+rw /dev/usb/lp0
else
    address="$(cat address)"
    address=${address//"file://"/}
    echo "address file found, setting permissions for $address"
    chmod a+rw "$address"
fi
