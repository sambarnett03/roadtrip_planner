// static/js/firebase_auth.js
(function () {
  if (!window.firebase) {
    console.error('Firebase SDK not loaded');
    return;
  }

  firebase.initializeApp(window.firebaseConfig || {});

  const auth = firebase.auth();

  const emailEl = document.getElementById('email');
  const passEl = document.getElementById('password');
  const statusEl = document.getElementById('status');
  const btnSignup = document.getElementById('btn-signup');
  const btnSignin = document.getElementById('btn-signin');
  const btnSignout = document.getElementById('btn-signout');

  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.className = kind === 'error' ? 'error' : (kind === 'success' ? 'success' : '');
  }

  // send idToken to server to create session
  async function sendTokenToServer(idToken) {
    try {
      const res = await fetch('/session_login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || res.statusText || 'Failed to create session');
      }
      const payload = await res.json();
      // Redirect to roadtrips page for the logged-in user
      window.location.href = '/roadtrips';
      return payload;
    } catch (err) {
      throw err;
    }
  }


  async function handleSignUp() {
    setStatus('', null);
    const email = emailEl.value.trim();
    const password = passEl.value;
    if (!email || !password) {
      setStatus('Please provide email and password.', 'error');
      return;
    }
    try {
      const cred = await auth.createUserWithEmailAndPassword(email, password);
      const token = await cred.user.getIdToken();
      await sendTokenToServer(token);
      setStatus('Account created and signed in!', 'success');
      btnSignout.style.display = 'inline-block';
    } catch (err) {
      setStatus(err.message || 'Signup failed', 'error');
      console.error(err);
    }
  }

  async function handleSignIn() {
    setStatus('', null);
    const email = emailEl.value.trim();
    const password = passEl.value;
    if (!email || !password) {
      setStatus('Please provide email and password.', 'error');
      return;
    }
    try {
      const cred = await auth.signInWithEmailAndPassword(email, password);
      const token = await cred.user.getIdToken();
      await sendTokenToServer(token);
      setStatus('Signed in!', 'success');
      btnSignout.style.display = 'inline-block';
    } catch (err) {
      setStatus(err.message || 'Sign in failed', 'error');
      console.error(err);
    }
  }

  async function handleSignOut() {
    try {
      // Sign out client-side auth
      await auth.signOut();
      // Notify server to clear session
      await fetch('/sign_out');
      setStatus('Signed out', null);
      btnSignout.style.display = 'none';
    } catch (err) {
      setStatus('Error signing out', 'error');
      console.error(err);
    }
  }

  btnSignup.addEventListener('click', handleSignUp);
  btnSignin.addEventListener('click', handleSignIn);
  btnSignout.addEventListener('click', handleSignOut);

  // reflect current state
  auth.onAuthStateChanged(user => {
    if (user) {
      btnSignout.style.display = 'inline-block';
    } else {
      btnSignout.style.display = 'none';
    }
  });
})();
