const socket = io();
let myFiles = new Map();

// UI Elements
const fileInput = document.getElementById('fileInput');
const selectedFile = document.getElementById('selectedFile');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const searchResults = document.getElementById('searchResults');
const myFilesDiv = document.getElementById('myFiles');
const peerCount = document.getElementById('peerCount');

// File Input Handler
fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Check file size (10MB limit for example)
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
    if (file.size > MAX_FILE_SIZE) {
        showNotification('File size too large. Maximum size is 10MB', 'error');
        fileInput.value = '';
        return;
    }

    selectedFile.textContent = `Selected: ${file.name}`;
    showLoading('Uploading file...');

    try {
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);

        // Upload file using HTTP POST
        const response = await fetch('/api/flood_upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            showNotification('File uploaded successfully!', 'success');
            // Clear file input
            fileInput.value = '';
            selectedFile.textContent = '';
            
            // Update my files list
            myFiles.set(data.fileId, {
                name: data.name,
                size: data.size,
                fileId: data.fileId
            });
            updateMyFilesList();
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showNotification(error.message, 'error');
    } finally {
        hideLoading();
    }
});

// Search Handler
searchBtn.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (!query) return;

    searchResults.innerHTML = '<div class="text-center">Searching...</div>';
    socket.emit('flood_search', { query });
});

// Socket Events
socket.on('flood_peer_count', (data) => {
    peerCount.textContent = data.count;
});

socket.on('flood_search_results', (data) => {
    displaySearchResults(data.results);
});

socket.on('flood_file_shared', (data) => {
    if (data.success) {
        showNotification('File shared successfully!', 'success');
        fileInput.value = '';
        selectedFile.textContent = '';
        hideLoading();
        
        // Update my files list
        myFiles.set(data.fileId, {
            name: data.name,
            size: data.size,
            fileId: data.fileId
        });
        updateMyFilesList();
    }
});

// Helper Functions
function displaySearchResults(results) {
    if (!results || results.length === 0) {
        searchResults.innerHTML = '<div class="text-center">No results found</div>';
        return;
    }

    searchResults.innerHTML = results.map(file => `
        <div class="flex justify-between items-center p-2 border-b">
            <div>
                <div class="font-medium">${file.name}</div>
                <div class="text-sm text-gray-500">Size: ${formatSize(file.size)}</div>
                <div class="text-xs text-gray-400">From: ${file.peer}</div>
            </div>
            <button onclick="downloadFile('${file.fileId}')"
                    class="bg-blue-500 hover:bg-blue-700 text-white text-sm py-1 px-3 rounded flex items-center gap-2">
                <i class="fas fa-download"></i>
                Download
            </button>
        </div>
    `).join('');
}

function updateMyFilesList() {
    if (myFiles.size === 0) {
        myFilesDiv.innerHTML = '<div class="text-center">No files shared yet</div>';
        return;
    }

    myFilesDiv.innerHTML = Array.from(myFiles.values()).map(file => `
        <div class="flex justify-between items-center p-2 border-b">
            <div>
                <div class="font-medium">${file.name}</div>
                <div class="text-sm text-gray-500">Size: ${formatSize(file.size)}</div>
            </div>
            <button onclick="removeFile('${file.fileId}')"
                    class="text-red-500 hover:text-red-700">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `).join('');
}

function formatSize(bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
}

// Global Functions
window.downloadFile = function(fileId) {
    showLoading('Downloading file...');
    
    // Create a hidden anchor element for download
    const downloadLink = document.createElement('a');
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    
    // Set the download URL
    downloadLink.href = `/api/flood_download/${fileId}`;
    downloadLink.click();
    document.body.removeChild(downloadLink);
    hideLoading();
};

window.removeFile = function(fileId) {
    if (!confirm('Remove this shared file?')) return;
    socket.emit('flood_remove_file', { fileId });
    myFiles.delete(fileId);
    updateMyFilesList();
};

// Add these helper functions
function showLoading(message = 'Uploading...') {
    const loadingDiv = document.getElementById('loadingOverlay');
    const loadingText = loadingDiv.querySelector('p');
    loadingText.textContent = message;
    loadingDiv.classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// Add notification function if not already present
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 
        'bg-blue-500'
    } text-white z-50`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}

// Add socket listener for download errors
socket.on('download_error', (data) => {
    hideLoading();
    showNotification(data.error, 'error');
});