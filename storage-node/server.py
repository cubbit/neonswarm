import socket
import threading


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
            print(f"[Server] Listening on {self.host}:{self.port}")
            while True:
                conn, addr = server_sock.accept()
                threading.Thread(
                    target=self.handle_client, args=(conn, addr), daemon=True
                ).start()

    def handle_client(self, conn, addr):
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"[Server] Echoing back to {addr}: {data!r}")
                conn.sendall(data)


if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 4000

    # Start the test TCP server
    test_server = TCPTestServer(HOST, PORT)
    test_server.start()

    test_server.join()
