// Fetch session info and publish to window.EACIS.session
(function(){
  async function fetchSession(){
    try{
      const res = await fetch('/api/session', { credentials: 'same-origin' });
      const data = await res.json();
      window.EACIS = window.EACIS || {};
      window.EACIS.session = data;
      // body class for role
      document.body.classList.remove('role-public','role-customer','role-seller','role-admin');
      if(!data.authenticated){ document.body.classList.add('role-public'); }
      else if(data.role === 'customer') document.body.classList.add('role-customer');
      else if(data.role === 'seller') document.body.classList.add('role-seller');
      else if(data.role === 'admin') document.body.classList.add('role-admin');
      // emit event
      document.dispatchEvent(new CustomEvent('eacis:session', { detail: data }));
    }catch(e){ console.error('session fetch failed', e); window.EACIS = window.EACIS || {}; window.EACIS.session = { authenticated:false, role:null }; document.body.classList.add('role-public'); document.dispatchEvent(new CustomEvent('eacis:session', { detail: window.EACIS.session })); }
  }
  document.addEventListener('DOMContentLoaded', fetchSession);
})();
