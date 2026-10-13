const sendBtn = document.getElementById('sendBtn');

sendBtn.addEventListener('click', async () => {
  const name    = document.getElementById('userName').value.trim();
  const email   = document.getElementById('userEmail').value.trim();
  const subject = document.getElementById('userSubject').value;
  const message = document.getElementById('userMessage').value.trim();
  const botcheck = document.getElementById('botcheck').checked;

  if (!name || !email || !subject || !message) {
    showToast('⚠️ Please fill in all fields before sending.');
    return;
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showToast('⚠️ Please enter a valid email address.');
    return;
  }

  sendBtn.innerHTML = '⏳ Sending...';
  sendBtn.disabled = true;

  try {
    const accessKey = document.getElementById('web3forms_access_key').value;
    const response = await fetch('https://api.web3forms.com/submit', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        access_key: accessKey,
        name: name,
        email: email,
        subject: `[${subject}] Message from ${name}`,
        message: message,
        botcheck: botcheck
      })
    });

    const result = await response.json();

    if (response.status === 200) {
      showToast('✅ Message sent successfully! We will be in touch.');
      document.getElementById('userName').value = '';
      document.getElementById('userEmail').value = '';
      document.getElementById('userSubject').value = '';
      document.getElementById('userMessage').value = '';
    } else {
      console.error(result);
      showToast('⚠️ Failed to send: ' + result.message);
    }
  } catch (error) {
    console.error(error);
    showToast('⚠️ Network error. Please check your internet connection.');
  } finally {
    sendBtn.innerHTML = '✉️ &nbsp;Send Message';
    sendBtn.disabled = false;
  }
});
