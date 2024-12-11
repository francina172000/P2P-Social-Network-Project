document.addEventListener('DOMContentLoaded', function() {
    const resetPasswordRequestForm = document.getElementById('resetPasswordRequestForm');
    const resetStatus = document.getElementById('resetStatus');

    resetPasswordRequestForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Show loading status
        resetStatus.style.display = 'flex';
        resetStatus.querySelector('.status-message').textContent = 'Sending reset link...';

        const email = document.getElementById('email').value;

        try {
            const response = await fetch('/reset_password_request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email: email }),
            });

            const data = await response.json();

            if (data.error) {
                resetStatus.querySelector('.status-message').textContent = data.error;
                setTimeout(() => {
                    resetStatus.style.display = 'none';
                }, 3000);
            } else {
                resetStatus.querySelector('.status-message').textContent = data.message;
                setTimeout(() => {
                    resetStatus.style.display = 'none';
                }, 3000);
            }
        } catch (error) {
            console.error('Error:', error);
            resetStatus.querySelector('.status-message').textContent = 'An error occurred. Please try again.';
            setTimeout(() => {
                resetStatus.style.display = 'none';
            }, 3000);
        }
    });
});