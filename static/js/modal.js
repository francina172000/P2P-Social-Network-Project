class Modal {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        this.isOpen = false;
        
        // Bind methods
        this.open = this.open.bind(this);
        this.close = this.close.bind(this);
        this.handleEscape = this.handleEscape.bind(this);
        this.handleClickOutside = this.handleClickOutside.bind(this);
        
        // Set up event listeners
        if (this.modal) {
            // Close button listeners
            const closeButtons = this.modal.querySelectorAll('[data-modal-close]');
            closeButtons.forEach(button => {
                button.addEventListener('click', this.close);
            });
            
            // Click outside listener
            this.modal.addEventListener('click', this.handleClickOutside);
        }
    }

    open() {
        if (!this.modal) return;
        
        // Show modal
        this.modal.classList.remove('hidden');
        
        // Add animation classes
        requestAnimationFrame(() => {
            // Backdrop animation
            const backdrop = this.modal.querySelector('.bg-gray-500');
            backdrop.classList.add('opacity-75');
            backdrop.classList.remove('opacity-0');

            // Modal content animation
            const content = this.modal.querySelector('.transform');
            content.classList.add('translate-y-0', 'opacity-100');
            content.classList.remove('translate-y-4', 'opacity-0');
        });

        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        this.isOpen = true;
        
        // Add escape key listener
        document.addEventListener('keydown', this.handleEscape);
        
        // Trigger open event
        const event = new CustomEvent('modal:open');
        this.modal.dispatchEvent(event);
    }

    close() {
        if (!this.modal) return;
        
        // Add closing animations
        const backdrop = this.modal.querySelector('.bg-gray-500');
        const content = this.modal.querySelector('.transform');

        // Animate out
        backdrop.classList.add('opacity-0');
        backdrop.classList.remove('opacity-75');
        content.classList.add('translate-y-4', 'opacity-0');
        content.classList.remove('translate-y-0', 'opacity-100');

        // Hide modal after animation
        setTimeout(() => {
            this.modal.classList.add('hidden');
            document.body.style.overflow = '';
        }, 200);

        this.isOpen = false;
        
        // Remove escape key listener
        document.removeEventListener('keydown', this.handleEscape);
        
        // Trigger close event
        const event = new CustomEvent('modal:close');
        this.modal.dispatchEvent(event);
    }

    handleEscape(event) {
        if (event.key === 'Escape' && this.isOpen) {
            this.close();
        }
    }

    handleClickOutside(event) {
        if (this.isOpen && event.target === this.modal) {
            this.close();
        }
    }
}

// Initialize modals
document.addEventListener('DOMContentLoaded', () => {
    // Profile Picture Modal
    const profilePicModal = new Modal('profilePicModal');
    const changeProfilePicBtn = document.getElementById('changeProfilePic');
    if (changeProfilePicBtn) {
        changeProfilePicBtn.addEventListener('click', (e) => {
            e.preventDefault();
            profilePicModal.open();
        });
    }

    // Blockchain Status Modal
    const blockchainModal = new Modal('blockchainStatusModal');
    window.blockchainModal = blockchainModal; // Export for use in other files
    
    // Image preview functionality
    const profilePicInput = document.getElementById('profilePicInput');
    const imagePreview = document.getElementById('imagePreview');
    
    if (profilePicInput && imagePreview) {
        profilePicInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    imagePreview.innerHTML = `
                        <div class="relative w-full h-48">
                            <img src="${e.target.result}" 
                                 alt="Preview" 
                                 class="w-full h-full object-contain rounded-lg">
                            <button type="button"
                                    class="absolute top-2 right-2 p-1 bg-gray-800 bg-opacity-50 rounded-full text-white hover:bg-opacity-75 transition-opacity"
                                    onclick="clearImagePreview()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    `;
                };
                reader.readAsDataURL(file);
            }
        });
    }
});

// Clear image preview
window.clearImagePreview = function() {
    const imagePreview = document.getElementById('imagePreview');
    const profilePicInput = document.getElementById('profilePicInput');
    
    if (imagePreview) {
        imagePreview.innerHTML = `
            <div class="text-center">
                <i class="fas fa-image text-4xl text-gray-400"></i>
                <p class="mt-1 text-sm text-gray-500">
                    Preview will appear here
                </p>
            </div>
        `;
    }
    if (profilePicInput) {
        profilePicInput.value = '';
    }
};

// Loading state for blockchain modal
window.showBlockchainLoading = function(message) {
    const messageElement = document.getElementById('blockchainStatusMessage');
    if (messageElement) {
        messageElement.innerHTML = `
            <div class="flex flex-col items-center">
                <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mb-4"></div>
                <p>${message}</p>
            </div>
        `;
    }
    window.blockchainModal.open();
};

// Update blockchain modal message
window.updateBlockchainMessage = function(message, isSuccess = true) {
    const messageElement = document.getElementById('blockchainStatusMessage');
    if (messageElement) {
        messageElement.innerHTML = `
            <div class="flex flex-col items-center">
                <i class="fas fa-${isSuccess ? 'check-circle text-success' : 'exclamation-circle text-danger'} text-3xl mb-4"></i>
                <p>${message}</p>
            </div>
        `;
    }
};