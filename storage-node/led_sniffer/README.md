# Led Sniffer

## How to build (Docker)

From the root of the repository run the following command

```
sudo docker build -t led_sniffer -f storage-node/led_sniffer/Dockerfile
```

## How to run (Docker)

LED sniffer needs to access the following host resources:

- network interfaces on which to sniff TCP packets (usually eth0 on Raspberry)
- GPIO board on which to control the LEDs

For this, it is necessary to run the container in privileged mode (via sudo), giving it access to the host network and exposing the devices necessary for proper operation of the LED strip.

The following command will do the trick

```
sudo docker run --rm --privileged --network host --device /dev/gpiomem --device /dev/i2c-1 --device /dev/spidev10.0 led_sniffer
```
