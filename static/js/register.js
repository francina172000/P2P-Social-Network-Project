document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('registerForm');
    const registrationStatus = document.getElementById('registrationStatus');
    const showPasswordCheckbox = document.getElementById('showPassword');
    const passwordInputs = document.querySelectorAll('input[type="password"]');

    // Show/Hide password functionality
    showPasswordCheckbox.addEventListener('change', function() {
        passwordInputs.forEach(input => {
            input.type = this.checked ? 'text' : 'password';
        });
    });

    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Validate passwords match
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        if (password !== confirmPassword) {
            alert('Passwords do not match!');
            return;
        }

        // Show loading status
        registrationStatus.style.display = 'flex';
        registrationStatus.querySelector('.status-message').textContent = 'Creating account...';

        // Create the request data
        const requestData = {
            username: document.getElementById('username').value,
            email: document.getElementById('email').value,
            password: password
        };

        // Log the data being sent (for debugging)
        console.log('Sending registration data:', requestData);

        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            console.log('Server response:', data); // Log the server response

            if (response.ok) {
                registrationStatus.querySelector('.status-message').textContent = data.message;
                setTimeout(() => {
                    window.location.href = '/login';
                }, 3000);
            } else {
                registrationStatus.querySelector('.status-message').textContent = 
                    data.error || 'Registration failed. Please try again.';
                setTimeout(() => {
                    registrationStatus.style.display = 'none';
                }, 3000);
            }
        } catch (error) {
            console.error('Registration error:', error); // Log any errors
            registrationStatus.querySelector('.status-message').textContent = 
                'An error occurred. Please try again.';
            setTimeout(() => {
                registrationStatus.style.display = 'none';
            }, 3000);
        }
    });
});