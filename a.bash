cd /tmp
sudo rm -rf klippy.log
cd ~/
sudo rm -rf klipper
git clone https://github.com/lxf2020/klipper
./klipper/scripts/install-octopi.sh
cd ~/klipper/
make menuconfig
make
sudo service klipper stop
make flash FLASH_DEVICE=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AK0707K7-if00-port0
sudo service klipper start
nano /tmp/klippy.log
