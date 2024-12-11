from python_scripts.dht.dht_node import DHTNode
import time

class GroupDHT:
    def __init__(self, group_id):
        self.group_id = group_id
        self.nodes = {}  # user_id -> DHTNode
        self.node_list = []  # Sorted list of nodes
        self.message_keys = set()  # Track message keys for retrieval

    def add_member(self, user_id, ip_address, port):
        """Add a new member to the DHT ring"""
        node = DHTNode(ip_address, port, user_id)
        self.nodes[user_id] = node
        
        # Update node list and finger tables
        self._update_node_list()
        self._update_finger_tables()
        
        # Start the node
        node.start()
        return node

    def _update_node_list(self):
        """Update the sorted list of nodes"""
        self.node_list = sorted(
            self.nodes.values(),
            key=lambda x: x.position
        )
        
        # Update successors and predecessors
        for i, node in enumerate(self.node_list):
            node.successor = self.node_list[(i + 1) % len(self.node_list)]
            node.predecessor = self.node_list[i - 1]

    def _update_finger_tables(self):
        """Update finger tables for all nodes"""
        for node in self.nodes.values():
            finger_table = {}
            for i in range(10):  # 10-bit ring = 1024 positions
                ideal_position = (node.position + 2**i) % 1024
                successor = self._find_successor(ideal_position)
                finger_table[2**i] = successor
            node.finger_table = finger_table

    def _find_successor(self, position):
        """Find the successor node for a position"""
        for node in self.node_list:
            if node.position > position:
                return node
        return self.node_list[0]  # Wrap around to first node

    def store_message(self, message_data):
        """Store a message in the DHT"""
        timestamp = time.time()
        message_key = f"msg_{timestamp}_{message_data['sender_id']}"
        key_hash = self.node_list[0]._hash(message_key) % 1024
        
        # Find responsible node
        responsible_node = self._find_successor(key_hash)
        responsible_node.store_data(message_key, message_data)
        
        # Track message key for retrieval
        self.message_keys.add(message_key)
        return message_key

    def get_messages(self):
        """Retrieve all messages from the DHT"""
        messages = []
        for key in sorted(self.message_keys):  # Sort by key to maintain chronological order
            key_hash = self.node_list[0]._hash(key) % 1024
            responsible_node = self._find_successor(key_hash)
            message = responsible_node.get_data(key)
            if message:
                messages.append(message)
        return messages