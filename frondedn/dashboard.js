(function() {
// Dashboard-specific functionality
const API_BASE = (() => {
  try {
    if (window.API_BASE_URL) return window.API_BASE_URL.replace(/\/$/, '') + '/api/v1';
  } catch {}
  return 'http://localhost:8000/api/v1';
})();

// DOM Elements
const els = {
  sidebar: document.querySelector('.sidebar'),
  navLinks: document.querySelectorAll('.nav-links li'),
  pages: document.querySelectorAll('.page'),
  currentTimeEl: document.getElementById('currentTime'),
  searchInput: document.querySelector('.search-bar input'),
  notificationsBtn: document.querySelector('.notifications'),
  modal: document.getElementById('modal'),
  closeModal: document.querySelector('.close-modal'),
  modalBody: document.getElementById('modal-body'),
  loadingOverlay: document.getElementById('loadingOverlay'),
  overviewStats: document.getElementById('overviewStats'),
  conversationsList: document.getElementById('conversationsList'),
  liveOrdersList: document.getElementById('liveOrdersList'),
  refreshBtn: document.getElementById('refreshBtn')
};

// State
let currentPage = 'dashboard';
let notifications = [];

// Bookings Page State
let bookings = [];
let tables = [];
let currentBookingsPage = 1;
const BOOKINGS_PER_PAGE = 10;
let totalBookings = 0;

// Initialize the dashboard
function initDashboard() {
  console.log('Initializing dashboard...');
  
  // Initialize event listeners
  setupEventListeners();
  
  // Load initial data
  loadPage(currentPage);
  
  // Initialize bookings page
  initBookingsPage();
  
  // Show dashboard by default
  navigateTo('dashboard');
}

// Initialize Bookings Page
function initBookingsPage() {
  // Load tables for dropdown
  loadTables();
  
  // Set default date to today
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('filter-date').value = today;
  document.getElementById('booking-date').min = today;
  
  // Set initial booking time to next hour
  const now = new Date();
  const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
  const timeString = nextHour.getHours().toString().padStart(2, '0') + ':' + 
                    nextHour.getMinutes().toString().padStart(2, '0');
  document.getElementById('booking-time').value = timeString;
  
  // Load initial bookings
  loadBookings();
}

// Load tables for dropdown
async function loadTables() {
  try {
    const response = await fetch(`${window.API_BASE_URL}/tables`);
    if (!response.ok) throw new Error('Failed to load tables');
    
    tables = await response.json();
    const tableSelect = document.getElementById('table-id');
    
    // Clear existing options except the first one
    while (tableSelect.options.length > 1) {
      tableSelect.remove(1);
    }
    
    // Add tables to dropdown
    tables.forEach(table => {
      const option = document.createElement('option');
      option.value = table.id;
      option.textContent = `Table ${table.number} (${table.capacity} people, ${table.zone || 'Any'})`;
      tableSelect.appendChild(option);
    });
  } catch (error) {
    console.error('Error loading tables:', error);
    showNotification('Failed to load tables. Please try again.', 'error');
  }
}

// Load bookings with filters
async function loadBookings(page = 1) {
  try {
    showLoading();
    
    const status = document.getElementById('filter-status').value;
    const date = document.getElementById('filter-date').value;
    const partySize = document.getElementById('filter-party-size').value;
    const search = document.getElementById('search-bookings').value;
    
    let url = `${window.API_BASE_URL}/bookings?page=${page}&limit=${BOOKINGS_PER_PAGE}`;
    
    if (status) url += `&status=${status}`;
    if (date) url += `&date=${date}`;
    if (partySize) url += `&party_size=${partySize}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to load bookings');
    
    const data = await response.json();
    bookings = data.bookings || [];
    totalBookings = data.total || 0;
    currentBookingsPage = page;
    
    renderBookings();
    updatePagination();
  } catch (error) {
    console.error('Error loading bookings:', error);
    showNotification('Failed to load bookings. Please try again.', 'error');
  } finally {
    hideLoading();
  }
}

// Render bookings in the table
function renderBookings() {
  const tbody = document.getElementById('bookings-tbody');
  
  if (bookings.length === 0) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="6" class="empty-state">
          <i class="fas fa-calendar-alt"></i>
          <h3>No bookings found</h3>
          <p>Try adjusting your filters or create a new booking</p>
          <button class="btn btn-primary mt-2" id="empty-new-booking">
            <i class="fas fa-plus"></i> New Booking
          </button>
        </td>
      </tr>
    `;
    
    // Add event listener to the empty state button
    const emptyBtn = document.getElementById('empty-new-booking');
    if (emptyBtn) {
      emptyBtn.addEventListener('click', () => openBookingModal());
    }
    
    return;
  }
  
  tbody.innerHTML = bookings.map(booking => `
    <tr data-booking-id="${booking.id}">
      <td class="customer-cell">
        <span class="customer-name">${booking.customer_name || 'Guest'}</span>
        ${booking.customer_phone ? `<span class="customer-contact">${booking.customer_phone}</span>` : ''}
      </td>
      <td>
        <div>${new Date(booking.booking_time).toLocaleDateString()}</div>
        <div class="text-muted">${new Date(booking.booking_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
      </td>
      <td>${booking.party_size} ${booking.party_size === 1 ? 'person' : 'people'}</td>
      <td>${booking.table ? `Table ${booking.table.number}` : 'Not assigned'}</td>
      <td><span class="status-badge status-${booking.status}">${booking.status}</span></td>
      <td class="actions">
        <button class="btn-icon view-booking" data-id="${booking.id}" title="View">
          <i class="fas fa-eye"></i>
        </button>
        <button class="btn-icon edit-booking" data-id="${booking.id}" title="Edit">
          <i class="fas fa-edit"></i>
        </button>
        ${booking.status !== 'cancelled' ? `
          <button class="btn-icon danger cancel-booking" data-id="${booking.id}" title="Cancel">
            <i class="fas fa-times"></i>
          </button>
        ` : ''}
      </td>
    </tr>
  `).join('');
  
  // Add event listeners to action buttons
  document.querySelectorAll('.view-booking').forEach(btn => {
    btn.addEventListener('click', (e) => viewBooking(e.target.closest('button').dataset.id));
  });
  
  document.querySelectorAll('.edit-booking').forEach(btn => {
    btn.addEventListener('click', (e) => editBooking(e.target.closest('button').dataset.id));
  });
  
  document.querySelectorAll('.cancel-booking').forEach(btn => {
    btn.addEventListener('click', (e) => confirmCancelBooking(e.target.closest('button').dataset.id));
  });
}

// Update pagination controls
function updatePagination() {
  const totalPages = Math.ceil(totalBookings / BOOKINGS_PER_PAGE);
  const currentPageEl = document.getElementById('current-page');
  const totalPagesEl = document.getElementById('total-pages');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  
  currentPageEl.textContent = currentBookingsPage;
  totalPagesEl.textContent = totalPages || 1;
  
  prevBtn.disabled = currentBookingsPage <= 1;
  nextBtn.disabled = currentBookingsPage >= totalPages;
  
  // Update event listeners
  prevBtn.onclick = () => loadBookings(currentBookingsPage - 1);
  nextBtn.onclick = () => loadBookings(currentBookingsPage + 1);
}

// Open booking modal for new booking
function openBookingModal(booking = null) {
  const modal = document.getElementById('booking-modal');
  const form = document.getElementById('booking-form');
  const title = document.getElementById('booking-modal-title');
  const idField = document.getElementById('booking-id');
  
  // Reset form
  form.reset();
  
  if (booking) {
    // Edit mode
    title.textContent = 'Edit Booking';
    idField.value = booking.id;
    document.getElementById('customer-name').value = booking.customer_name || '';
    document.getElementById('customer-phone').value = booking.customer_phone || '';
    document.getElementById('booking-date').value = formatDateForInput(booking.booking_time);
    document.getElementById('booking-time').value = formatTimeForInput(booking.booking_time);
    document.getElementById('party-size').value = booking.party_size || 2;
    document.getElementById('table-id').value = booking.table_id || '';
    document.getElementById('booking-notes').value = booking.notes || '';
  } else {
    // New booking mode
    title.textContent = 'New Booking';
    idField.value = '';
    // Set default party size to 2
    document.getElementById('party-size').value = 2;
    // Set default date to today
    document.getElementById('booking-date').value = new Date().toISOString().split('T')[0];
  }
  
  // Show modal
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
  
  // Focus on first input
  setTimeout(() => {
    const firstInput = form.querySelector('input:not([type="hidden"]), select');
    if (firstInput) firstInput.focus();
  }, 100);
}

// View booking details
function viewBooking(bookingId) {
  const booking = bookings.find(b => b.id === bookingId);
  if (!booking) return;
  
  // For now, just open in edit mode
  // In a real app, you might have a read-only view
  openBookingModal(booking);
  
  // Disable all form fields for view mode
  const form = document.getElementById('booking-form');
  const inputs = form.querySelectorAll('input, select, textarea, button');
  inputs.forEach(input => {
    if (input.id !== 'close-booking-modal') {
      input.disabled = true;
    }
  });
  
  // Change title and hide submit button
  document.getElementById('booking-modal-title').textContent = 'View Booking';
  document.getElementById('save-booking').style.display = 'none';
  document.getElementById('cancel-booking').textContent = 'Close';
}

// Edit booking
function editBooking(bookingId) {
  const booking = bookings.find(b => b.id === bookingId);
  if (!booking) return;
  
  openBookingModal(booking);
  
  // Ensure form is enabled
  const form = document.getElementById('booking-form');
  const inputs = form.querySelectorAll('input, select, textarea, button');
  inputs.forEach(input => {
    input.disabled = false;
  });
  
  // Update UI for edit mode
  document.getElementById('booking-modal-title').textContent = 'Edit Booking';
  document.getElementById('save-booking').style.display = 'block';
  document.getElementById('cancel-booking').textContent = 'Cancel';
}

// Confirm cancel booking
function confirmCancelBooking(bookingId) {
  if (confirm('Are you sure you want to cancel this booking?')) {
    cancelBooking(bookingId);
  }
}

// Cancel booking
async function cancelBooking(bookingId) {
  try {
    showLoading();
    
    const response = await fetch(`${window.API_BASE_URL}/bookings/${bookingId}/cancel`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) throw new Error('Failed to cancel booking');
    
    showNotification('Booking cancelled successfully', 'success');
    loadBookings(currentBookingsPage);
  } catch (error) {
    console.error('Error cancelling booking:', error);
    showNotification('Failed to cancel booking. Please try again.', 'error');
  } finally {
    hideLoading();
  }
}

// Save booking (create or update)
async function saveBooking(formData) {
  try {
    showLoading();
    
    const bookingData = {
      customer_name: formData.get('customer_name'),
      customer_phone: formData.get('customer_phone'),
      booking_time: `${formData.get('booking_date')}T${formData.get('booking_time')}:00`,
      party_size: parseInt(formData.get('party_size')),
      table_id: formData.get('table_id') || null,
      notes: formData.get('notes'),
      status: 'confirmed' // Default status
    };
    
    const bookingId = formData.get('booking_id');
    let response;
    
    if (bookingId) {
      // Update existing booking
      response = await fetch(`${window.API_BASE_URL}/bookings/${bookingId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(bookingData),
      });
    } else {
      // Create new booking
      response = await fetch(`${window.API_BASE_URL}/bookings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(bookingData),
      });
    }
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || 'Failed to save booking');
    }
    
    const result = await response.json();
    showNotification(
      bookingId ? 'Booking updated successfully' : 'Booking created successfully',
      'success'
    );
    
    // Close modal and refresh bookings list
    closeModal('booking-modal');
    loadBookings(bookingId ? currentBookingsPage : 1);
    
    return result;
  } catch (error) {
    console.error('Error saving booking:', error);
    showNotification(
      error.message || 'Failed to save booking. Please try again.',
      'error'
    );
    throw error;
  } finally {
    hideLoading();
  }
}

