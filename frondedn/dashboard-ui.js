(function(){
  // Dashboard UI controller for notebook-style layout
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
  // Menu categories (local persistence)
  const DEFAULT_CATEGORIES = ['Beverages','Appetizers','Main Dishes','Desserts','Specials'];
  let categories = readCategories();

  function readSources(){
    try { return JSON.parse(localStorage.getItem('x7_sources')||'[]'); } catch { return []; }
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
    form?.addEventListener('submit', (e)=>{
      e.preventDefault();
      const name = (nameEl?.value||'').trim();
      if (!name) { errEl.textContent = 'Please enter a category name.'; return; }
      if (hasCatName(name)) { errEl.textContent = 'This category already exists.'; return; }
      // Store as object to allow future metadata, keep renderer backward compatible
      writeCategories([...(categories||[]), { name, description: (descEl?.value||'').trim() }]);
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
        <div class="nb-empty" style="padding:16px;">
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
      if (!chatInitialized && typeof window.initChat === 'function') {
        chatInitialized = true;
        try { window.initChat(); } catch(e) { console.warn('initChat failed', e); }
      }
    }
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
      grid.innerHTML = `<div class="nb-empty" style="padding:16px;">No items yet. Add items in <b>Menu Management</b> and they'll appear here automatically.</div>`;
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

  function initMenuMgmt(){
    renderMenuCategories();
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
    const dyn = getDynamicContainer();
    if (dyn) dyn.innerHTML = renderExpanded(kind);
    if (kind === 'menuMgmt') initMenuMgmt();
    if (kind === 'menuBrowse') initMenuBrowse();
    if (kind === 'workingHours') initWorkingHours();
    // sync big counters from overview if available
    if (kind === 'quickStatus') {
      if (els.revCounter && document.getElementById('revCounterBig')) document.getElementById('revCounterBig').textContent = els.revCounter.textContent;
      if (els.activeOrdersCount && document.getElementById('activeOrdersCountBig')) document.getElementById('activeOrdersCountBig').textContent = els.activeOrdersCount.textContent;
      if (els.qrScansToday && document.getElementById('qrScansTodayBig')) document.getElementById('qrScansTodayBig').textContent = els.qrScansToday.textContent;
    }
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
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  }

  async function updateLive(){
    try {
      const [overview, conversations, orders] = await Promise.all([
        fetchJSON(`${API_BASE}/dashboard/overview`),
        fetchJSON(`${API_BASE}/dashboard/conversations?limit=5`),
        fetchJSON(`${API_BASE}/dashboard/orders/live?limit=5`),
      ]);
      renderOverview(overview||{});
      updateQuickStatus(overview||{});
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
      els.conversationsList.innerHTML = `<li class="empty-state" style="padding:8px;" ><i class="fas fa-comments"></i> <span class="muted small">No active conversations</span></li>`;
      return;
    }
    els.conversationsList.innerHTML = list.map(conv => {
      const name = conv.customer_name || 'Guest';
      const initial = (name[0]||'G').toUpperCase();
      const time = conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
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
        // init chat once
        if (!chatInitialized && typeof window.initChat === 'function') {
          chatInitialized = true;
          try { window.initChat(); } catch(e) { console.warn('initChat failed', e); }
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
      profileBtn.addEventListener('click', ()=> { window.location.href = 'onboarding.html'; });
      menu.appendChild(profileBtn);

      const subBtn = document.createElement('button');
      subBtn.style.cssText = btnStyle;
      subBtn.innerHTML = '<i class="fa-regular fa-credit-card"></i> <span>Subscription</span>';
      subBtn.onmouseover = function(){ eval(btnHover); };
      subBtn.onmouseout = function(){ eval(btnOut); };
      subBtn.addEventListener('click', ()=> { window.location.href = 'subscription.html'; });
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
      loginBtn.addEventListener('click', ()=> { window.location.href = 'login.html'; });
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
    els.studioCards.addEventListener('click', (e)=>{
      const card = e.target.closest('.nb-card');
      if (!card) return;
      const tool = card.getAttribute('data-tool');
      const out = document.querySelector('.nb-studio-output');
      if (out) {
        const div = document.createElement('div');
        div.className = 'studio-item';
        div.style.cssText = 'margin-top:8px;padding:10px;border:1px solid var(--nb-border);border-radius:8px;background:var(--nb-elev-2)';
        div.innerHTML = `<strong>${tool}</strong> output added. Connect sources to generate content.`;
        out.prepend(div);
      }
    });
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
  document.addEventListener('click', (e)=>{
    const card = e.target?.closest?.('#cardChat');
    if (card) {
      e.preventDefault();
      setActiveLeftCard(els.cardChat);
      forceShowChat();
    }
  });

  function initLive(){
    els.refreshBtn?.addEventListener('click', handleRefreshClick);
    // Initial and periodic refresh
    updateLive();
    if (liveInterval) clearInterval(liveInterval);
    liveInterval = setInterval(updateLive, 30000);
  }

  // Refresh button: spin icon and reload the page
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
    initStudio();
    initLive();
    initTabs();
    // Open Home as the default main screen
    openCenterPage('home', 'Home');
    setActiveLeftCard(els.cardHome);
  });
})();
