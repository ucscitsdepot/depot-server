#!/usr/bin/bash

getdevice() {
    idV=${1%:*}
    idP=${1#*:}
    for path in $(find /sys/ -name idVendor | rev | cut -d/ -f 2- | rev); do
        if grep -q $idV $path/idVendor; then
            if grep -q $idP $path/idProduct; then
                find $path -name 'device' | rev | cut -d / -f 2 | rev
            fi
        fi
    done
}

echo "$(getdevice 21c4:0809)"
# echo ""
# echo "$(getdevice 1d6b:0003)"
# echo ""
# echo "$(getdevice 8087:0a2b)"
# echo ""
# echo "$(getdevice 04f9:2028)"
# echo ""
# echo "$(getdevice 1d6b:0002)"
# echo ""
