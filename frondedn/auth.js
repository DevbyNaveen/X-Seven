(function(){
  const AUTH_KEY = 'x7_auth';
  const PROFILE_KEY = 'x7_business_profile';

  function setAuth(auth) {
    try { localStorage.setItem(AUTH_KEY, JSON.stringify(auth || {})); } catch {}
  }
  function getAuth() {
    try { return JSON.parse(localStorage.getItem(AUTH_KEY) || 'null'); } catch { return null; }
  }
  function clearAuth() {
    try { localStorage.removeItem(AUTH_KEY); } catch {}
  }
  function isLoggedIn() { return !!(getAuth() && getAuth().token); }

  function getProfile() {
    try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
  }
  function setProfile(profile) {
    try { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile || {})); } catch {}
  }

  // Expose globally
  window.X7Auth = { setAuth, getAuth, clearAuth, isLoggedIn, getProfile, setProfile };
})();
