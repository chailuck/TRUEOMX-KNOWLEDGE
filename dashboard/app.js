// ============================================================
// TRUEOMX AI — Discovery Dashboard
// ============================================================

const CATALOG = [
  {
    id: 'api-docs',
    label: 'API Documentation',
    icon: '📡',
    defaultOpen: true,
    items: [
      {
        id: 'api-html',
        label: 'REST/SOAP API Reference',
        path: '/output/Summary/TRUEOMX_REST_SOAP_API.html',
        type: 'html',
        size: '326 KB',
        description: 'Complete REST & SOAP API documentation with all endpoints, request/response schemas, and integration examples.',
        tags: ['REST', 'SOAP', 'HTML', 'API'],
      },
      {
        id: 'api-static',
        label: 'API Static View',
        path: '/output/Summary/TRUEOMX_REST_SOAP_Static.html',
        type: 'html',
        size: '129 KB',
        description: 'Static HTML view of the API specification — lighter weight, quick reference for endpoint browsing.',
        tags: ['API', 'Static', 'HTML'],
      },
      {
        id: 'api-json',
        label: 'OpenAPI Spec (JSON)',
        path: '/output/Summary/TRUEOMX_REST_SOAP_API.json',
        type: 'json',
        size: '550 KB',
        description: 'OpenAPI 3.0 specification in JSON format. Import into Postman, Insomnia, or any API tool.',
        tags: ['OpenAPI', 'JSON', 'Swagger'],
      },
      {
        id: 'api-yaml',
        label: 'OpenAPI Spec (YAML)',
        path: '/output/Summary/TRUEOMX_REST_SOAP_API.yaml',
        type: 'yaml',
        size: '400 KB',
        description: 'OpenAPI 3.0 specification in YAML format. Human-readable API contract for review and tooling.',
        tags: ['OpenAPI', 'YAML', 'Swagger'],
      },
    ],
  },
  {
    id: 'reports',
    label: 'Analysis Reports',
    icon: '📊',
    defaultOpen: true,
    items: [
      {
        id: 'assessment',
        label: 'Migration Assessment',
        path: '/output/Summary/TRUEOMX_Assessment.xlsx',
        type: 'xlsx',
        size: '545 KB',
        description: 'Migration complexity assessment — effort estimates, risk ratings, and modernization priorities per component.',
        tags: ['Assessment', 'Migration', 'Excel'],
      },
      {
        id: 'integration-spec',
        label: 'Integration Specification',
        path: '/output/Summary/TRUEOMX_Integration_Spec.xlsx',
        type: 'xlsx',
        size: '886 KB',
        description: 'Complete integration specification covering all ESB, BW, BE, EJB interactions and interface contracts.',
        tags: ['Integration', 'ESB', 'BW', 'BE', 'Excel'],
      },
    ],
  },
  {
    id: 'field-mappings',
    label: 'Field Mappings',
    icon: '🗂️',
    defaultOpen: true,
    items: [
      {
        id: 'mapping-catalog',
        label: 'FM Field Mapping Catalog',
        path: '/FM_Field_Mapping_Catalog.html',
        type: 'html',
        size: '91 KB',
        description: 'Comprehensive catalog of all field mappings across the TIBCO FM system. Searchable HTML report.',
        tags: ['FM', 'Mapping', 'Catalog'],
      },
      {
        id: 'mapping-detail',
        label: 'Field Mapping Detail',
        path: '/output/Summary/TRUEOMX_Field_Mapping.xlsx',
        type: 'xlsx',
        size: '660 KB',
        description: 'Detailed field-level mapping matrix for data transformation, source-to-target traceability.',
        tags: ['Mapping', 'Detail', 'Excel'],
      },
    ],
  },
  {
    id: 'fm-logic',
    label: 'FM Logic',
    icon: '🔀',
    defaultOpen: true,
    items: [
      {
        id: 'ats-bundle',
        label: 'Request ATS Bundle Product',
        path: '/output/FMlogic/Request_ATS_BUNDLEPRODUCT_NUMBER.html',
        type: 'html',
        size: '95 KB',
        description: 'FM Logic documentation for the Request ATS Bundle Product Number flow — rules, conditions, mappings.',
        tags: ['FM', 'ATS', 'Bundle', 'Logic'],
      },
      {
        id: 'bdh-direct-debit',
        label: 'Request BDH Update Direct Debit Status',
        path: '/output/FMlogic/Request_BDH_UPDATE_DIRECT_DEBIT_STATUS.html',
        type: 'html',
        size: '~75 KB',
        description: 'FM Logic documentation for cancelling Direct Debit mandates across all Customer accounts via BDH (Bank Direct Handle) JMS integration.',
        tags: ['FM', 'BDH', 'DirectDebit', 'Banking', 'Logic'],
      },
    ],
  },
];

