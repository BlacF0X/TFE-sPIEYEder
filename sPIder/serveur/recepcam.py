import socket
import struct

def receive_cam(port, queue):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", port))
    server.listen(1)

    print(f"camera connect on port {port}")
    conn, addr = server.accept()
    print("Connected from", addr)

    data = b""

    while True:
        try:
            while len(data) < 8:
                packet = conn.recv(4096)
                if not packet:
                    return
                data += packet

            header = data[:8]
            data = data[8:]

            x_percent, size = struct.unpack("fI", header)

            while len(data) < size:
                packet = conn.recv(4096)
                if not packet:
                    return
                data += packet

            frame_bytes = data[:size]
            data = data[size:]

            if not queue.full():
                queue.put({
                    "frame": frame_bytes,
                    "percent": x_percent
                })

        except Exception as e:
            print("receive error:", e)
            break
