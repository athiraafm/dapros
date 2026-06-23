// ===== DAPROS - Shared JavaScript =====

// ===== Toast Notifications =====
function showToast(message, type = 'info', duration = 3500) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const container = document.getElementById('toast-container') || createToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span style="font-size:16px">${icons[type]}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease forwards';
    toast.addEventListener('animationend', () => toast.remove());
  }, duration);
}

function createToastContainer() {
  const container = document.createElement('div');
  container.id = 'toast-container';
  container.className = 'toast-container';
  document.body.appendChild(container);
  return container;
}

// Add toastOut animation
const toastStyle = document.createElement('style');
toastStyle.textContent = `
  @keyframes toastOut {
    from { opacity: 1; transform: translateX(0); }
    to { opacity: 0; transform: translateX(20px); }
  }
`;
document.head.appendChild(toastStyle);

// ===== File Upload Helpers =====
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const icons = { xlsx: '📊', xls: '📊', csv: '📋', pdf: '📄', zip: '🗜️', txt: '📝' };
  return icons[ext] || '📎';
}

// ===== Drag and Drop Upload =====
function initUploadZone(zoneEl, fileInput, onFilesSelected) {
  if (!zoneEl || !fileInput) return;

  zoneEl.addEventListener('click', (e) => {
    if (!e.target.closest('.file-remove')) {
      fileInput.click();
    }
  });

  zoneEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    zoneEl.classList.add('drag-over');
  });

  zoneEl.addEventListener('dragleave', () => {
    zoneEl.classList.remove('drag-over');
  });

  zoneEl.addEventListener('drop', (e) => {
    e.preventDefault();
    zoneEl.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    onFilesSelected(files);
  });

  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files);
    onFilesSelected(files);
    fileInput.value = '';
  });
}

// ===== Progress Simulation =====
function simulateProgress(barEl, pctEl, logEl, steps, onComplete) {
  let current = 0;
  const total = steps.length;

  function nextStep() {
    if (current >= total) {
      onComplete && onComplete();
      return;
    }

    const step = steps[current];
    const targetPct = Math.round(((current + 1) / total) * 100);

    // Update bar
    barEl.style.width = targetPct + '%';
    pctEl.textContent = targetPct + '%';

    // Add log entry
    if (logEl && step.log) {
      const entry = document.createElement('div');
      entry.className = `log-entry ${step.type || ''}`;
      entry.textContent = step.log;
      logEl.appendChild(entry);
      logEl.scrollTop = logEl.scrollHeight;
    }

    current++;
    setTimeout(nextStep, step.delay || 600);
  }

  nextStep();
}

// ===== Step Indicator ====
function updateSteps(stepItems, activeIndex) {
  stepItems.forEach((item, i) => {
    const circle = item.querySelector('.step-circle');
    const line = item.querySelector('.step-line');
    if (!circle) return;

    circle.classList.remove('active', 'done');
    if (line) line.classList.remove('done');

    if (i < activeIndex) {
      circle.classList.add('done');
      circle.textContent = '✓';
      if (line) line.classList.add('done');
    } else if (i === activeIndex) {
      circle.classList.add('active');
    }
  });
}

// ===== Sidebar Mobile Toggle =====
function initSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  const menuBtn = document.querySelector('.mobile-menu-btn');

  if (menuBtn) {
    menuBtn.addEventListener('click', () => {
      sidebar?.classList.toggle('open');
      overlay?.classList.toggle('show');
    });
  }

  overlay?.addEventListener('click', () => {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('show');
  });
}

// ===== Number Input Helpers =====
function initNumInputs() {
  document.querySelectorAll('.form-input-num').forEach(wrap => {
    const minus = wrap.querySelector('.num-btn.minus');
    const plus = wrap.querySelector('.num-btn.plus');
    const input = wrap.querySelector('.num-input');
    if (!minus || !plus || !input) return;

    minus.addEventListener('click', () => {
      const min = parseInt(input.dataset.min || 0);
      const val = parseInt(input.value) || 0;
      if (val > min) input.value = val - 1;
      input.dispatchEvent(new Event('input'));
    });

    plus.addEventListener('click', () => {
      const max = parseInt(input.dataset.max || 9999);
      const val = parseInt(input.value) || 0;
      if (val < max) input.value = val + 1;
      input.dispatchEvent(new Event('input'));
    });
  });
}

// ===== Init on Load =====
document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initNumInputs();
});

// ===== Backend API Config =====
const API_BASE = 'https://dapros-production.up.railway.app';
function downloadOutput(fileId) {
  if (!fileId) return showToast('File output belum tersedia', 'warning');
  window.location.href = `${API_BASE}/api/download/${fileId}`;
}
