# depot-server
Automatic Label Printer for the ITS Depot

## First Setup:
  Clone this repo into the home folder (ex: /home/depot/depot-server)
  ```
  sudo apt install python3-pip  # install pip (if not already installed)
  cd depot-server  # change directory into the label printer repository
  pip install -r requirements.txt  # install the necessary libraries
  brother_ql -b linux_kernel discover | grep 'file' | tr -d [:cntrl:] > address  # copy the printer address into the "address" file
  sudo ./usb_perms.sh  # make the printer's usb address writable
  brother_ql -m QL-570 -p $(cat address) print -l 62 static/depot.png  # test print using "depot" label to usb path stored in address file
  ```
  Create a .env file in the directory with the following:
  ```
  app_username ="depot@ucsc.edu"
  app_password =""  # add the Google app password (not the Gold password) here
  ```

## Activate:
  `./start.sh`
  
## Usage:
  1. Navigate to Service Now RITM
  2. Click print label
  3. Script will print label
  OR
  1. Navigate to its-depot.ucsc.edu from one of the depot computers
  2. Use dashboard to fill out & print labels, or reprint/edit previously printed labels
  
## Notes:
  If a certain department keeps showing up as blank in the pc name, ex `___-servicetag`, the script cannot find a department that matches with at least 70% similarity.
  Departments can be added in departments.csv with the following format:
  `DEPTNAME,ABBREVIATION`
  Example: `Information Technology,ITS`


## Nginx/HTTPS setup:
- https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04
- https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu
- https://www.geeksforgeeks.org/how-to-generate-a-csr-certificate-signing-request-in-linux/

## Certificate renewal (InCommon):
  InCommon emails the depot account whenever a certificate is issued. cert_pull.py reads those emails and installs the certificate for nginx, and cert_check.py asks for a new one before the current one runs out. Both run on systemd timers.
  Set it up on the server with:
  ```
  sudo ./cert_setup.sh  # install the root helper, the sudoers rule and both timers
  sudo ./cert_setup.sh --uninstall  # take it all back out again
  ```
  The script checks the machine before it changes anything, and is safe to re-run.
  In the depot Gmail account, add a filter putting the InCommon emails under the "Depot-Cert" label. Nothing happens until that label exists.

## Certificate usage:
  1. InCommon emails the depot account, cert_pull.py finds the email and downloads the certificate (hourly)
  2. Script checks the certificate is for its-depot.ucsc.edu, is not expired, and is chained in the order nginx wants
  3. depot-cert-install checks it matches /etc/ssl/private/depot-server.key, installs it as /etc/ssl/certs/depot-server.crt, runs `nginx -t` and reloads
  4. If nginx rejects it the old certificate is put back, and the email is left unread so the next run tries again
  OR
  1. cert_check.py reads the expiry off the certificate nginx is serving (daily)
  2. Within 30 days of expiring, with no renewal in hand, it emails depot@ucsc.edu "I need a new certificate in [number of] days"
  3. Once a renewal is installed it goes quiet on its own

## Certificate notes:
  ```
  systemctl list-timers 'depot-cert*'  # when the timers last ran and when they run next
  sudo -u depot venv/bin/python cert_pull.py --dry-run  # download & check a certificate without installing it
  sudo -u depot venv/bin/python cert_check.py --dry-run --force  # print the warning email without sending it
  openssl x509 -in /etc/ssl/certs/depot-server.crt -noout -subject -enddate  # what is installed right now
  ```
  Logs are in logs/cert_pull/latest.log and logs/cert_check/latest.log.
  If a renewal is made with a new CSR and private key, the install stops with "certificate does not match" and nginx keeps serving the old certificate. Put the matching key in /etc/ssl/private/depot-server.key, then mark the email unread so it gets picked up again.
  Thresholds can be changed by adding any of the following to the .env file:
  ```
  cert_warn_days ="30"  # start asking for a renewal this many days before expiry
  cert_warn_every_days ="1"  # how often to send the warning again
  cert_notify ="depot@ucsc.edu"  # who gets the warning
  ```
