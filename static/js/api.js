export function notice(message, error = false) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.toggle('error', error);
  toast.hidden = false;
  clearTimeout(notice.timer);
  notice.timer = setTimeout(() => { toast.hidden = true; }, 4500);
}

export function errorText(data) {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(errorText).join(' ');
  if (data && typeof data === 'object') return Object.values(data).map(errorText).join(' ');
  return 'Não foi possível concluir. Tente novamente.';
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  const method = options.method || 'GET';
  if (!['GET', 'HEAD'].includes(method)) {
    const cookie = document.cookie.split('; ').find(c => c.startsWith('csrftoken='));
    if (cookie) headers.set('X-CSRFToken', decodeURIComponent(cookie.split('=').slice(1).join('=')));
  }
  let body = options.body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }
  let response;
  try { response = await fetch(path, {...options, method, headers, body, credentials: 'same-origin'}); }
  catch (_) { throw new Error('Sem conexão. Confira sua internet e tente novamente.'); }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({detail: 'Não foi possível concluir. Atualize a página e tente novamente.'}));
  if (!response.ok) {
    const error = new Error(errorText(data));
    error.status = response.status;
    throw error;
  }
  return data;
}

export function element(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

export function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('icon'); svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`); svg.append(use);
  return svg;
}

export function button(text, className, action, iconName) {
  const result = element('button', className);
  result.type = 'button';
  if (iconName) result.append(icon(iconName));
  if (text) result.append(element('span', '', text));
  if (action) result.addEventListener('click', action);
  return result;
}

export function avatar(user, large = false) {
  const result = element('span', `avatar${large ? ' large' : ''}`);
  const hue = [...user.username].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 4;
  result.dataset.color = hue;
  if (user.avatar) {
    const image = document.createElement('img'); image.src = user.avatar; image.alt = `Foto de ${user.name}`;
    image.loading = 'lazy'; image.addEventListener('error', () => { image.remove(); result.textContent = (user.name || user.username).slice(0, 2).toUpperCase(); });
    result.append(image);
  } else result.textContent = (user.name || user.username).split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase();
  return result;
}

export function link(text, path, className = '') {
  const result = element('a', className, text); result.href = path; result.dataset.nav = ''; return result;
}
