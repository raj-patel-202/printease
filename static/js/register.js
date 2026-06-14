const registerForm  = document.getElementById('registerForm');
const passwordInput = document.getElementById('password');
const confirmInput  = document.getElementById('confirmPassword');
const registerBtn   = document.getElementById('registerBtn');
const strengthMeter = document.getElementById('strengthMeter');
const strengthFill  = document.getElementById('strengthFill');
const strengthLabel = document.getElementById('strengthLabel');
const matchHint     = document.getElementById('matchHint');
const togglePwBtn   = document.getElementById('togglePw');

function scorePassword(pw) {
  let s = 0;
  if (pw.length >= 8)           s++;
  if (pw.length >= 12)          s++;
  if (/[A-Z]/.test(pw))         s++;
  if (/[0-9]/.test(pw))         s++;
  if (/[^A-Za-z0-9]/.test(pw))  s++;
  return s;
}

passwordInput.addEventListener('input', () => {
  const pw = passwordInput.value;
  if (!pw) { strengthMeter.classList.remove('visible'); return; }
  strengthMeter.classList.add('visible');
  const score  = scorePassword(pw);
  const pct    = Math.min(score / 5 * 100, 100);
  const colors = ['#d94f4f','#e58a1e','#e5c41e','#2d9e5e','#1a7a4a'];
  const labels = ['Weak','Fair','Good','Strong','Very strong'];
  strengthFill.style.width      = pct + '%';
  strengthFill.style.background = colors[score - 1] ?? colors[0];
  strengthLabel.textContent     = labels[score - 1] ?? 'Weak';
  checkMatch();
});

function checkMatch() {
  if (!confirmInput.value) { matchHint.classList.remove('visible'); return; }
  const match = passwordInput.value === confirmInput.value;
  matchHint.textContent = match ? '✓ Passwords match' : '✗ Passwords do not match';
  matchHint.className   = 'match-hint visible ' + (match ? 'ok' : 'no');
  confirmInput.setCustomValidity(match ? '' : 'Passwords do not match');
}

confirmInput.addEventListener('input', checkMatch);

togglePwBtn.addEventListener('click', () => {
  const isText = passwordInput.type === 'text';
  passwordInput.type = isText ? 'password' : 'text';
  const pwIcon = document.getElementById('pwIcon');
  if (pwIcon) {
    pwIcon.src = isText ? '/static/icons/view_password.svg?v=2' : '/static/icons/hide_password.svg?v=2';
  }
});

registerForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  if (passwordInput.value !== confirmInput.value) {
    window.showModal({
      type:    'warning',
      title:   'Password Mismatch',
      message: 'The passwords you entered do not match. Please check them and try again.',
      primary: { label: 'OK' }
    });
    return;
  }

  registerBtn.disabled    = true;
  registerBtn.textContent = 'Creating account…';

  const formData = new FormData(registerForm);
  try {
    const response = await fetch('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: formData.get('username'),
        email:    formData.get('email'),
        password: formData.get('password'),
      }),
    });

    if (response.ok) {
      showToast('Account created! Redirecting…');
      setTimeout(() => { window.location.href = "/login"; }, 1500);
    } else {
      const err = await response.json();

      registerBtn.disabled    = false;
      registerBtn.textContent = 'Create Account';

      let errMsg = 'Failed to create account. Username or email may be taken.';
      if (err.detail && Array.isArray(err.detail)) {
        errMsg = err.detail.map(errObj => `${errObj.loc[errObj.loc.length - 1]}: ${errObj.msg}`).join(' · ');
      } else if (err.detail) {
        errMsg = typeof err.detail === 'object' ? err.detail.message : err.detail;
      }

      window.showModal({
        type:    'error',
        title:   'Registration Failed',
        message: errMsg,
        primary: { label: 'Try Again' }
      });
    }
  } catch {
    registerBtn.disabled    = false;
    registerBtn.textContent = 'Create Account';

    window.showModal({
      type:    'error',
      title:   'Connection Error',
      message: 'Network error. Check your connection and try again.',
      primary: { label: 'Dismiss' }
    });
  }
});
