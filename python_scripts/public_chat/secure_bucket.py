from cryptography.fernet import Fernet
import json
import time
from typing import Dict, List, Optional
from config import Config
from python_scripts.handlers.ipfs_handler import IPFSHandler
import hashlib

class SecureBucket:
    def __init__(self, node_id: str, username: str):
        self.node_id = node_id
        self.username = username
        self.bucket_id = f"user_{node_id}_bucket"
        self.ipfs_handler = IPFSHandler()
        
        # Initialize Fernet cipher with existing ENCRYPTION_KEY
        self.cipher_suite = Fernet(Config.ENCRYPTION_KEY)
        
        # Initialize bucket structure
        self.bucket_structure = {
            'metadata': {
                'owner_id': node_id,
                'owner_username': username,
                'created_at': time.time(),
                'last_updated': time.time()
            },
            'chat_history': [],
            'files': {},
            'file_requests': {  # Changed from 'requests' to be more specific
                'sent': [],     
                'received': []  
            }
        }
        
        # Initialize or load existing bucket
        self._init_bucket()

    def _init_bucket(self):
        """Initialize or load existing bucket"""
        try:
            from app import bucket_manager
            main_bucket_hash = bucket_manager.get_bucket_hash(self.node_id)
            sent_requests_hash = bucket_manager.get_sent_requests_hash(self.node_id)
            received_requests_hash = bucket_manager.get_received_requests_hash(self.node_id)
            
            print(f"Loading bucket data - Main: {main_bucket_hash}, Sent: {sent_requests_hash}, Received: {received_requests_hash}")
            
            # Initialize empty structures
            self.bucket_structure = {
                'metadata': {
                    'owner_id': self.node_id,
                    'owner_username': self.username,
                    'created_at': time.time(),
                    'last_updated': time.time()
                },
                'chat_history': [],
                'files': {}
            }
            
            self.sent_requests = []
            self.received_requests = []
            
            # Load main bucket
            if main_bucket_hash:
                encrypted_data = self.ipfs_handler.get_content(main_bucket_hash)
                if encrypted_data:
                    loaded_structure = self._decrypt_data(encrypted_data)
                    self._merge_bucket_structures(loaded_structure)
            
            # Load sent requests
            if sent_requests_hash:
                try:
                    encrypted_data = self.ipfs_handler.get_content(sent_requests_hash)
                    if encrypted_data:
                        self.sent_requests = self._decrypt_data(encrypted_data)
                        print(f"Loaded {len(self.sent_requests)} sent requests")
                except Exception as e:
                    print(f"Error loading sent requests: {e}")
            
            # Load received requests
            if received_requests_hash:
                try:
                    encrypted_data = self.ipfs_handler.get_content(received_requests_hash)
                    if encrypted_data:
                        self.received_requests = self._decrypt_data(encrypted_data)
                        print(f"Loaded {len(self.received_requests)} received requests")
                except Exception as e:
                    print(f"Error loading received requests: {e}")
                    
        except Exception as e:
            print(f"Error initializing buckets: {e}")
            raise

    def _merge_bucket_structures(self, loaded_structure):
        """Merge loaded structure with current structure while preserving existing data"""
        for key, value in loaded_structure.items():
            if key in self.bucket_structure:
                if isinstance(value, dict):
                    self.bucket_structure[key].update(value)
                elif isinstance(value, list):
                    self.bucket_structure[key].extend(value)
                else:
                    self.bucket_structure[key] = value

    def _encrypt_data(self, data: dict) -> bytes:
        """Encrypt data before storing in IPFS"""
        json_data = json.dumps(data)
        return self.cipher_suite.encrypt(json_data.encode())
    
    def add_file_request(self, request_data: Dict) -> Dict[str, str]:
        """Add file request and return both bucket hashes"""
        try:
            from app import bucket_manager

            # Generate unique ID for request if not present
            if 'id' not in request_data:
                request_data['id'] = hashlib.sha256(f"{self.node_id}:{time.time()}".encode()).hexdigest()

            result = {}
            
            # Add request to appropriate list and get hash
            if request_data.get('requester_id') == self.node_id:
                self.sent_requests.append(request_data)
                encrypted_data = self._encrypt_data(self.sent_requests)
                sent_hash = self.ipfs_handler.add_content(encrypted_data)
                bucket_manager.update_sent_requests_hash(self.node_id, sent_hash)
                result['sent_hash'] = sent_hash
            else:
                self.received_requests.append(request_data)
                encrypted_data = self._encrypt_data(self.received_requests)
                received_hash = self.ipfs_handler.add_content(encrypted_data)
                bucket_manager.update_received_requests_hash(self.node_id, received_hash)
                result['received_hash'] = received_hash

            return result

        except Exception as e:
            print(f"Error adding file request: {e}")
            raise

    def get_requests(self) -> Dict:
        """Get all requests from both buckets"""
        try:
            from app import bucket_manager
            
            # Get hashes from bucket manager
            sent_hash = bucket_manager.get_sent_requests_hash(self.node_id)
            received_hash = bucket_manager.get_received_requests_hash(self.node_id)
            
            # Initialize empty lists
            sent_requests = []
            received_requests = []
            
            # Load sent requests if hash exists
            if sent_hash:
                try:
                    encrypted_data = self.ipfs_handler.get_content(sent_hash)
                    if encrypted_data:
                        sent_requests = self._decrypt_data(encrypted_data)
                except Exception as e:
                    print(f"Error loading sent requests: {e}")
            
            # Load received requests if hash exists
            if received_hash:
                try:
                    encrypted_data = self.ipfs_handler.get_content(received_hash)
                    if encrypted_data:
                        received_requests = self._decrypt_data(encrypted_data)
                except Exception as e:
                    print(f"Error loading received requests: {e}")
            
            return {
                'sent': sent_requests,
                'received': received_requests
            }
            
        except Exception as e:
            print(f"Error getting requests: {e}")
            return {'sent': [], 'received': []}

    def clear_all_requests(self):
        """Clear all requests from bucket"""
        try:
            from app import bucket_manager
            # Clear both sent and received requests
            self.sent_requests = []
            self.received_requests = []
            
            # Save empty states to IPFS
            sent_hash = self.ipfs_handler.add_content(self._encrypt_data([]))
            received_hash = self.ipfs_handler.add_content(self._encrypt_data([]))
            
            # Update bucket manager
            bucket_manager.update_sent_requests_hash(self.node_id, sent_hash)
            bucket_manager.update_received_requests_hash(self.node_id, received_hash)
        
        except Exception as e:
            print(f"Error clearing all requests: {e}")
            raise

    def get_requests(self) -> Dict:
        """Get all requests"""
        # Filter requests based on user ID/username
        sent = [r for r in self.sent_requests if r.get('requester_id') == self.node_id]
        received = [r for r in self.received_requests if r.get('requester_id') != self.node_id]
        
        return {
        'sent': sent,
            'received': received
        }

    def get_requests(self) -> Dict:
        """Get all requests"""
        try:
            # Filter sent requests - those created by current user
            sent = [r for r in self.sent_requests if r.get('requester_id') == self.node_id]
            
            # Filter received requests - those created by other users
            received = [r for r in self.received_requests if r.get('requester_id') != self.node_id]
            
            return {
                'sent': sent,
                'received': received
            }
        except Exception as e:
            print(f"Error getting requests: {e}")
            return {'sent': [], 'received': []}

    def _decrypt_data(self, encrypted_data: bytes) -> dict:
        """Decrypt data retrieved from IPFS"""
        decrypted_data = self.cipher_suite.decrypt(encrypted_data)
        return json.loads(decrypted_data)

    def _save_bucket(self) -> str:
        """Save encrypted bucket to IPFS"""
        try:
            # Update last modified timestamp
            self.bucket_structure['metadata']['last_updated'] = time.time()
            
            # Encrypt and save
            encrypted_data = self._encrypt_data(self.bucket_structure)
            return self.ipfs_handler.add_content(encrypted_data)
        except Exception as e:
            print(f"Error saving bucket: {e}")
            raise

    def _load_bucket(self, bucket_hash: str):
        """Load and decrypt bucket from IPFS"""
        try:
            encrypted_data = self.ipfs_handler.get_content(bucket_hash)
            self.bucket_structure = self._decrypt_data(encrypted_data)
        except Exception as e:
            print(f"Error loading bucket: {e}")
            raise

    def _get_bucket_hash(self) -> Optional[str]:
        """Get latest bucket hash from IPFS"""
        try:
            # Get hash from bucket manager
            from app import bucket_manager  # Import here to avoid circular import
            return bucket_manager.get_bucket_hash(self.node_id)
        except Exception as e:
            print(f"Error getting bucket hash: {e}")
            return None

    def add_chat_message(self, message: Dict) -> str:
        """Add chat message to bucket"""
        try:
            # Create a copy of the message for storage
            storage_message = message.copy()
            
            # Encrypt only the content
            storage_message['content'] = self.cipher_suite.encrypt(
                message['content'].encode()
            ).decode()
            
            # Add message to chat history
            self.bucket_structure['chat_history'].append(storage_message)
            
            # Keep only last 100 messages
            if len(self.bucket_structure['chat_history']) > 100:
                self.bucket_structure['chat_history'] = self.bucket_structure['chat_history'][-100:]
            
            # Save updated bucket and return new hash
            return self._save_bucket()
        except Exception as e:
            print(f"Error adding chat message: {e}")
            raise

    def get_chat_history(self) -> List[Dict]:
        """Get decrypted chat history"""
        try:
            decrypted_history = []
            for message in self.bucket_structure['chat_history']:
                # Create a copy of the message
                decrypted_message = message.copy()
                # Decrypt only the content
                decrypted_message['content'] = self.cipher_suite.decrypt(
                    message['content'].encode()
                ).decode()
                decrypted_history.append(decrypted_message)
            return decrypted_history
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    def search_files(self, query: str) -> list:
        """Search for files in bucket matching the query"""
        try:
            if 'files' not in self.bucket_structure:
                return []
                
            query = query.lower()
            matching_files = []
            
            for file_info in self.bucket_structure['files'].values():
                if query in file_info['name'].lower():
                    # Add download URL to file info
                    file_data = file_info.copy()
                    file_data['downloadUrl'] = f"/api/share_file/{file_data['id']}/{file_data['name']}"
                    matching_files.append(file_data)
            
            return sorted(matching_files, key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            print(f"Error searching files: {e}")
            return []

    def get_chat_history(self) -> List[Dict]:
        """Get decrypted chat history"""
        try:
            decrypted_history = []
            for message in self.bucket_structure['chat_history']:
                # Create a copy of the message
                decrypted_message = message.copy()
                # Decrypt only the content
                decrypted_message['content'] = self.cipher_suite.decrypt(
                    message['content'].encode()
                ).decode()
                decrypted_history.append(decrypted_message)
            return decrypted_history
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    def sync_chat_history(self, peer_bucket_hash: str):
        """Sync chat history with another peer's bucket"""
        try:
            # Get peer's bucket
            encrypted_data = self.ipfs_handler.get_content(peer_bucket_hash)
            peer_bucket = self._decrypt_data(encrypted_data)
            
            # Merge chat histories
            merged_history = self._merge_chat_histories(
                self.bucket_structure['chat_history'],
                peer_bucket['chat_history']
            )
            
            # Update local history
            self.bucket_structure['chat_history'] = merged_history
            
            # Save updated bucket
            return self._save_bucket()
            
        except Exception as e:
            print(f"Error syncing chat history: {e}")
            raise

    def _merge_chat_histories(self, history1: List[Dict], history2: List[Dict]) -> List[Dict]:
        """Merge two chat histories, removing duplicates"""
        # Combine histories and sort by timestamp
        all_messages = {msg['id']: msg for msg in history1 + history2}
        merged = list(all_messages.values())
        return sorted(merged, key=lambda x: x['timestamp'])

    def add_file(self, file_content: bytes, filename: str) -> dict:
        """Add a file to the bucket"""
        try:
            file_id = hashlib.sha256(f"{self.node_id}:{time.time()}".encode()).hexdigest()
            
            # Encrypt file content using Fernet cipher
            encrypted_content = self.cipher_suite.encrypt(file_content)
            
            # Add encrypted file to IPFS
            ipfs_hash = self.ipfs_handler.add_content(encrypted_content)
            print(f"Added file to IPFS with hash: {ipfs_hash}")
            
            # Add file metadata to bucket
            file_info = {
                'id': file_id,
                'name': filename,
                'ipfs_hash': ipfs_hash,
                'timestamp': time.time(),
                'size': len(file_content)
            }
            self.bucket_structure['files'][file_id] = file_info
            
            # Save updated bucket to IPFS
            new_bucket_hash = self._save_bucket()
            print(f"Updated bucket hash: {new_bucket_hash}")
            
            # Update bucket manager with new hash
            from app import bucket_manager
            bucket_manager.update_bucket_hash(self.node_id, new_bucket_hash)
            
            return file_info
        
        except Exception as e:
            print(f"Error adding file: {e}")
            raise

    def get_file_content(self, file_id: str) -> Optional[bytes]:
        """Get decrypted file content from bucket"""
        try:
            if file_id not in self.bucket_structure['files']:
                return None
            
            # Get file info from bucket
            file_info = self.bucket_structure['files'][file_id]
            
            # Get encrypted content from IPFS
            encrypted_content = self.ipfs_handler.get_content(file_info['ipfs_hash'])
            
            # Decrypt and return content
            return self.cipher_suite.decrypt(encrypted_content)
        
        except Exception as e:
            print(f"Error getting file content: {e}")
            raise

    def get_files(self) -> list:
        """Get list of files in bucket"""
        try:
            # Ensure files dictionary exists in bucket structure
            if 'files' not in self.bucket_structure:
                self.bucket_structure['files'] = {}
                
            # Convert dictionary values to list and sort by timestamp
            files = list(self.bucket_structure.get('files', {}).values())
            print(f"Retrieved {len(files)} files from bucket structure for user {self.username}")
            return sorted(files, key=lambda x: x['timestamp'], reverse=True)
        except Exception as e:
            print(f"Error getting files: {e}")
            print(f"Current bucket structure: {self.bucket_structure}")
            return []

    def delete_file(self, file_id: str) -> bool:
        """Delete a file from the bucket"""
        try:
            if file_id in self.bucket_structure['files']:
                # Remove file from bucket structure
                del self.bucket_structure['files'][file_id]
                
                # Save updated bucket to IPFS
                self._save_bucket()
                return True
            
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

    def clear_chat_history(self) -> Dict:
        """Clear all chat history from bucket"""
        try:
            # Clear the chat history array
            self.bucket_structure['chat_history'] = []
            
            # Save the updated bucket to IPFS
            new_hash = self._save_bucket()
            
            # Update the bucket manager with new hash
            from app import bucket_manager
            bucket_manager.update_bucket_hash(self.node_id, new_hash)
            
            return {
                'success': True,
                'bucket_hash': new_hash
            }
        except Exception as e:
            print(f"Error clearing chat history: {e}")
            return {
                'success': False,
                'error': str(e)
            }