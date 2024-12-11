let socket;
if (!socket) {
    socket = io('/');
}

var currentChatFriendId = null;

if (typeof currentUserId == 'undefined'){
    console.error('currentUserId is not defined. Make sure it is set in HTML before the script loads!');
}

// Add this near the top of the file, after the socket initialization
document.addEventListener('DOMContentLoaded', function() {
    const clearChatButton = document.getElementById('clearChatButton');
    if (clearChatButton) {
        clearChatButton.addEventListener('click', clearChat);
    }
});

// Add this function to your chat.js file
function clearChat() {
    if (confirm('Are you sure you want to clear your chat history? This action cannot be undone and will only affect your view of the conversation.')) {
        fetch(`/api/clear_chat/${currentChatFriendId}`, {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('messageArea').innerHTML = '<p class="text-muted">No messages to display.</p>';
                console.log('Chat history cleared successfully');
            } else {
                console.error('Failed to clear chat history:', data.error);
            }
        })
        .catch(error => {
            console.error('Error clearing chat history:', error);
        });
    }
}

let isUploading = false;

function setupFileSharing() {
    const fileInput = document.getElementById('fileInput');
    const shareFileBtn = document.getElementById('shareFileBtn');

    // Remove any existing event listeners
    shareFileBtn.removeEventListener('click', handleShareButtonClick);
    fileInput.removeEventListener('change', handleFileSelection);

    // Add new event listeners
    shareFileBtn.addEventListener('click', handleShareButtonClick);
    fileInput.addEventListener('change', handleFileSelection);
}

function handleShareButtonClick(event) {
    event.preventDefault();
    const fileInput = document.getElementById('fileInput');
    fileInput.click();
}

function handleFileSelection(event) {
    const file = event.target.files[0];
    if (file && !isUploading) {
        shareFile(file);
    }
}

function shareFile(file) {
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('filename', file.name);
    
    const uploadId = `upload_${Date.now()}`;
    showUploadStatus('Starting upload...', 0, {
        steps: [
            { id: 'prepare', label: 'Preparing file...', status: 'current' },
            { id: 'ipfs', label: 'IPFS Upload', status: 'pending' }
        ]
    }, uploadId);

    fetch('/api/share_file', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Create message content with proper file link
            const message = `Shared file: [Download](${data.file_link})`;
            
            // Send the message using the existing sendMessage function
            sendMessage(currentChatFriendId, message);
            
            // Update upload status
            updateUploadStatus('Upload complete!', 100, {
                steps: [
                    { id: 'prepare', label: 'File prepared', status: 'complete' },
                    { id: 'ipfs', label: 'IPFS Upload complete', status: 'complete' }
                ]
            }, uploadId);
            
            // Remove status after delay
            setTimeout(() => {
                removeUploadStatus(uploadId);
            }, 3000);
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    })
    .catch(error => {
        console.error('Error sharing file:', error);
        handleUploadError(error.message, uploadId);
    });
}

