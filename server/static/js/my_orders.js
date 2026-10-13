let allOrdersGlobal = [];

const PRINT_STATUS_LABELS = {
  pending: 'Pending',
  printing: 'Printing',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled'
};

function formatPrintStatus(status) {
  if (!status) return 'Unknown';
  return PRINT_STATUS_LABELS[status] || status.charAt(0).toUpperCase() + status.slice(1);
}

function formatQueuePosition(position) {
  if (position == null) return '—';
  return `#${position}`;
}

async function parseApiErrorDetail(response) {
  try {
    const data = await response.json();
    const detail = data.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && detail.message) return detail.message;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail[0].msg || JSON.stringify(detail[0]);
    }
  } catch (_) {}
  return null;
}

function buildStatusDetailsHtml(data, order) {
  const inQueue = data.queue_position != null;

  let statusColor = 'var(--ink)';
  let statusBg = 'var(--cream)';
  let statusBorder = 'var(--border)';

  if (data.print_status === 'delivered') {
    statusColor = '#166534';
    statusBg = '#dcfce7';
    statusBorder = '#86efac';
  } else if (['completed', 'printing'].includes(data.print_status)) {
    statusColor = '#1e40af';
    statusBg = '#e0f2fe';
    statusBorder = '#7dd3fc';
  } else if (data.print_status === 'pending') {
    statusColor = 'var(--accent)';
    statusBg = 'var(--accent-light)';
    statusBorder = '#fce2c8';
  } else if (['failed', 'cancelled'].includes(data.print_status)) {
    statusColor = '#991b1b';
    statusBg = '#fee2e2';
    statusBorder = '#fca5a5';
  }

  const colorText = order ? (order.color_mode === 'color' ? 'Color' : 'Black & White') : '—';
  const sideText = order ? (order.side_mode === 'double' ? 'Double-Sided' : 'Single-Sided') : '—';
  const orientationText = order ? (order.orientation === 'landscape' ? 'Landscape' : 'Portrait') : '—';

  const hideQueueInfo = ['completed', 'delivered', 'printing'].includes(data.print_status);

  let html = `
    <div style="text-align: center; margin-bottom: 1.5rem; padding: 1.25rem 0; border: 1px solid ${statusBorder}; border-radius: 12px; background: ${statusBg}; box-shadow: 0 4px 12px rgba(44, 40, 37, 0.03);">
      <div style="font-size: 2rem; font-weight: 700; color: ${statusColor}; font-family: 'Playfair Display', serif; letter-spacing: -0.01em;">${formatPrintStatus(data.print_status)}</div>
    </div>
  `;

  if (!hideQueueInfo) {
    let estWaitDisplay = String(data.estimated_wait_minutes ?? 0);
    if (inQueue && (data.estimated_wait_minutes == null || data.estimated_wait_minutes === 0)) {
      estWaitDisplay = 'Next in queue';
    } else if (!inQueue) {
      estWaitDisplay = '—';
    }

    html += `
      <div style="margin-bottom: 1.5rem;">
        <ul class="status-detail-list">
          <li>
            <span class="label">Queue position</span>
            <span class="value ${inQueue ? 'is-wait' : ''}" style="font-size: 1.05rem;">${inQueue ? formatQueuePosition(data.queue_position) : 'Not in queue'}</span>
          </li>
          <li>
            <span class="label">Est. wait (min)</span>
            <span class="value ${inQueue ? 'is-wait' : ''}" style="font-size: 1.05rem;">${estWaitDisplay}</span>
          </li>
        </ul>
      </div>
    `;
  }

  if (order) {
    const restRows = [
      { label: 'Copies', value: String(order.copies || 1) },
      { label: 'Pages count', value: String(order.total_pages || 1) },
      { label: 'Paper size', value: String(order.paper_size || 'A4') },
      { label: 'Color Mode', value: colorText },
      { label: 'Side Mode', value: sideText },
      { label: 'Orientation', value: orientationText }
    ];

    const restItems = restRows.map(r => `
      <li>
        <span class="label">${r.label}</span>
        <span class="value" style="max-width: 60%; word-break: break-all;">${r.value}</span>
      </li>
    `).join('');

    html += `<ul class="status-detail-list">${restItems}</ul>`;
  }

  return html;
}

