(function(){
  // Auth module
  window.X7Auth = {
    // Get auth data from localStorage
    getAuth: function() {
      try {
        const authData = localStorage.getItem('x7_auth');
        return authData ? JSON.parse(authData) : null;
      } catch (e) {
        console.error('Failed to get auth data:', e);
        return null;
      }
    },
    
    // Set auth data in localStorage
    setAuth: function(data) {
      try {
        localStorage.setItem('x7_auth', JSON.stringify(data));
      } catch (e) {
        console.error('Failed to set auth data:', e);
      }
    },
    
    // Get profile data from localStorage
    getProfile: function() {
      try {
        const profileData = localStorage.getItem('x7_profile');
        return profileData ? JSON.parse(profileData) : null;
      } catch (e) {
        console.error('Failed to get profile data:', e);
        return null;
      }
    },
    
    // Set profile data in localStorage
    setProfile: function(data) {
      try {
        localStorage.setItem('x7_profile', JSON.stringify(data));
      } catch (e) {
        console.error('Failed to set profile data:', e);
      }
    },
    
    // Clear auth and profile data
    clearAuth: function() {
      try {
        localStorage.removeItem('x7_auth');
        localStorage.removeItem('x7_profile');
      } catch (e) {
        console.error('Failed to clear auth data:', e);
      }
    },
    
    // Check if user is logged in
    isLoggedIn: function() {
      const auth = this.getAuth();
      return !!auth && !!auth.token;
    }
  };

  // Authentication logic
  const API_BASE = 'http://localhost:8000/api/v1';
  const form = document.getElementById('authForm');
  const tabs = document.querySelectorAll('.auth-tab');
  const businessNameField = document.getElementById('businessNameField');
  const confirmPasswordField = document.getElementById('confirmPasswordField');
  const errorEl = document.getElementById('authError');
  
  let mode = 'login'; // Default mode
  
  // Tab switching
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      mode = tab.dataset.mode;
      
      // Show/hide signup-specific fields
      businessNameField.style.display = mode === 'signup' ? 'block' : 'none';
      confirmPasswordField.style.display = mode === 'signup' ? 'block' : 'none';
      
      // Clear errors
      if (errorEl) errorEl.style.display = 'none';
    });
  });
  
  // Form submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form values
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const businessName = document.getElementById('businessName').value.trim();
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    // Validation
    if (!email || !password) {
      showError('Please fill in all required fields.');
      return;
    }
    
    if (mode === 'signup') {
      if (!businessName) {
        showError('Business name is required.');
        return;
      }
      
      if (password !== confirmPassword) {
        showError('Passwords do not match.');
        return;
      }
      
      // Register new business
      await registerBusiness(businessName, email, password);
    } else {
      // Login
      await loginUser(email, password);
    }
  });
  
  // Register a new business
  async function registerBusiness(businessName, email, password) {
    try {
      console.log('Attempting registration with API_BASE:', API_BASE);
      const url = `${API_BASE}/auth/register`;
      console.log('Registration URL:', url);
      
      const payload = {
        business_name: businessName,
        business_slug: businessName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
        admin_name: email.split('@')[0],
        admin_email: email,
        admin_password: password,
      };
      
      console.log('Sending registration request with payload:', payload);
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      console.log('Registration response status:', response.status);
      console.log('Registration response headers:', response.headers);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Registration error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Registration successful, data:', data);
      
      // Save auth data
      X7Auth.setAuth({
        token: data.access_token,
        refreshToken: data.refresh_token,
        email: email,
        businessId: data.business_id,
        userRole: data.user_role,
        createdAt: Date.now()
      });
      
      // Save basic profile
      X7Auth.setProfile({
        businessName: businessName,
        accountEmail: email
      });
      
      // Redirect to dashboard
      window.location.href = 'dashboard.html';
    } catch (error) {
      console.error('Registration error:', error);
      showError(error.message);
    }
  }
  
  // Login user
  async function loginUser(email, password) {
    try {
      console.log('Attempting login with API_BASE:', API_BASE);
      const url = `${API_BASE}/auth/login`;
      console.log('Login URL:', url);
      
      const formBody = new URLSearchParams();
      formBody.append('username', email);
      formBody.append('password', password);
      
      console.log('Sending login request...');
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formBody,
      });
      
      console.log('Login response status:', response.status);
      console.log('Login response headers:', response.headers);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Login error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Login successful, data:', data);
      
      // Save auth data
      X7Auth.setAuth({
        token: data.access_token,
        refreshToken: data.refresh_token,
        email: email,
        businessId: data.business_id,
        userRole: data.user_role,
        createdAt: Date.now()
      });
      
      // Ensure we have at least a minimal profile
      const existingProfile = X7Auth.getProfile() || {};
      if (!existingProfile.accountEmail) {
        X7Auth.setProfile({
          ...existingProfile,
          accountEmail: email
        });
      }
      
      // Redirect to dashboard
      window.location.href = 'dashboard.html';
    } catch (error) {
      showError(error.message);
    }
  }
  
  // Show error message
  function showError(message) {
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';
    }
  }
  
  // Check if already authenticated
  document.addEventListener('DOMContentLoaded', () => {
    if (X7Auth.isLoggedIn()) {
      window.location.href = 'dashboard.html';
    }
  });
})();
