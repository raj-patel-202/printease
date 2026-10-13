document.addEventListener("DOMContentLoaded", async () => {

  const urlParams  = new URLSearchParams(window.location.search);
  const orderToken = urlParams.get('order');
  const errorCode  = urlParams.get('error');

  const ERROR_MESSAGES = {
    missing_parameters: 'Payment parameters were missing. Please try again.',
    missing_order_metadata: 'Order metadata could not be found. Please contact support.',
    order_not_found: 'This order could not be found.',
    verification_failed: 'Payment signature verification failed. If money was deducted, it will be refunded automatically.',
    payment_not_captured: 'Your payment is still being processed. Please wait a few minutes and check your order status.',
    order_cancelled_refund_initiated: 'This order was cancelled. A refund has been initiated and will appear in your account shortly.',
    refund_failed: 'We attempted to refund this cancelled order but encountered an issue. Please contact support.',
    amount_mismatch: 'A payment amount discrepancy was detected. Our team will review this order.',
    currency_mismatch: 'Payment currency did not match. Please contact support.',
    internal_server_error: 'An unexpected error occurred. Please try again or contact support.',
  };

  function getErrorMessage(code) {
    return ERROR_MESSAGES[code] || `An error occurred (${code}). Please try again or contact support.`;
  }

  if (!orderToken && errorCode) {
    window.showModal({
      type: 'error',
      title: 'Payment Error',
      message: getErrorMessage(errorCode),
      primary: { label: 'Go Home', href: '/' }
    });
    return;
  }

  if (!orderToken) {
    window.location.href = '/';
    return;
  }

  if (errorCode) {
    const terminalErrors = [
      'order_cancelled_refund_initiated', 'refund_failed', 'amount_mismatch',
      'verification_failed', 'order_not_found'
    ];
    const isTerminal = terminalErrors.includes(errorCode);

    window.showModal({
      type: isTerminal ? 'error' : 'warning',
      title: isTerminal ? 'Order Issue' : 'Payment Notice',
      message: getErrorMessage(errorCode),
      primary: isTerminal
        ? { label: 'View My Orders', href: '/my_orders' }
        : { label: 'Try Again', action: 'close' },
      secondary: isTerminal ? { label: 'Go Home', href: '/' } : undefined
    });

    if (isTerminal) return;
  }

  let currentOrderId = null;
  const btnPay = document.getElementById('rzp-button');

  try {
    const response = await fetch(`/api/orders/checkout-details?order=${orderToken}`);

    if (!response.ok) {
      let errMsg = 'Could not load checkout details. You may need to restart your order.';
      let isAlreadyProcessed = false;
      let isNotFound = false;
      try {
        const errData = await response.json();
        if (errData && errData.detail) {
          errMsg = typeof errData.detail === 'string' ? errData.detail : (errData.detail.message || JSON.stringify(errData.detail));
          if (errMsg.includes('paid or cancelled')) {
            isAlreadyProcessed = true;
          } else if (errMsg.includes('not found')) {
            isNotFound = true;
          }
        }
      } catch (e) {}

      if (isAlreadyProcessed) {
        window.showModal({
          type: 'info',
          title: 'Order Completed',
          message: 'This order has already been paid for or cancelled. You can view your order status in your orders history.',
          primary: { label: 'View Orders', href: '/my_orders' },
          secondary: { label: 'Go Home', href: '/' }
        });
        return;
      }

      if (isNotFound) {
        window.showModal({
          type: 'error',
          title: 'Order Not Found',
          message: 'The requested print order could not be found. Please start over.',
          primary: { label: 'Start Over', href: '/' }
        });
        return;
      }

      throw new Error(errMsg);
    }

    const data = await response.json();
    currentOrderId = data.id;

    const paperMap = { A4: 'A4', A3: 'A3', Letter: 'Letter', Legal: 'Legal' };
    document.getElementById('c-paper').textContent = paperMap[data.paper_size] || data.paper_size;

    const colorMap = { bw: 'Black & White', color: 'Color' };
    document.getElementById('c-color').textContent = colorMap[data.color_mode] || data.color_mode;

    const sideMap = { single: 'Single-Sided', double: 'Double-Sided' };
    document.getElementById('c-sides').textContent = sideMap[data.side_mode] || data.side_mode;

    const orientationMap = { portrait: 'Portrait', landscape: 'Landscape' };
    document.getElementById('c-orientation').textContent = orientationMap[data.orientation] || data.orientation;

    document.getElementById('c-pages').textContent = data.total_pages;
    document.getElementById('c-copies').textContent = data.copies;

    const totalPagesPrinted = data.total_pages * data.copies;
    const isColor = data.color_mode === 'color';
    
    document.getElementById('c-label-price-per-page').textContent = isColor ? 'Price per page (Color)' : 'Price per page (B&W)';
    document.getElementById('c-price-per-page').textContent = `₹${(data.base_cost / totalPagesPrinted).toFixed(2)}`;
    document.getElementById('c-total-pages-printed').textContent = totalPagesPrinted;
    document.getElementById('c-total-pages-printed-sub').textContent = `(${data.total_pages} pages × ${data.copies} copies)`;
    document.getElementById('c-base-print-cost').textContent = `₹${parseFloat(data.base_cost).toFixed(2)}`;

    if (data.discount_amount > 0) {
      document.getElementById('c-discount-label-text').textContent = `Double-sided discount`;
      document.getElementById('c-row-discount').style.display = 'flex';
      document.getElementById('c-discount-val').textContent = `-₹${parseFloat(data.discount_amount).toFixed(2)}`;
    } else {
      document.getElementById('c-row-discount').style.display = 'none';
    }

    document.getElementById('c-grand-total').textContent = `₹${parseFloat(data.total_cost).toFixed(2)}`;
    document.getElementById('c-cost').textContent = parseFloat(data.total_cost).toFixed(2);

    const breakupModal = document.getElementById('breakupModal');
    const showBreakupBtn = document.getElementById('show-breakup-btn');
    const closeBreakupBtn = document.getElementById('close-breakup-btn');

    if (showBreakupBtn && breakupModal && closeBreakupBtn) {
      showBreakupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        breakupModal.classList.add('is-open');
      });

      closeBreakupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        breakupModal.classList.remove('is-open');
      });

      breakupModal.addEventListener('click', (e) => {
        if (e.target === breakupModal) {
          breakupModal.classList.remove('is-open');
        }
      });
    }

    document.getElementById('skeleton-loader').style.display = 'none';
    document.getElementById('checkout-content').style.display = 'block';

  } catch (error) {
    window.showModal({
      type: 'error',
      title: 'Checkout Expired',
      message: error.message,
      primary: { label: 'Go Home', href: '/' }
    });
  }

  async function revalidateOrder() {
    try {
      const res = await fetch(`/api/orders/checkout-details?order=${orderToken}`);
      if (!res.ok) {
        let errMsg = '';
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            errMsg = typeof errData.detail === 'string' ? errData.detail : (errData.detail.message || JSON.stringify(errData.detail));
          }
        } catch (e) {}

        if (typeof errMsg === 'string' && errMsg.includes('paid or cancelled')) {
          window.showModal({
            type: 'info',
            title: 'Order No Longer Available',
            message: 'This order has already been paid, cancelled, or refunded. You can view your order status in your orders history.',
            primary: { label: 'View Orders', href: '/my_orders' },
            secondary: { label: 'Go Home', href: '/' }
          });
          btnPay.disabled = true;
          btnCancel.disabled = true;
          setTimeout(() => { window.location.href = '/my_orders'; }, 8000);
          return false;
        }
      }
      return true;
    } catch (e) {
      return true;
    }
  }

  btnPay.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!currentOrderId) return;

    if (typeof Razorpay === 'undefined') {
      window.showModal({
        type: 'warning',
        title: 'Connection Issue',
        message: 'The secure payment module failed to load. Please refresh the page and try again.',
        primary: { label: 'Refresh Page', action: () => window.location.reload() },
        secondary: { label: 'Cancel', action: 'close' }
      });
      return;
    }

    btnPay.disabled = true;
    btnPay.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="animation:spin 0.8s linear infinite">
        <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
        <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      Initializing…
    `;

    const isValid = await revalidateOrder();
    if (!isValid) return;

    try {
      const orderResponse = await fetch(`/api/payments/${currentOrderId}/create-razorpay-order`, {
        method: 'POST'
      });

      if (!orderResponse.ok) {
        let errMsg = 'Failed to initialize payment gateway.';
        try {
          const errData = await orderResponse.json();
          if (errData && errData.detail) {
            errMsg = errData.detail;
          }
        } catch (e) {}
        throw new Error(errMsg);
      }

      const rzpData = await orderResponse.json();

      var options = {
        "key": window.razorpay_api_key,
        "amount": rzpData.amount,
        "currency": rzpData.currency,
        "name": "PrintEase",
        "description": "Print Order Configuration",
        "order_id": rzpData.id,
        "handler": function (response) {
          btnPay.disabled = true;
          btnPay.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="animation:spin 0.8s linear infinite">
              <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            Verifying payment…
          `;

          const form = document.createElement('form');
          form.method = 'POST';
          form.action = '/api/payments/verify-payment';

          const fields = {
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_signature: response.razorpay_signature
          };

          for (const [key, value] of Object.entries(fields)) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            form.appendChild(input);
          }

          document.body.appendChild(form);
          form.submit();
        },
        "theme": { "color": "#c8602a" },
        "modal": {
          "ondismiss": function() {
            btnPay.disabled = false;
            btnPay.innerHTML = `
              <span class="btn-pay-icon">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="5" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 5V4a4 4 0 0 1 8 0v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="9.5" r="1.2" fill="currentColor"/></svg>
              </span>
              Pay Securely
            `;
          }
        }
      };

      var rzp1 = new Razorpay(options);
      rzp1.open();

    } catch (err) {
      btnPay.disabled = false;
      btnPay.innerHTML = `
        <span class="btn-pay-icon">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="5" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 5V4a4 4 0 0 1 8 0v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="9.5" r="1.2" fill="currentColor"/></svg>
        </span>
        Pay Securely
      `;
      if (err.message === 'Order is already paid') {
        window.showModal({
          type: 'info',
          title: 'Already Paid',
          message: 'This order has already been paid for. You can view your order status in your orders history.',
          primary: { label: 'View Orders', href: '/my_orders' },
          secondary: { label: 'Go Home', href: '/' }
        });
      } else {
        window.showModal({ type: 'error', title: 'Payment Error', message: err.message });
      }
    }
  });

  const btnCancel = document.getElementById('cancel-button');
  btnCancel.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!confirm("Are you sure you want to cancel this print order?")) return;

    btnCancel.disabled = true;
    btnCancel.textContent = 'Canceling…';

    const isValid = await revalidateOrder();
    if (!isValid) return;

    try {
      const cancelResponse = await fetch(`/api/orders/${orderToken}`, { method: 'DELETE' });
      if (cancelResponse.ok) {
        window.location.href = '/';
      } else {
        let errMsg = 'Failed to cancel order.';
        try {
          const errData = await cancelResponse.json();
          if (errData && errData.detail) errMsg = errData.detail;
        } catch (e) {}
        throw new Error(errMsg);
      }
    } catch (err) {
      btnCancel.disabled = false;
      btnCancel.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Cancel Order`;
      if (err.message.includes('already completed or cancelled')) {
        window.showModal({
          type: 'info',
          title: 'Cannot Cancel Order',
          message: 'This order has already been completed (paid) or is already cancelled. You can check its status in your order history.',
          primary: { label: 'View Orders', href: '/my_orders' },
          secondary: { label: 'Go Home', href: '/' }
        });
      } else {
        window.showModal({ type: 'error', title: 'Error', message: err.message });
      }
    }
  });

});
