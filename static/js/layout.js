import { getCurrentUser, logout } from '/static/js/auth.js';
import { PDFPreviewer } from '/static/js/pdf_viewer.js';

const navGuest   = document.getElementById('nav-guest');
const navUser    = document.getElementById('nav-user');
const navSkeleton = document.getElementById('nav-skeleton');
const mobileMenuGuest   = document.getElementById('mobile-menu-guest');
const mobileMenuUser    = document.getElementById('mobile-menu-user');
const mobileNavSkeleton = document.getElementById('mobile-nav-skeleton');

function isNavLinkActive(link, currentPath) {
  const href = link.getAttribute('href');
  if (!href || href === '#' || href.startsWith('#')) return false;
  try {
    const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '');
    return linkPath.length > 0 && linkPath === currentPath;
  } catch {
    return false;
  }
}

function highlightMobileLinks() {
  const currentPath = window.location.pathname.replace(/\/$/, '');
  mobileNav?.querySelectorAll('a[href]').forEach((a) => {
    a.classList.toggle('active', isNavLinkActive(a, currentPath));
  });
}

const navToggle      = document.getElementById('nav-toggle');
const mobileNav      = document.getElementById('mobile-nav');
const mobileBackdrop = document.getElementById('mobile-nav-backdrop');

function setMobileAuthMode(isUser) {
  mobileMenuGuest?.classList.toggle('is-active', !isUser);
  mobileMenuUser?.classList.toggle('is-active', isUser);
}

function openMobileNav() {
  mobileNav.classList.add('open');
  document.body.classList.add('mobile-nav-open');
  mobileNav.setAttribute('aria-hidden', 'false');
  navToggle.setAttribute('aria-expanded', 'true');
  navToggle.setAttribute('aria-label', 'Close menu');
  document.body.style.overflow = 'hidden';
}

function closeMobileNav() {
  mobileNav.classList.remove('open');
  document.body.classList.remove('mobile-nav-open');
  mobileNav.setAttribute('aria-hidden', 'true');
  navToggle.setAttribute('aria-expanded', 'false');
  navToggle.setAttribute('aria-label', 'Open menu');
  document.body.style.overflow = '';
}

if (navToggle && mobileNav) {
  navToggle.addEventListener('click', () => {
    navToggle.getAttribute('aria-expanded') === 'true'
      ? closeMobileNav()
      : openMobileNav();
  });
  mobileBackdrop?.addEventListener('click', closeMobileNav);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mobileNav.classList.contains('open')) closeMobileNav();
  });
  mobileNav.querySelectorAll('a').forEach((a) => {
    if (a.id !== 'mobile-account-settings') {
      a.addEventListener('click', closeMobileNav);
    }
  });
}

function showSkeleton() {
  navSkeleton.style.display = 'block';
  if (mobileNavSkeleton) mobileNavSkeleton.style.display = 'block';
  mobileMenuGuest?.classList.remove('is-active');
  mobileMenuUser?.classList.remove('is-active');
}

function hideSkeleton() {
  navSkeleton.style.display = 'none';
  if (mobileNavSkeleton) mobileNavSkeleton.style.display = 'none';
}