function showStatusModalError(bodyEl, message) {
  bodyEl.innerHTML = `<p class="status-modal-error">${message}</p>`;
}

function openStatusModal(orderId) {
  const backdrop = document.getElementById('status-modal');
  const bodyEl = document.getElementById('status-modal-body');
  const subtitle = document.getElementById('status-modal-subtitle');

  subtitle.textContent = `Order #${orderId}`;
  bodyEl.innerHTML = '<p class="status-modal-loading">Loading status…</p>';
  backdrop.hidden = false;
  backdrop.classList.add('is-open');
  document.body.style.overflow = 'hidden';
  return bodyEl;
}

function closeStatusModal() {
  const backdrop = document.getElementById('status-modal');
  backdrop.classList.remove('is-open');
  document.body.style.overflow = '';
  setTimeout(() => { backdrop.hidden = true; }, 220);
}

function revertOrderCardToUnpaid(orderId, receiptToken, orderCost) {
  const card = document.querySelector(`.order-card[data-order-id="${orderId}"]`);
  if (!card) return;

  card.classList.remove('is-completed');
  card.classList.add('is-pending');
  card.dataset.paymentStatus = 'pending';

  const badge = card.querySelector('.status-badge');
  if (badge) {
    badge.className = 'status-badge status-pending';
    badge.textContent = 'Pending';
  }

  const actions = card.querySelector('.order-actions');
  if (actions) {
    actions.innerHTML = `
      <div class="order-action-buttons">
        <a href="/checkout?order=${receiptToken || card.dataset.receiptToken}" class="btn-action btn-pay">Pay Now</a>
      </div>
    `;
  }
}