// ── State ────────────────────────────────────────────────────
const state = {
  currentId: 'overview',
  sectionOpen: {},
  searchTimeout: null,
};

// ── Entry ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  CATALOG.forEach(s => { state.sectionOpen[s.id] = s.defaultOpen; });

  buildSidebar();
  buildSearchNav();

  const hash = location.hash.replace('#', '');
  navigate(hash || 'overview', true);

  window.addEventListener('hashchange', () => {
    const id = location.hash.replace('#', '');
    if (id) navigate(id, true);
  });
});

// ── Sidebar ──────────────────────────────────────────────────
function buildSidebar() {
  const nav = document.getElementById('sidebar-nav');
  nav.innerHTML = '';

  // Overview link
  const overviewEl = document.createElement('div');
  overviewEl.className = 'nav-row';
  overviewEl.dataset.id = 'overview';
  overviewEl.innerHTML = `<span class="icon">🏠</span><span>Overview</span>`;
  overviewEl.addEventListener('click', () => navigate('overview'));
  nav.appendChild(overviewEl);

  // Sections
  CATALOG.forEach(section => {
    const sectionEl = document.createElement('div');
    sectionEl.dataset.section = section.id;

    const header = document.createElement('div');
    header.className = `nav-row ${state.sectionOpen[section.id] ? 'open' : ''}`;
    header.innerHTML = `
      <span class="icon">${section.icon}</span>
      <span>${section.label}</span>
      <span class="chevron">▶</span>
    `;
    header.addEventListener('click', () => toggleSection(section.id));

    const children = document.createElement('div');
    children.className = `nav-children ${state.sectionOpen[section.id] ? 'open' : ''}`;
    children.id = `section-children-${section.id}`;

    section.items.forEach(item => {
      const itemEl = document.createElement('div');
      itemEl.className = 'nav-item';
      itemEl.dataset.id = item.id;
      itemEl.innerHTML = `
        <span class="type-dot dot-${item.type}"></span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${item.label}</span>
        <span class="nav-badge badge-${item.type}">${item.type}</span>
      `;
      itemEl.addEventListener('click', () => navigate(item.id));
      children.appendChild(itemEl);
    });

    sectionEl.appendChild(header);
    sectionEl.appendChild(children);
    nav.appendChild(sectionEl);
  });
}

