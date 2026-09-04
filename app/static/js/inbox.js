(function () {
  'use strict';

  var S = {
    filter: 'all',
    search: '',
    activeId: null,
    activeConv: null,
    lastMsgId: 0,
    convs: [],
    listTimer: null,
    threadTimer: null,
    listBusy: false,
    threadBusy: false,
    lastDateKey: null,
    soundOn: false,
  };

  var $ = function (id) { return document.getElementById(id); };
  var wrap = $('ib-wrap');
  var listEl = $('ib-conv-list');
  var msgsEl = $('ib-msgs');
  var emptyEl = $('ib-empty');
  var bodyEl = $('ib-thread-body');
  var textEl = $('ib-text');
  var fileEl = $('ib-file');
  var filePrev = $('ib-filepreview');
  var sendBtn = $('ib-send');
  var searchEl = $('ib-search');
  var soundBtn = $('ib-sound');
  var lightbox = $('ib-lightbox');
  var newModal = $('ib-new-modal');
  var ME = window.IB_USER_ID;

  function chIcon(t) { return t === 'instagram' ? 'instagram' : 'telegram'; }

  var AVA = ['#0ea5e9', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444', '#6366f1', '#14b8a6'];
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function initials(name) {
    var p = (name || '?').replace(/^[@#]/, '').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p[1] ? p[1][0] : '')).toUpperCase();
  }
  function avaColor(s) {
    var h = 0; s = s || '';
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return AVA[Math.abs(h) % AVA.length];
  }
  function relTime(iso) {
    if (!iso) return '';
    var d = new Date(iso), now = new Date(), diff = (now - d) / 1000;
    if (diff < 60) return 'щойно';
    if (diff < 3600) return Math.floor(diff / 60) + ' хв';
    if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
    var y = new Date(now); y.setDate(y.getDate() - 1);
    if (d.toDateString() === y.toDateString()) return 'вчора';
    return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' });
  }
  function dateKey(iso) {
    var d = new Date(iso), now = new Date();
    if (d.toDateString() === now.toDateString()) return 'Сьогодні';
    var y = new Date(now); y.setDate(y.getDate() - 1);
    if (d.toDateString() === y.toDateString()) return 'Вчора';
    return d.toLocaleDateString('uk-UA', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  // ---- conversation list -------------------------------------------
  function renderList() {
    var items = S.convs.filter(function (c) {
      return !S.search || (c.name || '').toLowerCase().indexOf(S.search) !== -1
        || (c.username || '').toLowerCase().indexOf(S.search) !== -1;
    });
    if (!items.length) {
      listEl.innerHTML = '<p style="padding:1.2rem;color:#a8a29e;font-size:0.85rem;text-align:center;">Порожньо</p>';
      return;
    }
    listEl.innerHTML = items.map(function (c) {
      return '<div class="conv' + (c.id === S.activeId ? ' active' : '') + (c.unread ? ' unread' : '') +
        '" data-id="' + c.id + '">' +
        '<div class="conv__avatar" style="background:' + avaColor(c.name) + '">' + esc(initials(c.name)) +
        '<span class="conv__ch ' + esc(c.channel_type) + '"><i class="bi bi-' +
        chIcon(c.channel_type) + '"></i></span></div>' +
        '<div class="conv__body">' +
        '<div class="conv__top"><span class="conv__name">' + esc(c.name) + '</span>' +
        '<span class="conv__time">' + relTime(c.last_message_at) + '</span></div>' +
        '<div class="conv__preview">' + (c.direction === 'out' ? '<i class="bi bi-reply"></i> ' : '') +
        esc(c.preview) + (c.unread ? '<span class="conv__badge">' + c.unread + '</span>' : '') + '</div>' +
        (c.assigned_user_id ? '<div class="conv__assigned"><i class="bi bi-person-fill"></i>' +
          (c.assigned_user_id === ME ? 'ви' : 'інший менеджер') + '</div>' : '') +
        '</div></div>';
    }).join('');
    [].forEach.call(listEl.querySelectorAll('.conv'), function (el) {
      el.addEventListener('click', function () { openConv(+el.dataset.id); });
    });
  }

  function pollList() {
    if (S.listBusy) return;
    S.listBusy = true;
    fetch('/inbox/conversations?filter=' + S.filter)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var prevUnread = S.convs.reduce(function (a, c) { return a + (c.unread || 0); }, 0);
        S.convs = data.conversations || [];
        renderList();
        setNavBadge(data.total_unread || 0);
        var nowUnread = S.convs.reduce(function (a, c) { return a + (c.unread || 0); }, 0);
        if (S.soundOn && nowUnread > prevUnread) beep();
      })
      .catch(function () {})
      .finally(function () { S.listBusy = false; scheduleList(); });
  }
  function scheduleList() { clearTimeout(S.listTimer); S.listTimer = setTimeout(pollList, document.hidden ? 30000 : 10000); }

  function setNavBadge(n) {
    var b = $('inbox-nav-badge');
    if (b) { b.textContent = n > 99 ? '99+' : n; b.style.display = n > 0 ? '' : 'none'; }
  }

  // ---- thread -----------------------------------------------------
  function msgNode(m) {
    var wrapEl = document.createElement('div');
    wrapEl.className = 'msg ' + m.direction + (m.status === 'failed' ? ' failed' : '');
    var inner = '<div class="msg__bubble">';
    if (m.text) inner += esc(m.text);
    (m.media || []).forEach(function (md) {
      if (md.expired) inner += '<div class="msg__file" style="color:#a8a29e"><i class="bi bi-slash-circle"></i> Вкладення видалено (14 днів)</div>';
      else if (md.type === 'photo') inner += '<img class="msg__img" data-full="/inbox/media/' + m.id + '/' + md.idx + '" src="/inbox/media/' + m.id + '/' + md.idx + '" alt="">';
      else inner += '<a class="msg__file" href="/inbox/media/' + m.id + '/' + md.idx + '" target="_blank"><i class="bi bi-paperclip"></i> ' + esc(md.type) + '</a>';
    });
    inner += '</div>';
    var tick = m.direction === 'out'
      ? (m.status === 'failed' ? '<i class="bi bi-exclamation-circle" style="color:#ef4444"></i>'
        : '<i class="bi bi-check2"></i>') : '';
    inner += '<div class="msg__meta">' + new Date(m.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) +
      ' ' + tick + (m.status === 'failed' && m.error ? ' <span style="color:#ef4444">' + esc(m.error) + '</span>' : '') + '</div>';
    wrapEl.innerHTML = inner;
    return wrapEl;
  }

  function appendMsgs(list) {
    var atBottom = msgsEl.scrollHeight - msgsEl.scrollTop - msgsEl.clientHeight < 80;
    list.forEach(function (m) {
      var dk = dateKey(m.created_at);
      if (dk !== S.lastDateKey) {
        var sep = document.createElement('div'); sep.className = 'ib-date'; sep.textContent = dk;
        msgsEl.appendChild(sep); S.lastDateKey = dk;
      }
      msgsEl.appendChild(msgNode(m));
      if (m.id > S.lastMsgId) S.lastMsgId = m.id;
    });
    if (atBottom) msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function openConv(id) {
    var c = S.convs.find(function (x) { return x.id === id; });
    S.activeId = id; S.activeConv = c; S.lastMsgId = 0; S.lastDateKey = null;
    msgsEl.innerHTML = '';
    emptyEl.style.display = 'none';
    bodyEl.style.display = 'flex';
    if (c) {
      $('ib-th-name').textContent = c.name;
      $('ib-th-sub').innerHTML = '<i class="bi bi-' + chIcon(c.channel_type) + '"></i> ' +
        (c.username ? '@' + esc(c.username) : c.channel_type);
      var a = $('ib-th-avatar');
      a.style.background = avaColor(c.name); a.textContent = initials(c.name);
      c.unread = 0;
    }
    renderList();
    if (window.matchMedia('(max-width:768px)').matches) {
      wrap.classList.add('mobile-thread');
      $('ib-back').style.display = '';
    }
    fetchThread(true);
    scheduleThread();
  }

  function fetchThread(initial) {
    if (!S.activeId || S.threadBusy) return;
    S.threadBusy = true;
    var url = '/inbox/conversations/' + S.activeId + '/messages';
    if (!initial && S.lastMsgId) url += '?after=' + S.lastMsgId;
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.conversation || data.conversation.id !== S.activeId) return;
        appendMsgs(data.messages || []);
      })
      .catch(function () {})
      .finally(function () { S.threadBusy = false; });
  }
  function scheduleThread() {
    clearTimeout(S.threadTimer);
    S.threadTimer = setTimeout(function () {
      if (!document.hidden && S.activeId) fetchThread(false);
      scheduleThread();
    }, 5000);
  }

  // ---- composer -------------------------------------------------
  function autoGrow() { textEl.style.height = 'auto'; textEl.style.height = Math.min(textEl.scrollHeight, 140) + 'px'; }
  textEl.addEventListener('input', autoGrow);
  textEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('ib-compose').requestSubmit(); }
  });
  fileEl.addEventListener('change', function () {
    if (fileEl.files[0]) { $('ib-filename').textContent = fileEl.files[0].name; filePrev.style.display = 'flex'; }
    else filePrev.style.display = 'none';
  });
  $('ib-fileclear').addEventListener('click', function () { fileEl.value = ''; filePrev.style.display = 'none'; });

  $('ib-compose').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!S.activeId) return;
    var txt = textEl.value.trim();
    if (!txt && !fileEl.files[0]) return;
    var fd = new FormData();
    fd.append('text', textEl.value);
    if (fileEl.files[0]) fd.append('file', fileEl.files[0]);
    sendBtn.disabled = true;
    fetch('/inbox/conversations/' + S.activeId + '/reply', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.message) appendMsgs([data.message]);
        if (!data.ok) showToast(data.error || 'Не вдалося надіслати', 'error');
        else {
          textEl.value = ''; autoGrow();
          fileEl.value = ''; filePrev.style.display = 'none';
          pollList();
        }
      })
      .catch(function () { showToast('Помилка мережі', 'error'); })
      .finally(function () { sendBtn.disabled = false; });
  });

  // ---- header actions -----------------------------------------
  $('ib-back').addEventListener('click', function () { wrap.classList.remove('mobile-thread'); });

  [].forEach.call(document.querySelectorAll('.ib-tab'), function (t) {
    t.addEventListener('click', function () {
      S.filter = t.dataset.filter;
      document.querySelectorAll('.ib-tab').forEach(function (x) { x.classList.toggle('active', x === t); });
      pollList();
    });
  });
  searchEl.addEventListener('input', function () { S.search = searchEl.value.trim().toLowerCase(); renderList(); });

  // ---- new conversation -----------------------------------------
  var newConvBtn = $('ib-new-conv');
  if (newConvBtn && newModal) {
    newConvBtn.addEventListener('click', function () {
      $('ib-new-query').value = '';
      newModal.style.display = 'flex';
    });
    newModal.addEventListener('click', function (e) { if (e.target === newModal) newModal.style.display = 'none'; });
    $('ib-new-cancel').addEventListener('click', function () { newModal.style.display = 'none'; });
    $('ib-new-submit').addEventListener('click', function () {
      var channelId = +$('ib-new-channel').value;
      var query = $('ib-new-query').value.trim();
      if (!query) { showToast('Вкажіть номер або username', 'error'); return; }
      fetch('/inbox/conversations/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: channelId, query: query }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) { showToast(data.error || 'Помилка', 'error'); return; }
          newModal.style.display = 'none';
          var existing = S.convs.some(function (c) { return c.id === data.conversation.id; });
          if (!existing) S.convs.unshift(data.conversation);
          renderList();
          openConv(data.conversation.id);
        })
        .catch(function () { showToast('Помилка мережі', 'error'); });
    });
  }

  // ---- sound --------------------------------------------------
  try { S.soundOn = localStorage.getItem('ibSound') === '1'; } catch (e) {}
  function paintSound() { soundBtn.classList.toggle('active', S.soundOn); soundBtn.querySelector('i').className = S.soundOn ? 'bi bi-bell-fill' : 'bi bi-bell'; }
  paintSound();
  soundBtn.addEventListener('click', function () {
    S.soundOn = !S.soundOn;
    try { localStorage.setItem('ibSound', S.soundOn ? '1' : '0'); } catch (e) {}
    paintSound();
    if (S.soundOn) beep();
  });
  function beep() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = 660; g.gain.value = 0.05;
      o.start(); o.stop(ctx.currentTime + 0.15);
    } catch (e) {}
  }

  // ---- lightbox ----------------------------------------------
  msgsEl.addEventListener('click', function (e) {
    if (e.target.classList.contains('msg__img')) {
      lightbox.querySelector('img').src = e.target.dataset.full;
      lightbox.style.display = 'flex';
    }
  });
  lightbox.addEventListener('click', function () { lightbox.style.display = 'none'; lightbox.querySelector('img').src = ''; });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { pollList(); if (S.activeId) fetchThread(false); }
  });

  pollList();
})();