function applyUserUI(user) {
  hideSkeleton();
  navGuest.classList.remove('nav-visible');
  navUser.classList.add('nav-visible');
  setMobileAuthMode(true);
  document.getElementById('nav-username').textContent = user.username;
  const mobileUsername = document.getElementById('mobile-nav-username');
  if (mobileUsername) mobileUsername.textContent = user.username;

  highlightMobileLinks();

  const navLinks = document.querySelector('.nav-links');
  if (navLinks) {
    const hasMyOrders = Array.from(navLinks.querySelectorAll('a')).some(a => {
      try {
        const path = new URL(a.href, window.location.origin).pathname.replace(/\/$/, '');
        return path === '/my_orders' || path === '/my-orders';
      } catch {
        return false;
      }
    });
    if (!hasMyOrders) {
      const myOrdersLink = document.createElement('a');
      myOrdersLink.href = "/my_orders";
      myOrdersLink.id = 'nav-my-orders-dynamic';
      myOrdersLink.textContent = 'My Orders';
      const currentPath = window.location.pathname.replace(/\/$/, '');
      const isMyOrdersActive = currentPath === '/my_orders' || currentPath === '/my-orders';
      if (isMyOrdersActive) {
        myOrdersLink.classList.add('active');
      }
      navLinks.appendChild(myOrdersLink);
    }
  }

  const avatarBtn      = document.getElementById('avatar-toggle');
  const avatarDropdown = document.getElementById('avatar-dropdown');
  if (!avatarBtn.dataset.bound) {
    avatarBtn.dataset.bound = '1';
    avatarBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = avatarDropdown.classList.toggle('show');
      avatarBtn.setAttribute('aria-expanded', open);
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.nav-avatar-wrapper')) {
        avatarDropdown.classList.remove('show');
        avatarBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }
}

function applyGuestUI() {
  hideSkeleton();
  navUser.classList.remove('nav-visible');
  navGuest.classList.add('nav-visible');
  setMobileAuthMode(false);

  const dynamicLink = document.getElementById('nav-my-orders-dynamic');
  if (dynamicLink) {
    dynamicLink.remove();
  }
  highlightMobileLinks();
}

async function updateAuthUI() {
  const raw = sessionStorage.getItem('pe_user');
  if (raw) {
    try { applyUserUI(JSON.parse(raw)); }
    catch { sessionStorage.removeItem('pe_user'); showSkeleton(); }
  } else {
    showSkeleton();
  }

  try {
    const user = await getCurrentUser();
    if (user) {
      sessionStorage.setItem('pe_user', JSON.stringify(user));
      applyUserUI(user);
    } else {
      sessionStorage.removeItem('pe_user');
      applyGuestUI();
    }
  } catch {
    if (!raw) applyGuestUI();
    else hideSkeleton();
  }
}

updateAuthUI();

async function handleLogout(e) {
  e.preventDefault();
  sessionStorage.removeItem('pe_user');
  const btn = e.currentTarget;
  btn.style.pointerEvents = 'none';
  if (btn.id === 'mobile-logout-btn') {
    btn.innerHTML = '<img src="/static/icons/login.svg" style="height: 20px; width: auto; vertical-align: middle; margin-right: 10px; transform: scaleX(-1);" class="svg-icon"> Logging out…';
  } else {
    btn.innerHTML = '<img src="/static/icons/login.svg" style="height: 24px; width: auto; vertical-align: middle; margin-right: 8px; transform: scaleX(-1);" class="svg-icon"> Logging out…';
  }
  closeMobileNav();
  await logout();
}

const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

const mobileLogoutBtn = document.getElementById('mobile-logout-btn');
if (mobileLogoutBtn) mobileLogoutBtn.addEventListener('click', handleLogout);