// Set up event listeners
function setupEventListeners() {
  // Navigation
  els.navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const page = link.getAttribute('data-page');
      if (page) navigateTo(page);
    });
  });
  
  // Bookings page event delegation
  document.addEventListener('click', (e) => {
    // New booking button
    if (e.target.closest('#new-booking-btn, #empty-new-booking')) {
      e.preventDefault();
      openBookingModal();
    }
    
    // Apply filters
    if (e.target.closest('#apply-filters')) {
      e.preventDefault();
      loadBookings(1); // Reset to first page when applying filters
    }
    
    // Reset filters
    if (e.target.closest('#reset-filters')) {
      e.preventDefault();
      document.getElementById('filter-status').value = '';
      document.getElementById('filter-date').value = new Date().toISOString().split('T')[0];
      document.getElementById('filter-party-size').value = '';
      document.getElementById('search-bookings').value = '';
      loadBookings(1);
    }
    
    // Close modal buttons
    if (e.target.closest('.close-modal, #cancel-booking, .modal')) {
      e.preventDefault();
      const modal = e.target.closest('.modal');
      if (modal) {
        closeModal(modal.id);
      }
    }
  });
  
  // Search input debounce
  let searchTimeout;
  const searchInput = document.getElementById('search-bookings');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        loadBookings(1);
      }, 500);
    });
  }
  
  // Booking form submission
  const bookingForm = document.getElementById('booking-form');
  if (bookingForm) {
    bookingForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      // Basic form validation
      const requiredFields = bookingForm.querySelectorAll('[required]');
      let isValid = true;
      
      requiredFields.forEach(field => {
        if (!field.value.trim()) {
          field.classList.add('error');
          isValid = false;
        } else {
          field.classList.remove('error');
        }
      });
      
      if (!isValid) {
        showNotification('Please fill in all required fields', 'error');
        return;
      }
      
      try {
        const formData = new FormData(bookingForm);
        await saveBooking(formData);
      } catch (error) {
        // Error handling is done in saveBooking
      }
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
      const modal = document.querySelector('.modal.active');
      if (e.target === modal) {
        closeModal(modal.id);
      }
    });
  }

  // Search
  if (els.searchInput) {
    els.searchInput.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') {
        const query = els.searchInput.value.trim();
        if (query) handleSearch(query);
      }
    });
  }

  // Notifications
  if (els.notificationsBtn) {
    els.notificationsBtn.addEventListener('click', showNotifications);
  }
  
  // Modal
  if (els.closeModal) {
    els.closeModal.addEventListener('click', () => {
      els.modal?.classList.remove('active');
    });
  }

  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === els.modal) {
      els.modal?.classList.remove('active');
    }
  });

  // Refresh button
  if (els.refreshBtn) {
    els.refreshBtn.addEventListener('click', () => {
      loadPage(currentPage, true);
    });
  }
}

