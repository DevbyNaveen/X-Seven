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
      window.location.href = 'index.html';
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
      // NOTE: Backend endpoints not present; storing locally for now.
      const token = uuid();
      X7Auth.setAuth({ token, email, createdAt: Date.now() });
      if (mode === 'signup') {
        // Save initial business/account details; subscription chosen on next step
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
        window.location.href = 'subscription.html';
      } else {
        redirectAfterAuth();
      }
    } catch (err) {
      errorEl.textContent = 'Authentication failed. Please try again.';
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