function initPrinteaseBarcodes() {
  const widths = [3, 1, 2, 1, 3, 2, 1, 4, 2, 1, 3, 1, 2, 3, 1, 2, 1, 3, 2, 1];
  document.querySelectorAll('.printease-badge__barcode').forEach((bc) => {
    if (bc.childElementCount) return;
    widths.forEach((w) => {
      const bar = document.createElement('span');
      bar.style.width = w + 'px';
      bc.appendChild(bar);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initPrinteaseBarcodes();
  document.querySelectorAll('.reveal').forEach((el, i) => {
    setTimeout(() => el.classList.add('visible'), 80 + i * 140);
  });
});

window.showToast = function (msg, duration = 3500) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
};

(function () {
  const backdrop = document.getElementById('globalModal');
  const closeBtn = document.getElementById('modalClose');
  const iconEl   = document.getElementById('modalIcon');
  const titleEl  = document.getElementById('modalTitle');
  const bodyEl   = document.getElementById('modalBody');
  const footerEl = document.getElementById('modalFooter');

  const ICONS = {
    error: '<img src="/static/icons/error.svg" class="svg-icon" style="height: 1em; width: auto;">',
    warning: '<img src="/static/icons/warning.svg" class="svg-icon" style="height: 1em; width: auto;">',
    info: '<img src="/static/icons/info.svg" class="svg-icon" style="height: 1em; width: auto;">'
  };
  let _dismissTimer = null;

  function hideModal() {
    backdrop.classList.remove('modal-open');
    clearTimeout(_dismissTimer);
    setTimeout(() => { document.body.style.overflow = ''; }, 260);
  }

  function showModal(opts = {}) {
    const type      = opts.type    || 'error';
    const title     = opts.title   || 'Something went wrong';
    const message   = opts.message || '';
    const primary   = opts.primary   || null;
    const secondary = opts.secondary || null;
    const autoDismiss = opts.autoDismiss || null;

    iconEl.className  = 'modal-icon ' + type;
    iconEl.innerHTML = ICONS[type] || ICONS.error;
    titleEl.textContent = title;
    bodyEl.textContent  = message;

    footerEl.innerHTML = '';

    if (secondary) {
      const btn = secondary.href
        ? Object.assign(document.createElement('a'), { href: secondary.href, className: 'modal-btn-secondary', textContent: secondary.label })
        : Object.assign(document.createElement('button'), { type: 'button', className: 'modal-btn-secondary', textContent: secondary.label });
      if (secondary.action) btn.addEventListener('click', () => { hideModal(); secondary.action(); });
      else btn.addEventListener('click', hideModal);
      footerEl.appendChild(btn);
    }

    if (primary) {
      const btn = primary.href
        ? Object.assign(document.createElement('a'), { href: primary.href, className: 'modal-btn-primary', textContent: primary.label })
        : Object.assign(document.createElement('button'), { type: 'button', className: 'modal-btn-primary', textContent: primary.label });

      if (primary.action) {
        btn.addEventListener('click', () => { hideModal(); primary.action(); });
      } else if (!primary.href) {
        btn.addEventListener('click', hideModal);
      }

      footerEl.appendChild(btn);
    }

    if (!primary && !secondary) {
      const btn = Object.assign(document.createElement('button'), { type: 'button', className: 'modal-btn-primary', textContent: 'Dismiss' });
      btn.addEventListener('click', hideModal);
      footerEl.appendChild(btn);
    }

    document.body.style.overflow = 'hidden';
    backdrop.classList.add('modal-open');

    if (autoDismiss) {
      clearTimeout(_dismissTimer);
      _dismissTimer = setTimeout(hideModal, autoDismiss);
    }
  }

  closeBtn.addEventListener('click', hideModal);

  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) hideModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && backdrop.classList.contains('modal-open')) hideModal();
  });

  window.showModal = showModal;
  window.hideModal = hideModal;
})();

(function () {
  const modal = document.getElementById('pdfViewerModal');
  const closeBtn = document.getElementById('pdfModalClose');
  const titleEl = document.getElementById('pdfModalTitle');

  const pdfPreviewer = new PDFPreviewer({
    previewBoxId: 'pdfModalPreview',
    pagesElId: 'pdfModalPreviewPages',
    loadingElId: 'pdfModalPreviewLoading',
    errorElId: 'pdfModalPreviewError',
    zoomBarId: 'pdfModalZoomBar',
    zoomLabelId: 'pdfModalZoomLabel',
    zoomInId: 'pdfModalZoomIn',
    zoomOutId: 'pdfModalZoomOut',
    resetId: 'pdfModalZoomReset'
  });

  function hidePdfModal() {
    modal.classList.remove('modal-open');
    pdfPreviewer.cleanup();
    document.body.style.overflow = '';
  }

  function showPdfModal(fileObj, filename) {
    titleEl.textContent = filename || 'document.pdf';
    document.body.style.overflow = 'hidden';
    modal.classList.add('modal-open');
    pdfPreviewer.renderPdfPreview(fileObj);
  }

  closeBtn.addEventListener('click', hidePdfModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) hidePdfModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('modal-open')) hidePdfModal();
  });

  window.viewPdf = showPdfModal;
})();
