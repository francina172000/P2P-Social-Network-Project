import hashlib
import time
from typing import Dict, List
import socket
from python_scripts.public_chat.secure_bucket import SecureBucket
from python_scripts.public_chat.p2p_flood import P2PFloodNetwork

class ChatNode:
    def __init__(self, node_id: str, username: str):
        self.node_id = node_id
        self.username = username
        self.secure_bucket = SecureBucket(node_id, username)
        
        # Initialize P2P flooding network
        self.p2p_network = P2PFloodNetwork(
            host='0.0.0.0',  # Listen on all interfaces
            port=self._get_available_port(),
            username=username
        )
    
    def _get_available_port(self):
        """Get an available port for P2P communication"""
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def broadcast_message(self, content: str) -> Dict:
        """Create and broadcast a new message"""
        message = {
            'id': hashlib.sha256(f"{self.node_id}:{time.time()}".encode()).hexdigest(),
            'sender_id': self.node_id,
            'username': self.username,
            'content': content,
            'timestamp': time.time()
        }
        
        # Add message to secure bucket
        bucket_hash = self.secure_bucket.add_chat_message(message)
        
        return {
            'message': message,
            'bucket_hash': bucket_hash
        }

    def receive_message(self, message: Dict):
        """Receive and store message from another peer"""
        if self._is_valid_message(message):
            self.secure_bucket.add_chat_message(message)

    def _is_valid_message(self, message: Dict) -> bool:
        """Validate incoming message format"""
        required_fields = ['id', 'sender_id', 'username', 'content', 'timestamp']
        return all(field in message for field in required_fields)

    def sync_with_peer(self, peer_bucket_hash: str):
        """Sync chat history with another peer"""
        return self.secure_bucket.sync_chat_history(peer_bucket_hash)

    def get_chat_history(self) -> List[Dict]:
        """Get current chat history"""
        return self.secure_bucket.get_chat_history()

    def get_bucket_hash(self) -> str:
        """Get current bucket hash"""
        return self.secure_bucket._save_bucket()

    def clear_chat_history(self) -> Dict:
        """Clear chat history from bucket"""
        try:
            # Clear chat history using secure bucket
            result = self.secure_bucket.clear_chat_history()
            
            if result['success']:
                return {
                    'success': True,
                    'bucket_hash': result['bucket_hash']
                }
            else:
                return {
                    'success': False,
                    'message': result.get('error', 'Unknown error occurred')
                }
        except Exception as e:
            print(f"Error in clear_chat_history: {e}")
            return {
                'success': False,
                'message': str(e)
            }