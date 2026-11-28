(() => {
  'use strict';
  const form = document.getElementById('account-form');
  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.disabled = false;
    button.addEventListener('click', () => {
      const field = document.getElementById(button.dataset.passwordToggle);
      const show = field.type === 'password';
      field.type = show ? 'text' : 'password';
      button.textContent = show ? 'Hide' : 'Show';
      button.setAttribute('aria-pressed', String(show));
      button.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} ${field.id === 'confirm_password' ? 'password confirmation' : 'password'}`);
    });
  });
  if (!form) return;
  const banner = document.getElementById('account-error');
  const status = document.getElementById('account-status');
  const submit = document.getElementById('account-submit');
  const signup = form.dataset.mode === 'signup';
  let busy = false;
  function fieldError(name, message) {
    const field = document.getElementById(name);
    const error = document.getElementById(`${name}-error`);
    if (field && error) {
      field.setAttribute('aria-invalid', String(Boolean(message)));
      error.textContent = message;
    }
  }
  const names = signup ? ['name', 'email', 'address', 'password', 'confirm_password'] : ['email', 'password'];
  names.forEach((name) => document.getElementById(name).addEventListener('input', () => fieldError(name, '')));
  const firstServerError = form.querySelector('[aria-invalid="true"]');
  if (firstServerError) firstServerError.focus();
  else if (banner.textContent.trim()) banner.focus();
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy || submit.disabled) return;
    banner.textContent = '';
    names.forEach((name) => fieldError(name, ''));
    const data = new FormData(form);
    const errors = {};
    const length = (value) => Array.from(value).length;
    if (signup) {
      if (!data.get('name').trim() || length(data.get('name').trim()) > 100) errors.name = 'Enter your name using 100 characters or fewer.';
      if (!data.get('address').trim() || length(data.get('address').trim()) > 500) errors.address = 'Enter your address using 500 characters or fewer.';
      if (length(data.get('password')) < 15 || length(data.get('password')) > 128) errors.password = 'Use a password between 15 and 128 characters.';
      if (data.get('password') !== data.get('confirm_password')) errors.confirm_password = 'The passwords must match.';
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.get('email').trim()) || data.get('email').length > 254) errors.email = 'Enter a valid email address.';
    if (!data.get('password')) errors.password = signup ? 'Use a password between 15 and 128 characters.' : 'Enter your password.';
    if (Object.keys(errors).length) {
      Object.entries(errors).forEach(([name, message]) => fieldError(name, message));
      document.getElementById(names.find((name) => errors[name])).focus();
      return;
    }
    if (!navigator.onLine) {
      banner.textContent = 'You are offline. Reconnect, then try again.';
      banner.focus();
      return;
    }
    busy = true; submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.textContent = signup ? 'Creating your account…' : 'Logging in…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(form.action, { method:'POST', body:data, headers:{Accept:'application/json'}, signal:controller.signal, credentials:'same-origin', cache:'no-store' });
      if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('The server could not complete the request. Try again shortly.');
      const result = await response.json();
      if (!response.ok) {
        Object.entries(result.errors || {}).forEach(([name, message]) => fieldError(name, message));
        banner.textContent = result.error || 'The request failed. Try again.';
        if (response.status === 401 || response.status === 403) {
          document.getElementById('password').value = '';
          if (signup) document.getElementById('confirm_password').value = '';
        }
        const first = names.find((name) => result.errors?.[name]);
        if (first) document.getElementById(first).focus(); else banner.focus();
        return;
      }
      if (result.redirect !== '/') throw new Error('Your account was processed. Open the dashboard to continue.');
      status.textContent = signup ? 'Account created. Opening your dashboard…' : 'Logged in. Opening your dashboard…';
      window.location.assign(result.redirect);
    } catch (error) {
      banner.textContent = error.name === 'AbortError' || error instanceof TypeError
        ? (signup ? 'Could not confirm account creation. Check your connection and try logging in before creating an account again.' : 'Could not confirm login. Check your connection, reload this page, and try again.')
        : error.message;
      banner.focus();
    } finally {
      clearTimeout(timer);
      busy = false; submit.disabled = false;
      form.setAttribute('aria-busy', 'false');
      if (banner.textContent) status.textContent = '';
    }
  });
})();