// Add new function to check upload status
function checkUploadStatus(taskId, uploadId) {
    const checkStatus = () => {
        fetch(`/api/upload_status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'completed' && data.file_link) {
                    // Create file message and send it
                    const fileMessage = `Shared file: [Download](${data.file_link})`;
                    sendMessage(currentChatFriendId, fileMessage);
                    
                    // Update upload status UI
                    updateUploadStatus('Upload complete!', 100, {
                        steps: [
                            { id: 'prepare', label: 'File prepared', status: 'complete' },
                            { id: 'ipfs', label: 'IPFS Upload complete', status: 'complete' }
                        ]
                    }, uploadId);

                    // Remove status after delay
                    setTimeout(() => {
                        removeUploadStatus(uploadId);
                    }, 3000);
                } else if (data.status === 'error') {
                    handleUploadError(data.error || 'Upload failed', uploadId);
                } else {
                    // Continue polling
                    setTimeout(checkStatus, 1000);
                }
            })
            .catch(error => {
                console.error('Error checking upload status:', error);
                handleUploadError('Failed to check upload status', uploadId);
            });
    };

    // Start polling
    checkStatus();
}

function handleUploadError(errorMessage) {
    updateUploadStatus(errorMessage, 100, {
        steps: [
            { id: 'prepare', label: 'File prepared', status: 'error' },
            { id: 'ipfs', label: 'IPFS Upload failed', status: 'error' }
        ]
    }, true);
    
    setTimeout(() => {
        hideUploadStatus();
        isUploading = false;
        document.getElementById('shareFileBtn').disabled = false;
    }, 3000);
}

function updateUploadStatus(message, progress, stepsData, uploadId) {
    showUploadStatus(message, progress, stepsData, uploadId);
}

function showUploadStatus(message, progress, stepsData, uploadId) {
    let statusContainer = document.getElementById('uploadStatusContainer');
    if (!statusContainer) {
        statusContainer = document.createElement('div');
        statusContainer.id = 'uploadStatusContainer';
        statusContainer.className = 'fixed bottom-4 right-4 space-y-2 z-50';
        document.body.appendChild(statusContainer);
    }

    // Get the current chat name properly
    const currentChatNameElement = document.getElementById('currentChatName');
    const recipientName = currentChatNameElement ? currentChatNameElement.textContent : 'User';

    let statusElement = document.getElementById(`upload-${uploadId}`);
    if (!statusElement) {
        statusElement = document.createElement('div');
        statusElement.id = `upload-${uploadId}`;
        statusElement.className = 'flyout-notification bg-white shadow-lg rounded-lg p-4';
        statusElement.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-gray-700">
                    Sending file to: ${recipientName}
                </span>
                <button class="text-gray-400 hover:text-gray-600" onclick="removeUploadStatus('${uploadId}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="text-sm text-gray-600 mb-2">${message}</div>
            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div class="h-full bg-blue-600 transition-all duration-300" style="width: ${progress}%"></div>
            </div>
            <div class="mt-2 flex gap-2">
                ${stepsData.steps.map(step => `
                    <span class="text-xs ${step.status === 'complete' ? 'text-green-500' : 
                                    step.status === 'current' ? 'text-blue-500' : 
                                    step.status === 'error' ? 'text-red-500' : 
                                    'text-gray-400'}">
                        ${step.label}
                    </span>
                `).join(' • ')}
            </div>
        `;
        statusContainer.appendChild(statusElement);
        
        // Trigger animation after a small delay
        setTimeout(() => {
            statusElement.classList.add('show');
        }, 100);
    } else {
        // Update existing notification (rest of the code remains the same)
        const messageEl = statusElement.querySelector('.text-gray-600');
        const progressBar = statusElement.querySelector('.bg-blue-600');
        const stepsEl = statusElement.querySelector('.mt-2');
        
        if (messageEl) messageEl.textContent = message;
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (stepsEl) {
            stepsEl.innerHTML = stepsData.steps.map(step => `
                <span class="text-xs ${step.status === 'complete' ? 'text-green-500' : 
                                    step.status === 'current' ? 'text-blue-500' : 
                                    step.status === 'error' ? 'text-red-500' : 
                                    'text-gray-400'}">
                    ${step.label}
                </span>
            `).join(' • ');
        }
    }
}

function removeUploadStatus(uploadId) {
    const statusElement = document.getElementById(`upload-${uploadId}`);
    if (statusElement) {
        statusElement.classList.remove('show');
        setTimeout(() => {
            statusElement.remove();
        }, 300);
    }
}

function handleUploadError(error, uploadId) {
    showUploadStatus('Upload failed', 0, {
        steps: [
            { id: 'prepare', label: 'Preparation failed', status: 'error' },
            { id: 'ipfs', label: 'Upload failed', status: 'error' }
        ]
    }, uploadId);
}

function renderMessage(senderId, content, timestamp) {
    const messageArea = document.getElementById('messageArea');
    const messageElement = document.createElement('div');
    messageElement.className = 'message';
    
    // Determine if the message is from the current user
    const senderLabel = Number(senderId) === Number(currentUserId) ? 'You' : 'Friend';
    const localtimestamp = new Date(timestamp).toLocaleString();
    
    // Parse the decrypted content
    let messageContent = '';
    let messageType = 'text';
    
    if (typeof content === 'object') {
        messageType = content.type || 'text';
        messageContent = content.content;
    } else {
        messageContent = content;
    }

    // Create message header
    let headerHTML = `
        <div class="message-header">
            <strong>${senderLabel}</strong>
            <small class="text-muted">${localtimestamp}</small>
        </div>
    `;

    // Create message content based on type
    let contentHTML = '';
    if (messageType === 'file') {
        const fileName = messageContent.filename || messageContent.split('/').pop();
        contentHTML = `
            <div class="message-content file-message">
                <i class="fas fa-file"></i>
                <a href="${messageContent}" download="${fileName}" target="_blank">
                    Download ${fileName}
                </a>
            </div>
        `;
    } else {
        contentHTML = `
            <div class="message-content">
                ${messageContent}
            </div>
        `;
    }

    messageElement.innerHTML = headerHTML + contentHTML;
    messageArea.appendChild(messageElement);
    messageArea.scrollTop = messageArea.scrollHeight;
}

