import os
from scapy.all import sniff, TCP, IP, conf

# import board
# from led.strip import ledstrip


class LedSniffer:
    DEFAULT_LED_COUNT = 30
    DEFAULT_LED_STRIP_CONTROL_PIN = 18  # board.d18

    def __init__(
        self,
        port,
        led_count=DEFAULT_LED_COUNT,
        led_strip_control_pin=DEFAULT_LED_STRIP_CONTROL_PIN,
    ):
        self.port = int(port)
        self.led_count = led_count
        self.led_strip_control_pin = led_strip_control_pin
        # self.led_strip = ledstrip(self.led_strip_control_pin, led_count=self.led_count)

    def _handle_packet(self, pkt):
        src = pkt[IP].src
        dst = pkt[IP].dst
        flags = pkt[TCP].flags
        payload_len = len(pkt[TCP].payload)
        print(
            f"[Sniffer] {src}:{pkt[TCP].sport} → {dst}:{pkt[TCP].dport} | Flags={flags} | Payload={payload_len} bytes"
        )

    def sniff(self, iface=None):
        """
        Start sniffing TCP traffic to/from the specified port, skipping SYN+ACK via BPF.
        """

        # Filter packets that carry actual data (PSH bit set)
        bpf_filter = f"tcp port {self.port} and tcp[13] & 0x08 != 0"

        selected_iface = iface or conf.iface
        print(
            f"[Sniffer] Capturing on iface={selected_iface} filter='{bpf_filter}' (run with sudo)"
        )
        sniff(
            iface=selected_iface,
            filter=bpf_filter,
            prn=self._handle_packet,
            store=False,
        )


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 4000))

    print(
        f"[Main] Starting LedSniffer on port {PORT}. Use external netcat to generate traffic."
    )
    print(f"[Main] Run with sudo for packet capture.")

    led_sniffer = LedSniffer(port=PORT)
    led_sniffer.sniff()
