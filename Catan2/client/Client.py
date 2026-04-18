# Catan/client/Client.py
import socket
import pickle

HOST = 'localhost'
PORT = 5502
ADDR = (HOST, PORT)
BUFSIZE = 4096
import pickle
import struct
def send_msg(sock, obj):
    data = pickle.dumps(obj)
    # pack length as 4-byte integer
    sock.sendall(struct.pack('!I', len(data)) + data)

def recv_msg(sock):
    # first 4 bytes: length
    raw_len = recvall(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('!I', raw_len)[0]
    # receive the exact message
    return pickle.loads(recvall(sock, msg_len))

def recvall(sock, n):
    """Helper to receive exactly n bytes"""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
class Client:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(ADDR)

    def send_request(self, action, username="", password="", **extra):
        """
        Generic request to the server.
        Extra keyword arguments are sent as additional fields.
        """
        request = {
            "action": action,
            "username": username,
            "password": password,
        }
        request.update(extra)

        try:
            send_msg(self.client, request)
            response = recv_msg(self.client)
        except Exception as e:
            print("Client send_request error:", e)
            response = {"success": False, "message": str(e)}

        return response

    def close(self):
        self.client.close()


# Short-lived helper for windows like SignupWindow
def send_request_once(data: dict):
    """
    Sends a single request to the server without using persistent connection.
    `data` is a dict with keys like: action, username, password, etc.
    """
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(ADDR)
        client.send(pickle.dumps(data))
        response = pickle.loads(client.recv(BUFSIZE))
    except Exception as e:
        print("send_request_once error:", e)
        response = {"success": False, "message": str(e)}
    finally:
        client.close()

    return response
