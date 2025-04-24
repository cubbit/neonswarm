# LCD Storage

## How to build (Docker)

From the root of the repository run the following command

```
sudo docker build -t lcd_storage -f storage-node/lcd_storage/Dockerfile
```

## How to run (Docker)

This program controls an LCD screen via I2C protocol. This requires granting access to the host drivers. The following command should suffice

```
sudo docker run --rm  --device /dev/i2c-1 lcd_storage /
```
