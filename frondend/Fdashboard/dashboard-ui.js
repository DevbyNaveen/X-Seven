(function(){
  // Dashboard UI controller for notebook-style layout
  // Auth guard: ensure only authenticated and onboarded users can access dashboard
  try {
    if (!window.X7Auth || !X7Auth.isLoggedIn || !X7Auth.isLoggedIn()) {
      window.location.replace('../auth.html');
      return;
    }
    const profile = (X7Auth.getProfile && X7Auth.getProfile()) || null;
    function _isProfileComplete(p) {
      if (!p || !p.businessName) return false;
      const otherKeys = ['website','industry','timezone','contactEmail','contactPhone','hours','welcome','logoDataUrl'];
      return otherKeys.some(k => {
        const v = p[k];
        return typeof v === 'string' ? v.trim().length > 0 : !!v;
      });
    }
    if (!profile || !profile.subscriptionPlan) {
      window.location.replace('../subscription.html');
      return;
    }
    if (!_isProfileComplete(profile)) {
      window.location.replace('../onboarding.html');
      return;
    }
  } catch (e) {
    try { window.location.replace('../auth.html'); } catch {}
    return;
  }

  // Dashboard chat interface instance
  let dashboardChat = null;
  // Set to store received message IDs to prevent duplicates
  const receivedMessageIds = new Set();
  // Map to store message content hashes to prevent content duplicates
  const receivedMessageHashes = new Map();

  const els = {
    tabs: document.querySelectorAll('#centerTabs .nb-tab'),
    centerTitle: document.getElementById('centerTitle'),
    centerContent: document.getElementById('centerContent'),
    centerEmpty: document.getElementById('centerEmpty'),
    waChat: document.getElementById('waChat'),
    toggleSidebarBtn: document.getElementById('toggleSidebarBtn'),
    addSource: document.getElementById('addSource'),
    discoverSource: document.getElementById('discoverSource'),
    uploadSourceFooter: document.getElementById('uploadSourceFooter'),
    uploadSourceCenter: document.getElementById('uploadSourceCenter'),
    sourceFile: document.getElementById('sourceFile'),
    sourcesList: document.getElementById('sourcesList'),
    // Live updates containers
    overviewStats: document.getElementById('overviewStats'),
    conversationsList: document.getElementById('conversationsList'),
    liveOrdersList: document.getElementById('liveOrdersList'),
    refreshBtn: document.getElementById('refreshBtn'),
    // Quick Access buttons
    qaAddMenuItem: document.getElementById('qaAddMenuItem'),
    qaGenerateQR: document.getElementById('qaGenerateQR'),
    qaEightySixItem: document.getElementById('qaEightySixItem'),
    qaDailySpecial: document.getElementById('qaDailySpecial'),
    qaQuickPrice: document.getElementById('qaQuickPrice'),
    // Upload Zones buttons
    uzMenuPhotos: document.getElementById('uzMenuPhotos'),
    uzCsvImports: document.getElementById('uzCsvImports'),
    uzReceipts: document.getElementById('uzReceipts'),
    uzMarketing: document.getElementById('uzMarketing'),
    uzSocial: document.getElementById('uzSocial'),
    // Live counters and sections
    overviewStats: document.getElementById('overviewStats'),
    revCounter: document.getElementById('revCounter'),
    activeOrdersCount: document.getElementById('activeOrdersCount'),
    tablesOccupied: document.getElementById('tablesOccupied'),
    staffOnDuty: document.getElementById('staffOnDuty'),
    itemsOOS: document.getElementById('itemsOOS'),
    qrScansToday: document.getElementById('qrScansToday'),
    // Left card entries
    cardHome: document.getElementById('cardHome'),
    cardChat: document.getElementById('cardChat'),
    cardMenu: document.getElementById('cardMenu'),
    cardMenuMgmt: document.getElementById('cardMenuMgmt'),
    cardTableMgmt: document.getElementById('cardTableMgmt'),
    cardQrAssets: document.getElementById('cardQrAssets'),
    cardCustomerData: document.getElementById('cardCustomerData'),
    cardOpsFiles: document.getElementById('cardOpsFiles'),
    cardWorkingHours: document.getElementById('cardWorkingHours'),
    cardQuickStatus: document.getElementById('cardQuickStatus'),
    cardUploadZones: document.getElementById('cardUploadZones'),
    studioCards: document.getElementById('studioCards'),
    addNote: document.getElementById('addNote'),
    nbTitle: document.querySelector('.nb-title'),
    topProfile: document.getElementById('nbProfile'),
    analyticsBtn: document.getElementById('analyticsBtn'),
    shareBtn: document.getElementById('shareBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
  };

  // Ensure default center state on load: show placeholder, hide chat
  try {
    if (els.centerEmpty) els.centerEmpty.style.display = 'flex';
    if (els.waChat) els.waChat.style.display = 'none';
    // Hide chat-only controls until Chat is explicitly opened
    if (typeof setChatHeaderVisible === 'function') setChatHeaderVisible(false);
  } catch {}

  let chatInitialized = false;
  let liveInterval = null;
  const API_BASE = (() => {
    try {
      if (window.API_BASE_URL) return window.API_BASE_URL.replace(/\/$/, '') + '/api/v1';
    } catch {}
    return 'http://localhost:8000/api/v1';
  })();
  let sources = readSources();
  // Only allow opening chat when explicitly triggered by user interaction
  let allowChatOpen = false;
  // Track current expanded page to avoid redundant re-renders
  let currentCenterKind = null;
  // Menu categories (local persistence)
  const DEFAULT_CATEGORIES = ['Beverages','Appetizers','Main Dishes','Desserts','Specials'];
  let categories = readCategories();

  function readSources(){
    try { return JSON.parse(localStorage.getItem('x7_sources')||'[]'); } catch { return []; }
  }

  // -------- Live Chat (Grid Tiles) --------
  function initLiveChat(){
    const grid = document.getElementById('liveChatGrid');
    if (!grid) return;
    const chats = Array.isArray(window.liveChats) ? window.liveChats : [];
    renderLiveChatGrid(chats);
    // Live updates via custom event: document.dispatchEvent(new CustomEvent('x7:newChat', { detail: chat }))
    try {
      if (window._onNewChat) document.removeEventListener('x7:newChat', window._onNewChat);
    } catch {}
    window._onNewChat = (e)=>{
      const chat = e && e.detail;
      if (!chat) return;
      const empty = document.getElementById('liveChatEmpty');
      if (empty) empty.remove();
      grid.insertAdjacentHTML('afterbegin', createChatCard(chat));
    };
    document.addEventListener('x7:newChat', window._onNewChat);
  }

  function renderLiveChatGrid(chats){
    const grid = document.getElementById('liveChatGrid');
    if (!grid) return;
    if (!chats || chats.length === 0) return;
    const empty = document.getElementById('liveChatEmpty');
    if (empty) empty.remove();
    grid.innerHTML = chats.map(createChatCard).join('');
  }

  function createChatCard(chat){
    const id = chat?.id || '#';
    const name = chat?.customerName || chat?.name || 'Customer';
    const last = chat?.lastMessage || '';
    const unread = chat?.unreadCount ? `<span style="background:var(--nb-accent);color:#001; border-radius:10px; padding:0 6px; font-size:11px; font-weight:700;">${chat.unreadCount}</span>` : '';
    const time = chat?.time || '';
    return `
      <div class="nb-card nb-chat-card" style="aspect-ratio:1/1;border-radius:12px;padding:12px;display:flex;flex-direction:column;justify-content:space-between;">
        <div style="display:flex;gap:8px;align-items:center;justify-content:space-between;">
          <div style="display:flex;gap:8px;align-items:center;">
            <i class="fa-regular fa-circle-play" style="color:var(--nb-accent);"></i>
            <div style="font-weight:700;">${name}</div>
          </div>
          ${unread}
        </div>
        <div class="small" style="opacity:.85;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${last}</div>
        <div class="small" style="opacity:.75;display:flex;justify-content:flex-end;">${time}</div>
      </div>`;
  }

  function readCategories(){
    try {
      const arr = JSON.parse(localStorage.getItem('x7_menu_categories')||'[]');
      if (Array.isArray(arr) && arr.length) return arr;
    } catch {}
    return [];
  }

  function writeCategories(arr){
    categories = Array.isArray(arr) ? arr : [];
    try { localStorage.setItem('x7_menu_categories', JSON.stringify(categories)); } catch {}
    // Update Menu aggregator view if it's currently visible
    refreshMenuBrowseIfVisible();
  }

  // Category utils (support plain strings or objects with {name, description})
  function getCatName(c){ return (typeof c === 'string') ? c : (c && c.name) || ''; }
  function hasCatName(name){
    const target = (name||'').trim().toLowerCase();
    return (categories||[]).some(c => getCatName(c).trim().toLowerCase() === target);
  }
  function openAddCategoryModal(){
    // Remove existing if any
    document.getElementById('addCatBackdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.id = 'addCatBackdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px;';
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'width:min(560px,96%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:14px;padding:16px;box-shadow:0 2px 0 rgba(0,0,0,.25)';
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <i class="fa-solid fa-folder-plus" style="color:var(--nb-accent)"></i>
        <div style="font-weight:700;">Add Category</div>
      </div>
      <form id="addCatForm" style="display:flex;flex-direction:column;gap:10px;">
        <label style="display:flex;flex-direction:column;gap:6px;">
          <span class="small muted" style="font-weight:600;">Category Name</span>
          <input id="addCatName" type="text" placeholder="e.g. Appetizers" required
            style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;" />
        </label>
        <label style="display:flex;flex-direction:column;gap:6px;">
          <span class="small muted" style="font-weight:600;">Description (optional)</span>
          <textarea id="addCatDesc" rows="3" placeholder="Short description"
            style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;resize:vertical;"></textarea>
        </label>
        <div id="addCatError" class="small" style="min-height:18px;color:#ff6b6b;"></div>
        <div style="display:flex;justify-content:flex-end;gap:8px;">
          <button type="button" class="btn btn-outline" id="addCatCancel">Cancel</button>
          <button type="submit" class="btn" id="addCatSave"><i class="fa-solid fa-check"></i> Save</button>
        </div>
      </form>
    `;
    backdrop.appendChild(card);
    els.centerContent?.appendChild(backdrop);

    // Events
    const nameEl = card.querySelector('#addCatName');
    const descEl = card.querySelector('#addCatDesc');
    const errEl  = card.querySelector('#addCatError');
    const cancelBtn = card.querySelector('#addCatCancel');
    const form = card.querySelector('#addCatForm');

    nameEl?.focus();
    cancelBtn?.addEventListener('click', ()=> backdrop.remove());
    backdrop.addEventListener('click', (e)=> { if (e.target === backdrop) backdrop.remove(); });
    form?.addEventListener('submit', async (e)=>{
      e.preventDefault();
      errEl.textContent = '';
      const name = (nameEl?.value||'').trim();
      if (!name) { errEl.textContent = 'Please enter a category name.'; return; }
      if (hasCatName(name)) { errEl.textContent = 'This category already exists.'; return; }
      const description = (descEl?.value||'').trim();
      // Try backend first
      try {
        const headers = (typeof authHeaders === 'function')
          ? authHeaders({ 'Content-Type': 'application/json' })
          : (()=>{ const h = { 'Accept':'application/json','Content-Type':'application/json' }; try { const a = (window.X7Auth && X7Auth.getAuth && X7Auth.getAuth()); if (a && a.token) h['Authorization'] = `Bearer ${a.token}`; } catch {} return h; })();
        const res = await x7Fetch(`${API_BASE}/menu/categories`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ name, description })
        });
        if (!res.ok) {
          try { const j = await res.json(); errEl.textContent = (j && (j.detail?.message || j.detail || j.error || j.msg)) || `Failed to create category (${res.status})`; }
          catch { errEl.textContent = `Failed to create category (${res.status})`; }
          return;
        }
        const created = await res.json();
        // Merge into local store and re-render
        writeCategories([...(categories||[]), created]);
        renderMenuCategories();
        backdrop.remove();
        return;
      } catch (e) {
        console.warn('POST /menu/categories failed, falling back to local storage', e);
      }
      // Fallback: local-only persistence
      writeCategories([...(categories||[]), { name, description }]);
      renderMenuCategories();
      backdrop.remove();
    });
  }

  // -------- Category Detail + Items --------
  function catStorageKey(catOrName){
    const name = (typeof catOrName === 'string') ? catOrName : getCatName(catOrName);
    const slug = (name||'').toLowerCase().trim().replace(/\s+/g,'_').replace(/[^a-z0-9_]/g,'');
    return 'x7_menu_items:' + slug;
  }
  function readCatItems(catOrName){
    try { return JSON.parse(localStorage.getItem(catStorageKey(catOrName))||'[]'); } catch { return []; }
  }
  function writeCatItems(catOrName, arr){
    try { localStorage.setItem(catStorageKey(catOrName), JSON.stringify(Array.isArray(arr)?arr:[])); } catch {}
    // Update Menu aggregator view if it's currently visible
    refreshMenuBrowseIfVisible();
  }

  function renderCategoryItemsList(catOrName, listEl){
    if (!listEl) return;
    const items = readCatItems(catOrName);
    if (!items.length) {
      listEl.innerHTML = `
        <div class="nb-empty compact">
          <div class="nb-empty-icon"><i class="fa-regular fa-rectangle-list"></i></div>
          <div class="nb-empty-text">No items yet</div>
          <div class="muted small">Click Add Item to create your first menu entry.</div>
        </div>`;
      return;
    }
    listEl.innerHTML = items.map((it, i)=>{
      const name = it.name || `Item ${i+1}`;
      const price = (it.price!=null && it.price!=='') ? `$${Number(it.price).toFixed(2)}` : '';
      const desc = it.description ? `<div class=\"muted small\" style=\"margin-top:2px;\">${it.description}</div>` : '';
      return `
        <div class=\"nb-card\" data-idx=\"${i}\" style=\"display:flex;flex-direction:column;align-items:flex-start;gap:4px;\">
          <div style=\"display:flex;gap:8px;align-items:center;width:100%;\">
            <div class=\"nb-card-title\" style=\"font-weight:600;flex:1;\">${name}</div>
            <div class=\"muted\" style=\"font-weight:600;\">${price}</div>
            <div style=\"display:flex;gap:6px;margin-left:8px;\">
              <button class=\"nb-icon\" title=\"Edit\" data-action=\"edit-item\" data-idx=\"${i}\"><i class=\"fa-solid fa-pen\"></i></button>
              <button class=\"nb-icon\" title=\"Delete\" data-action=\"delete-item\" data-idx=\"${i}\"><i class=\"fa-solid fa-trash\"></i></button>
            </div>
          </div>
          ${desc}
        </div>`;
    }).join('');
  }

  function openAddMenuItemModal(catOrName, onSaved){
    document.getElementById('addItemBackdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.id = 'addItemBackdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:10000;padding:16px;';
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'width:min(560px,96%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:14px;padding:16px;box-shadow:0 2px 0 rgba(0,0,0,.25)';
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <i class="fa-solid fa-utensils" style="color:var(--nb-accent)"></i>
        <div style="font-weight:700;">Add Menu Item</div>
      </div>
      <form id="addItemForm" style="display:flex;flex-direction:column;gap:10px;">
        <label style="display:flex;flex-direction:column;gap:6px;">
          <span class="small muted" style="font-weight:600;">Item Name</span>
          <input id="itemName" type="text" placeholder="e.g. Chicken Biryani" required
            style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;" />
        </label>
        <div style="display:grid;grid-template-columns: 1fr 120px; gap: 8px;">
          <label style="display:flex;flex-direction:column;gap:6px;">
            <span class="small muted" style="font-weight:600;">Description</span>
            <textarea id="itemDesc" rows="3" placeholder="Short description"
              style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;resize:vertical;"></textarea>
          </label>
          <label style="display:flex;flex-direction:column;gap:6px;">
            <span class="small muted" style="font-weight:600;">Price</span>
            <input id="itemPrice" type="number" step="0.01" min="0" placeholder="0.00"
              style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;" />
          </label>
        </div>
        <div id="addItemError" class="small" style="min-height:18px;color:#ff6b6b;"></div>
        <div style="display:flex;justify-content:flex-end;gap:8px;">
          <button type="button" class="btn btn-outline" id="itemCancel">Cancel</button>
          <button type="submit" class="btn" id="itemSave"><i class="fa-solid fa-check"></i> Save</button>
        </div>
      </form>
    `;
    backdrop.appendChild(card);
    els.centerContent?.appendChild(backdrop);

    const form = card.querySelector('#addItemForm');
    const nameEl = card.querySelector('#itemName');
    const descEl = card.querySelector('#itemDesc');
    const priceEl = card.querySelector('#itemPrice');
    const errEl  = card.querySelector('#addItemError');
    const cancel = card.querySelector('#itemCancel');
    nameEl?.focus();
    cancel?.addEventListener('click', ()=> backdrop.remove());
    backdrop.addEventListener('click', (e)=> { if (e.target === backdrop) backdrop.remove(); });
    form?.addEventListener('submit', (e)=>{
      e.preventDefault();
      const name = (nameEl?.value||'').trim();
      if (!name) { errEl.textContent = 'Please enter item name.'; return; }
      const priceVal = priceEl?.value;
      const price = priceVal!=='' ? Number(priceVal) : '';
      const desc = (descEl?.value||'').trim();
      const list = readCatItems(catOrName);
      list.push({ name, price, description: desc });
      writeCatItems(catOrName, list);
      if (typeof onSaved === 'function') onSaved();
      backdrop.remove();
    });
  }

  function openEditMenuItemModal(catOrName, idx, item, onSaved){
    document.getElementById('editItemBackdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.id = 'editItemBackdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:10000;padding:16px;';
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'width:min(560px,96%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:14px;padding:16px;box-shadow:0 2px 0 rgba(0,0,0,.25)';
    card.innerHTML = `
      <div style=\"display:flex;align-items:center;gap:10px;margin-bottom:8px;\">
        <i class=\"fa-solid fa-utensils\" style=\"color:var(--nb-accent)\"></i>
        <div style=\"font-weight:700;\">Edit Menu Item</div>
      </div>
      <form id=\"editItemForm\" style=\"display:flex;flex-direction:column;gap:10px;\">
        <label style=\"display:flex;flex-direction:column;gap:6px;\">
          <span class=\"small muted\" style=\"font-weight:600;\">Item Name</span>
          <input id=\"itemName\" type=\"text\" required
            style=\"background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;\" />
        </label>
        <div style=\"display:grid;grid-template-columns: 1fr 120px; gap: 8px;\">
          <label style=\"display:flex;flex-direction:column;gap:6px;\">
            <span class=\"small muted\" style=\"font-weight:600;\">Description</span>
            <textarea id=\"itemDesc\" rows=\"3\" style=\"background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;resize:vertical;\"></textarea>
          </label>
          <label style=\"display:flex;flex-direction:column;gap:6px;\">
            <span class=\"small muted\" style=\"font-weight:600;\">Price</span>
            <input id=\"itemPrice\" type=\"number\" step=\"0.01\" min=\"0\"
              style=\"background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;\" />
          </label>
        </div>
        <div id=\"editItemError\" class=\"small\" style=\"min-height:18px;color:#ff6b6b;\"></div>
        <div style=\"display:flex;justify-content:flex-end;gap:8px;\">
          <button type=\"button\" class=\"btn btn-outline\" id=\"itemCancel\">Cancel</button>
          <button type=\"submit\" class=\"btn\" id=\"itemSave\"><i class=\"fa-solid fa-check\"></i> Save</button>
        </div>
      </form>
    `;
    backdrop.appendChild(card);
    els.centerContent?.appendChild(backdrop);
    const nameEl = card.querySelector('#itemName');
    const descEl = card.querySelector('#itemDesc');
    const priceEl = card.querySelector('#itemPrice');
    const errEl  = card.querySelector('#editItemError');
    const cancel = card.querySelector('#itemCancel');
    nameEl.value = item?.name || '';
    descEl.value = item?.description || '';
    if (item && item.price!=='' && item.price!=null) priceEl.value = String(item.price);
    nameEl?.focus();
    cancel?.addEventListener('click', ()=> backdrop.remove());
    backdrop.addEventListener('click', (e)=> { if (e.target === backdrop) backdrop.remove(); });
    card.querySelector('#editItemForm')?.addEventListener('submit', (e)=>{
      e.preventDefault();
      const name = (nameEl?.value||'').trim();
      if (!name) { errEl.textContent = 'Please enter item name.'; return; }
      const priceVal = priceEl?.value;
      const price = priceVal!=='' ? Number(priceVal) : '';
      const desc = (descEl?.value||'').trim();
      const list = readCatItems(catOrName);
      list[idx] = { name, price, description: desc };
      writeCatItems(catOrName, list);
      if (typeof onSaved === 'function') onSaved();
      backdrop.remove();
    });
  }

  function openCategoryModal(idx){
    const cat = (categories||[])[idx];
    if (!cat) return;
    document.getElementById('catDetailBackdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.id = 'catDetailBackdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px;';
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'width:min(720px,96%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:14px;padding:16px;box-shadow:0 2px 0 rgba(0,0,0,.25)';
    const name = getCatName(cat) || 'Untitled';
    const desc = (typeof cat === 'object' && cat.description) ? `<div class="muted small" style="margin-top:4px;">${cat.description}</div>` : '';
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:10px;">
          <i class="fa-solid fa-folder" style="color:var(--nb-accent)"></i>
          <div class="nb-card-title" style="font-weight:700;">${name}</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
          <button id="catEdit" class="nb-icon" title="Edit Category"><i class="fa-solid fa-pen"></i></button>
          <button id="catDelete" class="nb-icon" title="Delete Category"><i class="fa-solid fa-trash"></i></button>
          <button id="catClose" class="nb-icon" title="Close"><i class="fa-solid fa-xmark"></i></button>
        </div>
      </div>
      ${desc}
      <div class="nb-section-title" style="margin-top:10px;">Items</div>
      <div id="catItemsList" style="display:flex;flex-direction:column;gap:8px;"></div>
      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;">
        <button id="catAddItem" class="btn"><i class="fa-solid fa-plus"></i> Add Item</button>
      </div>
    `;
    backdrop.appendChild(card);
    els.centerContent?.appendChild(backdrop);

    const itemsList = card.querySelector('#catItemsList');
    renderCategoryItemsList(cat, itemsList);

    const closeBtn = card.querySelector('#catClose');
    const addBtn = card.querySelector('#catAddItem');
    const editCatBtn = card.querySelector('#catEdit');
    const delCatBtn  = card.querySelector('#catDelete');
    closeBtn?.addEventListener('click', ()=> backdrop.remove());
    addBtn?.addEventListener('click', ()=> openAddMenuItemModal(cat, ()=> renderCategoryItemsList(cat, itemsList)));
    backdrop.addEventListener('click', (e)=> { if (e.target === backdrop) backdrop.remove(); });

    // Item actions (edit/delete) via delegation
    itemsList?.addEventListener('click', (e)=>{
      const editBtn = e.target.closest('[data-action="edit-item"]');
      const delBtn  = e.target.closest('[data-action="delete-item"]');
      if (editBtn) {
        const id = Number(editBtn.getAttribute('data-idx'));
        const list = readCatItems(cat);
        openEditMenuItemModal(cat, id, list[id], ()=> renderCategoryItemsList(cat, itemsList));
        return;
      }
      if (delBtn) {
        const id = Number(delBtn.getAttribute('data-idx'));
        const list = readCatItems(cat);
        if (!Number.isNaN(id) && id>=0 && id<list.length) {
          if (confirm('Delete this item?')) {
            list.splice(id, 1);
            writeCatItems(cat, list);
            renderCategoryItemsList(cat, itemsList);
            refreshMenuBrowseIfVisible();
          }
        }
        return;
      }
    });

    editCatBtn?.addEventListener('click', ()=> openEditCategoryModal(idx));
    delCatBtn?.addEventListener('click', ()=> deleteCategory(idx));
  }

  function openEditCategoryModal(idx){
    const cat = (categories||[])[idx];
    if (!cat) return;
    document.getElementById('editCatBackdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.id = 'editCatBackdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:10001;padding:16px;';
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'width:min(560px,96%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:14px;padding:16px;box-shadow:0 2px 0 rgba(0,0,0,.25)';
    const name = getCatName(cat) || '';
    const desc = (typeof cat === 'object' && cat.description) ? cat.description : '';
    card.innerHTML = `
      <div style=\"display:flex;align-items:center;gap:10px;margin-bottom:8px;\">
        <i class=\"fa-solid fa-folder\" style=\"color:var(--nb-accent)\"></i>
        <div style=\"font-weight:700;\">Edit Category</div>
      </div>
      <form id=\"editCatForm\" style=\"display:flex;flex-direction:column;gap:10px;\">
        <label style=\"display:flex;flex-direction:column;gap:6px;\">
          <span class=\"small muted\" style=\"font-weight:600;\">Category Name</span>
          <input id=\"catName\" type=\"text\" required
            style=\"background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;\" />
        </label>
        <label style=\"display:flex;flex-direction:column;gap:6px;\">
          <span class=\"small muted\" style=\"font-weight:600;\">Description</span>
          <textarea id=\"catDesc\" rows=\"3\" style=\"background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:10px;padding:10px 12px;outline:none;resize:vertical;\"></textarea>
        </label>
        <div id=\"editCatError\" class=\"small\" style=\"min-height:18px;color:#ff6b6b;\"></div>
        <div style=\"display:flex;justify-content:flex-end;gap:8px;\">
          <button type=\"button\" class=\"btn btn-outline\" id=\"catCancel\">Cancel</button>
          <button type=\"submit\" class=\"btn\" id=\"catSave\"><i class=\"fa-solid fa-check\"></i> Save</button>
        </div>
      </form>
    `;
    backdrop.appendChild(card);
    els.centerContent?.appendChild(backdrop);
    const nameEl = card.querySelector('#catName');
    const descEl = card.querySelector('#catDesc');
    const errEl  = card.querySelector('#editCatError');
    const cancel = card.querySelector('#catCancel');
    nameEl.value = name;
    descEl.value = desc;
    nameEl?.focus();
    cancel?.addEventListener('click', ()=> backdrop.remove());
    backdrop.addEventListener('click', (e)=> { if (e.target === backdrop) backdrop.remove(); });
    card.querySelector('#editCatForm')?.addEventListener('submit', (e)=>{
      e.preventDefault();
      const newName = (nameEl?.value||'').trim();
      if (!newName) { errEl.textContent = 'Please enter a category name.'; return; }
      const dup = (categories||[]).some((c, i)=> i!==idx && getCatName(c).toLowerCase() === newName.toLowerCase());
      if (dup) { errEl.textContent = 'This category already exists.'; return; }
      const newDesc = (descEl?.value||'').trim();
      const arr = [...(categories||[])];
      const oldName = getCatName(arr[idx]);
      arr[idx] = { name: newName, description: newDesc };
      writeCategories(arr);
      // migrate items key if name changed
      if (oldName !== newName) {
        try {
          const oldKey = catStorageKey(oldName);
          const newKey = catStorageKey(newName);
          if (oldKey !== newKey) {
            const data = localStorage.getItem(oldKey);
            if (data != null) localStorage.setItem(newKey, data);
            localStorage.removeItem(oldKey);
          }
        } catch {}
      }
      renderMenuCategories();
      backdrop.remove();
      // refresh category modal if open
      if (document.getElementById('catDetailBackdrop')) {
        document.getElementById('catDetailBackdrop').remove();
        openCategoryModal(idx);
      }
    });
  }

  function deleteCategory(idx){
    const arr = [...(categories||[])];
    const cat = arr[idx];
    if (!cat) return;
    const name = getCatName(cat);
    if (!confirm(`Delete category "${name}" and its items?`)) return;
    arr.splice(idx, 1);
    writeCategories(arr);
    try { localStorage.removeItem(catStorageKey(name)); } catch {}
    renderMenuCategories();
    const back = document.getElementById('catDetailBackdrop');
    if (back) back.remove();
    // Reflect deletion in Menu aggregator if open
    refreshMenuBrowseIfVisible();
  }

  // Explicit user-initiated chat open (bypass guard edge cases)
  function forceShowChat(){
    setCenterTitle('Dashboard AI');
    if (els.centerEmpty) els.centerEmpty.style.display = 'none';
    const dyn = document.getElementById('centerDynamic');
    if (dyn) dyn.style.display = 'none';
    // Remove any overlay soft card that may block the chat view
    const softCard = els.centerContent?.querySelector('.nb-soft-card');
    if (softCard) softCard.remove();
    if (els.waChat) {
      els.waChat.style.display = 'flex';
      setChatHeaderVisible(true);
      if (!chatInitialized) {
        chatInitialized = true;
        // Always initialize dashboard chat interface (WS handled by dashboard_chat.js)
        try { initDashboardChat(); } catch(e) { console.warn('initDashboardChat failed', e); }
      }
    }
  }

  // -------- Live Orders (Grid Tiles) --------
  function initLiveOrders(){
    const grid = document.getElementById('liveOrdersGrid');
    if (!grid) return;
    const orders = Array.isArray(window.liveOrders) ? window.liveOrders : [];
    renderLiveOrdersGrid(orders);
    // Live updates via custom event: document.dispatchEvent(new CustomEvent('x7:newOrder', { detail: order }))
    try {
      if (window._onNewOrder) document.removeEventListener('x7:newOrder', window._onNewOrder);
    } catch {}
    window._onNewOrder = (e)=>{
      const order = e && e.detail;
      if (!order) return;
      const empty = document.getElementById('liveOrdersEmpty');
      if (empty) empty.remove();
      grid.insertAdjacentHTML('afterbegin', createOrderCard(order));
    };
    document.addEventListener('x7:newOrder', window._onNewOrder);
  }

  function renderLiveOrdersGrid(orders){
    const grid = document.getElementById('liveOrdersGrid');
    if (!grid) return;
    if (!orders || orders.length === 0) return;
    const empty = document.getElementById('liveOrdersEmpty');
    if (empty) empty.remove();
    grid.innerHTML = orders.map(createOrderCard).join('');
  }

  function createOrderCard(order){
    const id = order?.id || order?.number || '#';
    const customer = order?.customerName || order?.customer || 'Customer';
    const items = (typeof order?.itemsCount === 'number') ? `${order.itemsCount} items` : (order?.items ? `${order.items.length} items` : '—');
    const total = (order?.total != null) ? `$${order.total}` : '';
    const time = order?.time || '';
    return `
      <div class="nb-card nb-order-card" style="aspect-ratio:1/1;border-radius:12px;padding:12px;display:flex;flex-direction:column;justify-content:space-between;">
        <div style="display:flex;gap:8px;align-items:center;">
          <i class="fa-solid fa-receipt" style="color:var(--nb-accent);"></i>
          <div style="font-weight:700;">#${id}</div>
        </div>
        <div class="small" style="opacity:.9;">${customer}</div>
        <div class="small" style="display:flex;justify-content:space-between;opacity:.75;">
          <span>${items}</span>
          <span>${total || time}</span>
        </div>
      </div>`;
  }
  
  // -------- Live Reservation (Grid Tiles) --------
  function initLiveReservation(){
    const grid = document.getElementById('liveReservationGrid');
    if (!grid) return;
    const reservations = Array.isArray(window.liveReservations) ? window.liveReservations : [];
    renderLiveReservationGrid(reservations);
    // Live updates via custom event: document.dispatchEvent(new CustomEvent('x7:newReservation', { detail: reservation }))
    try {
      if (window._onNewReservation) document.removeEventListener('x7:newReservation', window._onNewReservation);
    } catch {}
    window._onNewReservation = (e)=>{
      const res = e && e.detail;
      if (!res) return;
      const empty = document.getElementById('liveReservationEmpty');
      if (empty) empty.remove();
      grid.insertAdjacentHTML('afterbegin', createReservationCard(res));
    };
    document.addEventListener('x7:newReservation', window._onNewReservation);
  }

  function renderLiveReservationGrid(reservations){
    const grid = document.getElementById('liveReservationGrid');
    if (!grid) return;
    if (!reservations || reservations.length === 0) return;
    const empty = document.getElementById('liveReservationEmpty');
    if (empty) empty.remove();
    grid.innerHTML = reservations.map(createReservationCard).join('');
  }

  function createReservationCard(res){
    const id = res?.id || res?.code || '#';
    const name = res?.name || res?.customerName || 'Guest';
    const size = (res?.partySize != null) ? `x${res.partySize}` : '';
    const time = res?.time || res?.slot || '';
    const table = res?.table ? `Table ${res.table}` : '';
    return `
      <div class="nb-card nb-res-card" style="aspect-ratio:1/1;border-radius:12px;padding:12px;display:flex;flex-direction:column;justify-content:space-between;">
        <div style="display:flex;gap:8px;align-items:center;">
          <i class="fa-regular fa-lightbulb" style="color:var(--nb-accent);"></i>
          <div style="font-weight:700;">${name}</div>
        </div>
        <div class="small" style="opacity:.9;display:flex;gap:8px;align-items:center;">
          <span>${size}</span>
          <span>${table}</span>
        </div>
        <div class="small" style="opacity:.75;display:flex;justify-content:flex-end;">${time}</div>
      </div>`;
  }

  // -------- Center Expanded Pages --------
  function showCenterContent(){
    if (els.centerEmpty) els.centerEmpty.style.display = 'none';
    if (els.waChat) els.waChat.style.display = 'none';
    if (els.centerContent) els.centerContent.style.display = '';
    const dyn = getDynamicContainer();
    if (dyn) dyn.style.display = '';
    // Non-chat views should hide chat-only header controls
    setChatHeaderVisible(false);
  }

  function setCenterTitle(text){
    if (els.centerTitle) els.centerTitle.textContent = text || '';
  }

  // Show/hide chat-only header controls (history toggle button and chat icon)
  function setChatHeaderVisible(show){
    const disp = show ? '' : 'none';
    if (els.toggleSidebarBtn) els.toggleSidebarBtn.style.display = disp;
    if (els.centerChatIcon) els.centerChatIcon.style.display = disp;
  }

  // Ensure a lightweight fade animation style is present for dynamic swaps
  function ensureFadeStyle(){
    if (document.getElementById('nbFadeStyle')) return;
    const style = document.createElement('style');
    style.id = 'nbFadeStyle';
    style.textContent = `
      @keyframes nbFade { from { opacity: 0 } to { opacity: 1 } }
      #centerContent #centerDynamic.nb-fade-in { animation: nbFade .18s ease-in; }
    `;
    document.head.appendChild(style);
  }

  // -------- Menu (All Items) Aggregator --------
  function getAllMenuItems(){
    const all = [];
    (categories||[]).forEach((cat)=>{
      const catName = getCatName(cat);
      const items = readCatItems(cat);
      items.forEach((it, idx)=>{
        all.push({ category: catName, item: it, idx });
      });
    });
    return all;
  }

  function renderMenuBrowse(){
    const grid = document.getElementById('menuBrowseGrid');
    if (!grid) return;
    const all = getAllMenuItems();
    if (!all.length) {
      grid.innerHTML = `<div class="nb-empty compact">No items yet. Add items in <b>Menu Management</b> and they'll appear here automatically.</div>`;
      return;
    }
    grid.innerHTML = all.map(({category, item})=>{
      const name = (item?.name||'').trim() || 'Untitled';
      const price = (item!=null && item.price!=='' && item.price!=null) ? `<div class="nb-card-sub" style="font-weight:600;">$${Number(item.price).toFixed(2)}</div>` : '';
      const desc  = (item?.description) ? `<div class="nb-card-sub small muted" style="margin-top:4px;">${item.description}</div>` : '';
      const catPill = category ? `<div class="small muted" style="margin-top:6px;">${category}</div>` : '';
      return `
        <div class="nb-card nb-tile">
          <div class="stat-icon"><i class="fa-solid fa-utensils"></i></div>
          <div class="meta">
            <div class="nb-card-title">${name}</div>
            ${price}
            ${desc}
            ${catPill}
          </div>
        </div>`;
    }).join('');
  }

  function initMenuBrowse(){
    renderMenuBrowse();
  }

  function refreshMenuBrowseIfVisible(){
    if (document.getElementById('menuBrowseGrid')) {
      renderMenuBrowse();
    }
  }

  function pill(label){
    return `<span style="display:inline-block;padding:4px 8px;border:1px solid var(--nb-border);border-radius:999px;font-size:12px;margin-right:6px;">${label}</span>`;
  }

  function sectionCard(title, body){
    return `
      <div style="border:1px solid var(--nb-border);border-radius:12px;background:var(--nb-elev-2);padding:14px;margin-bottom:12px;">
        <div style="font-weight:700;margin-bottom:6px;">${title}</div>
        <div class="muted small">${body}</div>
      </div>`;
  }

  function renderExpanded(kind){
    switch(kind){
      case 'home':
        return `
          <div class="nb-section-header">
            <div class="nb-header-title">Welcome</div>
            <div class="muted small">Overview and quick actions</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div class="nb-card">
              <div class="nb-card-title">Getting Started</div>
              <div class="nb-card-sub">Use the left panel to navigate. Open Chat to talk to the AI, or manage your menu, tables, QR codes, and more.</div>
            </div>
            <div class="nb-card">
              <div class="nb-card-title">Tips</div>
              <div class="nb-card-sub">You can add categories and items in Menu Management, and edit them anytime. Data is saved locally.</div>
            </div>
          </div>
        `;
      case 'menuBrowse':
        return `
          <div class="nb-section-header">
            <div class="nb-header-title">Menu</div>
            <div class="muted small">All items across categories</div>
          </div>
          <div class="nb-tiles nb-tiles-items" id="menuBrowseGrid"></div>
        `;
      case 'menuMgmt':
        return `
          <div class="nb-section-header">
            <div class="nb-header-title">Menu Items Database</div>
            <div class="muted small">Browse by category and manage pricing, availability</div>
          </div>
          <div class="nb-tiles nb-tiles-categories" id="categoriesGrid">
          </div>
        `;
      case 'tableMgmt':
        return `
          ${sectionCard('Table Layout', 'Visualize table occupancy and manage reservations')}
          <div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin-bottom:10px;">
            ${Array.from({length:12}).map((_,i)=>`<div style=\"border:1px solid var(--nb-border);border-radius:8px;padding:8px;text-align:center;\">T${i+1}<br/><span class=\"muted small\">available</span></div>`).join('')}
          </div>
          <button class="btn btn-outline" id="actGenerateTableQR"><i class="fa-solid fa-qrcode"></i> Generate Table QR</button>
        `;
      case 'qrAssets':
        return `
          ${sectionCard('QR Templates', 'Standard, Premium, Circular with logo integration')}
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
            ${pill('Standard')}${pill('Premium')}${pill('Circular')}${pill('Business Card')}
          </div>
          <button class="btn" id="actBatchMenuQR"><i class="fa-solid fa-qrcode"></i> Generate Menu QR Batch</button>
        `;
      case 'customerData':
        return `
          ${sectionCard('Customer Lists', 'Loyalty members, segments, contacts, feedback')}
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
            ${pill('All')}${pill('Regulars')}${pill('New')}${pill('VIP')}
          </div>
          <button class="btn btn-outline" id="actImportCustomers"><i class="fa-regular fa-file-excel"></i> Import CSV</button>
        `;
      case 'opsFiles':
        return `
          ${sectionCard('Operations', 'Sales reports, schedules, inventory, permits')}
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
            ${pill('Reports')}${pill('Schedules')}${pill('Inventory')}${pill('Permits')}
          </div>
          <button class="btn btn-outline" id="actUploadOps"><i class="fa-regular fa-file-lines"></i> Upload Document</button>
        `;
      case 'quickStatus':
        return `
          ${sectionCard('Today', 'At-a-glance KPIs updated live')}
          <div class="nb-status-grid" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;">
            <div class="stat-item" style="padding:8px;border:1px solid var(--nb-border);border-radius:8px;"><div class="muted small">Revenue</div><div id="revCounterBig" style="font-weight:700;">$0</div></div>
            <div class="stat-item" style="padding:8px;border:1px solid var(--nb-border);border-radius:8px;"><div class="muted small">Active Orders</div><div id="activeOrdersCountBig" style="font-weight:700;">0</div></div>
            <div class="stat-item" style="padding:8px;border:1px solid var(--nb-border);border-radius:8px;"><div class="muted small">QR Scans</div><div id="qrScansTodayBig" style="font-weight:700;">-</div></div>
          </div>
        `;
      case 'uploadZones':
        return `
          ${sectionCard('Upload Zones', 'Menu photos, CSVs, receipts, marketing, social')}
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <button class="btn btn-outline" id="uzMenuPhotosCenter"><i class="fa-regular fa-image"></i> Menu photos</button>
            <button class="btn btn-outline" id="uzCsvCenter"><i class="fa-regular fa-file-excel"></i> CSV imports</button>
            <button class="btn btn-outline" id="uzReceiptsCenter"><i class="fa-regular fa-file-lines"></i> Receipts</button>
            <button class="btn btn-outline" id="uzMarketingCenter"><i class="fa-regular fa-paper-plane"></i> Marketing</button>
          </div>
        `;
      case 'liveOrders':
        return `
          <div class="nb-section-header">
            <div class="muted small">Incoming online orders</div>
          </div>
          <div id="liveOrdersGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;align-items:stretch;">
            <!-- Each order will render as a rounded square card inside this grid -->
            <div id="liveOrdersEmpty" class="muted small" style="grid-column:1/-1;opacity:0.7;">No live orders yet</div>
          </div>
        `;
      case 'liveChat':
        return `
          <div class="nb-section-header">
            <div class="muted small">Incoming customer chats</div>
          </div>
          <div id="liveChatGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;align-items:stretch;">
            <!-- Each chat will render as a rounded square card inside this grid -->
            <div id="liveChatEmpty" class="muted small" style="grid-column:1/-1;opacity:0.7;">No active chats yet</div>
          </div>
        `;
      case 'liveReservation':
        return `
          <div class="nb-section-header">
            <div class="muted small">Incoming table reservations</div>
          </div>
          <div id="liveReservationGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;align-items:stretch;">
            <!-- Each reservation will render as a rounded square card inside this grid -->
            <div id="liveReservationEmpty" class="muted small" style="grid-column:1/-1;opacity:0.7;">No upcoming reservations yet</div>
          </div>
        `;
      case 'reports':
        return `
          <div class="nb-section-header">
            <div class="nb-header-title">Reports</div>
            <div class="muted small">Select type</div>
          </div>
          <div class="nb-card" style="display:flex;gap:10px;align-items:flex-start;padding:12px;">
            <i class="fa-regular fa-clipboard" style="margin-top:2px;color:var(--nb-accent);"></i>
            <div>
              <div class="nb-card-title">Reports</div>
              <div class="nb-card-sub small muted">No report selected</div>
            </div>
          </div>
        `;
      case 'workingHours':
        return `
          <div class="nb-section-header">
            <div class="nb-header-title">Working Hours</div>
            <div class="muted small">Configure weekly open/close times</div>
          </div>
          <div class="nb-card" style="padding:12px;display:flex;flex-direction:column;gap:10px;">
            <div class="nb-card-sub small muted">Times are in 24h format</div>
            <form id="whForm" style="display:flex;flex-direction:column;gap:8px;">
              ${['mon','tue','wed','thu','fri','sat','sun'].map((d, i)=>{
                const labels = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
                return `
                <div class="wh-row" data-day="${d}" style="display:flex;align-items:center;gap:8px;">
                  <div style="flex:0 0 48px;font-weight:600;">${labels[i]}</div>
                  <label class="small" style="display:flex;align-items:center;gap:6px;min-width:80px;">
                    <input type="checkbox" id="wh-open-${d}" /> Open
                  </label>
                  <input type="time" id="wh-openTime-${d}" style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:8px;padding:6px 8px;" />
                  <span class="muted small">to</span>
                  <input type="time" id="wh-closeTime-${d}" style="background:transparent;color:var(--nb-text);border:1px solid var(--nb-border);border-radius:8px;padding:6px 8px;" />
                </div>`;
              }).join('')}
              <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:6px;">
                <button type="button" class="btn btn-outline" id="whReset">Reset</button>
                <button type="button" class="btn" id="whSave"><i class="fa-solid fa-check"></i> Save</button>
              </div>
            </form>
          </div>
        `;
      default:
        return '<div class="muted">Coming soon</div>';
    }
  }

  // -------- Menu Management (Categories) --------
  function renderMenuCategories(){
    const grid = document.querySelector('#centerDynamic .nb-tiles-categories') || document.getElementById('categoriesGrid');
    if (!grid) return;
    const tiles = (categories||[]).map((cat, i)=>{
      const name = getCatName(cat) || 'Untitled';
      const desc = (cat && typeof cat === 'object' && cat.description)
        ? `<div class="muted small" style="margin-top:4px;font-weight:400;">${cat.description}</div>`
        : '';
      return `<button class="nb-card nb-tile" data-cat-idx="${i}"><span>${name}</span>${desc}</button>`;
    }).join('');
    const addTile = `<button class="nb-card nb-tile" id="addCategoryTile" data-action="add-category"><i class="fa-solid fa-plus"></i><span>Add Category</span></button>`;
    grid.innerHTML = tiles + addTile;
  }

  // Fetch categories from backend and sync local cache/UI
  async function syncCategoriesFromBackend(){
    try {
      const headers = (typeof authHeaders === 'function')
        ? authHeaders()
        : (()=>{ // fallback if authHeaders isn't available
            const h = { Accept: 'application/json' };
            try { const a = (window.X7Auth && X7Auth.getAuth && X7Auth.getAuth()); if (a && a.token) h['Authorization'] = `Bearer ${a.token}`; } catch {}
            return h;
          })();
      const res = await x7Fetch(`${API_BASE}/menu/categories`, { headers });
      if (!res.ok) return; // silent fail, keep local
      const data = await res.json();
      if (Array.isArray(data)) {
        writeCategories(data);
        renderMenuCategories();
      }
    } catch (e) {
      console.warn('Failed to sync categories from API', e);
    }
  }

  function initMenuMgmt(){
    // Initial local render, then try to refresh from backend
    renderMenuCategories();
    try { syncCategoriesFromBackend(); } catch {}
    const grid = document.querySelector('#centerDynamic .nb-tiles-categories') || document.getElementById('categoriesGrid');
    if (!grid) return;
    grid.addEventListener('click', (e)=>{
      // Open a category when its tile is clicked
      const catBtn = e.target.closest('[data-cat-idx]');
      if (catBtn && !catBtn.matches('#addCategoryTile')) {
        const idx = Number(catBtn.getAttribute('data-cat-idx'));
        if (!Number.isNaN(idx)) openCategoryModal(idx);
        return;
      }
      const addBtn = e.target.closest('#addCategoryTile, [data-action="add-category"]');
      if (addBtn) {
        openAddCategoryModal();
        return;
      }
    });
  }

  function openCenterPage(kind, title){
    showCenterContent();
    setCenterTitle(title);
    // If the same page kind is requested again, avoid re-render to preserve state
    if (currentCenterKind === kind) {
      // Still sync quick status counters on re-open for freshness
      if (kind === 'quickStatus') {
        if (els.revCounter && document.getElementById('revCounterBig')) document.getElementById('revCounterBig').textContent = els.revCounter.textContent;
        if (els.activeOrdersCount && document.getElementById('activeOrdersCountBig')) document.getElementById('activeOrdersCountBig').textContent = els.activeOrdersCount.textContent;
        if (els.qrScansToday && document.getElementById('qrScansTodayBig')) document.getElementById('qrScansTodayBig').textContent = els.qrScansToday.textContent;
      }
      bindCenterPageEvents(kind);
      return;
    }
    ensureFadeStyle();
    const dyn = getDynamicContainer();
    if (dyn) {
      dyn.innerHTML = renderExpanded(kind);
      try { dyn.scrollTop = 0; } catch {}
      try { dyn.classList.remove('nb-fade-in'); void dyn.offsetWidth; dyn.classList.add('nb-fade-in'); } catch {}
    }
    if (els.centerContent) { try { els.centerContent.scrollTop = 0; } catch {} }
    if (kind === 'liveOrders') initLiveOrders();
    if (kind === 'liveChat') initLiveChat();
    if (kind === 'liveReservation') initLiveReservation();
    if (kind === 'menuMgmt') initMenuMgmt();
    if (kind === 'menuBrowse') initMenuBrowse();
    if (kind === 'workingHours') initWorkingHours();
    if (kind === 'reports') initReports();
    // sync big counters from overview if available
    if (kind === 'quickStatus') {
      if (els.revCounter && document.getElementById('revCounterBig')) document.getElementById('revCounterBig').textContent = els.revCounter.textContent;
      if (els.activeOrdersCount && document.getElementById('activeOrdersCountBig')) document.getElementById('activeOrdersCountBig').textContent = els.activeOrdersCount.textContent;
      if (els.qrScansToday && document.getElementById('qrScansTodayBig')) document.getElementById('qrScansTodayBig').textContent = els.qrScansToday.textContent;
    }
    bindCenterPageEvents(kind);
    currentCenterKind = kind;
  }

  function bindCenterPageEvents(kind){
    try {
      if (kind === 'qrAssets') {
        document.getElementById('actBatchMenuQR')?.addEventListener('click', ()=> alert('Generate Menu QR Batch coming soon'));
      } else if (kind === 'tableMgmt') {
        document.getElementById('actGenerateTableQR')?.addEventListener('click', ()=> alert('Generate Table QR coming soon'));
      } else if (kind === 'customerData') {
        document.getElementById('actImportCustomers')?.addEventListener('click', ()=> alert('CSV Import coming soon'));
      } else if (kind === 'opsFiles') {
        document.getElementById('actUploadOps')?.addEventListener('click', ()=> alert('Upload Document coming soon'));
      } else if (kind === 'uploadZones') {
        document.getElementById('uzMenuPhotosCenter')?.addEventListener('click', ()=> setCenterTitle('Upload: Menu Photos'));
        document.getElementById('uzCsvCenter')?.addEventListener('click', ()=> setCenterTitle('Upload: CSV Imports'));
        document.getElementById('uzReceiptsCenter')?.addEventListener('click', ()=> setCenterTitle('Upload: Receipts/Invoices'));
        document.getElementById('uzMarketingCenter')?.addEventListener('click', ()=> setCenterTitle('Upload: Marketing'));
      }
    } catch {}
  }

  function initReports(){
    // Placeholder for future report filters/downloads
    // e.g., bind dropdowns/date pickers when added
  }

  // -------- Working Hours (Weekly Schedule) --------
  const WH_KEY = 'x7_working_hours';
  const WH_DAYS = ['mon','tue','wed','thu','fri','sat','sun'];
  function defaultWorkingHours(){
    return {
      mon: { open: true,  start: '09:00', end: '17:00' },
      tue: { open: true,  start: '09:00', end: '17:00' },
      wed: { open: true,  start: '09:00', end: '17:00' },
      thu: { open: true,  start: '09:00', end: '17:00' },
      fri: { open: true,  start: '09:00', end: '17:00' },
      sat: { open: false, start: '',      end: ''      },
      sun: { open: false, start: '',      end: ''      },
    };
  }
  function readWorkingHours(){
    try {
      const obj = JSON.parse(localStorage.getItem(WH_KEY) || 'null');
      if (obj && typeof obj === 'object') return obj;
    } catch {}
    return defaultWorkingHours();
  }
  function writeWorkingHours(data){
    try { localStorage.setItem(WH_KEY, JSON.stringify(data||defaultWorkingHours())); } catch {}
  }
  function collectWHFromInputs(){
    const data = defaultWorkingHours();
    WH_DAYS.forEach(d => {
      const open = !!document.getElementById(`wh-open-${d}`)?.checked;
      const start = document.getElementById(`wh-openTime-${d}`)?.value || '';
      const end = document.getElementById(`wh-closeTime-${d}`)?.value || '';
      data[d] = { open, start, end };
    });
    return data;
  }
  function populateWHInputs(data){
    WH_DAYS.forEach(d => {
      const rowOpen = document.getElementById(`wh-open-${d}`);
      const rowStart = document.getElementById(`wh-openTime-${d}`);
      const rowEnd = document.getElementById(`wh-closeTime-${d}`);
      const val = data[d] || {};
      if (rowOpen) rowOpen.checked = !!val.open;
      if (rowStart) rowStart.value = val.start || '';
      if (rowEnd) rowEnd.value = val.end || '';
    });
  }
  function initWorkingHours(){
    const form = document.getElementById('whForm');
    if (!form) return;
    const saved = readWorkingHours();
    populateWHInputs(saved);
    const saveBtn = document.getElementById('whSave');
    const resetBtn = document.getElementById('whReset');
    const doSave = ()=> writeWorkingHours(collectWHFromInputs());
    saveBtn?.addEventListener('click', doSave);
    resetBtn?.addEventListener('click', ()=> { populateWHInputs(defaultWorkingHours()); doSave(); });
    form.addEventListener('change', doSave);
  }

  // -------- Live Updates (Overview, Conversations, Orders) --------
  async function fetchJSON(url){
    const res = await x7Fetch(url);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  }

  async function updateLive(){
    try {
      const auth = (window.X7Auth && typeof X7Auth.getAuth === 'function') ? X7Auth.getAuth() : null;
      if (!auth || !auth.token) {
        console.warn('Auth token not found, skipping live data update.');
        return;
      }

      const [overview, conversations, orders] = await Promise.all([
        fetchJSON(`${API_BASE}/dashboard/overview`),
        fetchJSON(`${API_BASE}/dashboard/conversations?limit=5`),
        fetchJSON(`${API_BASE}/dashboard/orders/live?limit=5`),
      ]);
      // Normalize backend overview shape to UI-expected keys
      const ov = overview || {};
      const today = ov && ov.today ? ov.today : {};
      const normalized = {
        total_revenue: today.total_revenue ?? 0,
        // Estimate active orders as non-completed orders for the day
        active_orders: Math.max(0, (today.total_orders ?? 0) - (today.completed_orders ?? 0)),
        new_customers: ov.new_customers ?? 0,
        active_bookings: ov.active_bookings ?? 0,
        business_status: ov.business_status || 'offline',
      };
      renderOverview(normalized);
      updateQuickStatus(normalized);
      renderConversations(conversations||[]);
      renderOrders(orders||[]);
    } catch (e) {
      // Soft-fail
      console.warn('Live updates failed', e);
    }
  }

  function renderOverview(stats){
    if (!els.overviewStats) return;
    const items = [
      {label:'Total Revenue', value: stats.total_revenue ? `$${Number(stats.total_revenue).toLocaleString()}` : '$0', icon:'dollar-sign'},
      {label:'Active Bookings', value: stats.active_bookings?.toLocaleString?.() || '0', icon:'calendar-check'},
      {label:'Active Orders', value: stats.active_orders?.toLocaleString?.() || '0', icon:'utensils'},
      {label:'New Customers', value: stats.new_customers?.toLocaleString?.() || '0', icon:'users'},
    ];
    els.overviewStats.innerHTML = items.map(it => `
      <div class="stat-item" style="display:flex;align-items:center;gap:10px;padding:8px;border:1px solid var(--nb-border);border-radius:8px;background:var(--nb-elev-2);margin-bottom:8px;">
        <div class="stat-icon" style="color:var(--nb-accent)"><i class="fas fa-${it.icon}"></i></div>
        <div class="stat-content" style="display:flex;justify-content:space-between;gap:12px;flex:1;">
          <div class="muted small">${it.label}</div>
          <div style="font-weight:600;">${it.value}</div>
        </div>
      </div>
    `).join('');
  }

  function updateQuickStatus(stats){
    // Defensive parsing with fallbacks
    const rev = typeof stats.total_revenue === 'number' ? `$${stats.total_revenue.toLocaleString()}` : (stats.total_revenue || '$0');
    if (els.revCounter) els.revCounter.textContent = rev;

    const activeOrders = stats.active_orders ?? stats.orders_active ?? 0;
    if (els.activeOrdersCount) els.activeOrdersCount.textContent = String(activeOrders);

    const occ = stats.tables_occupied ?? stats.tablesOccupied;
    const tot = stats.tables_total ?? stats.tablesTotal;
    if (els.tablesOccupied) els.tablesOccupied.textContent = (occ!=null && tot!=null) ? `${occ} / ${tot}` : '- / -';

    const staff = stats.staff_on_duty ?? stats.staffOnDuty;
    if (els.staffOnDuty) els.staffOnDuty.textContent = (staff!=null) ? String(staff) : '-';

    const oos = stats.items_out_of_stock ?? stats.itemsOutOfStock;
    if (els.itemsOOS) els.itemsOOS.textContent = (oos!=null) ? String(oos) : '-';

    const scans = stats.qr_scans_today ?? stats.qrScansToday;
    if (els.qrScansToday) els.qrScansToday.textContent = (scans!=null) ? String(scans) : '-';
  }

  function renderConversations(list){
    if (!els.conversationsList) return;
    if (!list.length) {
      els.conversationsList.innerHTML = `<li class="empty-state" style="padding:8px;"><i class="fas fa-comments"></i> <span class="muted small">No active conversations</span></li>`;
      return;
    }
    els.conversationsList.innerHTML = list.map(conv => {
      const name = conv.customer_name || 'Guest';
      const initial = (name[0]||'G').toUpperCase();
      const ts = conv.last_message_time || conv.last_message_at || conv.updated_at || conv.created_at;
      const time = ts ? new Date(ts).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
      const last = conv.last_message || '';
      return `
        <li class="conversation-item" style="padding:8px;border-bottom:1px solid var(--nb-border);">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="avatar" style="width:24px;height:24px;border-radius:50%;background:var(--nb-elev-2);display:inline-flex;align-items:center;justify-content:center;font-size:12px;">${initial}</span>
            <div style="flex:1;min-width:0;">
              <div style="display:flex;justify-content:space-between;gap:8px;">
                <span style="font-weight:600;">${name}</span>
                <span class="muted small">${time}</span>
              </div>
              <div class="muted small" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${last}</div>
            </div>
          </div>
        </li>`;
    }).join('');
  }

  function renderOrders(list){
    if (!els.liveOrdersList) return;
    if (!list.length) {
      els.liveOrdersList.innerHTML = `<li class="empty-state" style="padding:8px;"><i class="fas fa-utensils"></i> <span class="muted small">No live orders</span></li>`;
      return;
    }
    els.liveOrdersList.innerHTML = list.map(order => {
      const id = order.id || '';
      const status = (order.status || 'PENDING').toUpperCase();
      const itemsCount = order.items?.length || 0;
      const total = typeof order.total === 'number' ? `$${order.total.toFixed(2)}` : '$0.00';
      const customer = order.customer_name || 'Walk-in';
      return `
        <li class="order-item" style="padding:8px;border-bottom:1px solid var(--nb-border);">
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <div style="font-weight:600;">#${id}</div>
            <span class="status-badge" style="font-size:11px;padding:2px 6px;border:1px solid var(--nb-border);border-radius:999px;">${status}</span>
          </div>
          <div class="muted small" style="display:flex;gap:10px;margin-top:4px;">
            <span><i class="fas fa-user"></i> ${customer}</span>
            <span><i class="fas fa-utensils"></i> ${itemsCount} items</span>
            <span><i class="fas fa-receipt"></i> ${total}</span>
          </div>
        </li>`;
    }).join('');
  }
  function writeSources(arr){
    sources = Array.isArray(arr) ? arr : [];
    try { localStorage.setItem('x7_sources', JSON.stringify(sources)); } catch {}
  }

  function renderSources(){
    if (!els.sourcesList) return;
    if (!sources.length) {
      els.sourcesList.innerHTML = `
        <div class="nb-empty">
          <div class="nb-empty-icon"><i class="fa-regular fa-file-lines"></i></div>
          <div class="nb-empty-text">Saved sources will appear here</div>
          <p class="muted small">Click Add to include PDFs, websites, text, videos or audio files. Or import a file directly from Google Drive.</p>
        </div>`;
      return;
    }
    els.sourcesList.innerHTML = sources.map((s,i)=>`
      <div class="source-row" data-idx="${i}" style="display:flex;align-items:center;gap:8px;padding:8px;border-bottom:1px solid var(--nb-border);">
        <i class="fa-regular fa-file"></i>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${s.name}</div>
          <div class="muted small">${(s.type||'file').toUpperCase()} • ${(s.size||0)} KB</div>
        </div>
        <button class="nb-icon" title="Remove" data-action="remove"><i class="fa-solid fa-xmark"></i></button>
      </div>
    `).join('');
  }

  function bindSourceRowEvents(){
    if (!els.sourcesList) return;
    els.sourcesList.addEventListener('click', (e)=>{
      const btn = e.target.closest('button[data-action="remove"]');
      if (!btn) return;
      const row = btn.closest('.source-row');
      const idx = Number(row?.dataset.idx);
      if (Number.isInteger(idx)) {
        sources.splice(idx,1);
        writeSources(sources);
        renderSources();
      }
    });
  }

  function pickFiles(){ if (els.sourceFile) els.sourceFile.click(); }

  function handleFiles(files){
    const arr = Array.from(files||[]);
    if (!arr.length) return;
    const newOnes = arr.map(f=>({
      name: f.name,
      size: Math.ceil(f.size/1024),
      type: (f.type||'file')
    }));
    writeSources([...(sources||[]), ...newOnes]);
    renderSources();
    // Keep current view; do not auto-open chat
    // activateTab('chat'); // removed to prevent unintended auto-open
  }

  function activateTab(view){
    // Toggle active class
    els.tabs.forEach(t=>t.classList.toggle('active', t.dataset.view===view));
    // Update title
    if (view === 'chat') {
      setCenterTitle('Dashboard AI');
    } else {
      if (els.centerTitle) els.centerTitle.textContent = view.charAt(0).toUpperCase()+view.slice(1);
    }
    // Show appropriate content
    if (view === 'chat') {
      // Guard against non-user initiated open
      if (!allowChatOpen) { console.debug('[dashboard-ui] Blocked non-user chat open'); return; }
      // One-time permission, reset immediately
      allowChatOpen = false;
      // Always hide the center placeholder when viewing chat
      if (els.centerEmpty) els.centerEmpty.style.display = 'none';
      // Hide dynamic content container if present
      const dyn = document.getElementById('centerDynamic');
      if (dyn) dyn.style.display = 'none';
      // Remove any overlay soft card that may block the chat view
      const softCard = els.centerContent?.querySelector('.nb-soft-card');
      if (softCard) softCard.remove();
      if (els.waChat) {
        els.waChat.style.display = 'flex';
        // init dashboard chat once
        if (!chatInitialized) {
          chatInitialized = true;
          try { initDashboardChat(); } catch(e) { console.warn('initDashboardChat failed', e); }
        }
      }
    } else {
      if (els.waChat) els.waChat.style.display = 'none';
      if (els.centerEmpty) els.centerEmpty.style.display = 'flex';
      renderCenterView(view);
    }
  }

  // Ensure we never destroy #waChat by replacing centerContent; instead render into a dynamic container
  function getDynamicContainer(){
    if (!els.centerContent) return null;
    let dyn = els.centerContent.querySelector('#centerDynamic');
    if (!dyn) {
      dyn = document.createElement('div');
      dyn.id = 'centerDynamic';
      dyn.className = 'nb-center-dynamic';
      // Insert before #waChat so chat stays on top when shown
      const wa = els.centerContent.querySelector('#waChat');
      if (wa) {
        els.centerContent.insertBefore(dyn, wa);
      } else {
        els.centerContent.appendChild(dyn);
      }
    }
    return dyn;
  }

  function renderCenterView(view){
    // Simple placeholder content for non-chat tabs
    if (!els.centerContent) return;
    const map = {
      menu: {
        icon: 'utensils',
        title: 'Menu',
        desc: 'Manage items, categories, prices, and availability.'
      },
      tables: {
        icon: 'table-cells',
        title: 'Tables',
        desc: 'Create zones, manage table status, and assignments.'
      },
      waitlist: {
        icon: 'list-ol',
        title: 'Waitlist',
        desc: 'Track and notify waiting parties in real-time.'
      }
    };
    const meta = map[view] || {icon:'circle-info', title:'Coming Soon', desc:'Content will appear here.'};

    // Keep centerEmpty visible for guidance, but we can also inject a soft card
    const existing = els.centerContent.querySelector('.nb-soft-card');
    if (existing) existing.remove();
    const card = document.createElement('div');
    card.className = 'nb-soft-card';
    card.style.cssText = 'position:absolute;top:60px;left:50%;transform:translateX(-50%);width:min(640px,90%);border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:10px;padding:16px;box-shadow:0 1px 0 rgba(0,0,0,.2)';
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;">
        <i class="fa-solid fa-${meta.icon}" style="color:var(--nb-accent)"></i>
        <div style="font-weight:600;">${meta.title}</div>
      </div>
      <div class="muted small" style="margin-top:6px;">${meta.desc}</div>
    `;
    els.centerContent.appendChild(card);
  }

  // Logout utility
  function x7Logout(){
    try {
      if (window.X7Auth) {
        X7Auth.clearAuth();
        X7Auth.setProfile({});
      }
    } catch {}
    try { window.location.reload(); } catch {}
  }

  function removeProfileMenu(){
    document.getElementById('profileMenu')?.remove();
    document.removeEventListener('click', handleOutsideClickProfile, true);
  }

  function handleOutsideClickProfile(e){
    const menu = document.getElementById('profileMenu');
    if (!menu) return;
    if (!menu.contains(e.target) && !els.topProfile.contains(e.target)) {
      removeProfileMenu();
    }
  }

  function openProfileMenu(logged, profile){
    removeProfileMenu();
    const rect = els.topProfile.getBoundingClientRect();
    const menu = document.createElement('div');
    menu.id = 'profileMenu';
    menu.style.cssText = 'position:fixed;min-width:220px;border:1px solid var(--nb-border);background:var(--nb-elev-1);border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.4);padding:8px;z-index:9999;display:flex;flex-direction:column;gap:4px;';
    // Position below and right-aligned to the profile circle
    menu.style.top = (rect.bottom + 8) + 'px';
    menu.style.right = (window.innerWidth - rect.right) + 'px';

    const btnStyle = 'display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;border:1px solid transparent;background:transparent;color:var(--nb-text);cursor:pointer;text-align:left;';
    const btnHover = 'this.style.borderColor=\'' + "var(--nb-border)" + '\'';
    const btnOut = 'this.style.borderColor=\'transparent\'';

    if (logged) {
      const name = (profile && (profile.businessName || profile.name)) || 'My Business';
      const hdr = document.createElement('div');
      hdr.style.cssText = 'padding:6px 10px;font-weight:700;color:var(--nb-text)';
      hdr.textContent = name;
      menu.appendChild(hdr);

      const profileBtn = document.createElement('button');
      profileBtn.style.cssText = btnStyle;
      profileBtn.innerHTML = '<i class="fa-regular fa-user"></i> <span>Profile & Settings</span>';
      profileBtn.onmouseover = function(){ eval(btnHover); };
      profileBtn.onmouseout = function(){ eval(btnOut); };
      profileBtn.addEventListener('click', ()=> { window.location.href = '../onboarding.html'; });
      menu.appendChild(profileBtn);

      const subBtn = document.createElement('button');
      subBtn.style.cssText = btnStyle;
      subBtn.innerHTML = '<i class="fa-regular fa-credit-card"></i> <span>Subscription</span>';
      subBtn.onmouseover = function(){ eval(btnHover); };
      subBtn.onmouseout = function(){ eval(btnOut); };
      subBtn.addEventListener('click', ()=> { window.location.href = '../subscription.html'; });
      menu.appendChild(subBtn);

      const hr = document.createElement('div');
      hr.style.cssText = 'height:1px;background:var(--nb-border);margin:4px 0;';
      menu.appendChild(hr);

      const logoutBtn = document.createElement('button');
      logoutBtn.style.cssText = btnStyle + 'color:var(--nb-accent);';
      logoutBtn.innerHTML = '<i class="fa-solid fa-right-from-bracket"></i> <span>Logout</span>';
      logoutBtn.onmouseover = function(){ eval(btnHover); };
      logoutBtn.onmouseout = function(){ eval(btnOut); };
      logoutBtn.addEventListener('click', x7Logout);
      menu.appendChild(logoutBtn);
    } else {
      const loginBtn = document.createElement('button');
      loginBtn.style.cssText = btnStyle + 'justify-content:flex-start;';
      loginBtn.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> <span>Login</span>';
      loginBtn.onmouseover = function(){ eval(btnHover); };
      loginBtn.onmouseout = function(){ eval(btnOut); };
      loginBtn.addEventListener('click', ()=> { window.location.href = '../auth.html'; });
      menu.appendChild(loginBtn);
    }

    document.body.appendChild(menu);
    setTimeout(()=> document.addEventListener('click', handleOutsideClickProfile, true), 0);
  }

  function initTopbarProfile(){
    try {
      if (!window.X7Auth || !els.topProfile) return;
      const logged = X7Auth.isLoggedIn();
      const profile = X7Auth.getProfile();
      // Title = business name if available
      if (profile && profile.businessName && els.nbTitle) {
        els.nbTitle.textContent = profile.businessName;
      }
      els.topProfile.style.cursor = 'pointer';
      els.topProfile.title = logged ? 'Open profile' : 'Login';
      // Fill avatar color/initial
      try {
        const name = (profile && (profile.businessName || profile.name)) || '';
        if (name) {
          els.topProfile.textContent = (name.trim()[0] || '').toUpperCase();
          els.topProfile.style.display = 'flex';
          els.topProfile.style.alignItems = 'center';
          els.topProfile.style.justifyContent = 'center';
          els.topProfile.style.fontWeight = '700';
          els.topProfile.style.color = 'var(--nb-text)';
        }
      } catch {}
      // Toggle dropdown on click
      els.topProfile.addEventListener('click', () => openProfileMenu(X7Auth.isLoggedIn(), X7Auth.getProfile()));
    } catch {}
  }

  function initStudio(){
    if (!els.studioCards) return;
    // Capture-phase guard: intercept Live Orders click before any bubbling handlers
    els.studioCards.addEventListener('click', (e)=>{
      const card = e.target.closest('.nb-card');
      if (!card) return;
      const tool = card.getAttribute('data-tool');
      const titleEl = card.querySelector('.nb-card-title');
      const title = titleEl?.textContent?.trim();
      const isLiveOrders = (title === 'Live Orders' || tool === 'audio');
      const isLiveChat = (title === 'Live Chat' || tool === 'video');
      const isLiveReservation = (title === 'Live Reservation' || tool === 'mindmap');
      const isReports = (title === 'Reports' || tool === 'reports');
      if (isLiveOrders || isLiveChat || isLiveReservation || isReports) {
        e.preventDefault();
        if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
        e.stopPropagation();
        // Failsafe: remove any previously appended studio placeholder items
        try { document.querySelectorAll('.nb-studio-output .studio-item')?.forEach(n => n.remove()); } catch {}
        const kind = isLiveOrders ? 'liveOrders' : (isLiveChat ? 'liveChat' : (isLiveReservation ? 'liveReservation' : 'reports'));
        const pageTitle = isLiveOrders ? 'Incoming online orders' : (isLiveChat ? 'Incoming customer chats' : (isLiveReservation ? 'Incoming table reservations' : 'Reports'));
        openCenterPage(kind, pageTitle);
        return;
      }
    }, true);
    els.studioCards.addEventListener('click', (e)=>{
      const card = e.target.closest('.nb-card');
      if (!card) return;
      const tool = card.getAttribute('data-tool');
      const titleEl = card.querySelector('.nb-card-title');
      const title = titleEl?.textContent?.trim();
      // Special-case: Open Live Orders view in center panel
      const isLiveOrders = (title === 'Live Orders' || tool === 'audio');
      const isLiveChat = (title === 'Live Chat' || tool === 'video');
      const isLiveReservation = (title === 'Live Reservation' || tool === 'mindmap');
      const isReports = (title === 'Reports' || tool === 'reports');
      if (isLiveOrders || isLiveChat || isLiveReservation || isReports) {
        // Fully suppress studio output item for Live Orders card
        e.preventDefault();
        if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
        e.stopPropagation();
        const kind = isLiveOrders ? 'liveOrders' : (isLiveChat ? 'liveChat' : (isLiveReservation ? 'liveReservation' : 'reports'));
        const pageTitle = isLiveOrders ? 'Incoming online orders' : (isLiveChat ? 'Incoming customer chats' : (isLiveReservation ? 'Incoming table reservations' : 'Reports'));
        openCenterPage(kind, pageTitle);
        return;
      }
      // Disabled: do not append placeholder studio output items for any tool
      // const out = document.querySelector('.nb-studio-output');
      // if (out) { /* intentionally no-op */ }
    });
  }

  // Observe the studio output area and immediately remove any placeholder `.studio-item` nodes
  function installStudioOutputGuard(){
    try {
      const out = document.querySelector('.nb-studio-output');
      if (!out) return;
      // Initial cleanup
      try { out.querySelectorAll('.studio-item')?.forEach(n => n.remove()); } catch {}
      const obs = new MutationObserver((mutations) => {
        for (const m of mutations) {
          if (!m.addedNodes || m.addedNodes.length === 0) continue;
          m.addedNodes.forEach(node => {
            try {
              if (node.nodeType === 1) { // ELEMENT_NODE
                if (node.classList?.contains('studio-item')) node.remove();
                node.querySelectorAll?.('.studio-item')?.forEach(n => n.remove());
              }
            } catch {}
          });
        }
      });
      obs.observe(out, { childList: true, subtree: true });
    } catch {}
  }

  function initActions(){
    els.analyticsBtn?.addEventListener('click', ()=> alert('Analytics coming soon'));
    els.shareBtn?.addEventListener('click', ()=> alert('Share link copied'));
    els.settingsBtn?.addEventListener('click', ()=> alert('Settings coming soon'));
  }

  function initQuickAccess(){
    els.qaAddMenuItem?.addEventListener('click', ()=> openCenterPage('menuMgmt', 'Add Menu Item'));
    els.qaGenerateQR?.addEventListener('click', ()=> openCenterPage('qrAssets', 'Generate QR Codes'));
    els.qaEightySixItem?.addEventListener('click', ()=> openCenterPage('menuMgmt', '86 Item'));
    els.qaDailySpecial?.addEventListener('click', ()=> openCenterPage('menuMgmt', 'Create Daily Special'));
    els.qaQuickPrice?.addEventListener('click', ()=> openCenterPage('menuMgmt', 'Quick Price Update'));
  }

  function initUploadZones(){
    els.uzMenuPhotos?.addEventListener('click', ()=> openCenterPage('uploadZones', 'Upload: Menu Photos'));
    els.uzCsvImports?.addEventListener('click', ()=> openCenterPage('uploadZones', 'Upload: CSV Imports'));
    els.uzReceipts?.addEventListener('click', ()=> openCenterPage('uploadZones', 'Upload: Receipts/Invoices'));
    els.uzMarketing?.addEventListener('click', ()=> openCenterPage('uploadZones', 'Upload: Marketing'));
    els.uzSocial?.addEventListener('click', ()=> openCenterPage('uploadZones', 'Upload: Social Media'));
  }

  // Persist selection highlight on left panel cards
  function setActiveLeftCard(el){
    try {
      document.querySelectorAll('.nb-left .nb-link-card.active').forEach(n => n.classList.remove('active'));
      if (el) el.classList.add('active');
    } catch {}
  }

  function initLeftCards(){
    els.cardHome?.addEventListener('click', ()=> { setActiveLeftCard(els.cardHome); openCenterPage('home', 'Home'); });
    els.cardChat?.addEventListener('click', (e)=> { e.preventDefault(); setActiveLeftCard(els.cardChat); forceShowChat(); });
    els.cardMenu?.addEventListener('click', ()=> { setActiveLeftCard(els.cardMenu); openCenterPage('menuBrowse', 'Menu'); });
    els.cardMenuMgmt?.addEventListener('click', ()=> { setActiveLeftCard(els.cardMenuMgmt); openCenterPage('menuMgmt', 'Menu Management'); });
    els.cardTableMgmt?.addEventListener('click', ()=> { setActiveLeftCard(els.cardTableMgmt); openCenterPage('tableMgmt', 'Table Management'); });
    els.cardQrAssets?.addEventListener('click', ()=> { setActiveLeftCard(els.cardQrAssets); openCenterPage('qrAssets', 'QR Code Assets'); });
    els.cardCustomerData?.addEventListener('click', ()=> { setActiveLeftCard(els.cardCustomerData); openCenterPage('customerData', 'Customer Data'); });
    els.cardOpsFiles?.addEventListener('click', ()=> { setActiveLeftCard(els.cardOpsFiles); openCenterPage('opsFiles', 'Operational Files'); });
    els.cardWorkingHours?.addEventListener('click', ()=> { setActiveLeftCard(els.cardWorkingHours); openCenterPage('workingHours', 'Working Hours'); });
    els.cardQuickStatus?.addEventListener('click', ()=> { setActiveLeftCard(els.cardQuickStatus); openCenterPage('quickStatus', 'Quick Status'); });
    els.cardUploadZones?.addEventListener('click', ()=> { setActiveLeftCard(els.cardUploadZones); openCenterPage('uploadZones', 'Upload Zones'); });
  }

  // Drag & Drop reordering for left panel link cards
  const LEFT_ORDER_KEY = 'x7_left_card_order';

  function applySavedLeftOrder(){
    try {
      const container = document.querySelector('.nb-panel.nb-left');
      if (!container) return;
      const saved = JSON.parse(localStorage.getItem(LEFT_ORDER_KEY) || '[]');
      if (!Array.isArray(saved) || saved.length === 0) return;
      const sectionById = new Map();
      container.querySelectorAll('.nb-subsection').forEach(sec => {
        const card = sec.querySelector('.nb-link-card[id]');
        if (card) sectionById.set(card.id, sec);
      });
      // Append in saved order; any leftover sections remain in their current order
      saved.forEach(id => {
        const sec = sectionById.get(id);
        if (sec) container.appendChild(sec);
      });
    } catch {}
  }

  function persistLeftOrder(){
    try {
      const container = document.querySelector('.nb-panel.nb-left');
      if (!container) return;
      const ids = Array.from(container.querySelectorAll('.nb-subsection .nb-link-card[id]')).map(n => n.id);
      localStorage.setItem(LEFT_ORDER_KEY, JSON.stringify(ids));
    } catch {}
  }

  function initLeftReorder(){
    const container = document.querySelector('.nb-panel.nb-left');
    if (!container) return;
    let dragged = null;
    const sections = Array.from(container.querySelectorAll('.nb-subsection')).filter(sec => sec.querySelector('.nb-link-card[id]'));
    sections.forEach(sec => {
      sec.setAttribute('draggable', 'true');
      sec.addEventListener('dragstart', function(e){
        dragged = this;
        this.classList.add('dragging');
        try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', ''); } catch {}
        window.__leftReordering = true;
      });
      sec.addEventListener('dragend', function(){
        this.classList.remove('dragging');
        persistLeftOrder();
        window.__leftReordering = false;
        window.__leftReorderSuppressClicksUntil = (window.performance?.now?.() || Date.now()) + 250;
      });
      sec.addEventListener('dragover', function(e){
        e.preventDefault();
        if (!dragged || dragged === this) return;
        const rect = this.getBoundingClientRect();
        const after = e.clientY > rect.top + rect.height / 2;
        if (after) {
          container.insertBefore(dragged, this.nextSibling);
        } else {
          container.insertBefore(dragged, this);
        }
      });
    });
  }

  // Suppress accidental card clicks right after a drag-drop reorder (capture on left panel)
  document.addEventListener('click', function(e){
    const until = window.__leftReorderSuppressClicksUntil || 0;
    const now = (window.performance?.now?.() || Date.now());
    if (now < until && e.target?.closest?.('.nb-panel.nb-left')) {
      e.stopPropagation();
      e.preventDefault();
    }
  }, true);

  // Delegated fallback: ensure clicks anywhere inside #cardChat open chat
  document.addEventListener('click', (e) => {
    const card = e.target.closest('[data-open-chat]');
    if (card) {
      e.preventDefault();
      setActiveLeftCard(els.cardChat);
      forceShowChat();
    }
  });

  // Delegated handler: ensure New Chat button always works even if direct binding missed
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('#newChatBtn');
    if (btn) {
      // If direct binding exists, skip delegated to avoid double-fire
      if (btn.dataset && btn.dataset.bound === '1') return;
      e.preventDefault();
      try {
        console.debug('[dashboard-ui] New Chat (delegated) click');
        startNewDashboardChat();
      } catch (err) {
        console.warn('startNewDashboardChat (delegated) failed', err);
      }
    }
  });

  function initLiveUpdates(){
    // Initial fetch
    updateLive();
    // Set up interval for live updates (e.g., every 30 seconds)
    if (liveInterval) clearInterval(liveInterval);
    liveInterval = setInterval(updateLive, 30000);
  }

  function initLive(){
    initLiveUpdates();
    // Refresh button: spin icon and reload the page
    els.refreshBtn?.addEventListener('click', handleRefreshClick);
  }

  function handleRefreshClick(){
    try { els.refreshBtn?.querySelector('i')?.classList.add('fa-spin'); } catch {}
    try { if (typeof updateLive === 'function') updateLive(); } catch {}
    // Small delay to show spin before reload
    setTimeout(()=> { window.location.reload(); }, 400);
  }

  function initSources(){
    renderSources();
    bindSourceRowEvents();
    els.addSource?.addEventListener('click', pickFiles);
    els.discoverSource?.addEventListener('click', ()=> alert('Discover sources coming soon'));
    els.uploadSourceFooter?.addEventListener('click', pickFiles);
    els.uploadSourceCenter?.addEventListener('click', pickFiles);
    els.sourceFile?.addEventListener('change', (e)=> handleFiles(e.target.files));
  }

  /**
   * Initialize the dashboard chat interface
   * Sets up the DashboardChatInterface and connects event handlers
   */
  function initDashboardChat() {
    // Only initialize once
    if (dashboardChat) return;
    
    // Get business ID from profile
    const profile = window.X7Auth?.getProfile?.() || {};
    const auth = window.X7Auth?.getAuth?.() || {};
    const businessId = profile.businessId || auth.businessId;
    
    if (!businessId) {
      console.error('No business ID found (auth/profile). Please log in again.');
      return;
    }
    // Persist businessId into profile for future reads
    if (!profile.businessId && window.X7Auth?.setProfile) {
      try { window.X7Auth.setProfile({ ...profile, businessId }); } catch {}
    }
    
    // Create dashboard chat interface
    try {
      dashboardChat = new DashboardChatInterface(businessId);
      
      // Set up event handlers
      dashboardChat.onMessage = handleDashboardChatMessage;
      dashboardChat.onConnectionChange = handleDashboardConnectionChange;
      
      // Connect WebSocket
      dashboardChat.connectWebSocket();
      
      // Set up UI event handlers
      setupDashboardChatUI();
      
      console.log('Dashboard chat initialized');
    } catch (error) {
      console.error('Failed to initialize dashboard chat:', error);
    }
  }
  
  /**
   * Handle incoming dashboard chat messages
   * @param {Object} message - The message object from the chat interface
   */
  function handleDashboardChatMessage(message) {
    console.log('Dashboard chat message:', message);
    
    switch (message.type) {
      case 'word':
        // Handle word streaming
        appendWordToCurrentMessage(message.data);
        break;
      
      case 'message':
        // Handle complete message
        finalizeCurrentMessage(message.data, message.actions);
        break;
      
      case 'error':
        // Handle error message
        displayErrorMessage(message.data);
        break;
      
      default:
        console.warn('Unknown message type:', message.type);
        break;
    }
  }
  
  /**
   * Handle dashboard chat connection status changes
   * @param {boolean} connected - Whether the connection is established
   */
  function handleDashboardConnectionChange(connected) {
    const statusDot = document.getElementById('statusDot');
    if (statusDot) {
      statusDot.className = connected ? 'status-dot on' : 'status-dot off';
      statusDot.title = connected ? 'Connected' : 'Disconnected';
      statusDot.style.background = connected ? '#4caf50' : '#8796a0';
    }
    
    console.log('Dashboard chat connection:', connected ? 'Connected' : 'Disconnected');
  }
  
  /**
   * Set up UI event handlers for dashboard chat
   */
  function setupDashboardChatUI() {
    // Send button
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
      sendBtn.addEventListener('click', sendDashboardMessage);
    }
    
    // Input field
    const input = document.getElementById('input');
    if (input) {
      input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendDashboardMessage();
        }
      });
    }
    
    // New chat button
    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
      newChatBtn.addEventListener('click', (ev) => {
        console.debug('[dashboard-ui] New Chat (direct) click');
        startNewDashboardChat(ev);
      });
      // Mark as directly bound so delegated handler can skip it
      try { newChatBtn.dataset.bound = '1'; } catch {}
    }
  }
  
  /**
   * Send a message through the dashboard chat interface
   */
  function sendDashboardMessage() {
    const input = document.getElementById('input');
    if (!input || !dashboardChat) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    // Clear input
    input.value = '';
    
    // Add user message to UI
    addUserMessageToChat(message);
    // Persist to active conversation and refresh sidebar list
    try {
      const convId = window.X7Chat?.getActiveConversationId?.();
      if (convId && window.X7Chat?.addMessageToConversation) {
        window.X7Chat.addMessageToConversation(convId, 'user', message);
      }
    } catch {}
    
    // Send message via WebSocket
    try {
      dashboardChat.sendWebSocketMessage(message);
    } catch (error) {
      console.error('Failed to send message:', error);
      displayErrorMessage('Failed to send message. Please try again.');
    }
  }
  
  /**
   * Start a new dashboard chat session
   */
  async function startNewDashboardChat() {
    // Reentrancy guard to avoid double-invocation (e.g., direct + delegated handlers)
    if (window.__newChatBusy) {
      console.debug('[dashboard-ui] New Chat ignored: operation in progress');
      return;
    }
    window.__newChatBusy = true;
    try {
      // Disable the button during reset to prevent rapid clicks
      const btn = document.getElementById('newChatBtn');
      try { if (btn) btn.disabled = true; } catch {}

      // Always ensure the chat UI is visible when starting a new chat
      try { forceShowChat(); } catch (e) { console.debug('forceShowChat failed', e); }

      // Clear chat messages UI
      const messagesContainer = document.getElementById('messages');
      if (messagesContainer) messagesContainer.innerHTML = '';
      // Focus input for immediate typing
      try { document.getElementById('input')?.focus(); } catch {}

      // Create and activate a new conversation in the global list (dashboard-dedicated)
      try {
        const bizId = (dashboardChat && dashboardChat.businessId)
          || window.X7Auth?.getProfile?.()?.businessId
          || window.X7Auth?.getAuth?.()?.businessId
          || null;
        if (window.X7Chat?.createConversation && window.X7Chat?.setActiveConversation) {
          const conv = window.X7Chat.createConversation({
            isDedicated: !!bizId,
            businessId: bizId ? Number(bizId) : null,
            title: bizId ? `Business ${bizId}` : 'Business Owners Chatting',
          });
          window.X7Chat.setActiveConversation(conv.id, { connect: false, render: true });
        }
      } catch (e) { console.warn('Failed to create dashboard conversation', e); }

      if (dashboardChat) {
        const oldSessionId = dashboardChat.sessionId;
        const businessId = dashboardChat.businessId;
        try {
          // Best-effort: delete server-side conversation memory for this session
          await deleteDashboardConversation(businessId, oldSessionId);
          console.log('Deleted dashboard conversation', { businessId, oldSessionId });
        } catch (e) {
          console.warn('Delete dashboard conversation failed (continuing with reset):', e?.message || e);
        }

        // Close existing socket and reset local session id
        try { dashboardChat.closeWebSocket(); } catch {}
        try { localStorage.removeItem('x7_dashboard_chat_session_id'); } catch {}

        // Create new chat instance with a fresh session id
        dashboardChat = new DashboardChatInterface(businessId);
        dashboardChat.onMessage = handleDashboardChatMessage;
        dashboardChat.onConnectionChange = handleDashboardConnectionChange;
        dashboardChat.connectWebSocket();
      } else {
        // If the chat interface hasn't been initialized yet, do it now
        try {
          initDashboardChat();
          // After init, ensure a conversation exists and is active
          try {
            const bizId = window.dashboardChat?.businessId
              || window.X7Auth?.getProfile?.()?.businessId
              || window.X7Auth?.getAuth?.()?.businessId
              || null;
            if (window.X7Chat?.createConversation && window.X7Chat?.setActiveConversation) {
              const conv = window.X7Chat.createConversation({
                isDedicated: !!bizId,
                businessId: bizId ? Number(bizId) : null,
                title: bizId ? `Business ${bizId}` : 'Business Owners Chatting',
              });
              window.X7Chat.setActiveConversation(conv.id, { connect: false, render: true });
            }
          } catch {}
        } catch (e) { console.warn('initDashboardChat in new chat failed', e); }
      }

      console.log('Started new dashboard chat session (fresh temporary memory)');
    } finally {
      window.__newChatBusy = false;
      // Re-enable button
      try { const btn = document.getElementById('newChatBtn'); if (btn) btn.disabled = false; } catch {}
    }
  }
  
  /**
   * Add a user message to the chat UI
   * @param {string} message - The message text
   */
  function addUserMessageToChat(message) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = 'wa-message user';
    messageElement.innerHTML = `
      <div class="wa-message-bubble" style="background:#00a884;color:#0b141a;max-width:80%;margin-left:auto;margin-bottom:12px;padding:8px 12px;border-radius:8px;">
        <div class="wa-message-text">${escapeHtml(message)}</div>
      </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  /**
   * Append a word to the current AI message
   * @param {string} word - The word to append
   */
  function appendWordToCurrentMessage(word) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) return;
    
    // Find or create the current AI message bubble
    let currentMessage = messagesContainer.querySelector('.wa-message.ai:last-child');
    if (!currentMessage) {
      currentMessage = document.createElement('div');
      currentMessage.className = 'wa-message ai';
      currentMessage.innerHTML = `
        <div class="wa-message-bubble" style="background:var(--nb-elev-2);color:var(--nb-text);max-width:80%;margin-bottom:12px;padding:8px 12px;border-radius:8px;">
          <div class="wa-message-text"></div>
        </div>
      `;
      messagesContainer.appendChild(currentMessage);
    }
    
    const textElement = currentMessage.querySelector('.wa-message-text');
    if (textElement) {
      textElement.textContent += word + ' ';
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
  
  /**
   * Finalize the current AI message with the complete text and actions
   * @param {string} message - The complete message text
   * @param {Array} actions - Suggested actions
   */
  function finalizeCurrentMessage(message, actions) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) return;
    
    // Find the current AI message bubble
    const currentMessage = messagesContainer.querySelector('.wa-message.ai:last-child');
    if (currentMessage) {
      const textElement = currentMessage.querySelector('.wa-message-text');
      if (textElement) {
        textElement.textContent = message;
      }
      
      // Add actions if provided
      if (actions && actions.length > 0) {
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'wa-message-actions';
        actionsContainer.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;';
        
        actions.forEach(action => {
          const button = document.createElement('button');
          button.className = 'btn';
          button.style.cssText = 'padding:6px 10px;border:1px solid var(--nb-border);border-radius:8px;background:var(--nb-elev-2);color:var(--nb-text);';
          button.textContent = action.label || action.text || action;
          button.addEventListener('click', () => {
            const input = document.getElementById('input');
            if (input) {
              input.value = action.value || action.text || action;
              sendDashboardMessage();
            }
          });
          actionsContainer.appendChild(button);
        });
        
        currentMessage.appendChild(actionsContainer);
      }
    }
    
    // Persist bot message to active conversation and refresh sidebar list
    try {
      const convId = window.X7Chat?.getActiveConversationId?.();
      if (convId && window.X7Chat?.addMessageToConversation) {
        window.X7Chat.addMessageToConversation(convId, 'bot', message || '');
      }
    } catch {}

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  /**
   * Display an error message in the chat UI
   * @param {string} errorMessage - The error message to display
   */
  function displayErrorMessage(errorMessage) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = 'wa-message error';
    messageElement.innerHTML = `
      <div class="wa-message-bubble" style="background:#f44336;color:white;max-width:80%;margin-bottom:12px;padding:8px 12px;border-radius:8px;">
        <div class="wa-message-text">Error: ${escapeHtml(errorMessage)}</div>
      </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  /**
   * Escape HTML characters for safe display
   * @param {string} text - The text to escape
   * @returns {string} The escaped text
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Build Authorization headers for API requests
  function authHeaders(extra = {}) {
    try {
      let token = window.X7Auth?.getAuth?.()?.token;
      // Fallback to localStorage if X7Auth is unavailable or empty
      if (!token) {
        try {
          const raw = localStorage.getItem('x7_auth');
          if (raw) token = JSON.parse(raw)?.token || null;
        } catch {}
      }
      return {
        'Accept': 'application/json',
        ...extra,
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      };
    } catch {
      return { 'Accept': 'application/json', ...extra };
    }
  }

  // Resolve API base URL similar to DashboardChatInterface
  function getApiBase() {
    try {
      if (window.dashboardChat && window.dashboardChat.apiBase) return window.dashboardChat.apiBase;
      const qs = new URLSearchParams(window.location.search);
      const param = qs.get('api');
      if (param) localStorage.setItem('x7_api_base', param);
      const saved = localStorage.getItem('x7_api_base');
      const env = (typeof window !== 'undefined' && (window.API_BASE || window.__API_BASE__)) || saved;
      if (env) return ('' + env).replace(/\/$/, '');
      return 'http://localhost:8000/api/v1';
    } catch {
      return 'http://localhost:8000/api/v1';
    }
  }

  // DELETE dashboard conversation memory on backend (best-effort)
  async function deleteDashboardConversation(businessId, sessionId) {
    if (!businessId || !sessionId) return;
    const base = getApiBase();
    const url = `${base}/chat/dashboard/${businessId}/${sessionId}`;
    const res = await x7Fetch(url, { method: 'DELETE' });
    if (!res.ok) {
      const msg = `Delete failed: ${res.status}`;
      // surface 401 in logs but do not throw to avoid blocking UI reset
      console.warn('[deleteDashboardConversation]', msg);
    }
    return true;
  }

  function initTabs(){
    els.tabs.forEach(btn => btn.addEventListener('click', ()=> {
      if (btn.dataset.view === 'chat') allowChatOpen = true;
      activateTab(btn.dataset.view);
    }));
    // Default: keep center placeholder; only open chat when user clicks the Chat card
    if (els.centerEmpty) els.centerEmpty.style.display = 'flex';
    if (els.waChat) els.waChat.style.display = 'none';
  }

  document.addEventListener('DOMContentLoaded', function(){
    initTopbarProfile();
    initActions();
    initQuickAccess();
    initUploadZones();
    applySavedLeftOrder();
    initLeftCards();
    initLeftReorder();
    initSources();
    installStudioOutputGuard();
    initStudio();
    initLive();
    initTabs();
    // Open Home as the default main screen
    openCenterPage('home', 'Home');
    setActiveLeftCard(els.cardHome);
    // Enable dashboard chat mode so app.js does not connect to global AI
    try { window.USE_DASHBOARD_CHAT = true; } catch {}
    // Listen for conversation title updates from app.js and reflect in dashboard header
    try {
      if (window._onConvTitleChanged) document.removeEventListener('x7:conversationTitleChanged', window._onConvTitleChanged);
    } catch {}
    window._onConvTitleChanged = function(e){
      try {
        const detail = e && e.detail;
        if (!detail || !detail.id || !detail.title) return;
        const activeId = window.X7Chat?.getActiveConversationId?.();
        if (!activeId || detail.id !== activeId) return;
        const headerEl = document.querySelector('#waChat .wa-contact');
        if (headerEl) headerEl.textContent = detail.title;
      } catch {}
    };
    document.addEventListener('x7:conversationTitleChanged', window._onConvTitleChanged);
    // Initialize chat UI from app.js so sidebar toggle and chat list work
    try {
      if (typeof window.initChat === 'function') {
        window._chatInitByApp = true;
        window.initChat();
      }
    } catch (e) { console.warn('initChat failed', e); }
    // Initialize dashboard chat interface (WebSocket, send handlers) once
    try {
      if (!chatInitialized) {
        chatInitialized = true;
        initDashboardChat();
      }
    } catch (e) { console.warn('initDashboardChat failed', e); }
  });
})();
