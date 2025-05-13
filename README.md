```ascii
 _        _______  _______  _        _______           _______  _______  _______ 
( (    /|(  ____ \(  ___  )( (    /|(  ____ \|\     /|(  ___  )(  ____ )(       )
|  \  ( || (    \/| (   ) ||  \  ( || (    \/| )   ( || (   ) || (    )|| () () |
|   \ | || (__    | |   | ||   \ | || (_____ | | _ | || (___) || (____)|| || || |
| (\ \) ||  __)   | |   | || (\ \) |(_____  )| |( )| ||  ___  ||     __)| |(_)| |
| | \   || (      | |   | || | \   |      ) || || || || (   ) || (\ (   | |   | |
| )  \  || (____/\| (___) || )  \  |/\____) || () () || )   ( || ) \ \__| )   ( |
|/    )_)(_______/(_______)|/    )_)\_______)(_______)|/     \||/   \__/|/     \|                                                                              
```

Maker-friendly DIY DS3 Composer Demo Panel powered by Raspberry Pi 5.

<p align="center" width="100%">
  <img src="assets/prototype.png"  alt="Neonswarm Prototype"/>
</p>

---

## What is Neonswarm?

Neonswarm is a compact, PoE-powered Raspberry Pi 5 panel showcasing the Cubbit DS3 distributed storage system in action. It integrates an NVMe SSD, LCD screens, LED strip indicators, and runs Kubernetes (K3S) to orchestrate demo services in a real-world setup.

## Purpose

- **Demonstrate** Cubbit DS3 performance and resilience on low-power hardware.  
- **Enable** hands-on experimentation with containerized storage workloads.  
- **Showcase** remote access via VPN and automated LED/LCD feedback.

## Necessary Parts