function startChat(friendId, friendName) {
    currentChatFriendId = friendId;
    console.log('Starting chat with friend:', friendId, friendName);

    const currentChatNameElement = document.getElementById('currentChatName');
    if (currentChatNameElement) {
        currentChatNameElement.textContent = friendName;
    }

    const chatArea = document.getElementById('chatArea');
    if (chatArea) {
        chatArea.classList.remove('d-none');
    }

    // Clear existing messages
    const messageArea = document.getElementById('messageArea');
    messageArea.innerHTML = '';

    loadChatHistory(friendId);

    // Remove existing message listeners
    socket.off('new_message');

    // Create the room name using a consistent format
    const room = `chat_${Math.min(currentUserId, friendId)}_${Math.max(currentUserId, friendId)}`;
    console.log('Joining room:', room);
    
    // Leave previous room if any
    if (socket.currentRoom) {
        socket.emit('leave', { room: socket.currentRoom });
    }
    
    // Join new room
    socket.currentRoom = room;
    socket.emit('join', { room: room });

    // Add the new message listener
    socket.on('new_message', (data) => {
        console.log('Received message:', data);
        
        // Add message to chat
        addMessageToChat(data.sender_id, data.content, data.timestamp);
        
        // Update chat preview
        if (window.updateChatPreview) {
            updateChatPreview(
                data.sender_id === currentUserId ? data.recipient_id : data.sender_id,
                data.content
            );
        }
    });

    // Show the clear chat button
    const clearChatButton = document.getElementById('clearChatButton');
    if (clearChatButton) {
        clearChatButton.classList.remove('d-none');
    }

    setupFileSharing();
}

window.sendMessage = function(friendId, message) {
    if (!friendId || !message) return;
    
    const timestamp = new Date().toISOString();
    const room = `chat_${Math.min(currentUserId, friendId)}_${Math.max(currentUserId, friendId)}`;
    
    // Don't add message locally anymore - wait for socket response
    // This prevents duplication
    
    fetch('/api/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            friend_id: friendId,
            message: message,
            recipient_id: friendId,
            timestamp: timestamp,
            room: room,
            sender_id: currentUserId
        }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Server response:', data);
        document.getElementById('messageInput').value = '';
        if (data.error) {
            console.error('Error from server:', data.error);
        }
    })
    .catch(error => {
        console.error('Error sending message:', error);
    });
};

