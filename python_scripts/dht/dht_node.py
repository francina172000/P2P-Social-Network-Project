from hashlib import sha256
import socket
import json
import threading
import time

class DHTNode:
    def __init__(self, ip_address, port, user_id):
        self.ip = ip_address
        self.port = port
        self.user_id = user_id
        self.position = self._hash(f"{ip_address}:{port}") % 1024  # 10-bit ring
        self.data_store = {}
        self.finger_table = {}
        self.successor = None
        self.predecessor = None
        self.storage_file = f"dht_storage_{user_id}.json"
        self._load_stored_data()
        
        # Setup socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((ip_address, port))
        self.running = False

    def _hash(self, key):
        """Hash function for both node positions and data"""
        return int(sha256(str(key).encode()).hexdigest(), 16)

    def start(self):
        """Start the DHT node"""
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def _listen(self):
        """Listen for incoming DHT messages"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                self._handle_message(message, addr)
            except Exception as e:
                print(f"DHT Node error: {e}")

    def _handle_message(self, message, addr):
        """Handle incoming DHT messages"""
        msg_type = message.get('type')
        if msg_type == 'store':
            self._handle_store(message)
        elif msg_type == 'retrieve':
            self._handle_retrieve(message, addr)
        elif msg_type == 'find_successor':
            self._handle_find_successor(message, addr)

    def _load_stored_data(self):
        """Load persisted data from file"""
        try:
            with open(self.storage_file, 'r') as f:
                self.data_store = json.load(f)
        except FileNotFoundError:
            self.data_store = {}

    def _save_data(self):
        """Persist data to file"""
        with open(self.storage_file, 'w') as f:
            json.dump(self.data_store, f)

    def store_data(self, key, value):
        """Store data with timestamp"""
        if self._is_responsible_for(self._hash(key)):
            self.data_store[key] = {
                'value': value,
                'timestamp': time.time()
            }
            self._save_data()
            return True
        return False

    def get_data(self, key):
        """Retrieve data if available"""
        data = self.data_store.get(key)
        return data['value'] if data else None

    def _is_responsible_for(self, key_hash):
        """Check if this node is responsible for a key"""
        if self.successor is None:
            return True
        if self.position < self.successor.position:
            return self.position <= key_hash < self.successor.position
        return (self.position <= key_hash) or (key_hash < self.successor.position)