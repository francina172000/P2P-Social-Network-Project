import socket
import threading
import hashlib
from datetime import datetime
import mimetypes

class CommunityFileHandler:
    # Class variables to store file data
    shared_files = {}  # file_hash -> file_content mapping
    file_metadata = {}  # file_hash -> metadata mapping
    file_servers = {}  # community_id -> {user_id: (host, port)}

    def __init__(self):
        self.file_server = None
        self.server_thread = None

    @staticmethod
    def start_file_server(user_id, community_id):
        """Start a file sharing server for a specific community"""
        def run_server(host, port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.bind((host, port))
                server_socket.listen()
                
                # Register server in file_servers
                if community_id not in CommunityFileHandler.file_servers:
                    CommunityFileHandler.file_servers[community_id] = {}
                CommunityFileHandler.file_servers[community_id][user_id] = (host, port)
                
                while True:
                    conn, addr = server_socket.accept()
                    with conn:
                        data = conn.recv(1024)
                        if not data:
                            continue
                            
                        # Handle file requests
                        try:
                            message = data.decode()
                            if message.startswith("FILE_REQUEST:"):
                                file_hash = message.split(":")[1]
                                file_content = CommunityFileHandler.shared_files.get(file_hash)
                                if file_content:
                                    # Send file size first
                                    size = len(file_content)
                                    conn.sendall(f"SIZE:{size}".encode())
                                    # Wait for acknowledgment
                                    conn.recv(1024)
                                    # Send file content
                                    conn.sendall(file_content)
                                else:
                                    conn.sendall(b"FILE_NOT_FOUND")
                        except Exception as e:
                            print(f"Error handling file request: {str(e)}")

        host = '0.0.0.0'
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        thread = threading.Thread(target=run_server, args=(host, port))
        thread.daemon = True
        thread.start()
        return host, port

    @staticmethod
    def register_file(file_content, filename, user_id, community_id):
        """Register a new file in the community"""
        try:
            # Ensure file_content is bytes
            if isinstance(file_content, str):
                file_content = file_content.encode('utf-8')
            elif hasattr(file_content, 'read'):
                file_content = file_content.read()
            
            # Generate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Store file content
            CommunityFileHandler.shared_files[file_hash] = file_content
            
            # Store metadata
            CommunityFileHandler.file_metadata[file_hash] = {
                'filename': filename,
                'hash': file_hash,
                'user_id': user_id,
                'community_id': community_id,
                'timestamp': datetime.now().isoformat(),
                'mime_type': mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            }
            
            return CommunityFileHandler.file_metadata[file_hash]
            
        except Exception as e:
            print(f"Error registering file: {str(e)}")
            return None

    @staticmethod
    def request_file(file_hash, community_id):
        """Request a file from peers in the community"""
        if community_id not in CommunityFileHandler.file_servers:
            return None

        # Try each peer in the community until we get the file
        for user_id, (host, port) in CommunityFileHandler.file_servers[community_id].items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((host, port))
                    s.sendall(f"FILE_REQUEST:{file_hash}".encode())
                    
                    # Receive response
                    response = s.recv(1024).decode()
                    if response.startswith("SIZE:"):
                        # Get file size
                        size = int(response.split(":")[1])
                        # Send acknowledgment
                        s.sendall(b"OK")
                        # Receive file content
                        chunks = []
                        received = 0
                        while received < size:
                            chunk = s.recv(min(8192, size - received))
                            if not chunk:
                                break
                            chunks.append(chunk)
                            received += len(chunk)
                        
                        if received == size:
                            return b''.join(chunks)
            except Exception as e:
                print(f"Error requesting file from peer {user_id}: {str(e)}")
                continue

        return None

    @staticmethod
    def get_file_metadata(file_hash):
        """Get metadata for a specific file"""
        return CommunityFileHandler.file_metadata.get(file_hash)

    @staticmethod
    def cleanup_user_files(user_id, community_id):
        """Clean up when a user leaves the community"""
        if community_id in CommunityFileHandler.file_servers:
            CommunityFileHandler.file_servers[community_id].pop(user_id, None)
            if not CommunityFileHandler.file_servers[community_id]:
                del CommunityFileHandler.file_servers[community_id]

    @staticmethod
    def get_shared_file(file_hash):
        """Get a file directly from shared files"""
        return CommunityFileHandler.shared_files.get(file_hash)