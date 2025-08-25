(function(){
  const plans = [
    {
      id: 'starter',
      name: 'Starter',
      price: '$0',
      period: '/mo',
      features: [
        'Basic chat support',
        'Up to 100 messages/mo',
        'Email support'
      ]
    },
    {
      id: 'pro',
      name: 'Pro',
      price: '$29',
      period: '/mo',
      features: [
        'Priority chat support',
        'Up to 5,000 messages/mo',
        'Custom branding'
      ]
    },
    {
      id: 'business',
      name: 'Business',
      price: '$99',
      period: '/mo',
      features: [
        'Dedicated account manager',
        'Unlimited messages',
        'Advanced analytics'
      ]
    }
  ];

  function requireAuth(){
    if (!(window.X7Auth && X7Auth.isLoggedIn && X7Auth.isLoggedIn())) {
      window.location.href = 'login.html';
    }
  }

  function renderPlans(){
    const grid = document.getElementById('plansGrid');
    if (!grid) return;
    grid.innerHTML = '';
    plans.forEach(p => {
      const card = document.createElement('div');
      card.className = 'plan-card';
      card.innerHTML = `
        <div class="plan-header">
          <h3>${p.name}</h3>
          <div class="plan-price"><span>${p.price}</span><small>${p.period}</small></div>
        </div>
        <ul class="plan-features">
          ${p.features.map(f => `<li>${f}</li>`).join('')}
        </ul>
        <button class="btn primary w-100" data-plan="${p.id}">Choose ${p.name}</button>
      `;
      grid.appendChild(card);
    });
  }

  function choosePlan(planId){
    try {
      const profile = (X7Auth.getProfile && X7Auth.getProfile()) || {};
      X7Auth.setProfile({ ...profile, subscriptionPlan: planId, subscriptionChosenAt: Date.now() });
      // After plan selection, proceed to onboarding
      window.location.href = 'onboarding.html';
    } catch (e) {
      alert('Failed to save plan. Please try again.');
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    requireAuth();
    renderPlans();

    const grid = document.getElementById('plansGrid');
    if (grid) {
      grid.addEventListener('click', function(e){
        const btn = e.target.closest('button[data-plan]');
        if (btn) {
          const plan = btn.getAttribute('data-plan');
          if (plan) choosePlan(plan);
        }
      });
    }

    const skip = document.getElementById('skipPlan');
    if (skip) {
      skip.addEventListener('click', function(){
        // Set a placeholder plan so redirects don't loop back
        choosePlan('trial');
      });
    }
  });
})();
