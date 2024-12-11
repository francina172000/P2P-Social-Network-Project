import socket
import threading
from python_scripts.sql_models.models import db, User
from python_scripts.handlers.message_handler import MessageHandler

message_handler = MessageHandler()

class P2PSocketHandler:
    @staticmethod
    def start_user_socket_server(user):
        def run_server(host, port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.bind((host, port))
                server_socket.listen()
                while True:
                    conn, addr = server_socket.accept()
                    with conn:
                        while True:
                            data = conn.recv(1024)
                            if not data:
                                break
        host = '0.0.0.0'
        port = P2PSocketHandler.find_free_port()
        user.socket_host = socket.gethostbyname(socket.gethostname())
        user.socket_port = port
        db.session.commit()

        thread = threading.Thread(target=run_server, args=(host, port))
        thread.start()
    
    @staticmethod
    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    @staticmethod
    def connect_to_friend(friend):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((friend.socket_host, friend.socket_port))
        return s
    
    @staticmethod
    def send_message_to_friend(friend, message, message_handler):
        encrypted_message = message_handler.encrypt_message(message)
        s = P2PSocketHandler.connect_to_friend(friend)
        s.sendall(encrypted_message)
        s.close()