// Handle search
function handleSearch(query) {
  console.log('Searching for:', query);
  // Implement search functionality
}

// Close a modal dialog
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
    
    // Reset form if it's the booking modal
    if (modalId === 'booking-modal') {
      const form = document.getElementById('booking-form');
      if (form) form.reset();
      
      // Re-enable all form fields in case they were disabled in view mode
      const inputs = form.querySelectorAll('input, select, textarea, button');
      inputs.forEach(input => {
        input.disabled = false;
      });
      
      // Reset UI elements
      document.getElementById('booking-modal-title').textContent = 'New Booking';
      const saveBtn = document.getElementById('save-booking');
      if (saveBtn) saveBtn.style.display = 'block';
      const cancelBtn = document.getElementById('cancel-booking');
      if (cancelBtn) cancelBtn.textContent = 'Cancel';
    }
  }
}

// Update current time
function updateCurrentTime() {
  if (els.currentTimeEl) {
    const now = new Date();
    els.currentTimeEl.textContent = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}

// Navigate to a specific page
async function navigateTo(page) {
  console.log(`Navigating to ${page}...`);
  
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => {
    p.style.display = 'none';
  });
  
  // Remove active class from all nav links
  els.navLinks.forEach(link => {
    link.classList.remove('active');
  });
  
  // Show the selected page and update active nav link
  const pageElement = document.getElementById(page);
  if (pageElement) {
    pageElement.style.display = 'block';
    currentPage = page;
    
    // Update active nav link
    const activeLink = document.querySelector(`[data-page="${page}"]`);
    if (activeLink) {
      activeLink.classList.add('active');
    }
    
    // Load page-specific data
    loadPage(page);
    
    // Initialize specific page components
    if (page === 'bookings') {
      // The loadBookings call is now handled in loadPage
      // This ensures the page is properly initialized before loading data
    }
  } else {
    console.error(`Page ${page} not found`);
  }
}

// Load page content
async function loadPage(page, forceRefresh = false) {
  showLoading();
  try {
    switch (page) {
      case 'dashboard':
        await loadDashboard(forceRefresh);
        break;
        
      case 'bookings':
        // Load the first page of bookings
        await loadBookings(1);
        break;
      case 'orders':
        await initOrdersPage();
        break;
      case 'tables':
        await loadTables(forceRefresh);
        break;
      case 'customers':
        await loadCustomers(forceRefresh);
        break;
      case 'analytics':
        await loadAnalytics(forceRefresh);
        break;
      case 'settings':
        await loadSettings(forceRefresh);
        break;
      case 'chat':
        // Chat is handled by app.js
        break;
    }
  } catch (error) {
    console.error(`Error loading ${page}:`, error);
    showError(`Failed to load ${page}. Please try again.`);
  } finally {
    hideLoading();
  }
}

// Dashboard
async function loadDashboard(forceRefresh = false) {
  try {
    const [overview, conversations, orders] = await Promise.all([
      fetchData('/dashboard/overview', forceRefresh),
      fetchData('/dashboard/conversations?limit=5', forceRefresh),
      fetchData('/dashboard/orders/live?limit=5', forceRefresh)
    ]);
    
    renderOverviewStats(overview);
    renderConversations(conversations);
    renderLiveOrders(orders);
  } catch (error) {
    console.error('Error loading dashboard:', error);
    showError('Failed to load dashboard. Please try again.');
  }
}