function toggleSection(sectionId) {
  state.sectionOpen[sectionId] = !state.sectionOpen[sectionId];
  const isOpen = state.sectionOpen[sectionId];
  const header = document.querySelector(`[data-section="${sectionId}"] .nav-row`);
  const children = document.getElementById(`section-children-${sectionId}`);
  header.classList.toggle('open', isOpen);
  children.classList.toggle('open', isOpen);
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('mobile-open');
  document.getElementById('overlay').classList.toggle('mobile-open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('mobile-open');
  document.getElementById('overlay').classList.remove('mobile-open');
}

document.getElementById('menu-btn').addEventListener('click', toggleSidebar);

// ── Navigation ───────────────────────────────────────────────
function navigate(id, skipHash = false) {
  closeSidebar();
  clearSearch();

  state.currentId = id;
  if (!skipHash) location.hash = id;

  // Update active highlights
  document.querySelectorAll('[data-id]').forEach(el => el.classList.remove('active'));
  const active = document.querySelector(`[data-id="${id}"]`);
  if (active) active.classList.add('active');

  const item = findItem(id);
  setBreadcrumb(id, item);

  if (id === 'overview') {
    renderOverview();
  } else if (item) {
    renderFileViewer(item);
  }
}

function findItem(id) {
  for (const section of CATALOG) {
    const found = section.items.find(i => i.id === id);
    if (found) return { ...found, sectionLabel: section.label, sectionId: section.id };
  }
  return null;
}

function allItems() {
  return CATALOG.flatMap(s => s.items.map(i => ({ ...i, sectionLabel: s.label })));
}

// ── Breadcrumb ───────────────────────────────────────────────
function setBreadcrumb(id, item) {
  const el = document.getElementById('breadcrumb');
  if (id === 'overview') {
    el.innerHTML = `<span class="crumb-cur">Overview</span>`;
  } else if (item) {
    el.innerHTML = `
      <span class="crumb-link" onclick="navigate('overview')">Overview</span>
      <span class="crumb-sep">/</span>
      <span>${item.sectionLabel}</span>
      <span class="crumb-sep">/</span>
      <span class="crumb-cur">${item.label}</span>
    `;
  }
}

// ── Overview ─────────────────────────────────────────────────
function renderOverview() {
  const items = allItems();
  const htmlCount = items.filter(i => i.type === 'html').length;
  const xlsxCount = items.filter(i => i.type === 'xlsx').length;
  const specCount = items.filter(i => i.type === 'json' || i.type === 'yaml').length;

  const html = `
    <div class="overview-page">
      <div class="page-heading">
        <h1>TRUEOMX AI — Discovery Artifacts</h1>
        <p>Legacy TIBCO Order Management transformation analysis · ${items.length} documents across ${CATALOG.length} categories</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-ico ico-blue">📁</div>
          <div><div class="stat-val">${items.length}</div><div class="stat-lbl">Total Artifacts</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-ico ico-amber">🌐</div>
          <div><div class="stat-val">${htmlCount}</div><div class="stat-lbl">HTML Reports</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-ico ico-green">📊</div>
          <div><div class="stat-val">${xlsxCount}</div><div class="stat-lbl">Excel Reports</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-ico ico-purple">⚙️</div>
          <div><div class="stat-val">${specCount}</div><div class="stat-lbl">API Specs</div></div>
        </div>
      </div>

      ${CATALOG.map(section => `
        <div class="section-row">
          <span style="font-size:16px">${section.icon}</span>
          <h2>${section.label}</h2>
          <span class="count">${section.items.length} file${section.items.length !== 1 ? 's' : ''}</span>
        </div>
        <div class="docs-grid">
          ${section.items.map(item => renderDocCard(item)).join('')}
        </div>
      `).join('')}
    </div>
  `;

  document.getElementById('content').innerHTML = html;
}

function renderDocCard(item) {
  return `
    <div class="doc-card" onclick="navigate('${item.id}')">
      <div class="doc-card-top">
        <div class="doc-type-ico ico-${item.type}">${fileEmoji(item.type)}</div>
        <div style="flex:1;min-width:0">
          <div class="doc-name">${item.label}</div>
          <div class="doc-size">${item.size}</div>
        </div>
      </div>
      <div class="doc-desc">${item.description}</div>
      <div class="doc-footer">
        ${item.tags.slice(0, 3).map(t => `<span class="tag">${t}</span>`).join('')}
        <span class="doc-badge badge-${item.type}" style="margin-left:auto">${item.type.toUpperCase()}</span>
      </div>
    </div>
  `;
}

// ── File Viewer ───────────────────────────────────────────────
function renderFileViewer(item) {
  const fileBar = `
    <div class="file-bar">
      <div class="file-bar-ico ico-${item.type}">${fileEmoji(item.type)}</div>
      <div class="file-bar-info">
        <div class="file-bar-name">${item.label}</div>
        <div class="file-bar-meta">${item.size} &middot; ${item.type.toUpperCase()} &middot; ${item.sectionLabel}</div>
      </div>
      <div class="file-actions">
        ${item.type === 'html' ? `<button class="btn btn-ghost" onclick="openTab('${item.path}')"><span>🔗</span><span>New Tab</span></button>` : ''}
        <a class="btn btn-primary" href="${item.path}" download><span>⬇</span><span>Download</span></a>
      </div>
    </div>
  `;

  const content = document.getElementById('content');

  if (item.type === 'html') {
    content.innerHTML = `
      <div class="file-viewer">
        ${fileBar}
        <div class="iframe-wrap">
          <iframe src="${item.path}" title="${item.label}"></iframe>
        </div>
      </div>
    `;
  } else if (item.type === 'xlsx') {
    content.innerHTML = `
      <div class="file-viewer">
        ${fileBar}
        <div class="download-wrap">
          <div class="download-card">
            <div class="big-icon">📊</div>
            <h2>${item.label}</h2>
            <p class="dc-desc">${item.description}</p>
            <div class="info-grid">
              <div class="info-cell"><div class="lbl">Format</div><div class="val">Microsoft Excel (.xlsx)</div></div>
              <div class="info-cell"><div class="lbl">File Size</div><div class="val">${item.size}</div></div>
              <div class="info-cell"><div class="lbl">Category</div><div class="val">${item.sectionLabel}</div></div>
              <div class="info-cell"><div class="lbl">Tags</div><div class="val">${item.tags.join(', ')}</div></div>
            </div>
            <a class="btn btn-primary" href="${item.path}" download style="justify-content:center;width:100%;padding:12px 0;font-size:15px;">
              ⬇ &nbsp;Download Excel File
            </a>
          </div>
        </div>
      </div>
    `;
  } else if (item.type === 'json' || item.type === 'yaml') {
    content.innerHTML = `
      <div class="file-viewer">
        ${fileBar}
        <div class="code-viewer" id="code-viewer">
          <div class="loading-state" style="height:200px">
            <div class="spinner"></div>
            <span>Loading ${item.type.toUpperCase()} content…</span>
          </div>
        </div>
      </div>
    `;
    loadCodeFile(item);
  }
}

async function loadCodeFile(item) {
  const viewer = document.getElementById('code-viewer');
  if (!viewer) return;

  try {
    const res = await fetch(item.path);
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const text = await res.text();

    const LIMIT = 600 * 1024; // 600 KB display limit
    const truncated = text.length > LIMIT;
    const display = truncated ? text.slice(0, LIMIT) : text;

    viewer.innerHTML = `
      ${truncated ? `<div class="code-truncate-notice">
        Showing first 600 KB of ${fmtBytes(text.length)} file.
        <a href="${item.path}" download>Download full file</a> for complete content.
      </div>` : ''}
      <pre><code class="language-${item.type}">${escHtml(display)}</code></pre>
    `;

    if (window.hljs) {
      viewer.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    }
  } catch (err) {
    viewer.innerHTML = `
      <div class="error-state">
        <div class="err-icon">⚠️</div>
        <div><strong>Could not load file preview</strong></div>
        <div style="font-size:12px;margin-top:4px">${escHtml(err.message)}</div>
        <a class="btn btn-primary" href="${item.path}" download style="margin-top:16px">⬇ Download Instead</a>
      </div>
    `;
  }
}

// ── Search ───────────────────────────────────────────────────
function buildSearchNav() {
  const box = document.getElementById('search-box');
  box.addEventListener('input', e => {
    clearTimeout(state.searchTimeout);
    const q = e.target.value.trim();
    if (!q) {
      navigate(state.currentId, true);
      return;
    }
    state.searchTimeout = setTimeout(() => renderSearch(q), 200);
  });
  box.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      box.value = '';
      navigate(state.currentId, true);
    }
  });
}

