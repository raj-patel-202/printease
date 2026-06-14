const SVG_CHECK = `<svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="19" stroke="rgba(255,255,255,0.4)" stroke-width="1.5"/>
  <path d="M11 21l6 6 12-13" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
    stroke-dasharray="30" stroke-dashoffset="30">
    <animate attributeName="stroke-dashoffset" from="30" to="0" dur="0.45s" begin="0.1s" fill="freeze"/>
  </path>
</svg>`;

const SVG_CROSS = `<svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="19" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
  <path d="M13 13l14 14M27 13L13 27" stroke="rgba(255,255,255,0.85)" stroke-width="2.5" stroke-linecap="round"
    stroke-dasharray="40" stroke-dashoffset="40">
    <animate attributeName="stroke-dashoffset" from="40" to="0" dur="0.35s" begin="0.05s" fill="freeze"/>
  </path>
</svg>`;

const SVG_SPINNER = `<svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="16" stroke="var(--border)" stroke-width="3"/>
  <path d="M20 4 a16 16 0 0 1 16 16" stroke="var(--ink-muted)" stroke-width="3" stroke-linecap="round">
    <animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="0.9s" repeatCount="indefinite"/>
  </path>
</svg>`;

const SVG_WARNING = `<svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="19" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
  <path d="M20 12v8" stroke="rgba(255,255,255,0.9)" stroke-width="2.5" stroke-linecap="round"
    stroke-dasharray="10" stroke-dashoffset="10">
    <animate attributeName="stroke-dashoffset" from="10" to="0" dur="0.3s" begin="0.05s" fill="freeze"/>
  </path>
  <circle cx="20" cy="26" r="1.5" fill="rgba(255,255,255,0.9)"/>
</svg>`;