// Helper function to fetch data with caching
async function fetchData(endpoint, forceRefresh = false) {
  const cacheKey = `cache_${endpoint}`;
  
  // Return cached data if available and not forcing refresh
  if (!forceRefresh) {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        console.warn('Failed to parse cached data:', e);
      }
    }
  }

  // Fetch fresh data
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${endpoint}: ${res.statusText}`);
  }
  
  const data = await res.json();
  
  // Cache the response
  try {
    sessionStorage.setItem(cacheKey, JSON.stringify(data));
  } catch (e) {
    console.warn('Failed to cache data:', e);
  }
  
  return data;
}

// Render dashboard components
function renderOverviewStats(stats = {}) {
  if (!els.overviewStats) return;

  const statsData = [
    { 
      label: 'Total Revenue', 
      value: `$${stats.total_revenue?.toLocaleString() || '0'}`,
      trend: stats.revenue_trend,
      icon: 'dollar-sign'
    },
    { 
      label: 'Active Bookings', 
      value: stats.active_bookings?.toLocaleString() || '0',
      trend: stats.bookings_trend,
      icon: 'calendar-check'
    },
    { 
      label: 'Active Orders', 
      value: stats.active_orders?.toLocaleString() || '0',
      trend: stats.orders_trend,
      icon: 'utensils'
    },
    { 
      label: 'New Customers', 
      value: stats.new_customers?.toLocaleString() || '0',
      trend: stats.customers_trend,
      icon: 'users'
    }
  ];

  els.overviewStats.innerHTML = statsData.map(stat => `
    <div class="stat-item">
      <div class="stat-icon">
        <i class="fas fa-${stat.icon}"></i>
      </div>
      <div class="stat-content">
        <h3>${stat.label}</h3>
        <div class="value">${stat.value}</div>
        ${stat.trend !== undefined ? `
          <div class="trend ${stat.trend >= 0 ? 'up' : 'down'}">
            <i class="fas fa-arrow-${stat.trend >= 0 ? 'up' : 'down'}"></i>
            ${Math.abs(stat.trend)}%
          </div>
        ` : ''}
      </div>
    </div>
  `).join('');
}

function renderConversations(conversations = []) {
  if (!els.conversationsList) return;

  els.conversationsList.innerHTML = conversations.length ? conversations.map(conv => `
    <li class="conversation-item">
      <div class="conversation-header">
        <div class="customer-info">
          <span class="avatar">${(conv.customer_name || 'G')[0].toUpperCase()}</span>
          <span class="customer-name">${conv.customer_name || 'Guest'}</span>
        </div>
        <span class="time">${formatTime(conv.last_message_at)}</span>
      </div>
      <div class="message-preview">
        ${conv.last_message || 'No messages'}
      </div>
      <div class="conversation-actions">
        <button class="btn btn-sm btn-outline" onclick="handleViewConversation('${conv.id}')">
          <i class="fas fa-comment-alt"></i> View
        </button>
      </div>
    </li>
  `).join('') : `
    <li class="empty-state">
      <i class="fas fa-comments"></i>
      <p>No active conversations</p>
    </li>`;
}

function renderLiveOrders(orders = []) {
  if (!els.liveOrdersList) return;

  els.liveOrdersList.innerHTML = orders.length ? orders.map(order => `
    <li class="order-item">
      <div class="order-header">
        <div class="order-id">#${order.id}</div>
        <span class="status-badge status-${order.status?.toLowerCase()}">
          ${order.status || 'PENDING'}
        </span>
      </div>
      <div class="order-details">
        <div class="detail">
          <i class="fas fa-user"></i>
          <span>${order.customer_name || 'Walk-in'}</span>
        </div>
        <div class="detail">
          <i class="fas fa-utensils"></i>
          <span>${order.items?.length || 0} items</span>
        </div>
        <div class="detail">
          <i class="fas fa-receipt"></i>
          <span class="amount">$${order.total?.toFixed(2) || '0.00'}</span>
        </div>
      </div>
      <div class="order-actions">
        <button class="btn btn-sm btn-outline" onclick="handleViewOrder('${order.id}')">
          <i class="fas fa-eye"></i> View
        </button>
        ${order.status === 'PREPARING' ? `
          <button class="btn btn-sm btn-primary" onclick="handleOrderReady('${order.id}')">
            <i class="fas fa-check"></i> Ready
          </button>
        ` : ''}
      </div>
    </li>
  `).join('') : `
    <li class="empty-state">
      <i class="fas fa-utensils"></i>
      <p>No live orders</p>
    </li>`;
}

// Bookings Management
async function loadBookings(forceRefresh = false) {
  try {
    const [bookings, tables] = await Promise.all([
      fetchData('/bookings', forceRefresh),
      fetchData('/tables', forceRefresh)
    ]);
    
    renderBookings(bookings, tables);
    setupBookingEventListeners();
  } catch (error) {
    console.error('Error loading bookings:', error);
    showError('Failed to load bookings. Please try again.');
  }
}

function renderBookings(bookings = [], tables = []) {
  const container = document.getElementById('bookings');
  if (!container) return;

  container.innerHTML = `
    <div class="page-header">
      <h1>Bookings</h1>
      <div class="header-actions">
        <div class="search-bar">
          <i class="fas fa-search"></i>
          <input type="text" id="bookingSearch" placeholder="Search bookings...">
        </div>
        <button class="btn primary" id="newBookingBtn">
          <i class="fas fa-plus"></i> New Booking
        </button>
      </div>
    </div>
    
    <div class="bookings-filters">
      <div class="filter-group">
        <label for="bookingStatus">Status:</label>
        <select id="bookingStatus" class="form-select">
          <option value="">All Statuses</option>
          <option value="confirmed">Confirmed</option>
          <option value="seated">Seated</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>
      
      <div class="filter-group">
        <label for="bookingDate">Date:</label>
        <input type="date" id="bookingDate" class="form-input">
      </div>
      
      <button class="btn" id="applyFilters">Apply Filters</button>
      <button class="btn btn-outline" id="resetFilters">Reset</button>
    </div>
    
    <div class="table-responsive">
      <table class="bookings-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Customer</th>
            <th>Date & Time</th>
            <th>Guests</th>
            <th>Table</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="bookingsList">
          ${bookings.length ? '' : `
            <tr>
              <td colspan="7" class="empty-state">
                <i class="fas fa-calendar-alt"></i>
                <p>No bookings found</p>
              </td>
            </tr>
          `}
        </tbody>
      </table>
    </div>
    
    <div class="pagination">
      <button class="btn btn-outline" id="prevPage" disabled>Previous</button>
      <span class="page-info">Page 1 of 1</span>
      <button class="btn btn-outline" id="nextPage" disabled>Next</button>
    </div>
    
    <!-- Booking Modal -->
    <div id="bookingModal" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 id="bookingModalTitle">New Booking</h3>
          <button class="close-modal">&times;</button>
        </div>
        <div class="modal-body">
          <form id="bookingForm">
            <input type="hidden" id="bookingId">
            
            <div class="form-group">
              <label for="customerName">Customer Name *</label>
              <input type="text" id="customerName" class="form-input" required>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label for="customerEmail">Email</label>
                <input type="email" id="customerEmail" class="form-input">
              </div>
              <div class="form-group">
                <label for="customerPhone">Phone *</label>
                <input type="tel" id="customerPhone" class="form-input" required>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label for="bookingDateInput">Date *</label>
                <input type="date" id="bookingDateInput" class="form-input" required>
              </div>
              <div class="form-group">
                <label for="bookingTime">Time *</label>
                <input type="time" id="bookingTime" class="form-input" required>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label for="partySize">Party Size *</label>
                <select id="partySize" class="form-select" required>
                  ${Array.from({length: 20}, (_, i) => i + 1).map(n => 
                    `<option value="${n}">${n} ${n === 1 ? 'person' : 'people'}</option>`
                  ).join('')}
                </select>
              </div>
              <div class="form-group">
                <label for="tableId">Table</label>
                <select id="tableId" class="form-select">
                  <option value="">Auto-assign</option>
                  ${tables.map(table => 
                    `<option value="${table.id}">Table ${table.table_number} (${table.capacity} people)</option>`
                  ).join('')}
                </select>
              </div>
            </div>
            
            <div class="form-group">
              <label for="bookingNotes">Special Requests</label>
              <textarea id="bookingNotes" class="form-input" rows="3"></textarea>
            </div>
            
            <div class="form-actions">
              <button type="button" class="btn btn-outline" id="cancelBooking">Cancel</button>
              <button type="submit" class="btn primary" id="saveBooking">Save Booking</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  
  // Render bookings list
  const bookingsList = document.getElementById('bookingsList');
  if (bookingsList && bookings.length) {
    bookingsList.innerHTML = bookings.map(booking => `
      <tr data-booking-id="${booking.id}">
        <td>#${booking.id}</td>
        <td>
          <div class="customer-cell">
            <div class="customer-name">${booking.customer_name || 'Guest'}</div>
            <div class="customer-contact">${booking.customer_phone || ''}</div>
          </div>
        </td>
        <td>${formatDateTime(booking.booking_time)}</td>
        <td>${booking.party_size}</td>
        <td>${booking.table_number ? `Table ${booking.table_number}` : 'TBD'}</td>
        <td><span class="status-badge status-${booking.status}">${booking.status}</span></td>
        <td class="actions">
          <button class="btn-icon" onclick="handleViewBooking('${booking.id}')" title="View">
            <i class="fas fa-eye"></i>
          </button>
          <button class="btn-icon" onclick="handleEditBooking('${booking.id}')" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          ${booking.status !== 'cancelled' ? `
            <button class="btn-icon danger" onclick="handleCancelBooking('${booking.id}')" title="Cancel">
              <i class="fas fa-times"></i>
            </button>
          ` : ''}
        </td>
      </tr>
    `).join('');
  }
}