function clearSearch() {
  const box = document.getElementById('search-box');
  if (box) box.value = '';
}

function renderSearch(query) {
  const q = query.toLowerCase();
  const results = allItems().filter(item =>
    item.label.toLowerCase().includes(q) ||
    item.description.toLowerCase().includes(q) ||
    item.tags.some(t => t.toLowerCase().includes(q)) ||
    item.type.includes(q) ||
    item.sectionLabel.toLowerCase().includes(q)
  );

  document.getElementById('breadcrumb').innerHTML = `
    <span class="crumb-cur">Search: "${escHtml(query)}" &mdash; ${results.length} result${results.length !== 1 ? 's' : ''}</span>
  `;

  document.getElementById('content').innerHTML = `
    <div class="search-page">
      <h2>Search results for "${escHtml(query)}" (${results.length})</h2>
      ${results.length === 0 ? `<p style="color:var(--text-muted);font-size:14px">No documents matched your query.</p>` : ''}
      ${results.map(item => `
        <div class="result-item" onclick="navigate('${item.id}')">
          <div class="doc-type-ico ico-${item.type}" style="width:36px;height:36px;font-size:16px;flex-shrink:0">${fileEmoji(item.type)}</div>
          <div style="flex:1;min-width:0">
            <div class="ri-name">${item.label}</div>
            <div class="ri-desc">${item.description}</div>
            <div class="ri-tags">
              ${item.tags.map(t => `<span class="tag">${t}</span>`).join('')}
              <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${item.sectionLabel}</span>
            </div>
          </div>
          <span class="nav-badge badge-${item.type}">${item.type}</span>
        </div>
      `).join('')}
    </div>
  `;
}

// ── Utilities ────────────────────────────────────────────────
function fileEmoji(type) {
  return { html: '🌐', xlsx: '📗', json: '🔷', yaml: '🔶' }[type] || '📄';
}

function openTab(path) {
  window.open(path, '_blank', 'noopener');
}

function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' KB';
  return (n / (1024 * 1024)).toFixed(1) + ' MB';
}