document.addEventListener("DOMContentLoaded", async () => {
  const card    = document.getElementById('orderCard');
  const banner  = document.getElementById('statusBanner');
  const icon    = document.getElementById('statusIcon');
  const title   = document.getElementById('statusTitle');
  const desc    = document.getElementById('statusDesc');
  const actionContainer = document.getElementById('actionContainer');

  const urlParams    = new URLSearchParams(window.location.search);
  const receiptToken = urlParams.get('receipt');

  if (!receiptToken) {
    window.location.replace('/');
    return;
  }

  icon.innerHTML = SVG_SPINNER;
  card.style.display = 'block';

  try {
    const response = await fetch(`/api/orders/receipt-details?receipt=${receiptToken}`);
    if (!response.ok) {
      let errMsg = "Order not found or invalid token.";
      try {
        const errData = await response.json();
        if (errData && errData.detail) errMsg = typeof errData.detail === 'object' ? errData.detail.message : errData.detail;
      } catch (e) {}
      throw new Error(errMsg);
    }

    const order = await response.json();

    document.getElementById('o-id').textContent  = `Order #${order.id}`;

    const paperMap = { A4: 'A4', A3: 'A3', Letter: 'Letter', Legal: 'Legal' };
    document.getElementById('o-paper').textContent = paperMap[order.paper_size] || order.paper_size;

    const colorMap = { bw: 'Black & White', color: 'Color' };
    document.getElementById('o-color').textContent = colorMap[order.color_mode] || order.color_mode;

    const sideMap = { single: 'Single-sided', double: 'Double-sided' };
    document.getElementById('o-sides').textContent = sideMap[order.side_mode] || order.side_mode;

    const formatDateTimeBadge = (dateString) => {
      const dObj = new Date(dateString);

      let hours = dObj.getHours();
      let minutes = dObj.getMinutes();
      const ampm = hours >= 12 ? 'pm' : 'am';
      hours = hours % 12;
      hours = hours ? hours : 12;
      const minStr = minutes < 10 ? '0' + minutes : minutes;
      const timeStr = `${hours}:${minStr} ${ampm}`;

      const day = dObj.getDate();
      const month = dObj.toLocaleDateString('en-US', { month: 'short' }).toLowerCase();
      const dateStr = `${day} ${month}`;

      return `<span class="time-part">${timeStr}</span> <span class="datetime-divider">|</span> <span class="date-part">${dateStr}</span>`;
    };

    const displayDateTime = (order.payment && order.payment.payment_datetime) ? order.payment.payment_datetime : order.date_ordered;
    if (displayDateTime) {
      document.getElementById('o-datetime').innerHTML = formatDateTimeBadge(displayDateTime);
    }

    const totalPagesPrinted = order.total_pages * order.copies;
    const isColor = order.color_mode === 'color';
    
    document.getElementById('o-label-price-per-page').textContent = isColor ? 'Price per page (Coloured)' : 'Price per page (B&W)';
    document.getElementById('o-price-per-page').textContent = `₹${(order.base_cost / totalPagesPrinted).toFixed(2)}`;
    document.getElementById('o-total-pages-printed').textContent = totalPagesPrinted;
    document.getElementById('o-total-pages-printed-sub').textContent = `(${order.total_pages} pages × ${order.copies} copies)`;
    document.getElementById('o-base-print-cost').textContent = `₹${parseFloat(order.base_cost).toFixed(2)}`;

    if (order.discount_amount > 0) {
      document.getElementById('o-discount-label-text').textContent = `Double-sided discount`;
      document.getElementById('row-discount').style.display = 'flex';
      document.getElementById('o-discount-val').textContent = `-₹${parseFloat(order.discount_amount).toFixed(2)}`;
    } else {
      document.getElementById('row-discount').style.display = 'none';
    }

    document.getElementById('o-grand-total').textContent = `₹${parseFloat(order.total_cost).toFixed(2)}`;
    document.getElementById('o-cost').textContent = `₹${parseFloat(order.total_cost).toFixed(2)}`;

    const payment = order.payment;
    const paymentStatus = payment ? payment.payment_status : null;
    const printStatus = order.print_status;

    if (paymentStatus === "completed") {
      banner.className = "order-banner banner-success";
      icon.innerHTML   = SVG_CHECK;
      title.textContent = "Payment Confirmed";
      desc.textContent  = "Your prints are being processed.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
      `;
    } else if (paymentStatus === "refunded" || printStatus === "refunded") {
      banner.className = "order-banner banner-failed";
      icon.innerHTML   = SVG_CROSS;
      title.textContent = "Payment Refunded";
      desc.textContent  = "This order has been cancelled and refunded.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
      `;
    } else if (paymentStatus === "amount_mismatch_error") {
      banner.className = "order-banner banner-warning";
      icon.innerHTML   = SVG_WARNING;
      title.textContent = "Payment Under Review";
      desc.textContent  = "A payment discrepancy was detected. Our team is reviewing this order. You will be notified once it is resolved.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
      `;
    } else if (paymentStatus === "refund_pending") {
      banner.className = "order-banner banner-warning";
      icon.innerHTML   = SVG_SPINNER;
      title.textContent = "Refund Processing";
      desc.textContent  = "A refund for this order is being processed. It should appear in your account within 5–7 business days.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
      `;
    } else if (paymentStatus === "refund_failed") {
      banner.className = "order-banner banner-failed";
      icon.innerHTML   = SVG_CROSS;
      title.textContent = "Refund Failed";
      desc.textContent  = "We were unable to process the refund automatically. Please contact support for assistance.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
        <a href="/contact" class="btn-outline">Contact Support</a>
      `;
    } else if (paymentStatus === "cancelled" || printStatus === "cancelled") {
      banner.className = "order-banner banner-failed";
      icon.innerHTML   = SVG_CROSS;
      title.textContent = "Order Cancelled";
      desc.textContent  = "This order has been cancelled.";

      actionContainer.innerHTML = `
        <a href="/my_orders" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 12l-4-4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Back to My Orders
        </a>
      `;
    } else if (paymentStatus === "failed" || printStatus === "failed") {
      banner.className = "order-banner banner-failed";
      icon.innerHTML   = SVG_CROSS;
      title.textContent = "Payment Failed";
      desc.textContent  = "The payment attempt failed.";

      actionContainer.innerHTML = `
        <a href="/checkout?order=${receiptToken}" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="5" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 5V4a4 4 0 0 1 8 0v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="9.5" r="1.2" fill="currentColor"/></svg>
          Retry Payment
        </a>
        <a href="/" class="btn-outline">Go Home</a>
      `;
    } else {
      banner.className = "order-banner banner-failed";
      icon.innerHTML   = SVG_CROSS;
      title.textContent = "Payment Pending";
      desc.textContent  = "This order hasn't been paid for yet.";

      actionContainer.innerHTML = `
        <a href="/checkout?order=${receiptToken}" class="btn-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="5" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 5V4a4 4 0 0 1 8 0v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="9.5" r="1.2" fill="currentColor"/></svg>
          Pay Securely
        </a>
        <a href="/" class="btn-outline">Cancel &amp; Go Home</a>
      `;
    }

  } catch (err) {
    console.error(err);
    window.showModal({
      type: 'error',
      title: 'Error Loading Receipt',
      message: err.message || 'Could not load receipt details. Please try again.',
      primary: { label: 'Go Home', href: '/' }
    });
  }
});
