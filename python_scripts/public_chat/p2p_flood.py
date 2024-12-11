import socket
import json
import threading
from pathlib import Path
import tempfile
import time

class P2PFloodNetwork:
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.peers = {}  # {(host, port): connection}
        self.file_sources = {}  # {filename: [(host, port, file_id)]}
        self.temp_directory = tempfile.mkdtemp(prefix=f"p2p_flood_{username}_")
        self.processed_messages = set()  # Track processed message IDs
        
        # Setup socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(5)
        
        # Start listening thread
        self.listen_thread = threading.Thread(target=self.listen_for_connections)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def listen_for_connections(self):
        """Listen for incoming peer connections"""
        while True:
            try:
                connection, address = self.socket.accept()
                # Start a new thread to handle this peer
                peer_thread = threading.Thread(
                    target=self.handle_peer,
                    args=(connection, address)
                )
                peer_thread.daemon = True
                peer_thread.start()
                
                # Store the connection
                self.peers[address] = connection
            except Exception as e:
                print(f"Error accepting connection: {e}")

    def handle_peer(self, connection, address):
        """Handle messages from a connected peer"""
        while True:
            try:
                data = connection.recv(4096)
                if not data:
                    break
                
                message = json.loads(data.decode())
                message_id = message.get('id')
                
                # Skip if we've already processed this message
                if message_id in self.processed_messages:
                    continue
                    
                self.processed_messages.add(message_id)
                
                # Handle different message types
                if message['type'] == 'search':
                    self.handle_search(message, connection)
                elif message['type'] == 'search_response':
                    self.handle_search_response(message)
                elif message['type'] == 'file_request':
                    self.handle_file_request(message, connection)
                elif message['type'] == 'file_response':
                    self.handle_file_response(message)
                    
                # Forward the message to other peers (flooding)
                if message.get('ttl', 0) > 0:
                    self._flood_message(message, exclude=connection)
                    
            except Exception as e:
                print(f"Error handling peer {address}: {e}")
                break
                
        # Clean up
        connection.close()
        self.peers.pop(address, None)

    def handle_search(self, message, connection):
        """Handle incoming search request"""
        try:
            filename = message['filename']
            requester = message['from']
            
            # Check local files
            local_files = self.get_matching_files(filename)
            
            if local_files:
                # Send response for each matching file
                for file_info in local_files:
                    response = {
                        'type': 'search_response',
                        'id': f"response_{message['id']}",
                        'filename': file_info['name'],
                        'size': file_info['size'],
                        'host': self.host,
                        'port': self.port,
                        'username': self.username,
                        'file_id': file_info['id']
                    }
                    connection.send(json.dumps(response).encode())
        except Exception as e:
            print(f"Error handling search: {e}")

    def has_file(self, filename):
        """Check if we have the requested file"""
        file_path = Path(self.temp_directory) / filename
        return file_path.exists()

    def get_file_id(self, filename):
        """Get unique ID for a file"""
        file_path = Path(self.temp_directory) / filename
        if file_path.exists():
            return str(hash(file_path.read_bytes()))
        return None

    def _flood_message(self, message, exclude=None):
        """Forward message to all peers except the sender"""
        if message.get('ttl', 0) <= 0:
            return
            
        message['ttl'] = message['ttl'] - 1
        encoded_message = json.dumps(message).encode()
        
        for peer in self.peers.values():
            if peer != exclude:
                try:
                    peer.send(encoded_message)
                except Exception as e:
                    print(f"Error sending to peer: {e}")

    def handle_file_request(self, message, connection):
        """Handle request for file download"""
        try:
            filename = message.get('filename')
            file_id = message.get('file_id')
            
            if not filename or not file_id:
                return
                
            # Get file content from local storage
            file_content = None
            
            # Import chat_nodes here to avoid circular imports
            from app import chat_nodes
            
            # Find the node that has this file
            node_id = next((id for id, node in chat_nodes.items() 
                           if node.p2p_network == self), None)
            if node_id:
                node = chat_nodes[node_id]
                file_content = node.secure_bucket.get_file_content(file_id)
                        
            if file_content:
                # Send file content back to requester
                response = {
                    'type': 'file_response',
                    'id': f"file_{message.get('id')}",
                    'filename': filename,
                    'content': file_content.hex()  # Convert bytes to hex string
                }
                connection.send(json.dumps(response).encode())
                
        except Exception as e:
            print(f"Error handling file request: {e}")

    def connect_to_peer(self, host, port):
        """Establish connection to another peer"""
        try:
            if (host, port) not in self.peers:
                connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                connection.connect((host, port))
                self.peers[(host, port)] = connection
                
                # Start thread to handle this peer
                peer_thread = threading.Thread(
                    target=self.handle_peer,
                    args=(connection, (host, port))
                )
                peer_thread.daemon = True
                peer_thread.start()
                
                return True
        except Exception as e:
            print(f"Error connecting to peer {host}:{port}: {e}")
            return False

    def flood_search(self, filename):
        """Broadcast file search to all peers"""
        search_msg = {
            'type': 'search',
            'id': f"search_{time.time()}_{self.username}",  # Add unique ID
            'filename': filename,
            'from': {
                'host': self.host,
                'port': self.port,
                'username': self.username
            },
            'ttl': 7  # Time-to-live to prevent infinite flooding
        }
        
        # Clear previous search results
        self.file_sources = {}
        
        # Send search message to all peers
        self._flood_message(search_msg)

    def handle_search_response(self, response_data):
        """Handle response from a peer that has the file"""
        filename = response_data['filename']
        source = (response_data['host'], response_data['port'])
        file_id = response_data.get('file_id')
        
        if filename not in self.file_sources:
            self.file_sources[filename] = []
        self.file_sources[filename].append((source[0], source[1], file_id))

    def get_matching_files(self, query):
        """Get list of files matching the search query"""
        try:
            from app import chat_nodes
            node_id = next((id for id, node in chat_nodes.items() if node.p2p_network == self), None)
            if node_id:
                node = chat_nodes[node_id]
                return node.secure_bucket.search_files(query)
            return []
        except Exception as e:
            print(f"Error getting matching files: {e}")
            return []

    def request_file(self, filename, source):
        """Request a file from a specific peer"""
        try:
            host, port, file_id = source
            request_msg = {
                'type': 'file_request',
                'id': f"request_{time.time()}_{self.username}",
                'filename': filename,
                'file_id': file_id,
                'requester': {
                    'host': self.host,
                    'port': self.port
                }
            }
            
            # Connect to the source peer if not already connected
            if (host, port) not in self.peers:
                if not self.connect_to_peer(host, port):
                    raise Exception("Could not connect to peer")
                
            # Send request
            self.peers[(host, port)].send(json.dumps(request_msg).encode())
            
        except Exception as e:
            print(f"Error requesting file: {e}")
            raise

    def handle_file_response(self, message):
        """Handle incoming file response"""
        try:
            filename = message['filename']
            content = bytes.fromhex(message['content'])  # Convert hex string back to bytes
            
            # Save file to temp directory
            file_path = Path(self.temp_directory) / filename
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # Emit download ready event
            from app import socketio
            socketio.emit('download_ready', {
                'url': f'/download_temp/{filename}'
            })
            
        except Exception as e:
            print(f"Error handling file response: {e}")