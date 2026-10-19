import {api, avatar, button, element as el, icon, link, notice} from './api.js';

const content = document.querySelector('#page-content');
const dialog = document.querySelector('#dialog');
const dialogContent = document.querySelector('#dialog-content');
let me;
let routeVersion = 0;

function navigate(path) {
  if (location.pathname + location.search !== path) history.pushState({}, '', path);
  dialog.close();
  window.scrollTo({top: 0});
  renderRoute();
}

document.addEventListener('click', event => {
  const anchor = event.target.closest('a[data-nav]');
  if (!anchor || event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
  event.preventDefault(); navigate(anchor.getAttribute('href'));
});
window.addEventListener('popstate', () => { dialog.close(); renderRoute(); });
document.querySelector('#close-dialog').addEventListener('click', () => dialog.close());
document.querySelector('#logout').addEventListener('click', logout);
document.querySelector('.compose-trigger').addEventListener('click', () => {
  openDialog('Compartilhe uma ideia', composer());
  dialogContent.querySelector('textarea').focus();
});
document.querySelector('#global-search').addEventListener('submit', event => {
  event.preventDefault(); navigate(`/explorar/?q=${encodeURIComponent(event.target.q.value.trim())}`);
});

function openDialog(title, child) {
  document.querySelector('#dialog-title').textContent = title;
  dialogContent.replaceChildren(child);
  if (!dialog.open) dialog.showModal();
}

async function logout() {
  try { await api('/api/auth/logout/', {method: 'POST'}); location.assign('/entrar/'); }
  catch (error) { notice(error.message, true); }
}

function updateSidebar() {
  const user = document.querySelector('#sidebar-user');
  const copy = el('div', 'user-copy'); copy.append(el('strong', '', me.name), el('span', '', `@${me.username}`));
  user.replaceChildren(avatar(me), copy);
  document.querySelector('#my-profile-link').href = `/perfil/${me.username}/`;
}

function relativeDate(date) {
  const seconds = Math.max(0, (Date.now() - new Date(date)) / 1000);
  if (seconds < 60) return 'agora';
  if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `há ${Math.floor(seconds / 3600)} h`;
  return new Date(date).toLocaleDateString('pt-BR', {day: 'numeric', month: 'short'});
}

function empty(title, message, target = '/explorar/', action = 'Explorar o Pio', symbol = 'feather') {
  const box = el('div', 'empty-state');
  const mark = el('span', 'empty-symbol'); mark.append(icon(symbol));
  box.append(mark, el('h2', '', title), el('p', '', message));
  if (target) box.append(link(action, target, 'button secondary'));
  return box;
}

function spinner() { return el('div', 'loading', 'Carregando suas conversas…'); }

function header(title, kicker, section) {
  document.title = `${title} · Pio`;
  document.querySelector('#page-title').textContent = title;
  document.querySelector('#page-kicker').textContent = kicker;
  document.querySelectorAll('[data-section]').forEach(a => {
    a.classList.toggle('active', a.dataset.section === section);
    if (a.dataset.section === section) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}

function tabs(active) {
  const nav = el('nav', 'tabs'); nav.setAttribute('aria-label', 'Tipo de feed');
  nav.append(link('Sua rede', '/', active === 'home' ? 'active' : ''), link('Explorar', '/explorar/', active === 'explore' ? 'active' : ''));
  return nav;
}

function composer(existing = null, comment = false) {
  const form = el('form', 'composer');
  const body = el('div', 'composer-body');
  const input = el('textarea'); input.name = 'content'; input.maxLength = 280;
  input.setAttribute('aria-label', comment ? 'Texto do comentário' : 'Texto da publicação');
  input.placeholder = comment ? 'Adicione à conversa…' : 'O que está acontecendo por aí?';
  input.value = existing?.content || '';
  const footer = el('div', 'composer-footer');
  const hint = el('span', 'composer-hint'); hint.append(icon('feather'), el('span', '', comment ? 'Uma boa conversa é feita de trocas.' : 'Pequenas ideias também merecem espaço.'));
  const actions = el('div', 'composer-actions');
  const count = el('span', 'counter'); count.setAttribute('aria-live', 'off');
  const submit = button(existing ? 'Salvar' : 'Publicar', 'button primary'); submit.type = 'submit';
  const error = el('div', 'form-error'); error.hidden = true; error.setAttribute('role', 'alert');
  const update = () => { count.textContent = `${input.value.length}/280`; count.classList.toggle('near-limit', input.value.length > 250); submit.disabled = !input.value.trim(); };
  input.addEventListener('input', update); update();
  actions.append(count, submit); footer.append(hint, actions); body.append(input, error, footer);
  form.append(avatar(me), body);
  form.addEventListener('submit', async event => {
    event.preventDefault(); submit.disabled = true; error.hidden = true;
    try {
      const path = existing ? (comment ? `/api/comments/${existing.id}/` : `/api/posts/${existing.id}/`) : '/api/posts/';
      await api(path, {method: existing ? 'PATCH' : 'POST', body: {content: input.value}});
      dialog.close();
      notice(existing ? 'Alteração salva.' : 'Seu pio foi publicado!');
      if (existing) await renderRoute(); else navigate(`/perfil/${me.username}/`);
    } catch (failure) { error.textContent = failure.message; error.hidden = false; }
    finally { update(); }
  });
  return form;
}

function postCard(post) {
  const card = el('article', 'post-card'); card.dataset.postId = post.id;
  const row = el('div', 'post-layout');
  const profilePath = `/perfil/${post.author.username}/`;
  const picture = link('', profilePath); picture.setAttribute('aria-label', `Ver perfil de ${post.author.name}`); picture.append(avatar(post.author));
  const body = el('div', 'post-body');
  const meta = el('div', 'post-meta');
  const date = link(relativeDate(post.created_at), `/post/${post.id}/`, 'post-date'); date.title = new Date(post.created_at).toLocaleString('pt-BR');
  meta.append(link(post.author.name, profilePath), el('span', '', `@${post.author.username}`), date);
  const text = el('p', 'post-content', post.content);
  const actions = el('div', 'post-actions');
  const like = button(String(post.likes_count), `post-action${post.is_liked ? ' liked' : ''}`, async () => {
    like.disabled = true;
    try {
      const updated = await api(`/api/posts/${post.id}/like/`, {method: post.is_liked ? 'DELETE' : 'PUT'});
      card.replaceWith(postCard(updated));
    } catch (error) { notice(error.message, true); like.disabled = false; }
  }, 'heart');
  like.setAttribute('aria-label', `${post.is_liked ? 'Descurtir' : 'Curtir'} publicação (${post.likes_count})`);
  like.setAttribute('aria-pressed', String(post.is_liked));
  const comments = link('', `/post/${post.id}/`, 'post-action');
  comments.setAttribute('aria-label', `Abrir comentários (${post.comments_count})`);
  comments.append(icon('comment'), el('span', '', String(post.comments_count)));
  const save = button('', `post-action${post.is_saved ? ' saved' : ''}`, async () => {
    save.disabled = true;
    try {
      const updated = await api(`/api/posts/${post.id}/bookmark/`, {method: post.is_saved ? 'DELETE' : 'PUT'});
      notice(post.is_saved ? 'Publicação removida dos salvos.' : 'Publicação salva para depois.');
      if (location.pathname === '/salvos/' && post.is_saved) await renderRoute(); else card.replaceWith(postCard(updated));
    } catch (error) { notice(error.message, true); save.disabled = false; }
  }, 'bookmark');
  save.setAttribute('aria-label', post.is_saved ? 'Remover dos salvos' : 'Salvar publicação');
  save.setAttribute('aria-pressed', String(post.is_saved));
  actions.append(comments, like, save);
  body.append(meta, text, actions);
  if (post.is_owner) {
    const own = el('div', 'owner-actions');
    own.append(button('Editar', '', () => openDialog('Editar publicação', composer(post)), 'edit'),
      button('Excluir', 'danger', () => confirmDelete('Excluir publicação?', 'Sua publicação e os comentários dela serão excluídos.', async () => {
        await api(`/api/posts/${post.id}/`, {method: 'DELETE'});
        if (location.pathname.startsWith('/post/')) navigate(`/perfil/${me.username}/`); else await renderRoute();
      }), 'trash'));
    body.append(own);
  }
  row.append(picture, body); card.append(row); return card;
}

function confirmDelete(title, message, action) {
  const body = el('div'); body.append(el('p', '', message));
  const actions = el('div', 'dialog-actions');
  const remove = button('Excluir', 'button primary', async () => {
    remove.disabled = true;
    try { await action(); dialog.close(); notice('Excluído.'); }
    catch (error) { notice(error.message, true); remove.disabled = false; }
  });
  actions.append(button('Cancelar', 'button secondary', () => dialog.close()), remove);
  body.append(actions); openDialog(title, body);
}

async function loadPosts(path, host, version, emptyOptions) {
  const posts = el('div'); const more = el('div', 'load-more'); host.append(posts, more);
  async function load(url) {
    more.replaceChildren(spinner());
    try {
      const data = await api(url);
      if (routeVersion !== version) return;
      if (!data.count && !posts.children.length) posts.append(empty(...emptyOptions));
      data.results.forEach(post => posts.append(postCard(post)));
      more.replaceChildren();
      if (data.next) more.append(button('Carregar mais publicações', 'button secondary', () => load(data.next)));
    } catch (error) {
      if (routeVersion !== version) return;
      more.replaceChildren(button('Tentar novamente', 'button secondary', () => load(url)));
      notice(error.message, true);
    }
  }
  await load(path);
}

function personRow(user) {
  const row = el('div', 'person-row'); const picture = link('', `/perfil/${user.username}/`); picture.append(avatar(user));
  const copy = el('div', 'user-copy'); copy.append(link(user.name, `/perfil/${user.username}/`), el('span', '', `@${user.username}`));
  row.append(picture, copy);
  if (user.id !== me.id) row.append(followButton(user));
  return row;
}

function followButton(user) {
  const control = button(user.is_following ? 'Seguindo' : 'Seguir', `follow-button${user.is_following ? ' following' : ''}`, async () => {
    control.disabled = true;
    try {
      const updated = await api(`/api/users/${user.username}/follow/`, {method: user.is_following ? 'DELETE' : 'PUT'});
      user = updated;
      control.querySelector('span').textContent = user.is_following ? 'Seguindo' : 'Seguir';
      control.classList.toggle('following', user.is_following);
      control.setAttribute('aria-pressed', String(user.is_following));
      control.setAttribute('aria-label', `${user.is_following ? 'Deixar de seguir' : 'Seguir'} @${user.username}`);
      notice(user.is_following ? `Você está seguindo @${user.username}.` : `Você deixou de seguir @${user.username}.`);
      await refreshSuggestions();
      if (location.pathname === '/' || location.pathname.startsWith('/perfil/')) renderRoute();
    } catch (error) { notice(error.message, true); }
    finally { control.disabled = false; }
  });
  control.setAttribute('aria-pressed', String(user.is_following));
  control.setAttribute('aria-label', `${user.is_following ? 'Deixar de seguir' : 'Seguir'} @${user.username}`);
  return control;
}

async function refreshSuggestions() {
  const host = document.querySelector('#suggestions');
  try {
    const data = await api('/api/users/suggestions/');
    host.replaceChildren(...data.results.slice(0, 3).map(personRow));
    if (!data.count) host.append(el('p', 'muted', 'Sua rede está crescendo. Encontre mais pessoas em Explorar.'));
  } catch (_) { host.replaceChildren(el('p', 'muted', 'As sugestões estarão disponíveis em breve.')); }
}

async function peopleList(path, host, modal = false) {
  let closed = false;
  if (modal) dialog.addEventListener('close', () => { closed = true; }, {once: true});
  const list = el('div'); const more = el('div', 'load-more'); host.append(list, more);
  async function load(url) {
    more.replaceChildren(spinner());
    try {
      const data = await api(url); if (closed) return;
      data.results.forEach(user => list.append(personRow(user)));
      more.replaceChildren();
      if (!data.count) list.append(el('p', 'muted', 'Nenhuma pessoa por aqui ainda.'));
      if (data.next) more.append(button('Ver mais pessoas', 'button secondary', () => load(data.next)));
    } catch (error) { more.replaceChildren(button('Tentar novamente', 'button secondary', () => load(url))); notice(error.message, true); }
  }
  await load(path);
}

async function profile(username, version) {
  const user = await api(`/api/users/${encodeURIComponent(username)}/`); if (version !== routeVersion) return;
  header(user.name, 'UM POUCO DE QUEM FAZ A CONVERSA', 'profile');
  const cover = el('div', 'profile-cover'); const info = el('section', 'profile-info');
  const actions = el('div', 'profile-actions'); actions.append(avatar(user, true));
  actions.append(user.id === me.id ? link('Editar perfil', '/configuracoes/', 'button secondary') : followButton(user));
  const joined = new Date(user.date_joined).toLocaleDateString('pt-BR', {month: 'long', year: 'numeric'});
  info.append(actions, el('h2', '', user.name), el('p', 'profile-handle', `@${user.username}`));
  if (user.bio) info.append(el('p', 'profile-bio', user.bio));
  info.append(el('p', 'profile-joined', `No Pio desde ${joined}`));
  const stats = el('div', 'profile-stats');
  for (const [endpoint, count, label] of [['following', user.following_count, 'seguindo'], ['followers', user.followers_count, 'seguidores']]) {
    const control = button('', '', () => {
      const host = el('div'); openDialog(endpoint === 'following' ? 'Seguindo' : 'Seguidores', host);
      peopleList(`/api/users/${user.username}/${endpoint}/`, host, true);
    });
    control.append(el('strong', '', count), document.createTextNode(` ${label}`)); stats.append(control);
  }
  const postCount = el('span'); postCount.append(el('strong', '', user.posts_count), document.createTextNode(' publicações')); stats.append(postCount);
  info.append(stats);
  content.replaceChildren(cover, info);
  const feedLabel = el('div', 'feed-label'); feedLabel.append(el('span', '', 'PUBLICAÇÕES'), el('span', '', `@${user.username}`)); content.append(feedLabel);
  await loadPosts(`/api/posts/?author=${user.username}`, content, version, ['O primeiro pio vem aí.', user.id === me.id ? 'Compartilhe uma ideia no botão “Escrever um pio”.' : 'Esta pessoa ainda não compartilhou nenhuma publicação.', null]);
}

async function explore(version) {
  header('Explorar', 'DESCUBRA OUTRAS PERSPECTIVAS', 'explore');
  const search = new URLSearchParams(location.search).get('q') || '';
  const box = el('section', 'results-people');
  const form = el('form', 'search-box'); const input = el('input'); input.name = 'q'; input.value = search; input.maxLength = 80; input.placeholder = 'Buscar pessoas e publicações'; input.setAttribute('aria-label', 'Buscar no Pio');
  const submit = button('', 'icon-button', null, 'search'); submit.type = 'submit'; submit.setAttribute('aria-label', 'Buscar');
  form.append(input, submit); form.addEventListener('submit', event => { event.preventDefault(); navigate(`/explorar/?q=${encodeURIComponent(input.value.trim())}`); });
  box.append(form);
  const people = el('section', 'results-people'); people.append(el('h2', '', search ? 'Pessoas encontradas' : 'Amplie sua rede'));
  content.replaceChildren(tabs('explore'), box, people);
  if (search) peopleList(`/api/users/?search=${encodeURIComponent(search)}`, people);
  else {
    const data = await api('/api/users/suggestions/'); if (version !== routeVersion) return;
    data.results.slice(0, 4).forEach(user => people.append(personRow(user)));
    if (!data.count) people.append(el('p', 'muted', 'Use a busca para encontrar pessoas pelo nome ou @usuário.'));
  }
  const label = el('div', 'feed-label'); label.append(el('span', '', search ? 'PUBLICAÇÕES ENCONTRADAS' : 'ACONTECENDO NO PIO'), el('span', '', 'Mais recentes')); content.append(label);
  await loadPosts(`/api/posts/${search ? `?search=${encodeURIComponent(search)}` : ''}`, content, version, ['Ainda não temos pios por aqui.', search ? 'Tente outra palavra na busca.' : 'Seja a primeira pessoa a compartilhar uma ideia.', null]);
}

async function postDetail(id, version) {
  const post = await api(`/api/posts/${id}/`); if (version !== routeVersion) return;
  header('Conversa', 'IDEIAS BOAS MERECEM UMA TROCA', '');
  const back = link('', '/explorar/', 'back-link'); back.append(icon('arrow'), el('span', '', 'Voltar às publicações'));
  const commentForm = el('form', 'comment-form'); const input = el('textarea'); input.name = 'content'; input.maxLength = 280; input.required = true; input.placeholder = 'Qual é a sua perspectiva?'; input.setAttribute('aria-label', 'Seu comentário');
  const submit = button('Comentar', 'button primary'); submit.type = 'submit';
  commentForm.append(input, submit);
  const comments = el('div');
  content.replaceChildren(back, postCard(post), el('h2', 'comment-heading', 'Vamos conversar'), commentForm, comments);
  async function loadComments() {
    comments.replaceChildren();
    const list = el('div'); const more = el('div', 'load-more'); comments.append(list, more);
    async function load(url) {
      more.replaceChildren(spinner());
      try {
        const data = await api(url); if (version !== routeVersion) return;
        if (!data.count) list.append(empty('Abra a conversa.', 'Seja a primeira pessoa a comentar.', null, '', 'comment'));
        data.results.forEach(item => {
          const card = el('article', 'comment-card'); const body = el('div', 'post-body'); const meta = el('div', 'post-meta');
          meta.append(link(item.author.name, `/perfil/${item.author.username}/`), el('span', '', `@${item.author.username}`), el('span', 'post-date', relativeDate(item.created_at)));
          body.append(meta, el('p', 'post-content', item.content));
          if (item.is_owner) {
            const own = el('div', 'owner-actions');
            own.append(button('Editar', '', () => openDialog('Editar comentário', composer(item, true)), 'edit'), button('Excluir', 'danger', () => confirmDelete('Excluir comentário?', 'Este comentário será excluído.', async () => { await api(`/api/comments/${item.id}/`, {method: 'DELETE'}); await renderRoute(); }), 'trash'));
            body.append(own);
          }
          const picture = link('', `/perfil/${item.author.username}/`); picture.append(avatar(item.author)); card.append(picture, body); list.append(card);
        });
        more.replaceChildren(); if (data.next) more.append(button('Mais comentários', 'button secondary', () => load(data.next)));
      } catch (error) { more.replaceChildren(button('Tentar novamente', 'button secondary', () => load(url))); notice(error.message, true); }
    }
    await load(`/api/posts/${id}/comments/`);
  }
  commentForm.addEventListener('submit', async event => {
    event.preventDefault(); if (!input.value.trim()) return; submit.disabled = true;
    try { await api(`/api/posts/${id}/comments/`, {method: 'POST', body: {content: input.value}}); notice('Comentário publicado.'); await renderRoute(); }
    catch (error) { notice(error.message, true); submit.disabled = false; }
  });
  await loadComments();
}

function label(text, input) { const result = el('label', '', text); result.append(input); return result; }
function textInput(name, value = '', type = 'text') { const input = el('input'); input.name = name; input.value = value; input.type = type; return input; }

function settings() {
  header('Configurações', 'DO SEU JEITO, NO SEU TEMPO', 'settings');
  const section = el('section', 'settings-section');
  section.append(el('h2', '', 'Um perfil com a sua cara'), el('p', 'muted', 'Altere apenas o que quiser. Seu nome, sua foto e sua senha podem ser atualizados separadamente.'));
  const form = el('form'); const photo = el('div', 'avatar-setting'); const preview = el('div'); preview.append(avatar(me));
  const upload = textInput('avatar', '', 'file'); upload.accept = 'image/jpeg,image/png,image/webp';
  const uploadBody = el('div'); uploadBody.append(label('Foto de perfil', upload), el('p', 'field-hint', 'JPG, PNG ou WebP · até 2 MB'));
  const remove = textInput('remove_avatar', '', 'checkbox'); const removeLabel = el('label', 'checkbox-label'); removeLabel.append(remove, document.createTextNode('Remover foto atual')); uploadBody.append(removeLabel); photo.append(preview, uploadBody);
  upload.addEventListener('change', () => {
    const file = upload.files[0]; if (!file) return;
    if (file.size > 2 * 1024 * 1024) { notice('A foto deve ter no máximo 2 MB.', true); upload.value = ''; return; }
    remove.checked = false;
    const url = URL.createObjectURL(file); const image = el('img'); image.src = url; image.alt = 'Prévia da nova foto';
    image.addEventListener('load', () => URL.revokeObjectURL(url), {once: true}); const frame = el('span', 'avatar'); frame.append(image); preview.replaceChildren(frame);
  });
  remove.addEventListener('change', () => { if (remove.checked) { upload.value = ''; preview.replaceChildren(avatar({...me, avatar: null})); } else preview.replaceChildren(avatar(me)); });
  const name = textInput('name', me.name); name.maxLength = 80; name.required = true; name.autocomplete = 'name';
  const bio = el('textarea'); bio.name = 'bio'; bio.value = me.bio; bio.maxLength = 160; bio.placeholder = 'O que faz você ser você?';
  const error = el('div', 'form-error'); error.hidden = true; error.setAttribute('role', 'alert');
  const save = button('Salvar perfil', 'button primary'); save.type = 'submit';
  form.append(photo, label('Nome', name), label('Biografia (opcional)', bio), error, save);
  form.addEventListener('submit', async event => {
    event.preventDefault(); save.disabled = true; error.hidden = true;
    const data = new FormData(); data.set('name', name.value); data.set('bio', bio.value);
    if (upload.files[0]) data.set('avatar', upload.files[0]); if (remove.checked) data.set('remove_avatar', 'true');
    try { me = await api('/api/me/', {method: 'PATCH', body: data}); updateSidebar(); notice('Seu perfil foi atualizado.'); navigate(`/perfil/${me.username}/`); }
    catch (failure) { error.textContent = failure.message; error.hidden = false; }
    finally { save.disabled = false; }
  });
  section.append(form);
  const password = el('section', 'settings-section'); password.append(el('h2', '', 'Trocar senha'), el('p', 'muted', 'Mantenha sua conta segura com uma senha única de pelo menos 10 caracteres.'));
  const passwordForm = el('form');
  for (const [key, text] of [['current_password', 'Senha atual'], ['new_password', 'Nova senha'], ['password_confirm', 'Confirme a nova senha']]) {
    const input = textInput(key, '', 'password'); input.required = true; input.autocomplete = key === 'current_password' ? 'current-password' : 'new-password';
    if (key !== 'current_password') input.minLength = 10; passwordForm.append(label(text, input));
  }
  const passwordError = el('div', 'form-error'); passwordError.hidden = true; passwordError.setAttribute('role', 'alert');
  const change = button('Atualizar senha', 'button secondary'); change.type = 'submit'; passwordForm.append(passwordError, change);
  passwordForm.addEventListener('submit', async event => {
    event.preventDefault(); change.disabled = true; passwordError.hidden = true;
    try { await api('/api/me/password/', {method: 'POST', body: Object.fromEntries(new FormData(passwordForm))}); passwordForm.reset(); notice('Senha atualizada. Você continua conectado.'); }
    catch (failure) { passwordError.textContent = failure.message; passwordError.hidden = false; }
    finally { change.disabled = false; }
  });
  password.append(passwordForm);
  const appearance = el('section', 'settings-section'); appearance.append(el('h2', '', 'Sua experiência'), button('Alternar tema claro / escuro', 'text-button theme-toggle', null, 'moon'), button('Sair da conta', 'text-button', logout, 'out'));
  content.replaceChildren(section, password, appearance);
}

async function renderRoute() {
  const version = ++routeVersion; content.setAttribute('aria-busy', 'true'); content.replaceChildren(spinner());
  try {
    const path = location.pathname;
    if (path === '/') {
      header('Início', 'SUAS CONEXÕES, SUAS CONVERSAS', 'home');
      const label = el('div', 'feed-label'); label.append(el('span', '', 'DA SUA REDE'), el('span', '', 'Somente pessoas que você segue'));
      content.replaceChildren(tabs('home'), composer(), label);
      await loadPosts('/api/posts/feed/', content, version, ['Sua rede começa com uma conexão.', 'Siga pessoas em Explorar para ver as publicações delas por aqui. Este feed é só de quem você segue.']);
    } else if (path === '/explorar/') await explore(version);
    else if (path === '/salvos/') {
      header('Salvos', 'IDEIAS PARA REVISITAR', 'saved'); content.replaceChildren();
      await loadPosts('/api/posts/saved/', content, version, ['Guarde uma boa ideia.', 'Toque no marcador de uma publicação para encontrá-la aqui depois. Seus salvos são privados.', '/explorar/', 'Encontrar publicações', 'bookmark']);
    } else if (path === '/configuracoes/') settings();
    else if (/^\/perfil\/[^/]+\/$/.test(path)) await profile(decodeURIComponent(path.split('/')[2]), version);
    else if (/^\/post\/\d+\/$/.test(path)) await postDetail(path.split('/')[2], version);
    else content.replaceChildren(empty('Página não encontrada.', 'Volte ao início para continuar a conversa.', '/', 'Ir para o início'));
  } catch (error) {
    if (version !== routeVersion) return;
    content.replaceChildren(empty(error.status === 404 ? 'Não encontramos este conteúdo.' : 'Não foi possível carregar.', error.status === 404 ? 'O perfil ou a publicação pode ter sido removido.' : error.message, '/', 'Voltar ao início'));
  } finally { if (version === routeVersion) content.setAttribute('aria-busy', 'false'); }
}

async function start() {
  try { me = await api('/api/me/'); updateSidebar(); await Promise.all([renderRoute(), refreshSuggestions()]); }
  catch (error) {
    if ([401, 403].includes(error.status)) location.assign('/entrar/');
    else content.replaceChildren(empty('Estamos sem conexão.', error.message, '/', 'Tentar novamente'));
  }
}
start();
