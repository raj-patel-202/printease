export class PDFPreviewer {
  constructor(options = {}) {
    this.previewBox = document.getElementById(options.previewBoxId);
    this.pagesEl = document.getElementById(options.pagesElId);
    this.loadingEl = document.getElementById(options.loadingElId);
    this.errorEl = document.getElementById(options.errorElId);
    this.zoomBar = document.getElementById(options.zoomBarId);
    this.zoomLabel = document.getElementById(options.zoomLabelId);
    this.zoomInBtn = document.getElementById(options.zoomInId);
    this.zoomOutBtn = document.getElementById(options.zoomOutId);
    this.resetBtn = document.getElementById(options.resetId);

    this.pdfRenderToken = 0;
    this.pdfPreviewBlobUrl = null;
    this.pdfJsLib = null;

    this.PDF_ZOOM_MIN  = 0.5;
    this.PDF_ZOOM_MAX  = 3;
    this.PDF_ZOOM_STEP = 0.25;

    this.state = {
      file: null,
      pdfDoc: null,
      zoom: 1,
      usesCanvas: false,
    };

    this.PDFJS_LOCAL  = '/static/js/vendor/pdf.min.js';
    this.PDFJS_WORKER = '/static/js/vendor/pdf.worker.min.js';

    this.initZoomControls();
  }

  normalizePdfFile(raw) {
    if (raw instanceof Blob) {
      if (raw.type === 'application/pdf') return raw;
      return new Blob([raw], { type: 'application/pdf' });
    }
    throw new Error('Invalid file object');
  }

  loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const s = document.createElement('script');
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(s);
    });
  }

  async loadPdfJs() {
    if (this.pdfJsLib) return this.pdfJsLib;
    if (!window.pdfjsLib) {
      await this.loadScript(this.PDFJS_LOCAL);
    }
    if (!window.pdfjsLib) throw new Error('PDF.js failed to load');
    this.pdfJsLib = window.pdfjsLib;
    this.pdfJsLib.GlobalWorkerOptions.workerSrc = this.PDFJS_WORKER;
    return this.pdfJsLib;
  }

  revokePreviewUrl() {
    if (this.pdfPreviewBlobUrl) {
      URL.revokeObjectURL(this.pdfPreviewBlobUrl);
      this.pdfPreviewBlobUrl = null;
    }
  }

  setPreviewState(state) {
    if (this.loadingEl) this.loadingEl.hidden = state !== 'loading';
    if (this.pagesEl) this.pagesEl.hidden = state !== 'ready';
    if (this.errorEl) this.errorEl.hidden = state !== 'error';
  }

  updateZoomBar() {
    if (!this.zoomBar) return;
    const show = this.state.usesCanvas && this.state.pdfDoc;
    this.zoomBar.hidden = !show;
    if (!show) return;

    if (this.zoomLabel) {
      this.zoomLabel.textContent = `${Math.round(this.state.zoom * 100)}%`;
    }
    if (this.zoomOutBtn) {
      this.zoomOutBtn.disabled = this.state.zoom <= this.PDF_ZOOM_MIN;
    }
    if (this.zoomInBtn) {
      this.zoomInBtn.disabled = this.state.zoom >= this.PDF_ZOOM_MAX;
    }
  }

  async renderCanvasPages(pdf, renderId, zoom) {
    const containerWidth = Math.max(this.previewBox?.clientWidth || 320, 280);
    const maxPages = pdf.numPages;
    let renderedAny = false;

    this.pagesEl.innerHTML = '';

    for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
      if (renderId !== this.pdfRenderToken) return renderedAny;

      const page     = await pdf.getPage(pageNum);
      const baseVp   = page.getViewport({ scale: 1 });
      const cssScale = (containerWidth / baseVp.width) * zoom;
      const dpr      = Math.min(window.devicePixelRatio || 1, 3);
      const renderScale = cssScale * dpr;
      const viewport = page.getViewport({ scale: renderScale });
      const cssWidth  = Math.floor(baseVp.width * cssScale);
      const cssHeight = Math.floor(baseVp.height * cssScale);

      if (pdf.numPages > 1) {
        const label = document.createElement('p');
        label.className = 'pdf-page-label';
        label.textContent = `Page ${pageNum} of ${pdf.numPages}`;
        this.pagesEl.appendChild(label);
      }

      const wrap = document.createElement('div');
      wrap.className = 'pdf-page-wrap';
      const canvas = document.createElement('canvas');
      const ctx    = canvas.getContext('2d', { alpha: false });
      canvas.className = 'pdf-page-canvas';
      canvas.dataset.page = String(pageNum);
      canvas.width  = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width  = `${cssWidth}px`;
      canvas.style.height = `${cssHeight}px`;
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      wrap.appendChild(canvas);
      this.pagesEl.appendChild(wrap);

      await page.render({
        canvasContext: ctx,
        viewport,
        intent: 'display',
      }).promise;

      renderedAny = true;
    }

    return renderedAny;
  }

  async refreshCanvasPreview() {
    if (!this.state.pdfDoc) return;
    const renderId = ++this.pdfRenderToken;
    this.setPreviewState('loading');
    try {
      const ok = await this.renderCanvasPages(
        this.state.pdfDoc,
        renderId,
        this.state.zoom
      );
      if (renderId !== this.pdfRenderToken) return;
      if (ok) {
        this.setPreviewState('ready');
        this.updateZoomBar();
      }
    } catch (err) {
      console.warn('Zoom re-render failed:', err);
      if (renderId === this.pdfRenderToken) this.setPreviewState('ready');
    }
  }

  initZoomControls() {
    this.zoomInBtn?.addEventListener('click', () => {
      this.state.zoom = Math.min(this.PDF_ZOOM_MAX, this.state.zoom + this.PDF_ZOOM_STEP);
      this.refreshCanvasPreview();
    });
    this.zoomOutBtn?.addEventListener('click', () => {
      this.state.zoom = Math.max(this.PDF_ZOOM_MIN, this.state.zoom - this.PDF_ZOOM_STEP);
      this.refreshCanvasPreview();
    });
    this.resetBtn?.addEventListener('click', () => {
      this.state.zoom = 1;
      this.refreshCanvasPreview();
    });
  }

  createPreviewUrl(file) {
    this.revokePreviewUrl();
    this.pdfPreviewBlobUrl = URL.createObjectURL(this.normalizePdfFile(file));
    return this.pdfPreviewBlobUrl;
  }

  async tryCanvasPreview(file, renderId, zoom = 1) {
    const lib  = await this.loadPdfJs();
    const data = await this.normalizePdfFile(file).arrayBuffer();
    if (renderId !== this.pdfRenderToken) return false;

    const pdf = await lib.getDocument({
      data,
      disableWorker: true,
      disableAutoFetch: true,
      disableStream: true,
      isEvalSupported: false,
    }).promise;

    if (renderId !== this.pdfRenderToken) return false;

    this.state.file = file;
    this.state.pdfDoc = pdf;
    this.state.zoom = zoom;
    this.state.usesCanvas = true;

    return this.renderCanvasPages(pdf, renderId, zoom);
  }

  tryEmbedPreview(file) {
    const url = this.createPreviewUrl(file);
    this.pagesEl.innerHTML = '';
    const embed = document.createElement('embed');
    embed.className = 'pdf-fallback-embed';
    embed.type = 'application/pdf';
    embed.src = `${url}#toolbar=0&navpanes=0&view=FitH`;
    this.pagesEl.appendChild(embed);
    return true;
  }

  tryObjectPreview(file) {
    const url = this.createPreviewUrl(file);
    this.pagesEl.innerHTML = '';
    const obj = document.createElement('object');
    obj.className = 'pdf-fallback-object';
    obj.type = 'application/pdf';
    obj.data = `${url}#toolbar=0&navpanes=0&view=FitH`;
    obj.innerHTML = '<p style="color:#fff;padding:2rem;text-align:center;">PDF preview not supported.</p>';
    this.pagesEl.appendChild(obj);
    return true;
  }

  tryIframePreview(file) {
    const url = this.createPreviewUrl(file);
    this.pagesEl.innerHTML = '';
    const iframe = document.createElement('iframe');
    iframe.className = 'pdf-fallback-frame';
    iframe.src = `${url}#toolbar=0&navpanes=0&view=FitH`;
    iframe.title = 'Document Preview';
    this.pagesEl.appendChild(iframe);
    return true;
  }

  async renderPdfPreview(file) {
    const renderId = ++this.pdfRenderToken;

    this.state.pdfDoc = null;
    this.state.usesCanvas = false;
    this.state.zoom = 1;
    this.updateZoomBar();

    this.setPreviewState('loading');
    this.pagesEl.innerHTML = '';

    try {
      const ok = await this.tryCanvasPreview(file, renderId, 1);
      if (renderId !== this.pdfRenderToken) return;
      if (ok && this.pagesEl.querySelector('canvas')) {
        this.setPreviewState('ready');
        this.updateZoomBar();
        return;
      }
    } catch (err) {
      console.warn('Canvas PDF preview failed:', err);
      if (renderId !== this.pdfRenderToken) return;
      this.pagesEl.innerHTML = '';
      this.state.usesCanvas = false;
      this.state.pdfDoc = null;
    }

    try {
      this.tryEmbedPreview(file);
      if (renderId !== this.pdfRenderToken) return;
      this.setPreviewState('ready');
      return;
    } catch (err) {
      console.warn('Embed PDF preview failed:', err);
      if (renderId !== this.pdfRenderToken) return;
      this.pagesEl.innerHTML = '';
    }

    try {
      this.tryObjectPreview(file);
      if (renderId !== this.pdfRenderToken) return;
      this.setPreviewState('ready');
      return;
    } catch (err) {
      console.warn('Object PDF preview failed:', err);
      if (renderId !== this.pdfRenderToken) return;
      this.pagesEl.innerHTML = '';
    }

    try {
      this.tryIframePreview(file);
      if (renderId !== this.pdfRenderToken) return;
      this.setPreviewState('ready');
      return;
    } catch (err) {
      console.warn('Iframe PDF preview failed:', err);
    }

    if (renderId === this.pdfRenderToken) {
      this.setPreviewState('error');
    }
  }

  cleanup() {
    this.revokePreviewUrl();
    if (this.pagesEl) this.pagesEl.innerHTML = '';
    this.state.pdfDoc = null;
    this.state.file = null;
  }
}
