document.addEventListener('DOMContentLoaded', function() {
    const resetPasswordForm = document.getElementById('resetPasswordForm');
    const resetStatus = document.getElementById('resetStatus');
    const showPasswordCheckbox = document.getElementById('showPassword');
    const newPasswordInput = document.getElementById('new_password');
    const confirmPasswordInput = document.getElementById('confirm_password');

    // Show/Hide password functionality
    showPasswordCheckbox.addEventListener('change', function() {
        const type = this.checked ? 'text' : 'password';
        newPasswordInput.type = type;
        confirmPasswordInput.type = type;
    });

    resetPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const new_password = newPasswordInput.value;
        const confirm_password = confirmPasswordInput.value;
        const token = document.getElementById('token').value;

        if (new_password !== confirm_password) {
            document.getElementById('message').innerHTML = '<div class="alert alert-danger">Passwords do not match.</div>';
            return;
        }

        // Show loading status
        resetStatus.style.display = 'flex';
        resetStatus.querySelector('.status-message').textContent = 'Updating password...';

        try {
            const response = await fetch(`/reset_password/${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    new_password: new_password
                }),
            });

            const data = await response.json();

            if (data.error) {
                resetStatus.querySelector('.status-message').textContent = data.error;
                setTimeout(() => {
                    resetStatus.style.display = 'none';
                }, 3000);
            } else {
                resetStatus.querySelector('.status-message').textContent = 'Password updated successfully! Redirecting...';
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
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