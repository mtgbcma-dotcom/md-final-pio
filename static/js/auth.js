import {api, errorText} from './api.js';
const form = document.querySelector('#auth-form');
form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = form.querySelector('[type=submit]');
  const error = document.querySelector('#form-error');
  error.hidden = true; submit.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(form)); delete data.csrfmiddlewaretoken;
    await api(`/api/auth/${form.dataset.mode}/`, {method: 'POST', body: data});
    location.assign('/');
  } catch (failure) { error.textContent = errorText(failure.message); error.hidden = false; }
  finally { submit.disabled = false; }
});
