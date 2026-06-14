import { getCurrentUser } from '/static/js/auth.js';

const uploadCard    = document.getElementById('uploadCard');
const uploadBtn     = document.getElementById('uploadBtn');
const homeFileInput = document.getElementById('homeFileInput');
const uploadNote    = document.getElementById('uploadNote');

const serverError = sessionStorage.getItem('server_upload_error');
if (serverError) {
  sessionStorage.removeItem('server_upload_error');
  window.showModal({
    type:    'error',
    title:   'Upload Failed',
    message: serverError,
    primary: { label: 'Try Again', action: () => uploadBtn.click() },
    secondary: { label: 'Dismiss' },
  });
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('PDFPrintApp', 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore('files');
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function requireAuth() {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
    return null;
  }
  return user;
}

async function handleFile(file) {
  if (!file) return;

  if (file.type !== 'application/pdf') {
    window.showModal({
      type:    'warning',
      title:   'Wrong File Type',
      message: 'Only PDF files are supported. Please choose a .pdf file and try again.',
      primary: { label: 'Choose File', action: () => homeFileInput.click() },
      secondary: { label: 'Cancel' },
    });
    return;
  }

  if (file.size > 20 * 1024 * 1024) {
    window.showModal({
      type:    'warning',
      title:   'File Too Large',
      message: 'Your file exceeds the 20 MB limit. Please compress or split the PDF before uploading.',
      primary: { label: 'Choose Another', action: () => homeFileInput.click() },
      secondary: { label: 'Cancel' },
    });
    return;
  }

  const user = await requireAuth();
  if (!user) return;

  uploadNote.style.color = 'var(--muted)';
  uploadNote.textContent = 'Preparing document…';

  try {
    const db = await openDB();
    const tx = db.transaction('files', 'readwrite');
    tx.objectStore('files').put(file, 'pending_file');

    tx.oncomplete = () => {
      sessionStorage.setItem('pending_file_name', file.name);
      window.location.href = '/upload';
    };

    tx.onerror = () => {
      uploadNote.textContent = '';
      window.showModal({
        type:    'error',
        title:   'Storage Error',
        message: 'Could not save the file to browser storage. Try refreshing the page or using a different browser.',
        primary: { label: 'Retry', action: () => handleFile(file) },
        secondary: { label: 'Cancel' },
      });
    };
  } catch (err) {
    uploadNote.textContent = '';
    window.showModal({
      type:    'error',
      title:   'Storage Error',
      message: 'Browser storage is unavailable. ' + (err.message || 'Please try again.'),
      primary: { label: 'Dismiss' },
    });
    console.error('IndexedDB error:', err);
  }
}

uploadBtn.addEventListener('click', async () => {
  const user = await requireAuth();
  if (!user) return;
  homeFileInput.click();
});

homeFileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (file) {
    handleFile(file);
  }
});

uploadCard.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadCard.classList.add('drag-over');
});

uploadCard.addEventListener('dragleave', () => uploadCard.classList.remove('drag-over'));

uploadCard.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadCard.classList.remove('drag-over');
  handleFile(e.dataTransfer.files[0]);
});