// Modify the loadChatHistory function to handle potentially cleared chat history
function loadChatHistory(friendId) {
    console.log('Loading chat history for friend:', friendId);
    
    // Clear previous chat
    const messageArea = document.getElementById('messageArea');
    messageArea.innerHTML = '';
    
    // Set current chat friend ID
    currentChatFriendId = Number(friendId);
    console.log('Set currentChatFriendId to:', currentChatFriendId);
    
    fetch(`/api/chat_history/${friendId}`)
        .then(response => response.json())
        .then(data => {
            if (data.messages && Array.isArray(data.messages)) {
                data.messages.forEach(msg => {
                    if (msg && msg.sender_id !== undefined && msg.content !== undefined) {
                        addMessageToChat(
                            msg.sender_id, 
                            msg.content,
                            msg.timestamp || new Date().toISOString()
                        );
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
            messageArea.innerHTML = '<p class="text-center text-gray-500 mt-4">Error loading chat history</p>';
        });
}

function getFileIcon(fileName) {
    // Get file extension
    const ext = fileName.split('.').pop().toLowerCase();
    
    // Define file type patterns
    const fileTypes = {
        // Images
        image: ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
        // Documents
        pdf: ['pdf'],
        word: ['doc', 'docx'],
        excel: ['xls', 'xlsx', 'csv'],
        powerpoint: ['ppt', 'pptx'],
        text: ['txt', 'rtf', 'md'],
        // Code
        code: ['js', 'py', 'java', 'cpp', 'c', 'cs', 'html', 'css', 'php', 'json', 'xml'],
        // Archives
        archive: ['zip', 'rar', '7z', 'tar', 'gz'],
        // Audio
        audio: ['mp3', 'wav', 'ogg', 'm4a', 'flac'],
        // Video
        video: ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv'],
        // Database
        database: ['sql', 'db', 'sqlite', 'mdb']
    };

    // Return appropriate icon class based on file type
    for (const [type, extensions] of Object.entries(fileTypes)) {
        if (extensions.includes(ext)) {
            switch (type) {
                case 'image':
                    return 'fa-file-image';
                case 'pdf':
                    return 'fa-file-pdf';
                case 'word':
                    return 'fa-file-word';
                case 'excel':
                    return 'fa-file-excel';
                case 'powerpoint':
                    return 'fa-file-powerpoint';
                case 'text':
                    return 'fa-file-lines';
                case 'code':
                    return 'fa-file-code';
                case 'archive':
                    return 'fa-file-zipper';
                case 'audio':
                    return 'fa-file-audio';
                case 'video':
                    return 'fa-file-video';
                case 'database':
                    return 'fa-database';
            }
        }
    }
    
    // Default file icon
    return 'fa-file';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function addMessageToChat(senderId, content, timestamp) {
    console.log('Adding message to chat:', { senderId, content, timestamp });
    
    // Ensure content is a string and handle objects
    let displayContent;
    try {
        if (typeof content === 'object') {
            displayContent = content.message || content.content || JSON.stringify(content);
        } else if (typeof content === 'string' && content.startsWith('{')) {
            const parsed = JSON.parse(content);
            displayContent = parsed.message || parsed.content || content;
        } else {
            displayContent = String(content || '');
        }
    } catch (e) {
        displayContent = String(content || '');
    }

    const messageArea = document.getElementById('messageArea');
    const messageElement = document.createElement('div');
    messageElement.className = `message flex ${Number(senderId) === Number(currentUserId) ? 'justify-end' : 'justify-start'}`;
    
    // Check if the message contains a file link
    const fileMatch = displayContent.match(/Shared file: \[Download\]\((\/api\/download_file\/[^\)]+)\)(.*)/);
    
    let messageHTML;
    if (fileMatch) {
        // Extract file information
        const filePath = fileMatch[1];
        const fileName = filePath.split('/').pop();
        const fileIcon = getFileIcon(fileName);
        
        messageHTML = `
            <div class="${Number(senderId) === Number(currentUserId) ? 
                'bg-primary text-white' : 
                'bg-gray-100 text-gray-900'} 
                rounded-lg px-4 py-3 max-w-[70%]">
                <div class="file-message group">
                    <div class="file-icon-wrapper">
                        <i class="fas ${fileIcon} text-2xl"></i>
                    </div>
                    <div class="flex flex-col">
                        <span class="text-sm font-medium truncate max-w-[200px]">${fileName}</span>
                        <a href="${filePath}" 
                           class="text-sm ${Number(senderId) === Number(currentUserId) ? 
                               'text-blue-100 hover:text-white' : 
                               'text-blue-600 hover:text-blue-800'} 
                           underline flex items-center gap-2 mt-1"
                           target="_blank"
                           download>
                            <i class="fas fa-download text-xs"></i>
                            <span>Download</span>
                        </a>
                    </div>
                </div>
                <p class="text-xs opacity-70 mt-2">
                    ${new Date(timestamp).toLocaleTimeString()}
                </p>
            </div>
        `;
    } else {
        // Regular message handling (unchanged)
        const escapedContent = displayContent
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');

        messageHTML = `
            <div class="${Number(senderId) === Number(currentUserId) ? 
                'bg-primary text-white' : 
                'bg-gray-100 text-gray-900'} 
                rounded-lg px-4 py-2 max-w-[70%]">
                <p class="text-sm">${escapedContent}</p>
                <p class="text-xs opacity-70 mt-1">
                    ${new Date(timestamp).toLocaleTimeString()}
                </p>
            </div>
        `;
    }

    messageElement.innerHTML = messageHTML;
    messageArea.appendChild(messageElement);
    messageArea.scrollTop = messageArea.scrollHeight;
}

function updateChatPreview(chatId, lastMessage) {
    console.log('Updating chat preview:', { chatId, lastMessage });
    
    let previewText;
    try {
        if (typeof lastMessage === 'object') {
            previewText = lastMessage.message || lastMessage.content || JSON.stringify(lastMessage);
        } else if (typeof lastMessage === 'string' && lastMessage.startsWith('{')) {
            const parsed = JSON.parse(lastMessage);
            previewText = parsed.message || parsed.content || lastMessage;
        } else {
            previewText = String(lastMessage || '');
        }
    } catch (e) {
        previewText = String(lastMessage || '');
    }

    const chatLink = document.querySelector(`[data-chat-id="${chatId}"]`);
    if (chatLink) {
        const previewElement = chatLink.querySelector('small');
        if (previewElement) {
            previewElement.textContent = previewText;
        }
    }
}

// Optional: Function to remove the last message (in case of error)
function removeLastMessage() {
    const messageArea = document.getElementById('messageArea');
    if (messageArea.lastChild) {
        messageArea.removeChild(messageArea.lastChild);
        console.log('Last message removed. Current message count:', messageArea.children.length);
    }
}

// Add this to hide the clear button when no chat is active
function endChat() {
    currentChatFriendId = null;
    document.getElementById('currentChatName').textContent = '';
    document.getElementById('chatArea').classList.add('d-none');
    document.getElementById('clearChatButton').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const messageInput = document.getElementById('messageInput');
            const message = messageInput.value.trim();
            if (message && currentChatFriendId) {
                sendMessage(currentChatFriendId, message);
                messageInput.value = '';
            }
        });
    }
    setupFileSharing();
});