function setupBookingEventListeners() {
  // New booking button
  document.getElementById('newBookingBtn')?.addEventListener('click', () => {
    showBookingModal();
  });
  
  // Booking form submission
  document.getElementById('bookingForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await saveBooking();
  });
  
  // Cancel booking button
  document.getElementById('cancelBooking')?.addEventListener('click', () => {
    document.getElementById('bookingModal')?.classList.remove('active');
  });
  
  // Apply filters
  document.getElementById('applyFilters')?.addEventListener('click', () => {
    applyBookingFilters();
  });
  
  // Reset filters
  document.getElementById('resetFilters')?.addEventListener('click', () => {
    document.getElementById('bookingStatus').value = '';
    document.getElementById('bookingDate').value = '';
    applyBookingFilters();
  });
  
  // Search functionality
  const searchInput = document.getElementById('bookingSearch');
  let searchTimeout;
  
  searchInput?.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      applyBookingFilters();
    }, 300);
  });
}

async function showBookingModal(bookingId = null) {
  const modal = document.getElementById('bookingModal');
  const form = document.getElementById('bookingForm');
  const title = document.getElementById('bookingModalTitle');
  
  if (bookingId) {
    // Edit existing booking
    try {
      const booking = await fetchData(`/bookings/${bookingId}`);
      if (booking) {
        title.textContent = 'Edit Booking';
        populateBookingForm(booking);
      }
    } catch (error) {
      console.error('Error loading booking:', error);
      showError('Failed to load booking details.');
      return;
    }
  } else {
    // New booking
    title.textContent = 'New Booking';
    form.reset();
    document.getElementById('bookingId').value = '';
    // Set default time to next hour
    const now = new Date();
    const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
    document.getElementById('bookingDateInput').value = formatDateForInput(nextHour);
    document.getElementById('bookingTime').value = formatTimeForInput(nextHour);
  }
  
  modal.classList.add('active');
}

function populateBookingForm(booking) {
  if (!booking) return;
  
  const date = new Date(booking.booking_time);
  
  document.getElementById('bookingId').value = booking.id;
  document.getElementById('customerName').value = booking.customer_name || '';
  document.getElementById('customerEmail').value = booking.customer_email || '';
  document.getElementById('customerPhone').value = booking.customer_phone || '';
  document.getElementById('bookingDateInput').value = formatDateForInput(date);
  document.getElementById('bookingTime').value = formatTimeForInput(date);
  document.getElementById('partySize').value = booking.party_size || 2;
  document.getElementById('tableId').value = booking.table_id || '';
  document.getElementById('bookingNotes').value = booking.notes || '';
}

async function saveBooking() {
  const form = document.getElementById('bookingForm');
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  
  const bookingData = {
    id: document.getElementById('bookingId').value || undefined,
    customer_name: document.getElementById('customerName').value,
    customer_email: document.getElementById('customerEmail').value,
    customer_phone: document.getElementById('customerPhone').value,
    booking_time: `${document.getElementById('bookingDateInput').value}T${document.getElementById('bookingTime').value}`,
    party_size: parseInt(document.getElementById('partySize').value),
    table_id: document.getElementById('tableId').value || null,
    notes: document.getElementById('bookingNotes').value
  };
  
  try {
    showLoading();
    const method = bookingData.id ? 'PUT' : 'POST';
    const url = bookingData.id 
      ? `${API_BASE}/bookings/${bookingData.id}`
      : `${API_BASE}/bookings`;
    
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookingData)
    });
    
    if (!response.ok) {
      throw new Error('Failed to save booking');
    }
    
    document.getElementById('bookingModal').classList.remove('active');
    loadBookings(true); // Refresh the list
    showNotification('Booking saved successfully!', 'success');
  } catch (error) {
    console.error('Error saving booking:', error);
    showError('Failed to save booking. Please try again.');
  } finally {
    hideLoading();
  }
}

async function applyBookingFilters() {
  const status = document.getElementById('bookingStatus').value;
  const date = document.getElementById('bookingDate').value;
  const search = document.getElementById('bookingSearch').value.toLowerCase();
  
  try {
    showLoading();
    let url = '/bookings?';
    const params = new URLSearchParams();
    
    if (status) params.append('status', status);
    if (date) params.append('date', date);
    if (search) params.append('search', search);
    
    const response = await fetch(`${API_BASE}${url}${params.toString()}`);
    if (!response.ok) throw new Error('Failed to fetch filtered bookings');
    
    const bookings = await response.json();
    renderBookings(bookings);
  } catch (error) {
    console.error('Error applying filters:', error);
    showError('Failed to apply filters. Please try again.');
  } finally {
    hideLoading();
  }
}

// Global handlers for booking actions
window.handleViewBooking = (bookingId) => {
  // Implement view booking details
  console.log('View booking:', bookingId);
};

window.handleEditBooking = (bookingId) => {
  showBookingModal(bookingId);
};

window.handleCancelBooking = async (bookingId) => {
  if (!confirm('Are you sure you want to cancel this booking?')) return;
  
  try {
    showLoading();
    const response = await fetch(`${API_BASE}/bookings/${bookingId}/cancel`, {
      method: 'POST'
    });
    
    if (!response.ok) throw new Error('Failed to cancel booking');
    
    loadBookings(true); // Refresh the list
    showNotification('Booking cancelled successfully!', 'success');
  } catch (error) {
    console.error('Error cancelling booking:', error);
    showError('Failed to cancel booking. Please try again.');
  } finally {
    hideLoading();
  }
};

// Orders Management State
let orders = [];
let menuItems = [];
let currentOrdersPage = 1;
const ORDERS_PER_PAGE = 10;
let totalOrders = 0;

