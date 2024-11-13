sudo apt update
sudo apt upgrade

sudo apt install openssh-server vim curl sed unclutter htop

sudo useradd -m kiosk

sudo sed -i '/#WaylandEnable=false/c\WaylandEnable=false' /etc/gdm3/custom.conf
sudo sed -i '/#  AutomaticLoginEnable = true/c\AutomaticLoginEnable = true' /etc/gdm3/custom.conf
sudo sed -i '/#  AutomaticLogin = /c\AutomaticLogin = kiosk' /etc/gdm3/custom.conf

sudo mkdir -p /opt/kiosk

echo "[Unit]
Description=Chromium Kiosk
Wants=graphical.target
After=graphical.target

[Service]
Environment=DISPLAY=:0
Type=simple
ExecStart=/usr/bin/firefox --kiosk http://its-depot.ucsc.edu/calendar
Restart=always
User=kiosk
Group=kiosk

[Install]
WantedBy=graphical.target" | sudo tee /etc/systemd/system/kiosk.service
sudo systemctl enable kiosk

echo "#"'!'"/bin/bash
while true; do
    sleep 60
    xdotool keydown ctrl+R; xdotool keyup ctrl+R;
done" | sudo tee /opt/kiosk/reload.sh
sudo chmod +x /opt/kiosk/reload.sh

echo "[Unit]
Description=Chromium Kiosk Reload
Wants=graphical.target
After=graphical.target

[Service]
Environment=DISPLAY=:0
Type=simple
ExecStart=/opt/kiosk/reload.sh
Restart=always
User=kiosk
Group=kiosk

[Install]
WantedBy=graphical.target" | sudo tee /etc/systemd/system/kiosk_reload.service
sudo systemctl enable kiosk_reload

sudo ufw status
# sudo ufw allow from 128.114.2.0/24 to any port 22 proto tcp
sudo ufw allow ssh

echo "0 12 * * *    curl "'"'"http://its-depot.ucsc.edu/ip-db/?name=calendar-tv&ip="'$'"(hostname -I | grep -Eo '([0-9]*\.){3}[0-9]*')"'"'"" | tee crontab.txt
crontab crontab.txt