// Add these new functions to handle the upload status UI
function hideUploadStatus() {
    const statusModal = document.getElementById('uploadStatusModal');
    if (statusModal) {
        statusModal.classList.add('hidden');
    }
}

// Add these functions to handle typing indicators
let typingTimeout;

function showTypingIndicator(friendId) {
    const messageArea = document.getElementById('messageArea');
    const existingIndicator = document.getElementById('typing-indicator');
    
    if (!existingIndicator) {
        const indicatorElement = document.createElement('div');
        indicatorElement.id = 'typing-indicator';
        indicatorElement.className = 'flex justify-start mb-4';
        indicatorElement.innerHTML = `
            <div class="bg-gray-100 rounded-lg px-4 py-2 max-w-[70%] shadow-sm">
                <div class="flex items-center gap-2">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        messageArea.appendChild(indicatorElement);
        messageArea.scrollTop = messageArea.scrollHeight;
    }
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Add typing event emitters
const messageInput = document.getElementById('messageInput');
messageInput.addEventListener('input', () => {
    if (currentChatFriendId) {
        socket.emit('typing', {
            room: `chat_${Math.min(currentUserId, currentChatFriendId)}_${Math.max(currentUserId, currentChatFriendId)}`,
            user_id: currentUserId
        });
        
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            socket.emit('stop_typing', {
                room: `chat_${Math.min(currentUserId, currentChatFriendId)}_${Math.max(currentUserId, currentChatFriendId)}`,
                user_id: currentUserId
            });
        }, 1000);
    }
});

// Add socket listeners for typing
socket.on('user_typing', (data) => {
    if (Number(data.user_id) !== Number(currentUserId)) {
        showTypingIndicator(data.user_id);
    }
});

socket.on('user_stop_typing', (data) => {
    if (Number(data.user_id) !== Number(currentUserId)) {
        removeTypingIndicator();
    }
});

// Add Socket.IO listeners for upload events
socket.on('upload_complete', (data) => {
    updateUploadStatus('Upload complete!', 100, {
        steps: [
            { id: 'prepare', label: 'File prepared', status: 'complete' },
            { id: 'ipfs', label: 'IPFS Upload complete', status: 'complete' }
        ]
    }, data.uploadId);

    // Add the file message to chat
    const message = `Shared file: [Download](${data.file_link})`;
    sendMessage(currentChatFriendId, message);

    // Clean up the upload status after a delay
    setTimeout(() => {
        removeUploadStatus(data.uploadId);
    }, 3000);
});

socket.on('upload_error', (data) => {
    handleUploadError(data.error, data.uploadId);
});

// Update the message display function to handle file messages
function displayMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.sender_id === currentUserId ? 'sent' : 'received'}`;
    
    let content = message.content;
    if (message.type === 'file') {
        // Create proper file download link
        content = `Shared file: <a href="${message.file_link}" 
            class="text-blue-500 hover:text-blue-700 underline" 
            download="${message.filename}">${message.filename}</a>`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-sender">${message.username}</div>
            <div class="message-text">${content}</div>
            <div class="message-time">${formatTime(message.timestamp)}</div>
        </div>
    `;
    
    document.getElementById('messageArea').appendChild(messageDiv);
    scrollToBottom();
}
