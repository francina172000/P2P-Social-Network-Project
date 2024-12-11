class DHTChat {
    constructor(socket) {
        this.socket = socket;
        this.isDHTMode = false;
        this.currentGroup = null;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Toggle DHT mode
        const toggle = document.getElementById('dhtModeToggle');
        toggle.addEventListener('click', () => this.toggleDHTMode());

        // Listen for new DHT messages
        this.socket.on('new_group_message', (data) => {
            if (this.isDHTMode) {
                this.displayMessage(data);
            }
        });

        // Listen for DHT status updates
        this.socket.on('dht_status', (data) => {
            this.updateDHTStatus(data);
        });
    }

    toggleDHTMode() {
        this.isDHTMode = !this.isDHTMode;
        const toggle = document.getElementById('dhtModeToggle');
        const label = document.getElementById('chatModeLabel');
        const status = document.getElementById('dhtStatus');

        toggle.setAttribute('aria-checked', this.isDHTMode);
        toggle.querySelector('span').classList.toggle('translate-x-5');
        label.textContent = this.isDHTMode ? 'DHT Mode' : 'Server Mode';
        status.classList.toggle('hidden', !this.isDHTMode);

        if (this.isDHTMode && this.currentGroup) {
            this.socket.emit('join_dht_group', {
                group_id: this.currentGroup
            });
        }
    }

    sendMessage(content) {
        if (!this.currentGroup) return;

        const messageData = {
            group_id: this.currentGroup,
            content: content,
            timestamp: Date.now()
        };

        if (this.isDHTMode) {
            this.socket.emit('group_message', messageData);
        } else {
            // Use regular group chat
            this.socket.emit('message', messageData);
        }
    }

    displayMessage(data) {
        const messageArea = document.getElementById('messageArea');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex space-x-3';
        
        messageDiv.innerHTML = `
            <img src="/static/profile_pictures/default.png" 
                 alt="User" 
                 class="w-10 h-10 rounded-full">
            <div>
                <div class="flex items-center space-x-2">
                    <span class="font-medium">User ${data.sender_id}</span>
                    <span class="text-xs text-gray-500">${new Date(data.timestamp).toLocaleTimeString()}</span>
                </div>
                <p class="text-gray-700">${data.content}</p>
            </div>
        `;

        messageArea.appendChild(messageDiv);
        messageArea.scrollTop = messageArea.scrollHeight;
    }

    updateDHTStatus(data) {
        document.getElementById('nodePosition').textContent = data.position;
        document.getElementById('peerCount').textContent = data.peer_count;
    }

    setCurrentGroup(groupId) {
        this.currentGroup = groupId;
        if (this.isDHTMode) {
            this.socket.emit('join_dht_group', {
                group_id: groupId
            });
        }
    }
}