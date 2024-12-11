class CommunityFileSharing {
    constructor(socket) {
        this.socket = socket;
        this.downloadQueue = new Map();
        this.initialized = false;
        this.boundHandleFileSelect = this.handleFileSelect.bind(this);
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeUI());
        } else {
            this.initializeUI();
        }
    }

    initializeUI() {
        if (this.initialized) return;
        
        const messageForm = document.getElementById('messageForm');
        if (!messageForm) {
            console.warn('Message form not found');
            return;
        }

        const fileButton = document.getElementById('fileButton');
        const fileInput = document.getElementById('communityFileInput');

        if (fileButton && fileInput) {
            const newFileButton = fileButton.cloneNode(true);
            const newFileInput = fileInput.cloneNode(true);
            fileButton.parentNode.replaceChild(newFileButton, fileButton);
            fileInput.parentNode.replaceChild(newFileInput, fileInput);
            
            newFileButton.addEventListener('click', (e) => {
                e.preventDefault();
                newFileInput.click();
            });
            newFileInput.addEventListener('change', this.boundHandleFileSelect);
        }

        this.setupMessageListener();
        this.initialized = true;
    }

    async handleFileSelect(e) {
        const files = e.target.files;
        if (!files.length || !currentCommunityId) return;

        try {
            for (const file of files) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('community_id', currentCommunityId);

                window.communityHelpers.showUploadStatus(file.name, 0);

                const response = await fetch('/api/community/share_file', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) throw new Error('Upload failed');
                const result = await response.json();

                window.communityHelpers.showUploadStatus(file.name, 100);
                setTimeout(() => window.communityHelpers.removeUploadStatus(file.name), 2000);
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            alert('Failed to upload file(s)');
        }

        e.target.value = '';
    }

    handleFileDownload(fileHash, fileName, communityId) {
        if (!fileHash || !fileName || !communityId) {
            console.error('Missing required parameters:', { fileHash, fileName, communityId });
            return;
        }

        const downloadUrl = `/api/community/download_file/${encodeURIComponent(fileHash)}/${encodeURIComponent(fileName)}?community_id=${communityId}`;
        
        console.log('Download URL:', downloadUrl);

        fetch(downloadUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = fileName;
                document.body.appendChild(link);
                link.click();
                
                setTimeout(() => {
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(url);
                }, 100);
            })
            .catch(error => {
                console.error('Download error:', error);
                alert('Failed to download file. Please try again.');
            });
    }

    setupMessageListener() {
        this.socket.on('community_message', (message) => {
            if (message.fileInfo) {
                setTimeout(() => {
                    const messageElement = document.querySelector(`[data-message-id="${message.id}"]`);
                    if (messageElement) {
                        const fileLink = messageElement.querySelector('.file-link');
                        if (fileLink) {
                            fileLink.addEventListener('click', (e) => {
                                e.preventDefault();
                                const fileHash = message.fileInfo.hash;
                                const fileName = message.fileInfo.name;
                                if (!fileHash) {
                                    console.error('File hash is missing:', message.fileInfo);
                                    return;
                                }
                                this.handleFileDownload(fileHash, fileName, currentCommunityId);
                            });
                        }
                    }
                }, 100);
            }
        });
    }
}