async function loadOrderStatus(orderId, triggerBtn) {
  const bodyEl = openStatusModal(orderId);
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.classList.add('is-loading');
    triggerBtn.textContent = 'Loading…';
  }

  try {
    const response = await fetch(`/api/orders/${orderId}/status`);

    if (response.status === 401) {
      window.location.href = '/login?next=/my_orders';
      return;
    }

    if (response.status === 404) {
      const msg = await parseApiErrorDetail(response)
        || 'Order not found or you are not authorized to view it.';
      showStatusModalError(bodyEl, msg);
      window.showToast(msg);
      return;
    }

    if (response.status === 409) {
      const msg = await parseApiErrorDetail(response)
        || 'Complete payment before viewing print status.';
      const receiptToken = triggerBtn?.dataset.receiptToken;
      const orderCost = triggerBtn?.dataset.orderCost;
      closeStatusModal();
      revertOrderCardToUnpaid(orderId, receiptToken, orderCost);
      window.showToast(msg);
      return;
    }

    if (!response.ok) {
      const msg = await parseApiErrorDetail(response)
        || 'Could not load print status. Please try again.';
      showStatusModalError(bodyEl, msg);
      window.showToast(msg);
      return;
    }

    const data = await response.json();
    const orderObj = allOrdersGlobal.find(o => String(o.id) === String(orderId));
    bodyEl.innerHTML = buildStatusDetailsHtml(data, orderObj);
  } catch (err) {
    console.error('Status fetch failed:', err);
    const msg = 'Could not load print status. Please try again.';
    showStatusModalError(bodyEl, msg);
    window.showToast(msg);
  } finally {
    if (triggerBtn && triggerBtn.isConnected) {
      triggerBtn.disabled = false;
      triggerBtn.classList.remove('is-loading');
      triggerBtn.textContent = 'View Status';
    }
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const skeletonLoader = document.getElementById('skeleton-loader');
  const emptyState = document.getElementById('empty-state');
  const ordersList = document.getElementById('orders-list');
  const paginationContainer = document.getElementById('orders-pagination');

  let allOrders = [];
  let currentPage = 1;
  const pageSize = 10;

  const statusModal = document.getElementById('status-modal');
  document.getElementById('status-modal-close').addEventListener('click', closeStatusModal);
  document.getElementById('status-modal-dismiss').addEventListener('click', closeStatusModal);
  statusModal.addEventListener('click', (e) => {
    if (e.target === statusModal) closeStatusModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && statusModal.classList.contains('is-open')) closeStatusModal();
  });

  ordersList.addEventListener('click', async (e) => {
    const statusBtn = e.target.closest('.btn-status');
    if (statusBtn) {
      const orderId = statusBtn.dataset.orderId;
      if (orderId) loadOrderStatus(orderId, statusBtn);
      return;
    }

    const pdfBtn = e.target.closest('.btn-view-pdf');
    if (pdfBtn) {
      e.preventDefault();
      const orderId = pdfBtn.dataset.orderId;
      const filename = pdfBtn.dataset.filename || `order_${orderId}.pdf`;
      if (!orderId) return;

      pdfBtn.disabled = true;
      const originalText = pdfBtn.textContent;
      pdfBtn.textContent = 'Loading…';

      try {
        const response = await fetch(`/api/orders/${orderId}/pdf`);
        if (!response.ok) {
          let errMsg = "Could not load PDF file.";
          try {
            const errData = await response.json();
            if (errData && errData.detail) errMsg = typeof errData.detail === 'object' ? errData.detail.message : errData.detail;
          } catch (e) {}
          throw new Error(errMsg);
        }
        const blob = await response.blob();
        window.viewPdf(blob, filename);
      } catch (err) {
        window.showModal({
          type: 'error',
          title: 'Failed to Open PDF',
          message: err.message || 'Could not load PDF file. Please try again.'
        });
      } finally {
        pdfBtn.disabled = false;
        pdfBtn.textContent = originalText;
      }
    }
  });

  function renderPaginationHtml(data) {
    if (data.pages <= 1) return '';
    let html = `<div class="pagination-controls" style="display: flex; gap: 0.5rem; justify-content: center; margin-bottom: 2rem;">`;
    html += `<button class="btn-action btn-view" ${data.page === 1 ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''} id="btn-prev-page">Previous</button>`;
    html += `<span style="display:flex; align-items:center; font-size:0.9rem; margin:0 0.5rem; color:var(--ink-muted);">Page ${data.page} of ${data.pages}</span>`;
    html += `<button class="btn-action btn-view" ${data.page === data.pages ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''} id="btn-next-page">Next</button>`;
    html += `</div>`;
    return html;
  }

  function getStatusMatch(order, statusFilter) {
    if (statusFilter === 'all') return true;
    return order.print_status === statusFilter;
  }

  function getDateMatch(order, dateFilter) {
    if (dateFilter === 'all') return true;
    if (!order.date_ordered) return false;
    
    const orderDate = new Date(order.date_ordered);
    const now = new Date();
    
    if (dateFilter === 'this_week') {
      const firstDay = new Date(now.setDate(now.getDate() - now.getDay()));
      firstDay.setHours(0,0,0,0);
      return orderDate >= firstDay;
    } else if (dateFilter === 'this_month') {
      return orderDate.getMonth() === now.getMonth() && orderDate.getFullYear() === now.getFullYear();
    } else if (dateFilter === 'past_month') {
      let pastMonth = now.getMonth() - 1;
      let year = now.getFullYear();
      if (pastMonth < 0) {
        pastMonth = 11;
        year--;
      }
      return orderDate.getMonth() === pastMonth && orderDate.getFullYear() === year;
    } else if (dateFilter === 'this_year') {
      return orderDate.getFullYear() === now.getFullYear();
    } else if (dateFilter === 'last_year') {
      return orderDate.getFullYear() === now.getFullYear() - 1;
    }
    return true;
  }

  window.changeOrdersPage = async function(dir) {
    currentPage += dir;
    applyFiltersAndRender();
  };

  function applyFiltersAndRender() {
    const statusFilter = currentStatusFilter;
    const dateFilter = currentDateFilter;
    
    let filtered = allOrders.filter(order => getStatusMatch(order, statusFilter) && getDateMatch(order, dateFilter));
    
    const total = filtered.length;
    const pages = Math.ceil(total / pageSize) || 1;
    
    if (currentPage > pages) currentPage = pages;
    if (currentPage < 1) currentPage = 1;
    
    const startIndex = (currentPage - 1) * pageSize;
    const paginatedItems = filtered.slice(startIndex, startIndex + pageSize);
    
    document.getElementById('filter-container').style.display = allOrders.length > 0 ? 'flex' : 'none';

    if (!allOrders || allOrders.length === 0) {
      emptyState.style.display = 'block';
      ordersList.style.display = 'none';
      if (paginationContainer) paginationContainer.innerHTML = '';
      return;
    }
    
    emptyState.style.display = 'none';
    renderFilteredOrders(paginatedItems);
    
    if (paginationContainer) {
      paginationContainer.innerHTML = renderPaginationHtml({page: currentPage, pages: pages});
      const prevBtn = document.getElementById('btn-prev-page');
      const nextBtn = document.getElementById('btn-next-page');
      if (prevBtn) prevBtn.addEventListener('click', () => changeOrdersPage(-1));
      if (nextBtn) nextBtn.addEventListener('click', () => changeOrdersPage(1));
    }
  }

  function renderFilteredOrders(filteredOrders) {
    ordersList.innerHTML = '';

    if (filteredOrders.length === 0) {
      ordersList.innerHTML = `
        <div class="empty-state" style="display: block; padding: 4.5rem 2rem; border: 2px dashed var(--border); box-shadow: none; margin-top: 1rem;">
          <div class="empty-icon">📂</div>
          <h3>No records found</h3>
          <p>There are no orders matching your selected filters.</p>
        </div>
      `;
      ordersList.style.display = 'block';
      return;
    }

    filteredOrders.forEach((order, index) => {
      let orderDate = '';
      let orderTime = '';
      if (order.date_ordered) {
        const dObj = new Date(order.date_ordered);
        const rawTime = dObj.toLocaleTimeString('en-IN', {
          hour: 'numeric', minute: '2-digit', hour12: true
        });
        orderTime = rawTime.toLowerCase();
        const rawDate = dObj.toLocaleDateString('en-IN', {
          day: 'numeric', month: 'short'
        });
        orderDate = rawDate.toLowerCase();
      }

      const payment = order.payment || {};
      const paymentStatus = payment.payment_status || 'pending';
      const receiptToken = payment.receipt_token || '';

      const isCompleted = paymentStatus === 'completed';
      let badgeClass = 'status-pending';
      let badgeText = 'Pending';
      let actionHtml = '';

      if (isCompleted) {
        badgeClass = 'status-completed';
        badgeText = 'Paid';
        
        let pdfButtonHtml = '';
        if (order.print_status !== 'delivered') {
          pdfButtonHtml = `<button type="button" class="btn-action btn-view btn-view-pdf" data-order-id="${order.id}" data-filename="order_${order.id}.pdf">View PDF</button>`;
        }

        actionHtml = `<div class="order-action-buttons">
             <button type="button" class="btn-action btn-status"
               data-order-id="${order.id}"
               data-receipt-token="${receiptToken}"
               data-order-cost="${order.total_cost || 0}">View Status</button>
             <a href="/order?receipt=${receiptToken}" class="btn-action btn-view">View Receipt</a>
             ${pdfButtonHtml}
           </div>`;
      } else if (paymentStatus === 'cancelled') {
        badgeClass = 'status-cancelled';
        badgeText = 'Cancelled';
        actionHtml = `<div class="order-action-buttons">
             <button type="button" class="btn-action btn-status" disabled
               data-order-id="${order.id}">Cancelled</button>
           </div>`;
      } else if (paymentStatus === 'refunded') {
        badgeClass = 'status-refunded';
        badgeText = 'Refunded';
        actionHtml = `<div class="order-action-buttons">
             <button type="button" class="btn-action btn-status" disabled
               data-order-id="${order.id}">Refunded</button>
           </div>`;
      } else if (paymentStatus === 'amount_mismatch_error') {
        badgeClass = 'status-warning';
        badgeText = 'Under Review';
        actionHtml = `<div class="order-action-buttons">
             <button type="button" class="btn-action btn-status" disabled
               data-order-id="${order.id}">Under Review</button>
           </div>`;
      } else if (paymentStatus === 'refund_pending') {
        badgeClass = 'status-warning';
        badgeText = 'Refund Processing';
        actionHtml = `<div class="order-action-buttons">
             <button type="button" class="btn-action btn-status" disabled
               data-order-id="${order.id}">Refund Processing</button>
           </div>`;
      } else if (paymentStatus === 'refund_failed') {
        badgeClass = 'status-cancelled';
        badgeText = 'Refund Failed';
        actionHtml = `<div class="order-action-buttons">
             <a href="/order?receipt=${receiptToken}" class="btn-action btn-view">View Details</a>
           </div>`;
      } else {
        actionHtml = `<div class="order-action-buttons"><a href="/checkout?order=${receiptToken}" class="btn-action btn-pay">Pay Now</a></div>`;
      }

      const card = document.createElement('div');
      card.className = `order-card ${isCompleted ? 'is-completed' : 'is-pending'}`;

      card.innerHTML = `
        <div class="order-number-gutter">
          <span>${String(index + 1).padStart(2, '0')}</span>
        </div>
        <div class="order-inner">
          <div class="order-info">
            <div class="order-info-left">
              <div class="order-title-row">
                <h3>Order #${order.id || 'N/A'}</h3>
                <span class="status-badge ${badgeClass}">${badgeText}</span>
              </div>
              <div class="order-meta">
                <span class="order-meta-chip">
                  <span class="order-meta-time">${orderTime || '—'}</span>
                  <span class="order-meta-divider">|</span>
                  <span class="order-meta-date">${orderDate || 'unknown date'}</span>
                </span>
              </div>
            </div>
            <div class="order-cost-block">
              <div class="order-cost-label">Total</div>
              <div class="order-cost">₹${parseFloat(order.total_cost || 0).toFixed(2)}</div>
            </div>
          </div>
          <div class="order-actions">
            ${actionHtml}
          </div>
        </div>
      `;

      card.dataset.orderId = String(order.id);
      card.dataset.orderCost = String(order.total_cost || 0);
      card.dataset.paymentStatus = paymentStatus;
      card.dataset.receiptToken = receiptToken;

      ordersList.appendChild(card);

      setTimeout(() => card.classList.add('reveal', 'visible'), 50 + index * 80);
    });

    ordersList.style.display = 'flex';
  }

  async function fetchAndRenderOrders() {
    skeletonLoader.style.display = 'flex';
    ordersList.style.display = 'none';
    if (paginationContainer) paginationContainer.innerHTML = '';
    
    try {
      const response = await fetch(`/api/users/orders?page=1&size=10000`);

      if (!response.ok) {
        if (response.status === 401) {
          window.location.href = '/login?next=/my_orders';
          return;
        }
        const msg = await parseApiErrorDetail(response) || 'Failed to fetch orders.';
        throw new Error(msg);
      }

      const data = await response.json();
      allOrders = data.items;
      allOrdersGlobal = allOrders;

      skeletonLoader.style.display = 'none';

      applyFiltersAndRender();

    } catch (err) {
      console.error("Error loading orders:", err);
      skeletonLoader.style.display = 'none';
      window.showToast(err.message || "Could not load your order history.");
    }
  }

  let currentStatusFilter = 'all';
  let currentDateFilter = 'all';

  function setupCustomDropdowns() {
    document.querySelectorAll('.custom-select-wrapper').forEach(wrapper => {
      const trigger = wrapper.querySelector('.custom-select-trigger');
      const options = wrapper.querySelectorAll('.custom-option');
      const textSpan = trigger.querySelector('span');

      trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        const isOpen = wrapper.classList.contains('open');
        document.querySelectorAll('.custom-select-wrapper').forEach(w => w.classList.remove('open'));
        if (!isOpen) {
          wrapper.classList.add('open');
        }
      });

      options.forEach(option => {
        option.addEventListener('click', function(e) {
          e.stopPropagation();
          options.forEach(opt => opt.classList.remove('selected'));
          this.classList.add('selected');
          textSpan.textContent = this.textContent;
          wrapper.classList.remove('open');
          
          if (wrapper.id === 'status-filter-wrapper') {
            currentStatusFilter = this.dataset.value;
          } else if (wrapper.id === 'date-filter-wrapper') {
            currentDateFilter = this.dataset.value;
          }
          
          currentPage = 1;
          applyFiltersAndRender();
        });
      });
    });

    document.addEventListener('click', function() {
      document.querySelectorAll('.custom-select-wrapper').forEach(w => w.classList.remove('open'));
    });
  }

  setupCustomDropdowns();

  fetchAndRenderOrders();
});
