(function () {
  'use strict';

  var state = {
    status: 'open',
    activeId: null,
    lastMsgId: 0,
    listTimer: null,
    threadTimer: null,
    listInFlight: false,
    threadInFlight: false,
  };

  var convList = document.getElementById('conv-list');
  var threadEmpty = document.getElementById('thread-empty');
  var threadBody = document.getElementById('thread-body');
  var threadMsgs = document.getElementById('thread-msgs');
  var threadName = document.getElementById('thread-name');
  var composeForm = document.getElementById('compose-form');
  var composeText = document.getElementById('compose-text');
  var composeFile = document.getElementById('compose-file');
  var fileName = document.getElementById('file-name');

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : s;
    return d.innerHTML;
  }

  function fmtTime(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return d.toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  // --- conversation list ---------------------------------------------
  function renderList(items) {
    convList.innerHTML = '';
    if (!items.length) {
      convList.innerHTML = '<p class="p-4 text-sm text-stone-400">Порожньо</p>';
      return;
    }
    items.forEach(function (c) {
      var el = document.createElement('div');
      el.className = 'conv-item' + (c.id === state.activeId ? ' active' : '');
      el.dataset.id = c.id;
      el.innerHTML =
        '<div class="conv-item__top">' +
        '<span class="conv-item__name">' + esc(c.name) + '</span>' +
        (c.unread ? '<span class="conv-item__badge">' + c.unread + '</span>' : '') +
        '</div>' +
        '<span class="conv-item__preview">' + (c.direction === 'out' ? '↩ ' : '') + esc(c.preview) + '</span>';
      el.addEventListener('click', function () { openConversation(c.id, c.name); });
      convList.appendChild(el);
    });
  }

  function pollList() {
    if (state.listInFlight || document.hidden) { scheduleList(); return; }
    state.listInFlight = true;
    fetch('/inbox/conversations?status=' + state.status)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderList(data.conversations || []);
        updateNavBadge(data.total_unread || 0);
      })
      .catch(function () {})
      .finally(function () { state.listInFlight = false; scheduleList(); });
  }

  function scheduleList() {
    clearTimeout(state.listTimer);
    state.listTimer = setTimeout(pollList, 10000);
  }

  function updateNavBadge(n) {
    var badge = document.getElementById('inbox-nav-badge');
    if (badge) {
      badge.textContent = n > 99 ? '99+' : n;
      badge.style.display = n > 0 ? '' : 'none';
    }
  }

  // --- thread -------------------------------------------------------
  function bubble(m) {
    var el = document.createElement('div');
    el.className = 'bubble ' + m.direction + (m.status === 'failed' ? ' failed' : '');
    var html = '';
    if (m.text) html += esc(m.text);
    (m.media || []).forEach(function (md) {
      if (md.type === 'photo') {
        html += '<div><img src="/inbox/media/' + m.id + '/' + md.idx + '" loading="lazy"></div>';
      } else {
        html += '<div><a href="/inbox/media/' + m.id + '/' + md.idx + '" target="_blank">📎 ' + esc(md.type) + '</a></div>';
      }
    });
    html += '<div class="bubble__meta">' + fmtTime(m.created_at) +
      (m.status === 'failed' ? ' · помилка: ' + esc(m.error || '') : '') + '</div>';
    el.innerHTML = html;
    return el;
  }

  function appendMessages(msgs) {
    var atBottom = threadMsgs.scrollHeight - threadMsgs.scrollTop - threadMsgs.clientHeight < 60;
    msgs.forEach(function (m) {
      threadMsgs.appendChild(bubble(m));
      if (m.id > state.lastMsgId) state.lastMsgId = m.id;
    });
    if (atBottom) threadMsgs.scrollTop = threadMsgs.scrollHeight;
  }

  function openConversation(id, name) {
    state.activeId = id;
    state.lastMsgId = 0;
    threadMsgs.innerHTML = '';
    threadEmpty.style.display = 'none';
    threadBody.style.display = 'flex';
    threadName.textContent = name || '';
    document.querySelectorAll('.conv-item').forEach(function (el) {
      el.classList.toggle('active', +el.dataset.id === id);
    });
    if (window.matchMedia('(max-width:768px)').matches) {
      document.getElementById('inbox-list').classList.add('hidden-mobile');
      document.getElementById('inbox-thread').classList.remove('hidden-mobile');
    }
    fetchThread(true);
    scheduleThread();
  }

  function fetchThread(initial) {
    if (!state.activeId || state.threadInFlight) return;
    state.threadInFlight = true;
    var url = '/inbox/conversations/' + state.activeId + '/messages';
    if (!initial && state.lastMsgId) url += '?after=' + state.lastMsgId;
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.conversation && data.conversation.id !== state.activeId) return;
        appendMessages(data.messages || []);
      })
      .catch(function () {})
      .finally(function () { state.threadInFlight = false; });
  }

  function scheduleThread() {
    clearTimeout(state.threadTimer);
    state.threadTimer = setTimeout(function () {
      if (!document.hidden) fetchThread(false);
      scheduleThread();
    }, 5000);
  }

  // --- compose -----------------------------------------------------
  composeFile.addEventListener('change', function () {
    fileName.textContent = composeFile.files[0] ? 'Файл: ' + composeFile.files[0].name : '';
  });

  composeText.addEventListener('input', function () {
    composeText.style.height = 'auto';
    composeText.style.height = Math.min(composeText.scrollHeight, 120) + 'px';
  });

  composeForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (!state.activeId) return;
    var fd = new FormData();
    fd.append('text', composeText.value);
    if (composeFile.files[0]) fd.append('file', composeFile.files[0]);
    if (!composeText.value.trim() && !composeFile.files[0]) return;

    var btn = composeForm.querySelector('button[type=submit]');
    btn.disabled = true;
    fetch('/inbox/conversations/' + state.activeId + '/reply', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.message) appendMessages([data.message]);
        if (!data.ok) showToast(data.error || 'Не вдалося надіслати', 'error');
        else {
          composeText.value = '';
          composeText.style.height = 'auto';
          composeFile.value = '';
          fileName.textContent = '';
        }
      })
      .catch(function () { showToast('Помилка мережі', 'error'); })
      .finally(function () { btn.disabled = false; });
  });

  // --- header actions --------------------------------------------
  document.getElementById('assign-btn').addEventListener('click', function () {
    if (state.activeId) fetch('/inbox/conversations/' + state.activeId + '/assign', { method: 'POST' })
      .then(function () { showToast('Призначено вам', 'success'); });
  });
  document.getElementById('close-btn').addEventListener('click', function () {
    if (!state.activeId) return;
    fetch('/inbox/conversations/' + state.activeId + '/close', { method: 'POST' })
      .then(function () {
        threadBody.style.display = 'none';
        threadEmpty.style.display = 'flex';
        state.activeId = null;
        pollList();
      });
  });
  var backBtn = document.getElementById('back-btn');
  if (backBtn) backBtn.addEventListener('click', function () {
    document.getElementById('inbox-list').classList.remove('hidden-mobile');
    document.getElementById('inbox-thread').classList.add('hidden-mobile');
  });

  document.querySelectorAll('.filter-btn').forEach(function (b) {
    b.addEventListener('click', function () {
      state.status = b.dataset.status;
      document.querySelectorAll('.filter-btn').forEach(function (x) {
        x.className = 'filter-btn text-xs px-2 py-1 rounded ' +
          (x === b ? 'bg-stone-800 text-white' : 'bg-stone-100');
      });
      pollList();
    });
  });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { pollList(); fetchThread(false); }
  });

  // --- start -----------------------------------------------------
  pollList();
})();
