document.addEventListener('DOMContentLoaded', () => {
    const loginView = document.getElementById('loginView');
    const loggedInView = document.getElementById('loggedInView');
    const status = document.getElementById('status');

    // Check if token exists
    chrome.storage.local.get(['token'], function(result) {
        if (result.token) {
            loginView.style.display = 'none';
            loggedInView.style.display = 'block';
        }
    });

    document.getElementById('loginBtn').addEventListener('click', async () => {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        status.innerText = 'Cargando...';

        try {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            const res = await fetch('http://localhost:8000/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });

            const data = await res.json();
            
            if (res.ok) {
                chrome.storage.local.set({ token: data.access_token }, () => {
                    loginView.style.display = 'none';
                    loggedInView.style.display = 'block';
                    status.innerText = '';
                });
            } else {
                status.innerText = data.detail || 'Error de credenciales';
            }
        } catch (e) {
            status.innerText = 'Error contactando al servidor';
        }
    });

    document.getElementById('logoutBtn').addEventListener('click', () => {
        chrome.storage.local.remove(['token'], () => {
            loginView.style.display = 'block';
            loggedInView.style.display = 'none';
        });
    });
});