// Initialize Orders Page
function initOrdersPage() {
  console.log('Initializing orders page...');
  loadOrders();
  loadMenuItems();
  setupOrdersEventListeners();
}

// Load orders with filters
async function loadOrders(page = 1, forceRefresh = false) {
  try {
    showLoading();
    currentOrdersPage = page;
    
    // Get filter values
    const status = document.getElementById('order-status')?.value || '';
    const orderType = document.getElementById('order-type')?.value || '';
    const date = document.getElementById('order-date')?.value || '';
    const searchQuery = document.getElementById('search-orders')?.value.trim() || '';
    
    // Build query params
    const params = new URLSearchParams({
      page,
      limit: ORDERS_PER_PAGE,
      ...(status && { status }),
      ...(orderType && { type: orderType }),
      ...(date && { date }),
      ...(searchQuery && { q: searchQuery })
    });
    
    const response = await fetch(`${API_BASE}/orders?${params}`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (!response.ok) throw new Error('Failed to load orders');
    
    const data = await response.json();
    orders = data.items || [];
    totalOrders = data.total || 0;
    
    renderOrders();
    updateOrdersPagination();
  } catch (error) {
    console.error('Error loading orders:', error);
    showNotification('Failed to load orders', 'error');
  } finally {
    hideLoading();
  }
}

async function loadTables(forceRefresh = false) {
  // Implement tables page loading
  console.log('Loading tables...');
}

// Load menu items for order form
async function loadMenuItems() {
  try {
    const response = await fetch(`${API_BASE}/menu/items`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (!response.ok) throw new Error('Failed to load menu items');
    
    const data = await response.json();
    menuItems = data.items || [];
  } catch (error) {
    console.error('Error loading menu items:', error);
    showNotification('Failed to load menu items', 'error');
  }
}

// Render orders in the table
function renderOrders() {
  const tbody = document.getElementById('orders-tbody');
  
  if (!orders.length) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="8" class="empty-state">
          <i class="fas fa-receipt"></i>
          <h3>No orders found</h3>
          <p>Create your first order to get started</p>
          <button class="btn btn-primary mt-2" id="empty-new-order">
            <i class="fas fa-plus"></i> New Order
          </button>
        </td>
      </tr>
    `;
    return;
  }
  
  tbody.innerHTML = orders.map(order => `
    <tr>
      <td>#${order.id}</td>
      <td>${order.customer?.name || 'Walk-in Customer'}</td>
      <td>${order.items.length} items</td>
      <td>$${order.total.toFixed(2)}</td>
      <td><span class="type-badge type-${order.type}">${order.type}</span></td>
      <td><span class="status-badge status-${order.status}">${order.status}</span></td>
      <td>${formatDateTime(order.created_at)}</td>
      <td class="actions">
        <button class="btn-action" onclick="handleViewOrder('${order.id}')" title="View">
          <i class="fas fa-eye"></i>
        </button>
        ${order.status === 'pending' || order.status === 'preparing' ? `
          <button class="btn-action" onclick="handleEditOrder('${order.id}')" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button class="btn-action danger" onclick="handleCancelOrder('${order.id}')" title="Cancel">
            <i class="fas fa-times"></i>
          </button>
        ` : ''}
        ${order.status === 'ready' ? `
          <button class="btn-action success" onclick="handleMarkAsServed('${order.id}')" title="Mark as Served">
            <i class="fas fa-check"></i>
          </button>
        ` : ''}
      </td>
    </tr>
  `).join('');
}

// Update orders pagination
function updateOrdersPagination() {
  const totalPages = Math.ceil(totalOrders / ORDERS_PER_PAGE);
  const prevBtn = document.getElementById('orders-prev-page');
  const nextBtn = document.getElementById('orders-next-page');
  const currentPageEl = document.getElementById('orders-current-page');
  const totalPagesEl = document.getElementById('orders-total-pages');
  
  if (currentPageEl) currentPageEl.textContent = currentOrdersPage;
  if (totalPagesEl) totalPagesEl.textContent = totalPages || 1;
  
  if (prevBtn) prevBtn.disabled = currentOrdersPage <= 1;
  if (nextBtn) nextBtn.disabled = currentOrdersPage >= totalPages;
}

// Open order modal for new order
function openOrderModal(order = null) {
  const modal = document.getElementById('order-modal');
  const title = document.getElementById('order-modal-title');
  const form = document.getElementById('order-form');
  const orderIdInput = document.getElementById('order-id');
  
  // Reset form
  if (form) form.reset();
  
  if (order) {
    // Edit existing order
    if (title) title.textContent = `Order #${order.id}`;
    if (orderIdInput) orderIdInput.value = order.id;
    populateOrderForm(order);
  } else {
    // New order
    if (title) title.textContent = 'New Order';
    if (orderIdInput) orderIdInput.value = '';
    resetOrderForm();
  }
  
  // Show modal
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Focus first input
    setTimeout(() => {
      const firstInput = form?.querySelector('input, select, textarea');
      if (firstInput) firstInput.focus();
    }, 100);
  }
}

// Populate order form with data
function populateOrderForm(order) {
  if (!order) return;
  
  const customerSelect = document.getElementById('order-customer');
  const typeSelect = document.getElementById('order-type-select');
  const tableSelect = document.getElementById('order-table');
  const notesInput = document.getElementById('order-notes');
  
  if (customerSelect) customerSelect.value = order.customer_id || '';
  if (typeSelect) typeSelect.value = order.type;
  if (tableSelect) tableSelect.value = order.table_id || '';
  if (notesInput) notesInput.value = order.notes || '';
  
  // Populate order items
  const itemsContainer = document.getElementById('order-items-list');
  if (itemsContainer) {
    itemsContainer.innerHTML = (order.items || []).map((item, index) => `
      <div class="order-item-row" data-index="${index}">
        <div>
          <label>Item</label>
          <select class="form-select item-select" name="items[${index}][menu_item_id]" required>
            <option value="">Select an item</option>
            ${menuItems.map(menuItem => `
              <option value="${menuItem.id}" 
                      ${item.menu_item_id === menuItem.id ? 'selected' : ''}
                      data-price="${menuItem.price}">
                ${menuItem.name} ($${menuItem.price.toFixed(2)})
              </option>
            `).join('')}
          </select>
        </div>
        <div>
          <label>Quantity</label>
          <input type="number" class="form-input" name="items[${index}][quantity]" 
                 min="1" value="${item.quantity || 1}" required>
        </div>
        <div>
          <label>Special Instructions</label>
          <input type="text" class="form-input" name="items[${index}][notes]" 
                 value="${item.notes || ''}" placeholder="e.g. No onions">
        </div>
        <button type="button" class="btn-action danger remove-item" title="Remove item">
          <i class="fas fa-times"></i>
        </button>
      </div>
    `).join('');
    
    // Update order total
    updateOrderTotal();
  }
}

