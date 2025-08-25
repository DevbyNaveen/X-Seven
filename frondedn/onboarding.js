(function(){
  const form = document.getElementById('onboardForm');
  const err = document.getElementById('onboardError');
  const skipBtn = document.getElementById('skipBtn');
  const logoutLink = document.getElementById('logoutLink');

  function $(id){ return document.getElementById(id); }

  function loadProfileIntoForm(){
    const p = (window.X7Auth && X7Auth.getProfile && X7Auth.getProfile()) || {};
    if ($('bizName')) $('bizName').value = p.businessName || '';
    if ($('website')) $('website').value = p.website || '';
    if ($('industry')) $('industry').value = p.industry || '';
    if ($('timezone')) $('timezone').value = p.timezone || '';
    if ($('contactEmail')) $('contactEmail').value = p.contactEmail || '';
    if ($('contactPhone')) $('contactPhone').value = p.contactPhone || '';
    if ($('hours')) $('hours').value = p.hours || '';
    if ($('welcome')) $('welcome').value = p.welcome || '';
  }

  function toDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async function handleSubmit(e){
    e.preventDefault();
    if (err) err.style.display = 'none';

    const profile = {
      businessName: $('bizName').value.trim(),
      website: $('website').value.trim(),
      industry: $('industry').value,
      timezone: $('timezone').value.trim(),
      contactEmail: $('contactEmail').value.trim(),
      contactPhone: $('contactPhone').value.trim(),
      hours: $('hours').value.trim(),
      welcome: $('welcome').value.trim(),
      updatedAt: Date.now(),
    };

    if (!profile.businessName) {
      if (err) { err.textContent = 'Business name is required.'; err.style.display = 'block'; }
      return;
    }

    try {
      const logoFile = $('logo') && $('logo').files && $('logo').files[0];
      if (logoFile) {
        // Avoid huge images in localStorage; accept up to ~300KB
        if (logoFile.size > 300 * 1024) {
          if (err) { err.textContent = 'Logo is too large (max 300KB). Please upload a smaller image.'; err.style.display = 'block'; }
          return;
        }
        profile.logoDataUrl = await toDataUrl(logoFile);
      }
    } catch (e) {
      // Non-fatal, continue without logo
      console.warn('Logo processing failed:', e);
    }

    try {
      const existing = (X7Auth.getProfile && X7Auth.getProfile()) || {};
      X7Auth.setProfile({ ...existing, ...profile });
      // After onboarding, go back to chat
      window.location.href = 'index.html';
    } catch (e) {
      if (err) { err.textContent = 'Failed to save profile. Please try again.'; err.style.display = 'block'; }
    }
  }

  function requireAuth(){
    if (!(window.X7Auth && X7Auth.isLoggedIn && X7Auth.isLoggedIn())) {
      // Redirect to login if not authenticated
      window.location.href = 'login.html';
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    requireAuth();
    loadProfileIntoForm();
    if (form) form.addEventListener('submit', handleSubmit);
    if (skipBtn) skipBtn.addEventListener('click', function(){ window.location.href = 'index.html'; });
    if (logoutLink) logoutLink.addEventListener('click', function(e){
      e.preventDefault();
      try { if (window.X7Auth && X7Auth.clearAuth) X7Auth.clearAuth(); } catch {}
      window.location.href = 'login.html';
    });
  });
})();
