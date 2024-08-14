# Auto-Label-Generator
Automatic Label Printer for the ITS Depot

## First Setup:
  Clone this repo into the home folder (ex: /home/depot/Auto-Label-Generator)
  ```
  sudo apt install python3-pip  # install pip (if not already installed)
  pip install brother_ql  # install the label printer driver/API
  cd Auto-Label-Generator  # change directory into the label printer repository
  ~/.local/bin/brother_ql -b linux_kernel discover | grep 'file' | tr -d [:cntrl:] > address  # copy the printer address into the "address" file
  sudo ./usb_perms.sh  # make the printer's usb address writable
  export PATH="$PATH:/home/depot/.local/bin" >> ~/.bashrc  # add the brother_ql command to the PATH, so it can be executed normally
  source ~/.bashrc  # re-setup bash to bring in all necessary environment variables (including PATH change made above)
  brother_ql -m QL-570 -p $(cat address) print -l 62 static/depot.png  # test print using "depot" label to usb path stored in address file
  ```
  Create a .env file in the directory with the following:
  ```
  app_username ="depot@ucsc.edu"
  app_password =""  # add the Google app password (not the Gold password) here
  ```

## Activate:
  `./label_printer.sh`
  
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
