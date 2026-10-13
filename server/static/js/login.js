const loginForm = document.getElementById('loginForm');
const loginBtn  = document.getElementById('loginBtn');

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  loginBtn.disabled    = true;
  loginBtn.textContent = 'Logging in…';

  const formData = new FormData(loginForm);

  try {
    const response = await fetch('/api/users/token', {
      method: 'POST',
      body: formData,
    });

    if (response.ok) {
      showToast('Login successful! Redirecting…');
      setTimeout(() => { window.location.href = '/'; }, 1200);
    } else {
      const err = await response.json();

      loginBtn.disabled    = false;
      loginBtn.textContent = 'Log In';

      window.showModal({
        type:    'error',
        title:   'Login Failed',
        message: (err.detail && typeof err.detail === 'object' ? err.detail.message : err.detail) || 'Invalid credentials. Please try again.',
        primary: { label: 'Try Again' }
      });
    }
  } catch {
    loginBtn.disabled    = false;
    loginBtn.textContent = 'Log In';

    window.showModal({
      type:    'error',
      title:   'Connection Error',
      message: 'Network error. Please check your connection and try again.',
      primary: { label: 'Dismiss' }
    });
  }
});
