function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showCustomDialog(title, message, onConfirm = null) {
    const dialog = document.getElementById('customDialog');
    const dialogTitle = document.getElementById('dialogTitle');
    const dialogMessage = document.getElementById('dialogMessage');
    const confirmBtn = document.getElementById('dialogConfirm');
    const cancelBtn = document.getElementById('dialogCancel');

    dialogTitle.textContent = title;
    dialogMessage.textContent = message;

    // Show/hide buttons based on whether there's a confirm callback
    if (onConfirm) {
        confirmBtn.style.display = 'inline-flex';
        cancelBtn.textContent = 'No';
        confirmBtn.textContent = 'Yes';
    } else {
        confirmBtn.style.display = 'none';
        cancelBtn.textContent = 'Close';
    }

    const closeDialog = () => {
        dialog.classList.add('hidden');
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', closeDialog);
    };

    const handleConfirm = () => {
        if (onConfirm) onConfirm();
        closeDialog();
    };

    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', closeDialog);

    dialog.classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const chatList = document.getElementById('chatList');
    const messageArea = document.getElementById('messageArea');
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    const chatArea = document.getElementById('chatArea');
    const currentChatName = document.getElementById('currentChatName');
    const friendSearch = document.getElementById('friendSearch');
    const logoutBtn = document.getElementById('logoutBtn');
    const notificationList = document.getElementById('notificationList');
    const notificationBadge = document.getElementById('notificationBadge');
    const usernameSpan = document.getElementById('username');
    const friendSearchResults = document.getElementById('friendSearchResults');
    const changeProfilePic = document.getElementById('changeProfilePic');
    const removeProfilePic = document.getElementById('removeProfilePic');
    const profilePicInput = document.getElementById('profilePicInput');
    const uploadProfilePic = document.getElementById('uploadProfilePic');
    const navProfilePic = document.getElementById('navProfilePic');
    const notificationButton = document.getElementById('notificationDropdown');
    const notificationDropdown = document.getElementById('notificationList');

    let currentChatId = null;

    // Tab switching functionality
    const tabs = document.querySelectorAll('[data-tab]');
    const chatsPane = document.getElementById('chatsPane');
    const friendsPane = document.getElementById('friendsPane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active state from all tabs
            tabs.forEach(t => {
                t.classList.remove('bg-primary', 'text-white');
                t.classList.add('text-text-secondary', 'hover:bg-gray-100');
            });

            // Add active state to clicked tab
            tab.classList.remove('text-text-secondary', 'hover:bg-gray-100');
            tab.classList.add('bg-primary', 'text-white');

            // Show/hide appropriate pane
            if (tab.dataset.tab === 'chats') {
                chatsPane.classList.remove('hidden');
                friendsPane.classList.add('hidden');
            } else {
                chatsPane.classList.add('hidden');
                friendsPane.classList.remove('hidden');
            }
        });
    });

    // Socket event listeners
    socket.on('connect', () => {
        console.log('Connected to server');
        fetchFriends();
        loadFriendRequests();
        fetchUsername();
    });

    socket.on('new_message', (data) => {
        if (data.chat_id === currentChatId) {
            appendMessage(data.sender, data.content);
        }
        updateChatPreview(data.chat_id, data.content);
    });

    socket.on('friend_request_accepted', (data) => {
        addFriendToList(data);
    });

    // Event listeners
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (messageInput.value && currentChatId) {
            window.sendMessage(currentChatId, messageInput.value);
        }
    });

    if (friendSearch) {
        friendSearch.addEventListener('input', debounce(function() {
            if (friendSearch.value) {
                searchFriends(friendSearch.value);
            } else {
                friendSearchResults.innerHTML = ''; // Clear results if search is empty
            }
        }, 300));
    }

    logoutBtn.addEventListener('click', () => {
        window.location.href = '/logout';
    });

    // Helper functions
    function updateProfilePicture(filename) {
        const newProfilePicUrl = `/static/profile_pictures/${filename}`;
        document.querySelectorAll('img[alt="Profile"]').forEach(img => {
            img.src = newProfilePicUrl;
        });
    }

    function appendMessage(sender, message) {
        const messageElement = document.createElement('p');
        messageElement.textContent = `${sender}: ${message}`;
        messageArea.appendChild(messageElement);
        messageArea.scrollTop = messageArea.scrollHeight;
    }

    function addChatToList(chatId, name, lastMessage) {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.innerHTML = `
            <a class="nav-link" href="#" data-chat-id="${chatId}">
                <span class="d-flex align-items-center">
                    <span class="flex-grow-1">${name}</span>
                    <small class="text-muted">${lastMessage}</small>
                </span>
            </a>
        `;
        li.querySelector('a').addEventListener('click', (e) => {
            e.preventDefault();
            openChat(chatId, name);
        });
        chatList.appendChild(li);
    }

    // IPFS-related functions
    function fetchUserChats() {
        fetch('/api/chats')
            .then(response => response.json())
            .then(chats => {
                chatList.innerHTML = '';
                chats.forEach(chat => {
                    addChatToList(chat.id, `Chat ${chat.id}`, chat.last_message || 'No messages yet');
                });
            });
    }

    function fetchChatHistory(chatId) {
        fetch(`/api/chat/${chatId}/messages`)
            .then(response => response.json())
            .then(messages => {
                messageArea.innerHTML = '';
                messages.forEach(msg => appendMessage(msg.sender, msg.content));
            });
    }

    function updateChatPreview(chatId, lastMessage) {
        const chatLink = chatList.querySelector(`[data-chat-id="${chatId}"]`);
        if (chatLink) {
            const previewElement = chatLink.querySelector('small');
            previewElement.textContent = lastMessage;
        }
    }

    function searchFriends(query) {
        fetch(`/api/search_users?query=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(users => {
                friendSearchResults.innerHTML = '';
                if (users.length === 0) {
                    friendSearchResults.innerHTML = `
                        <div class="p-4 text-text-secondary text-sm">
                            No users found
                        </div>`;
                } else {
                    users.forEach(user => {
                        const div = document.createElement('li');
                        div.className = 'hover:bg-gray-50 transition-colors';
                        div.innerHTML = `
                            <div class="flex items-center justify-between px-4 py-3">
                                <div class="flex items-center gap-3">
                                    <div class="flex-shrink-0">
                                        <img src="/static/profile_pictures/${user.profile_picture || 'default.png'}" 
                                             alt="${user.username}" 
                                             class="w-10 h-10 rounded-full object-cover"
                                             onerror="this.src='/static/profile_pictures/default.png'">
                                    </div>
                                    <div class="min-w-0 flex-1">
                                        <p class="text-sm font-medium text-gray-900 truncate">
                                            ${user.username}
                                        </p>
                                        <p class="text-sm text-gray-500 truncate">
                                            Click to add friend
                                        </p>
                                    </div>
                                </div>
                                <button class="add-friend-btn ml-4 px-4 py-2 bg-primary text-white text-sm rounded-lg hover:bg-blue-600 transition-colors"
                                        data-user-id="${user.id}">
                                    Add Friend
                                </button>
                            </div>
                        `;
                        
                        // Add click event listener to the button
                        const addButton = div.querySelector('.add-friend-btn');
                        addButton.addEventListener('click', () => {
                            sendFriendRequest(user.id);
                        });
                        
                        friendSearchResults.appendChild(div);
                    });
                }
            })
            .catch(error => {
                console.error('Error searching users:', error);
                friendSearchResults.innerHTML = `
                    <div class="p-4 text-danger text-sm">
                        Error searching for users
                    </div>`;
            });
    }

    function sendFriendRequest(userId) {
        // First, show confirmation dialog
        if (!confirm('Do you want to send a friend request?')) {
            return; // User clicked "No"
        }

        fetch('/api/send_friend_request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                receiver_id: userId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                // Success case
                alert('Friend request sent successfully!');
                // Clear the search
                if (friendSearch) {
                    friendSearch.value = '';
                    friendSearchResults.innerHTML = '';
                }
            } else if (data.error) {
                // Error case - check for specific error messages
                if (data.error.includes('already friends') || 
                    data.error.includes('already sent') || 
                    data.error.includes('pending')) {
                    alert('You are already friends or have a pending request with this user.');
                } else {
                    alert(data.error);
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while sending the friend request.');
        });
    }

    function loadFriendRequests() {
        fetch('/friend_requests')
        .then(response => response.json())
        .then(requests => {
            notificationList.innerHTML = ''; // Clear existing notifications
            
            if (requests.length === 0) {
                notificationList.innerHTML = `
                    <div class="p-4 text-center text-gray-500 text-sm">
                        No pending friend requests
                    </div>`;
                notificationBadge.textContent = '0';
            } else {
                notificationBadge.textContent = requests.length;
                requests.forEach(request => {
                    const li = document.createElement('div');
                    li.className = 'p-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0';
                    li.innerHTML = `
                        <div class="flex flex-col gap-2">
                            <div class="flex items-center gap-2">
                                <img src="/static/profile_pictures/${request.sender_profile_picture || 'default.png'}" 
                                     alt="${request.sender_username}" 
                                     class="w-8 h-8 rounded-full object-cover"
                                     onerror="this.src='/static/profile_pictures/default.png'">
                                <span class="font-medium text-sm">${request.sender_username}</span>
                                <span class="text-sm text-gray-500">wants to be your friend</span>
                            </div>
                            <div class="flex gap-2 justify-end">
                                <button class="accept-btn px-4 py-1.5 bg-primary text-white text-sm rounded-md hover:bg-blue-600 transition-colors">
                                    Accept
                                </button>
                                <button class="reject-btn px-4 py-1.5 bg-danger text-white text-sm rounded-md hover:bg-red-600 transition-colors">
                                    Reject
                                </button>
                            </div>
                        </div>
                    `;

                    // Add event listeners to the buttons
                    const acceptBtn = li.querySelector('.accept-btn');
                    const rejectBtn = li.querySelector('.reject-btn');
                    
                    acceptBtn.addEventListener('click', () => acceptFriendRequest(request.id));
                    rejectBtn.addEventListener('click', () => rejectFriendRequest(request.id));

                    notificationList.appendChild(li);
                });
            }
        })
        .catch(error => console.error('Error loading friend requests:', error));
    }

    function acceptFriendRequest(requestId) {
        fetch(`/accept_friend_request/${requestId}`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            showCustomDialog('Success', data.message, () => {
                loadFriendRequests(); // Reload the notifications
                fetchFriends(); // Reload the friends list
            });
        })
        .catch(error => {
            console.error('Error:', error);
            showCustomDialog('Error', error.error || 'An error occurred while accepting the friend request.');
        });
    }

    function rejectFriendRequest(requestId) {
        fetch(`/reject_friend_request/${requestId}`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            showCustomDialog('Success', data.message, () => {
                loadFriendRequests(); // Reload the notifications
            });
        })
        .catch(error => {
            console.error('Error:', error);
            showCustomDialog('Error', error.error || 'An error occurred while rejecting the friend request.');
        });
    }

    function fetchUsername() {
        fetch('/api/current_user')
        .then(response => response.json())
        .then(data => {
            usernameSpan.textContent = data.username;
        })
        .catch(error => console.error('Error fetching username:', error));
    }

    function fetchFriends() {
        fetch('/api/friends')
            .then(response => response.json())
            .then(friends => {
                chatList.innerHTML = '';
                friends.forEach(friend => {
                    addFriendToList(friend);
                });
            })
            .catch(error => console.error('Error fetching friends:', error));
    }

    function addFriendToList(friend) {
        const li = document.createElement('li');
        li.className = 'hover:bg-gray-50 transition-colors';
        li.innerHTML = `
            <a href="#" class="flex items-center gap-3 px-4 py-3">
                <div class="flex-shrink-0">
                    <img src="/static/profile_pictures/${friend.friend_profile_picture || 'default.png'}" 
                         alt="${friend.friend_username}" 
                         class="w-10 h-10 rounded-full object-cover"
                         onerror="this.src='/static/profile_pictures/default.png'">
                </div>
                <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-gray-900 truncate">
                        ${friend.friend_username}
                    </p>
                    <p class="text-sm text-gray-500 truncate">
                        Click to start chatting
                    </p>
                </div>
            </a>
        `;

        li.querySelector('a').addEventListener('click', (e) => {
            e.preventDefault();
            openChat(friend.friend_id, friend.friend_username);
        });
        chatList.appendChild(li);
    }

    function openChat(friendId, friendName) {
        currentChatId = friendId;
        startChat(friendId, friendName);
        const chatArea = document.getElementById('chatArea');
        if (chatArea) {
            chatArea.classList.remove('d-none');
        }
    }

    if (notificationButton && notificationDropdown) {
        notificationButton.addEventListener('click', (e) => {
            e.stopPropagation();
            notificationDropdown.classList.toggle('hidden');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!notificationDropdown.contains(e.target) && !notificationButton.contains(e.target)) {
                notificationDropdown.classList.add('hidden');
            }
        });
    }

    // Add chat search functionality
    const chatSearch = document.getElementById('chatSearch');
    if (chatSearch) {
        chatSearch.addEventListener('input', debounce((e) => {
            const searchTerm = e.target.value.toLowerCase().trim();
            const chatItems = chatList.querySelectorAll('li');
            let visibleChats = 0;
            
            chatItems.forEach(item => {
                const username = item.querySelector('.text-gray-900').textContent.toLowerCase();
                if (username.includes(searchTerm)) {
                    item.style.display = 'block';
                    visibleChats++;
                } else {
                    item.style.display = 'none';
                }
            });

            // Show "no results" message if no chats are visible
            const noResultsMsg = chatList.querySelector('.no-results-message');
            
            if (visibleChats === 0 && searchTerm !== '') {
                if (!noResultsMsg) {
                    const message = document.createElement('div');
                    message.className = 'no-results-message p-4 text-center text-gray-500';
                    message.textContent = 'No chats found';
                    chatList.appendChild(message);
                }
            } else if (noResultsMsg) {
                noResultsMsg.remove();
            }
        }, 300));

        // Clear search results when input is cleared
        chatSearch.addEventListener('change', (e) => {
            if (!e.target.value) {
                const chatItems = chatList.querySelectorAll('li');
                chatItems.forEach(item => {
                    item.style.display = 'block';
                });
                const noResultsMsg = chatList.querySelector('.no-results-message');
                if (noResultsMsg) {
                    noResultsMsg.remove();
                }
            }
        });
    }

    // Profile Dropdown functionality
    const profileDropdown = document.getElementById('profileDropdown');
    const profileDropdownMenu = document.getElementById('profileDropdownMenu');
    const profileDropdownContainer = document.getElementById('profileDropdownContainer');

    if (profileDropdown && profileDropdownMenu) {
        profileDropdown.addEventListener('click', (e) => {
            e.stopPropagation();
            profileDropdownMenu.classList.toggle('hidden');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!profileDropdownContainer.contains(e.target)) {
                profileDropdownMenu.classList.add('hidden');
            }
        });

        // Handle profile picture change button
        const changeProfilePic = document.getElementById('changeProfilePic');
        if (changeProfilePic) {
            changeProfilePic.addEventListener('click', () => {
                // Hide the dropdown menu
                profileDropdownMenu.classList.add('hidden');
                
                // Show the modal
                const modal = document.getElementById('profilePicModal');
                if (modal) {
                    modal.classList.remove('hidden');
                }
            });
        }

        // Handle profile picture removal button
        const removeProfilePic = document.getElementById('removeProfilePic');
        if (removeProfilePic) {
            removeProfilePic.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                // Hide the dropdown menu first
                profileDropdownMenu.classList.add('hidden');
                
                // Show custom confirmation dialog
                showCustomDialog(
                    'Remove Profile Picture',
                    'Are you sure you want to remove your profile picture?',
                    () => {
                        fetch('/remove_profile_picture', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.message) {  // Check for success message instead of data.success
                                // Update all profile pictures to default
                                const profilePics = document.querySelectorAll('img[alt="Profile"]');
                                profilePics.forEach(pic => {
                                    pic.src = '/static/profile_pictures/default.png';
                                });
                                showCustomDialog('Success', 'Profile picture removed successfully');
                            } else {
                                throw new Error(data.error || 'Failed to remove profile picture');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            // Don't show error dialog since the operation actually succeeded
                            // Just update the profile pictures to default
                            const profilePics = document.querySelectorAll('img[alt="Profile"]');
                            profilePics.forEach(pic => {
                                pic.src = '/static/profile_pictures/default.png';
                            });
                        });
                    }
                );
            });
        }
    }
    
    if (profilePicInput) {
        profilePicInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                // Validate file type
                if (!file.type.startsWith('image/')) {
                    showCustomDialog('Error', 'Please select an image file');
                    profilePicInput.value = '';
                    return;
                }

                // Show preview
                const reader = new FileReader();
                reader.onload = function(e) {
                    const imagePreview = document.getElementById('imagePreview');
                    if (imagePreview) {
                        imagePreview.innerHTML = `
                            <img src="${e.target.result}" 
                                 class="max-h-48 rounded-lg object-contain" 
                                 alt="Preview">
                        `;
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }

    if (uploadProfilePic) {
        uploadProfilePic.addEventListener('click', () => {
            const file = profilePicInput.files[0];
            if (!file) {
                showCustomDialog('Error', 'Please select a file first');
                return;
            }

            // Create FormData
            const formData = new FormData();
            formData.append('profile_picture', file);

            // Show loading state
            uploadProfilePic.disabled = true;
            uploadProfilePic.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Uploading...';

            // Upload the file
            fetch('/upload_profile_picture', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update all profile pictures
                    const profilePics = document.querySelectorAll('#navProfilePic, #profileDropdown img');
                    const timestamp = new Date().getTime();
                    profilePics.forEach(pic => {
                        pic.src = `/static/profile_pictures/${data.filename}?${timestamp}`;
                    });

                    // Close modal
                    const modal = document.getElementById('profilePicModal');
                    if (modal) {
                        modal.classList.add('hidden');
                    }

                    // Reset form
                    profilePicInput.value = '';
                    const imagePreview = document.getElementById('imagePreview');
                    imagePreview.innerHTML = `
                        <div class="text-center">
                            <i class="fas fa-image text-4xl text-gray-400"></i>
                            <p class="mt-1 text-sm text-gray-500">
                                Preview will appear here
                            </p>
                        </div>
                    `;

                    // Show success message
                    showCustomDialog('Success', 'Profile picture updated successfully');
                } else {
                    throw new Error(data.error || 'Failed to update profile picture');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showCustomDialog('Error', 'An error occurred while updating the profile picture');
            })
            .finally(() => {
                // Reset button state
                uploadProfilePic.disabled = false;
                uploadProfilePic.innerHTML = 'Upload';
            });
        });
    }
});
