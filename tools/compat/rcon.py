"""Tiny RCON client: python -I tools/rcon.py <host> <password> <command> [<command> ...]"""
import socket
import struct
import sys


def packet(rid, kind, body):
    data = struct.pack("<ii", rid, kind) + body.encode() + b"\x00\x00"
    return struct.pack("<i", len(data)) + data


def recv(sock):
    head = b""
    while len(head) < 4:
        head += sock.recv(4 - len(head))
    (length,) = struct.unpack("<i", head)
    data = b""
    while len(data) < length:
        data += sock.recv(length - len(data))
    rid, kind = struct.unpack("<ii", data[:8])
    return rid, data[8:-2].decode("utf-8", "replace")


def main():
    host, password, commands = sys.argv[1], sys.argv[2], sys.argv[3:]
    s = socket.create_connection((host, 25575), timeout=600)
    s.sendall(packet(1, 3, password))
    rid, _ = recv(s)
    if rid == -1:
        sys.exit("bad password")
    for i, cmd in enumerate(commands, start=2):
        s.sendall(packet(i, 2, cmd))
        _, body = recv(s)
        print(f"> {cmd}\n{body}", flush=True)


if __name__ == "__main__":
    main()