| Component                    | Example Link                                                                                                                |
|----------------------------- |---------------------------------------------------------------------------------------------------------------------------- |
| Raspberry Pi 5               | [Amazon.it](https://www.amazon.it/Raspberry-Pi-Quad-Core-ARMA76-Bits/dp/B0CK2FCG1K/)                                        |
| PoE + NVMe HAT               | [Waveshare M.2 PoE HAT](https://www.amazon.it/Waveshare-M-2-PoE-HAT-Compatible/dp/B0DNLSZ3LF/)                              |
| NVMe SSD (500 GB)            | [Crucial CT500P3SSD8](https://www.amazon.it/Crucial-500GB-PCIe-3500MB-CT500P3SSD8/)                                         |
| PoE Switch (4 ports)         | [NETGEAR 4-Port PoE](https://www.amazon.it/NETGEAR-Ethernet-Unmanaged-Montaggio-Scrivania/dp/B0DDJYX1X6/)                   |
| LCD Screens (I2C, HD44780)   | [Freenove I2C LCD 1602](https://www.amazon.it/Freenove-Display-Compatible-Arduino-Raspberry/dp/B0B76Z83Y4/)                 |
| LED Strip (cuttable)         | [Generic LED Strip](https://www.amazon.it/dp/B088BPGMXB/)                                                                   |
| JST 3-Pin Connector Set      | [VISSQH 3-Pin JST](https://www.amazon.it/VISSQH-Connettore-Maschio-Femmina-Elettrico/dp/B0CRZ336Z4/)                        |
| Jumper Wires (M/M, M/F)      | [AZDelivery Jumper Cables](https://www.amazon.it/AZDelivery-Cavetti-Maschio-Femmina-Raspberry/dp/B074P726ZR/)               |
| On/Off Rocker Switch         | [Senven Rocker Switch](https://www.amazon.it/Senven-Interruttore-interruttore-bilanciere-electrodomestici/dp/B07X169PBN/)   |
| Solder (Sn63/Pb37)           | [TOWOT Solder Wire](https://www.amazon.it/TOWOT-saldatura-elettrica-contenuto-Sn0-7Cu/dp/B09H2HMJ29/)                       |
| WiFi Router / Access Point   | [TP-Link Archer AX58](https://www.amazon.it/TP-Link-Archer-AX58-AX3000Mbps-Dual-Band/dp/B0CFYMG5J2/)                        |
| Ethernet Cable CAT6 (50 cm)  | [CSL CAT6 50 cm](https://www.amazon.it/CSL-Ethernet-1000Mbit-compatibile-Patchpannel/dp/B017UPQWVI/)                        |
| Cable Organizer              | [SOUWLIT® Cable Clamp](https://www.amazon.it/SOUWLIT%C2%AE-Organizer-Fermacavi-Multifunzione-Organizzatore/dp/B07T72KRVX/)  |
| SKÅDIS Panel (rear)          | [IKEA SKÅDIS Panel](https://www.ikea.com/it/it/p/skadis-pannello-portaoggetti-nero-80534372/)                               |
| SKÅDIS Connectors            | [IKEA SKÅDIS Connector](https://www.ikea.com/it/it/p/skadis-accessorio-di-collegamento-bianco-10320789/)                    |
| Standoffs                    | —                                                                                                                           |
| Panel-to-Panel Mounts        | —                                                                                                                           |
| Thumbscrew                   | —                                                                                                                           |
| T-Nuts                       | —                                                                                                                           |
| RJ45 Male Connectors         | [Greluma RJ45](https://www.amazon.it/Greluma-Connettori-passanti-Estremit%C3%A0-terminale/dp/B0BX3877CR/)                   |
| RJ45 Crimp Tool              | [VCE Crimper](https://www.amazon.it/VCE-Crimping-Toolper-Crimpare-Crimpatrice/dp/B07VZTN6YK/)                               |

> *Note:* For custom parts (spacers, mounting brackets, adhesive prints), source locally or via your preferred supplier.

## How to Assemble

1. **Prepare the panel:** Attach SKÅDIS rear panel to mounting supports.  
2. **Mount Raspberry Pi & HAT:** Secure Pi 5 onto standoffs, then install the PoE + NVMe HAT and SSD.  
3. **Wire up LCDs:** Cut one I2C LCD, solder 3-pin JST connectors, and mount next to the Pi.  
4. **Install LED strip:** Cut to length, solder 3-pin JST, and route along panel edge.  
5. **Cable management:** Use jumpers and cable clamps to organize I2C, power, and data lines.  
6. **Network:** Crimp CAT6 cables to RJ45 and connect to PoE switch.  
7. **Power switch:** Wire rocker switch inline with 5 V feed.  
8. **Finalize:** Attach front adhesive with QR code and text, tighten thumbscrews.

## PIN Connections

| Signal           | Pi GPIO Pin       | Physical Pin | Connector         | Notes                                  |
|------------------|-------------------|--------------|-------------------|----------------------------------------|
| 5 V Supply       | —                 | 2            | Rocker Switch     | Feeds HAT VIN through power switch     |
| GND              | —                 | 6            | LCD & LED strips  | Common ground                          |
| SDA (I2C)        | GPIO 2 (BCM 2)    | 3            | LCD SCL/SDA       | I2C data line                          |
| SCL (I2C)        | GPIO 3 (BCM 3)    | 5            | LCD SCL/SDA       | I2C clock line                         |
| LED DIN          | GPIO 18 (BCM 18)  | 12           | LED strip DIN     | WS2812 data in                         |
| LED GND          | —                 | 14           | LED strip GND     | Strip ground                           |
| On/Off Button    | GPIO 17 (BCM 17)  | 11           | ButtonPin         | Scales LCD deployment on/off (pull-up) |

## Raspberry Pi Setup

1. **Flash OS:** Write Raspberry Pi OS to microSD (for initial boot).  
2. **Set Hostnames** (recommended):

   ```bash
   hostnamectl set-hostname pi-gateway
   hostnamectl set-hostname pi-storage1
   hostnamectl set-hostname pi-storage2
   hostnamectl set-hostname pi-storage3
   ```

3. Static IPs (recommended): We’ll use `192.168.1.101` (pi-gateway), `.102` (pi-storage1), `.103` (pi-storage2), `.104` (pi-storage3). Replace as needed.

    ```bash
    sudo mkdir -p /etc/systemd/network
    sudo tee /etc/systemd/network/10-eth0.network <<EOF
    [Match]
    Name=eth0

    [Network]
    Address=192.168.1.xxx/24
    Gateway=192.168.1.1
    DNS=192.168.1.1 8.8.8.8
    EOF
    sudo systemctl enable systemd-networkd
    sudo systemctl restart systemd-networkd
    sudo systemctl disable dhcpcd NetworkManager
    ```

    Restart Network

    ```bash
    sudo systemctl enable systemd-networkd
    sudo systemctl restart systemd-networkd
    sudo systemctl disable dhcpcd NetworkManager
    ```

3. **Create an SSH key** to connect via SSH:

    ```bash
    ssh-keygen -t ed25519 -f ~/.ssh/ed25519_pi
    ```

4. **Boot from NVMe**:

    ```bash
    sudo sed -i '1i dtparam=nvme\\ndtparam=pciex1_gen=3' /boot/firmware/config.txt
    sudo reboot
    ```

5. Clone root FS to NVMe:

    ```bash
    curl https://raw.githubusercontent.com/geerlingguy/rpi-clone/master/install | sudo bash
    sudo rpi-clone nvme0n1
    ```

6. Setup VPN (Optional, Netbird): We use [Netbird](https://netbird.io) to run a self-hosted WireGuard management plane. Replace `https://your-netbird.example.com` and `YOUR-KEY`.

    ```bash
    sudo tee /etc/systemd/system/netbird-once.service <<EOF
    [Unit]
    Description=Start Netbird at boot
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=oneshot
    ExecStart=/usr/bin/netbird up --management-url https://your-netbird.example.com --setup-key YOUR-KEY
    ExecStartPost=/bin/systemctl disable netbird-once.service
    RemainAfterExit=true
    User=root

    [Install]
    WantedBy=multi-user.target
    EOF
    sudo systemctl daemon-reload
    sudo systemctl enable netbird-once.service
    ```

    > *Ensures the VPN starts at boot and connects to your management network.*

## Kubernetes Setup (K3S)

On pi-gateway:

```bash
k3sup install --host pi-gateway --user pi --ssh-key ~/.ssh/ed25519_pi \
  --cluster --context neonswarm \
  --k3s-extra-args '--node-ip=192.168.1.101 --disable traefik'
```

Join storage nodes:

```bash
k3sup join --host pi-storage1 --user pi --ssh-key ~/.ssh/ed25519_pi \
  --server-user pi --server pi-gateway --k3s-extra-args '--disable traefik'
# repeat for pi-storage2, pi-storage3
```

## Configuring `values.yaml`

Copy & rename the provided example:

```bash
cp values.example.yaml values.yaml
```

Edit `values.yaml`, focusing on `agent.swarm`:

```yaml
agent:
  swarm:
    enabled: true
    agents:
      - name: agent1
        secret: <agent-secret-1>
        machineId: <agent-machineId-1>
        nodeName: pi-storage1
      # etc.
```

To obtain `secret` & `machineId`:

- Visit your Composer dashboard at [https://composer.cubbit.eu](https://composer.cubbit.eu).
- Create a Swarm & Nexus, then add three agent nodes.
- Copy the `--secret` and `--machineId` from the suggested `docker run` command.
- Paste into `values.yaml`.

Read more: [https://docs.cubbit.io/composer/swarms/quickstart](https://docs.cubbit.io/composer/swarms/quickstart)

## Installing the Swarm

```bash
helm upgrade --install neonswarm ./chart \
  -n neonswarm --create-namespace \
  -f values.yaml
```

## Installing the Gateway

Just follow the guidelines of the [official doc](https://docs.cubbit.io/composer/gateway/how-to-install)
