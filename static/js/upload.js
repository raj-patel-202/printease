import { getCurrentUser } from '/static/js/auth.js';
import { PDFPreviewer } from '/static/js/pdf_viewer.js';

const sessionFileName = sessionStorage.getItem('pending_file_name');

const user = await getCurrentUser();
if (!user) {
  window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
}
else if (!sessionFileName) {
  window.location.href = '/';
}
else {
  document.getElementById('filename').value = sessionFileName;
  document.getElementById('previewFileName').textContent = sessionFileName;

  const statusMsg = document.getElementById('statusMessage');
  const submitBtn = document.getElementById('submitBtn');

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('PDFPrintApp', 1);
      req.onupgradeneeded = e => e.target.result.createObjectStore('files');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function cleanupPending(db) {
    sessionStorage.removeItem('pending_file_name');
    try {
      const tx = db.transaction('files', 'readwrite');
      tx.objectStore('files').delete('pending_file');
    } catch (_) {}
    pdfPreviewer.cleanup();
  }

  const pdfPreviewer = new PDFPreviewer({
    previewBoxId: 'pdfPreview',
    pagesElId: 'pdfPreviewPages',
    loadingElId: 'pdfPreviewLoading',
    errorElId: 'pdfPreviewError',
    zoomBarId: 'pdfZoomBar',
    zoomLabelId: 'pdfZoomLabel',
    zoomInId: 'pdfZoomIn',
    zoomOutId: 'pdfZoomOut',
    resetId: 'pdfZoomReset'
  });

  async function initUploadPage() {
    let db;
    try {
      db = await openDB();
    } catch (err) {
      window.showModal({
        type:    'error',
        title:   'Storage Unavailable',
        message: 'Could not open browser storage. Please refresh and try again.',
        primary: { label: 'Go Home', href: '/' },
      });
      return;
    }

    const tx      = db.transaction('files', 'readonly');
    const request = tx.objectStore('files').get('pending_file');

    request.onerror = () => {
      window.showModal({
        type:    'error',
        title:   'File Not Found',
        message: 'The file could not be read from storage. Please go back and upload again.',
        primary: { label: 'Start Over', href: '/' },
      });
    };

    request.onsuccess = () => {
      const fileObj = request.result;

      if (!fileObj) {
        window.location.href = '/';
        return;
      }

      window._pendingPreviewFile = fileObj;
      pdfPreviewer.renderPdfPreview(fileObj);

      const orientationRadios = document.getElementsByName('orientation');
      const optionsForm = document.getElementById('printOptionsForm');

      function updateOrientationClass() {
        let selected = 'portrait';
        for (const r of orientationRadios) {
          if (r.checked) {
            selected = r.value;
            break;
          }
        }
        if (selected === 'landscape') {
          optionsForm.classList.add('is-landscape');
        } else {
          optionsForm.classList.remove('is-landscape');
        }
      }

      for (const r of orientationRadios) {
        r.addEventListener('change', updateOrientationClass);
      }
      
      updateOrientationClass();

      submitBtn.addEventListener('click', async () => {
        const copies = parseInt(document.getElementById('copies').value, 10);
        if (!copies || copies < 1 || copies > 10) {
          window.showModal({
            type:    'warning',
            title:   'Invalid Copies',
            message: 'Please enter a number of copies between 1 and 10.',
            primary: { label: 'OK' },
          });
          return;
        }

        submitBtn.disabled    = true;
        submitBtn.textContent = 'Uploading…';
        statusMsg.style.color = 'var(--ink-muted)';
        statusMsg.textContent = 'Processing your order…';

        const printOptions = {
          filename:    document.getElementById('filename').value,
          copies,
          paper_size:  document.querySelector('input[name="paper_size"]:checked').value,
          orientation: document.querySelector('input[name="orientation"]:checked').value,
          side_mode:   document.querySelector('input[name="side_mode"]:checked').value,
          color_mode:  document.querySelector('input[name="color_mode"]:checked').value,
        };

        const formData = new FormData();
        formData.append('file', fileObj);
        formData.append('options', JSON.stringify(printOptions));

        try {
          const response = await fetch(`/api/orders/uploads`, {
            method: 'POST',
            body:   formData,
          });

          if (response.status === 409) {
            const result = await response.json();
            const token = result.detail.existing_token;

            submitBtn.disabled    = false;
            submitBtn.textContent = 'Confirm & Upload';
            statusMsg.textContent = '';

            window.showModal({
              type:    'warning',
              title:   'Pending Order Found',
              message: result.detail.message,
              primary: {
                label: 'Resume Checkout',
                href: `/checkout?order=${token}`
              },
              secondary: {
                label: 'Cancel Old Order',
                action: async () => {
                  await fetch(`/api/orders/${token}`, { method: 'DELETE' });
                  window.showToast("Old order canceled. You can now upload this one.");
                }
              }
            });
            return;
          }

          const result = await response.json();

          if (response.ok) {
            statusMsg.style.color = '#2d7a4f';
            statusMsg.textContent = 'Preparing checkout...';

            cleanupPending(db);

            setTimeout(() => {
              window.location.href = `/checkout?order=${result.payment ? result.payment.receipt_token : ''}`;
            }, 1000);

          } else {
            let errMsg = 'The server rejected the upload.';
            if (result.detail && Array.isArray(result.detail)) {
              errMsg = result.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(' · ');
            } else if (result.detail) {
              errMsg = typeof result.detail === 'object' ? result.detail.message : result.detail;
            }

            submitBtn.disabled    = false;
            submitBtn.textContent = 'Confirm & Upload';
            statusMsg.textContent = '';

            window.showModal({
              type:    'error',
              title:   'Upload Failed',
              message: errMsg,
              primary: { label: 'Try Again', action: () => submitBtn.click() },
              secondary: {
                label: 'Start Over',
                action: () => {
                  cleanupPending(db);
                  window.location.href = '/';
                },
              },
            });
          }

        } catch (err) {
          submitBtn.disabled    = false;
          submitBtn.textContent = 'Confirm & Upload';
          statusMsg.textContent = '';

          const isOffline = !navigator.onLine;
          window.showModal({
            type:    'error',
            title:   isOffline ? "You're Offline" : "Connection Error",
            message: isOffline
              ? 'No internet connection detected. Please reconnect and try again.'
              : (err.message || 'An unexpected error occurred while uploading.'),
            primary: { label: 'Try Again', action: () => submitBtn.click() },
            secondary: {
              label: 'Start Over',
              action: () => {
                sessionStorage.setItem('server_upload_error', err.message || 'Upload failed.');
                cleanupPending(db);
                window.location.href = '/';
              },
            },
          });
        }
      });
    };
  }

  initUploadPage();
}
