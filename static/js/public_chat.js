document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    let currentBucketHash = null;
    let p2pChat = null;
    let currentUserId = null;
    let currentUsername = null;

    // DOM Elements
    const noBucketWarning = document.getElementById('noBucketWarning');
    const mainArea = document.getElementById('mainArea');
    const bucketHashElement = document.getElementById('bucketHash');
    const fileInput = document.getElementById('fileInput');
    const myFilesList = document.getElementById('myFilesList');
    const dropZone = document.querySelector('.border-dashed');
    const createBucketBtn = document.getElementById('createBucket');
    const messageInput = document.getElementById('messageInput');
    const sendMessageBtn = document.getElementById('sendMessageBtn');
    const chatMessages = document.getElementById('chatMessages');
    const broadcastFileInput = document.getElementById('broadcastFileInput');
    const broadcastBtn = document.getElementById('broadcastBtn');
    const myRequestsList = document.getElementById('myRequestsList');
    const incomingRequestsList = document.getElementById('incomingRequestsList');

    // P2P Chat Class
    class P2PChat {
        constructor(socket) {
            this.socket = socket;
            this.messageInput = messageInput;
            this.sendMessageBtn = sendMessageBtn;
            this.chatMessages = chatMessages;
            
            // Add a Set to track processed messages
            this.processedMessages = new Set();

            // Initialize UI handlers
            this.initializeUIHandlers();
            
            // Get initial chat history
            this.socket.emit('get_chat_history');
            
            // Update socket listeners
            this.socket.on('chat_history', (data) => {
                this.displayChatHistory(data.messages);
            });

            // Listen for new messages
            this.socket.on('new_message', (data) => {
                if (data && data.messages) {
                    // Handle array of messages
                    data.messages.forEach(msg => this.displayMessage(msg));
                } else if (data) {
                    // Handle single message
                    this.displayMessage(data);
                }
            });

            // Add clear chat button handler
            const clearChatBtn = document.getElementById('clearChatBtn');
            if (clearChatBtn) {
                clearChatBtn.addEventListener('click', () => this.clearChatHistory());
            }
        }

        initializeUIHandlers() {
            this.sendMessageBtn.addEventListener('click', () => this.sendMessage());
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }

        async sendMessage() {
            const content = this.messageInput.value.trim();
            if (!content) return;

            try {
                this.socket.emit('send_message', { 
                    message: content,
                    timestamp: Date.now() / 1000  // Add timestamp
                });

                // Clear input after successful send
                this.messageInput.value = '';
            } catch (error) {
                console.error('Error sending message:', error);
            }
        }

        displayMessage(message) {
            // Add check for empty or invalid message
            if (!message || (!message.id && !message.content)) {
                console.warn('Invalid message received:', message);
                return;
            }

            // Check for duplicate messages
            if (message.id && this.processedMessages.has(message.id)) {
                return;
            }
            this.processedMessages.add(message.id);

            const messageDiv = document.createElement('div');
            messageDiv.className = `flex ${message.sender_id === currentUserId ? 'justify-end' : 'justify-start'} mb-4 message-animate-in`;

            const isOwnMessage = message.sender_id === currentUserId;
            
            messageDiv.innerHTML = `
                <div class="max-w-[70%] ${isOwnMessage 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white' 
                    : 'bg-gray-50 border border-gray-100'} 
                    rounded-xl px-4 py-3 shadow-sm">
                    <div class="flex items-center space-x-2 mb-1">
                        <div class="w-6 h-6 rounded-full ${isOwnMessage 
                            ? 'bg-white/20' 
                            : 'bg-gray-200'} 
                            flex items-center justify-center">
                            <i class="fas fa-user text-xs ${isOwnMessage 
                                ? 'text-white/70' 
                                : 'text-gray-500'}"></i>
                        </div>
                        <div class="text-sm ${isOwnMessage 
                            ? 'text-white/90' 
                            : 'text-gray-600'} font-medium">
                            ${message.username}
                        </div>
                    </div>
                    <div class="break-words text-sm">
                        ${this.escapeHtml(message.content)}
                    </div>
                    <div class="text-xs ${isOwnMessage 
                        ? 'text-white/70' 
                        : 'text-gray-400'} mt-2 text-right">
                        ${new Date(message.timestamp * 1000).toLocaleTimeString()}
                    </div>
                </div>
            `;

            this.chatMessages.appendChild(messageDiv);
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }

        displayChatHistory(messages) {
            this.chatMessages.innerHTML = '';
            this.processedMessages.clear();
            if (Array.isArray(messages)) {
                messages.forEach(message => this.displayMessage(message));
            }
        }

        clearChatHistory() {
            if (confirm('Are you sure you want to clear your chat history? This cannot be undone.')) {
                this.socket.emit('clear_chat_history');
                this.chatMessages.innerHTML = '';
                this.processedMessages.clear();
            }
        }

        escapeHtml(unsafe) {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }
    }

    // Show/Hide UI sections
    function showMainArea(bucketHash) {
        noBucketWarning.style.display = 'none';
        mainArea.style.display = 'grid';
        bucketHashElement.textContent = bucketHash;
        currentBucketHash = bucketHash;
        
        // Initialize P2P chat if we have user info
        if (!p2pChat && currentUserId && currentUsername) {
            p2pChat = new P2PChat(socket);
        }
    }

    function showBucketWarning() {
        noBucketWarning.style.display = 'block';
        mainArea.style.display = 'none';
        bucketHashElement.textContent = 'No bucket';
        currentBucketHash = null;
    }

    // Socket event handlers
    socket.on('connect', () => {
        console.log('Connected to server');
        socket.emit('get_user_info');
        socket.emit('check_bucket');
    });

    socket.on('bucket_status', (data) => {
        console.log('Received bucket status:', data);
        if (data.has_bucket) {
            showMainArea(data.bucket_hash);
        } else {
            showBucketWarning();
        }
    });

    socket.on('user_info', (data) => {
        currentUserId = data.user_id.toString();
        currentUsername = data.username;
        console.log('User info received:', data);
        
        // Initialize chat if bucket is already ready
        if (currentBucketHash && !p2pChat) {
            p2pChat = new P2PChat(socket);
        }
    });

    socket.on('chat_history_cleared', (data) => {
        if (data.success) {
            if (data.bucket_hash) {
                document.getElementById('bucketHash').textContent = data.bucket_hash;
            }
            if (p2pChat) {
                p2pChat.chatMessages.innerHTML = '';
                p2pChat.processedMessages.clear();
            }
        } else {
            console.error('Failed to clear chat history:', data.message);
            alert('Failed to clear chat history. Please try again.');
        }
    });
});