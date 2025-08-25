(function(){
  const form = document.getElementById('authForm');
  const tabs = Array.from(document.querySelectorAll('.auth-tab'));
  const businessNameRow = document.querySelector('[data-for="businessName"]');
  const slugNameRow = document.querySelector('[data-for="slugName"]');
  const googleUrlRow = document.querySelector('[data-for="googleUrl"]');
  const locationLinkRow = document.querySelector('[data-for="locationLink"]');
  const categoryRow = document.querySelector('[data-for="category"]');
  const confirmPasswordRow = document.querySelector('[data-for="confirmPassword"]');
  const errorEl = document.getElementById('authError');

  let mode = 'login';

  function mapCategoryToEnum(label) {
    if (!label) return undefined;
    const v = String(label).toLowerCase();
    if (v.includes('restaurant') || v.includes('food') || v.includes('cafe')) return 'food_hospitality';
    if (v.includes('health')) return 'health_medical';
    if (v.includes('beauty') || v.includes('salon') || v.includes('spa')) return 'beauty_personal_care';
    if (v.includes('auto') || v.includes('car')) return 'automotive_services';
    // Retail, Services, E-commerce -> default to local services
    return 'local_services';
  }

  function setSignupVisibility(isSignup) {
    const disp = isSignup ? '' : 'none';
    if (businessNameRow) businessNameRow.style.display = disp;
    if (slugNameRow) slugNameRow.style.display = disp;
    if (googleUrlRow) googleUrlRow.style.display = disp;
    if (locationLinkRow) locationLinkRow.style.display = disp;
    if (categoryRow) categoryRow.style.display = disp;
    if (confirmPasswordRow) confirmPasswordRow.style.display = disp;
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      mode = tab.dataset.mode;
      setSignupVisibility(mode === 'signup');
      if (errorEl) errorEl.style.display = 'none';
    });
  });

  function uuid() {
    try { return crypto.randomUUID(); } catch { return 'tok_' + Math.random().toString(36).slice(2); }
  }

  function isProfileComplete(profile) {
    if (!profile || !profile.businessName) return false;
    const otherKeys = ['website','industry','timezone','contactEmail','contactPhone','hours','welcome','logoDataUrl'];
    return otherKeys.some(k => {
      const v = profile[k];
      return typeof v === 'string' ? v.trim().length > 0 : !!v;
    });
  }

  function redirectAfterAuth() {
    const profile = X7Auth.getProfile();
    if (!profile || !profile.subscriptionPlan) {
      window.location.href = 'subscription.html';
      return;
    }
    if (!isProfileComplete(profile)) {
      window.location.href = 'onboarding.html';
    } else {
      window.location.href = 'dashboard.html';
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const businessName = document.getElementById('businessName')?.value.trim() || '';
    const slugName = document.getElementById('slugName')?.value.trim() || '';
    const googleUrl = document.getElementById('googleUrl')?.value.trim() || '';
    const locationLink = document.getElementById('locationLink')?.value.trim() || '';
    const category = document.getElementById('category')?.value || '';
    const confirmPassword = document.getElementById('confirmPassword')?.value || '';

    if (!email || !password || (mode === 'signup' && (!businessName || !slugName || !locationLink || !category))) {
      errorEl.textContent = 'Please fill all required fields.';
      errorEl.style.display = 'block';
      return;
    }
    if (mode === 'signup' && password !== confirmPassword) {
      errorEl.textContent = 'Passwords do not match.';
      errorEl.style.display = 'block';
      return;
    }

    try {
      if (mode === 'signup') {
        // Call backend to register business and admin user
        const payload = {
          business_name: businessName,
          business_slug: slugName,
          admin_name: businessName || (email.split('@')[0] || 'Owner'),
          admin_email: email,
          admin_password: password,
          admin_phone: null,
          business_category: mapCategoryToEnum(category)
        };
        const resp = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) {
          let msg = 'Registration failed.';
          try { const data = await resp.json(); msg = data.detail || JSON.stringify(data); } catch {}
          throw new Error(msg);
        }
        const data = await resp.json();
        // Persist auth and profile
        X7Auth.setAuth({
          token: data.access_token,
          email,
          businessId: data.business_id,
          userRole: data.user_role,
          createdAt: Date.now(),
        });
        try { localStorage.setItem('x7_business_id', String(data.business_id)); } catch {}
        const existing = X7Auth.getProfile() || {};
        X7Auth.setProfile({
          ...existing,
          businessName,
          slugName,
          googleUrl,
          locationLink,
          category,
          accountEmail: email,
          createdAt: Date.now(),
        });
        // Proceed to subscription selection
        window.location.href = 'subscription.html';
      } else {
        // Login via backend
        const formBody = new URLSearchParams();
        formBody.set('username', email);
        formBody.set('password', password);
        const resp = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formBody
        });
        if (!resp.ok) {
          let msg = 'Login failed.';
          try { const data = await resp.json(); msg = data.detail || JSON.stringify(data); } catch {}
          throw new Error(msg);
        }
        const data = await resp.json();
        X7Auth.setAuth({
          token: data.access_token,
          email,
          businessId: data.business_id,
          userRole: data.user_role,
          createdAt: Date.now(),
        });
        try { localStorage.setItem('x7_business_id', String(data.business_id)); } catch {}
        // Ensure we have at least a minimal profile so redirects work
        const existing = X7Auth.getProfile() || {};
        if (!existing || !existing.accountEmail) {
          X7Auth.setProfile({ ...(existing || {}), accountEmail: email });
        }
        redirectAfterAuth();
      }
    } catch (err) {
      errorEl.textContent = (err && err.message) ? err.message : 'Authentication failed. Please try again.';
      errorEl.style.display = 'block';
    }
  });
  
  // If already authenticated, skip the login page entirely
  document.addEventListener('DOMContentLoaded', () => {
    try {
      if (window.X7Auth && X7Auth.isLoggedIn && X7Auth.isLoggedIn()) {
        redirectAfterAuth();
      }
    } catch {}
    // Ensure correct visibility on initial load
    setSignupVisibility(mode === 'signup');
  });
})();

