document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loginStatus = document.getElementById('loginStatus');
    const showPasswordCheckbox = document.getElementById('showPassword');
    const passwordInput = document.getElementById('password');

    // Show/Hide password functionality
    showPasswordCheckbox.addEventListener('change', function() {
        passwordInput.type = this.checked ? 'text' : 'password';
    });

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Show loading status
        loginStatus.style.display = 'flex';
        loginStatus.querySelector('.status-message').textContent = 'Signing in...';

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    identifier: document.getElementById('identifier').value,
                    password: passwordInput.value
                })
            });

            const data = await response.json();

            if (response.ok) {
                loginStatus.querySelector('.status-message').textContent = 'Login successful!';
                setTimeout(() => {
                    window.location.href = '/dashboard';  // or wherever you want to redirect after login
                }, 1000);
            } else {
                loginStatus.querySelector('.status-message').textContent = data.message || 'Invalid credentials';
                setTimeout(() => {
                    loginStatus.style.display = 'none';
                }, 3000);
            }
        } catch (error) {
            loginStatus.querySelector('.status-message').textContent = 'An error occurred. Please try again.';
            setTimeout(() => {
                loginStatus.style.display = 'none';
            }, 3000);
        }
    });

    // Add input validation and real-time feedback
    const identifier = document.getElementById('identifier');
    identifier.addEventListener('input', function() {
        if (this.value.length < 3) {
            this.classList.add('is-invalid');
        } else {
            this.classList.remove('is-invalid');
        }
    });

    passwordInput.addEventListener('input', function() {
        if (this.value.length < 8) {
            this.classList.add('is-invalid');
        } else {
            this.classList.remove('is-invalid');
        }
    });
});