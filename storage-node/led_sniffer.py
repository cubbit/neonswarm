import os
from scapy.all import sniff, TCP, IP
import socket
import threading

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
        self.port = port
        self.led_count = led_count
        self.led_strip_control_pin = led_strip_control_pin
        # self.led_strip(self.led_strip_control_pin, led_count=self.led_count)

    def _handle_packet(self, pkt):
        # Only process TCP packets to our port
        if TCP in pkt and pkt[TCP].dport == self.port:
            src = pkt[IP].src
            dst = pkt[IP].dst
            flags = pkt[TCP].flags
            payload_len = len(pkt[TCP].payload)
            print(
                f"[{src}:{pkt[TCP].sport} → {dst}:{pkt[TCP].dport}] Flags={flags}, Payload={payload_len} bytes"
            )
            # Here you could update LEDs based on traffic volume, flags, etc.
            # e.g. self.led_strip.blink() or set_color based on packet properties
            # self.led_strip.upload()

    def sniff(self, iface=None, timeout=None, count=None):
        """
        Start sniffing.
        :param iface: network interface to sniff on (e.g. "eth0"); default scapy chooses
        :param timeout: stop sniffing after this many seconds
        :param count: stop after this many packets
        """

        bpf_filter = f"tcp port {self.port}"
        print(f"Sniffing TCP traffic on port {self.port} (filter='{bpf_filter}')")
        sniff(
            filter=bpf_filter,
            prn=self._handle_packet,
            iface=iface,
            timeout=timeout,
            count=count,
            store=False,
        )


class TCPTestServer(threading.Thread):
    """
    Simple TCP echo server running in its own thread for testing.
    """

    def __init__(self, host, port):
        super().__init__(daemon=True)
        self.host = host
        self.port = port

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen()
            print(f"Test TCP server listening on {self.host}:{self.port}")
            while True:
                conn, addr = server_sock.accept()
                client_thread = threading.Thread(
                    target=self.handle_client, args=(conn, addr), daemon=True
                )
                client_thread.start()

    def handle_client(self, conn, addr):
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"Echoing back to {addr}: {data!r}")
                conn.sendall(data)


if __name__ == "__main__":
    PORT = os.environ.get("PORT", 4000)
    HOST = "0.0.0.0"

    # Start the test TCP server
    test_server = TCPTestServer(HOST, PORT)
    test_server.start()

    print(
        f"Starting LedSniffer on port {PORT} (you may need sudo/root privileges to sniff packets)"
    )

    led_sniffer = LedSniffer(port=PORT)
    led_sniffer.sniff()