// Reset order form
function resetOrderForm() {
  const itemsContainer = document.getElementById('order-items-list');
  if (itemsContainer) {
    itemsContainer.innerHTML = '';
    updateOrderTotal();
  }
}

// Update order total based on selected items
function updateOrderTotal() {
  let subtotal = 0;
  
  document.querySelectorAll('.order-item-row').forEach(row => {
    const select = row.querySelector('.item-select');
    const quantity = parseFloat(row.querySelector('input[type="number"]')?.value) || 0;
    const price = parseFloat(select?.selectedOptions[0]?.dataset.price) || 0;
    subtotal += price * quantity;
  });
  
  const tax = subtotal * 0.1; // 10% tax
  const total = subtotal + tax;
  
  const subtotalEl = document.getElementById('order-subtotal');
  const taxEl = document.getElementById('order-tax');
  const totalEl = document.getElementById('order-total');
  
  if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
  if (taxEl) taxEl.textContent = `$${tax.toFixed(2)}`;
  if (totalEl) totalEl.textContent = `$${total.toFixed(2)}`;
}

// Save order (create or update)
async function saveOrder(event) {
  if (event) event.preventDefault();
  
  const form = document.getElementById('order-form');
  if (!form) return;
  
  const formData = new FormData(form);
  const orderId = formData.get('id');
  const isNew = !orderId;
  
  try {
    showLoading();
    
    // Prepare order data
    const orderData = {
      customer_id: formData.get('customer_id') || null,
      type: formData.get('type'),
      table_id: formData.get('table_id') || null,
      notes: formData.get('notes'),
      items: []
    };
    
    // Get order items
    const itemCount = document.querySelectorAll('.order-item-row').length;
    for (let i = 0; i < itemCount; i++) {
      orderData.items.push({
        menu_item_id: formData.get(`items[${i}][menu_item_id]`),
        quantity: parseInt(formData.get(`items[${i}][quantity]`), 10) || 1,
        notes: formData.get(`items[${i}][notes]`) || ''
      });
    }
    
    // Validate order
    if (!orderData.items.length) {
      throw new Error('Please add at least one item to the order');
    }
    
    // Make API request
    const url = isNew ? `${API_BASE}/orders` : `${API_BASE}/orders/${orderId}`;
    const method = isNew ? 'POST' : 'PUT';
    
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(orderData)
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || 'Failed to save order');
    }
    
    // Close modal and refresh orders list
    closeModal('order-modal');
    loadOrders(currentOrdersPage);
    showNotification(`Order ${isNew ? 'created' : 'updated'} successfully`, 'success');
    
  } catch (error) {
    console.error('Error saving order:', error);
    showNotification(error.message || 'Failed to save order', 'error');
  } finally {
    hideLoading();
  }
}

// Handle view order
window.handleViewOrder = async (orderId) => {
  try {
    showLoading();
    
    const response = await fetch(`${API_BASE}/orders/${orderId}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (!response.ok) throw new Error('Failed to load order details');
    
    const order = await response.json();
    openOrderModal(order);
    
    // Disable form fields in view mode
    const form = document.getElementById('order-form');
    if (form) {
      const inputs = form.querySelectorAll('input, select, textarea, button');
      inputs.forEach(input => {
        input.disabled = true;
      });
    }
    
    // Hide save buttons
    const saveDraftBtn = document.getElementById('save-draft');
    const placeOrderBtn = document.getElementById('place-order');
    if (saveDraftBtn) saveDraftBtn.style.display = 'none';
    if (placeOrderBtn) placeOrderBtn.style.display = 'none';
    
  } catch (error) {
    console.error('Error viewing order:', error);
    showNotification('Failed to load order details', 'error');
  } finally {
    hideLoading();
  }
};

// Handle edit order
window.handleEditOrder = (orderId) => {
  // Just open the modal, it will handle loading the order data
  handleViewOrder(orderId);
  
  // Re-enable form fields
  const form = document.getElementById('order-form');
  if (form) {
    const inputs = form.querySelectorAll('input, select, textarea, button');
    inputs.forEach(input => {
      input.disabled = false;
    });
  }
  
  // Show save buttons
  const saveDraftBtn = document.getElementById('save-draft');
  const placeOrderBtn = document.getElementById('place-order');
  if (saveDraftBtn) saveDraftBtn.style.display = 'inline-block';
  if (placeOrderBtn) placeOrderBtn.style.display = 'inline-block';
  
  // Update title
  const title = document.getElementById('order-modal-title');
  if (title) title.textContent = `Edit Order #${orderId}`;
};

// Handle cancel order
window.handleCancelOrder = async (orderId) => {
  if (!confirm('Are you sure you want to cancel this order? This action cannot be undone.')) {
    return;
  }
  
  try {
    showLoading();
    
    const response = await fetch(`${API_BASE}/orders/${orderId}/cancel`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (!response.ok) throw new Error('Failed to cancel order');
    
    // Refresh orders list
    loadOrders(currentOrdersPage);
    showNotification('Order cancelled successfully', 'success');
    
  } catch (error) {
    console.error('Error cancelling order:', error);
    showNotification(error.message || 'Failed to cancel order', 'error');
  } finally {
    hideLoading();
  }
};

// Handle mark as served
window.handleMarkAsServed = async (orderId) => {
  try {
    showLoading();
    
    const response = await fetch(`${API_BASE}/orders/${orderId}/serve`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (!response.ok) throw new Error('Failed to update order status');
    
    // Refresh orders list
    loadOrders(currentOrdersPage);
    showNotification('Order marked as served', 'success');
    
  } catch (error) {
    console.error('Error updating order status:', error);
    showNotification(error.message || 'Failed to update order status', 'error');
  } finally {
    hideLoading();
  }
};

// Add new order item row
function addOrderItem() {
  const container = document.getElementById('order-items-list');
  if (!container) return;
  
  const index = container.children.length;
  
  const row = document.createElement('div');
  row.className = 'order-item-row';
  row.dataset.index = index;
  
  row.innerHTML = `
    <div>
      <label>Item <span class="required">*</span></label>
      <select class="form-select item-select" name="items[${index}][menu_item_id]" required>
        <option value="">Select an item</option>
        ${menuItems.map(item => `
          <option value="${item.id}" data-price="${item.price}">
            ${item.name} ($${item.price.toFixed(2)})
          </option>
        `).join('')}
      </select>
    </div>
    <div>
      <label>Quantity <span class="required">*</span></label>
      <input type="number" class="form-input" name="items[${index}][quantity]" 
             min="1" value="1" required>
    </div>
    <div>
      <label>Special Instructions</label>
      <input type="text" class="form-input" name="items[${index}][notes]" 
             placeholder="e.g. No onions">
    </div>
    <button type="button" class="btn-action danger remove-item" title="Remove item">
      <i class="fas fa-times"></i>
    </button>
  `;
  
  container.appendChild(row);
  
  // Focus the new select element
  const select = row.querySelector('select');
  if (select) select.focus();
}

// Setup event listeners for orders page
function setupOrdersEventListeners() {
  // New order button
  const newOrderBtn = document.getElementById('new-order-btn');
  const emptyNewOrderBtn = document.getElementById('empty-new-order');
  const orderForm = document.getElementById('order-form');
  const closeOrderModalBtn = document.getElementById('close-order-modal');
  const cancelOrderBtn = document.getElementById('cancel-order');
  const addItemBtn = document.getElementById('add-order-item');
  const orderItemsList = document.getElementById('order-items-list');
  const orderTypeSelect = document.getElementById('order-type-select');
  const tableSelectionGroup = document.getElementById('table-selection-group');
  const prevPageBtn = document.getElementById('orders-prev-page');
  const nextPageBtn = document.getElementById('orders-next-page');
  const applyFiltersBtn = document.getElementById('apply-order-filters');
  const resetFiltersBtn = document.getElementById('reset-order-filters');
  const searchOrdersInput = document.getElementById('search-orders');
  
  // New order buttons
  if (newOrderBtn) newOrderBtn.addEventListener('click', () => openOrderModal());
  if (emptyNewOrderBtn) emptyNewOrderBtn.addEventListener('click', () => openOrderModal());
  
  // Order form submission
  if (orderForm) orderForm.addEventListener('submit', saveOrder);
  
  // Close modal buttons
  if (closeOrderModalBtn) closeOrderModalBtn.addEventListener('click', () => closeModal('order-modal'));
  if (cancelOrderBtn) cancelOrderBtn.addEventListener('click', () => closeModal('order-modal'));
  
  // Add item button
  if (addItemBtn) addItemBtn.addEventListener('click', addOrderItem);
  
  // Remove item button (delegated)
  if (orderItemsList) {
    orderItemsList.addEventListener('click', (e) => {
      if (e.target.closest('.remove-item') || e.target.classList.contains('remove-item')) {
        e.preventDefault();
        const row = e.target.closest('.order-item-row');
        if (row) {
          row.remove();
          updateOrderTotal();
        }
      }
    });
    
    // Update total when item or quantity changes
    orderItemsList.addEventListener('change', (e) => {
      if (e.target.matches('.item-select, input[type="number"]')) {
        updateOrderTotal();
      }
    });
  }
  
  // Order type change
  if (orderTypeSelect && tableSelectionGroup) {
    orderTypeSelect.addEventListener('change', (e) => {
      tableSelectionGroup.style.display = e.target.value === 'dine-in' ? 'block' : 'none';
    });
    
    // Initial state
    tableSelectionGroup.style.display = orderTypeSelect.value === 'dine-in' ? 'block' : 'none';
  }
  
  // Pagination
  if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => {
      if (currentOrdersPage > 1) {
        loadOrders(currentOrdersPage - 1);
      }
    });
  }
  
  if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => {
      const totalPages = Math.ceil(totalOrders / ORDERS_PER_PAGE);
      if (currentOrdersPage < totalPages) {
        loadOrders(currentOrdersPage + 1);
      }
    });
  }
  
  // Apply filters
  if (applyFiltersBtn) {
    applyFiltersBtn.addEventListener('click', () => {
      loadOrders(1);
    });
  }
  
  // Reset filters
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', () => {
      const statusSelect = document.getElementById('order-status');
      const typeSelect = document.getElementById('order-type');
      const dateInput = document.getElementById('order-date');
      
      if (statusSelect) statusSelect.value = '';
      if (typeSelect) typeSelect.value = '';
      if (dateInput) dateInput.value = '';
      if (searchOrdersInput) searchOrdersInput.value = '';
      
      loadOrders(1);
    });
  }
  
  // Search input with debounce
  if (searchOrdersInput) {
    let searchTimeout;
    searchOrdersInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        loadOrders(1);
      }, 500);
    });
  }
}

// Initialize orders page when navigating to it
function loadCustomers(forceRefresh = false) {
  // Implement customers page loading
  console.log('Loading customers...');
}

async function loadAnalytics(forceRefresh = false) {
  // Implement analytics page loading
  console.log('Loading analytics...');
}

async function loadSettings(forceRefresh = false) {
  // Implement settings page loading
  console.log('Loading settings...');
}

// Notifications
async function loadNotifications() {
  try {
    const response = await fetch(`${API_BASE}/notifications`);
    if (response.ok) {
      notifications = await response.json();
      updateNotificationBadge(notifications.length);
    }
  } catch (error) {
    console.error('Error loading notifications:', error);
  }
}

function updateNotificationBadge(count) {
  const badge = document.querySelector('.notifications .badge');
  if (badge) {
    badge.textContent = count > 0 ? (count > 9 ? '9+' : count) : '';
    badge.style.display = count > 0 ? 'flex' : 'none';
  }
}

function showNotifications() {
  // Implement notifications dropdown/modal
  console.log('Showing notifications');
}

// Utility functions
function formatDateForInput(date) {
  if (!date) return '';
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatTimeForInput(date) {
  if (!date) return '';
  const d = new Date(date);
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.innerHTML = `
    <div class="notification-content">
      <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
      <span>${message}</span>
    </div>
    <button class="notification-close">&times;</button>
  `;
  
  notification.querySelector('.notification-close').addEventListener('click', () => {
    notification.remove();
  });
  
  document.body.appendChild(notification);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    notification.classList.add('fade-out');
    setTimeout(() => notification.remove(), 300);
  }, 5000);
}

function showLoading() {
  if (els.loadingOverlay) {
    els.loadingOverlay.classList.add('active');
  }
}

function hideLoading() {
  if (els.loadingOverlay) {
    els.loadingOverlay.classList.remove('active');
  }
}

function showError(message) {
  // Implement error toast/notification
  console.error('Error:', message);
  alert(message); // Temporary - replace with a proper toast/notification
}

function formatTime(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString();
}

// Handle window resize for responsive design
function handleResize() {
  // Add responsive behavior here if needed
}

// Event handlers for global actions
window.handleViewOrder = (orderId) => {
  console.log('View order:', orderId);
  // Implement view order modal
};

window.handleOrderReady = (orderId) => {
  console.log('Mark order as ready:', orderId);
  // Implement order ready functionality
};

window.handleViewConversation = (conversationId) => {
  console.log('View conversation:', conversationId);
  // Navigate to chat page and load conversation
  navigateTo('chat');
  // Additional logic to load specific conversation in chat
};

// Expose initializer for index.html to call
window.initDashboard = initDashboard;

// Handle window resize
window.addEventListener('resize', handleResize);
})();
