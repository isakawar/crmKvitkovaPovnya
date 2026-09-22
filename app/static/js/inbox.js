(function () {
  'use strict';

  var S = {
    filter: 'all',
    search: '',
    activeId: null,
    activeConv: null,
    lastMsgId: 0,
    firstMsgId: 0,
    hasMore: false,
    loadingOlder: false,
    convs: [],
    listTimer: null,
    threadTimer: null,
    listBusy: false,
    threadBusy: false,
    lastDateKey: null,
    firstDateKey: null,
    soundOn: false,
    replyTo: null,
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
  var clientPanelEl = $('ib-client-panel');
  var ME = window.IB_USER_ID;

  // The shared order/subscription composer (orders/_composer_script.html)
  // calls softReload()/softReloadWithToast() after a successful save, which
  // does a full page reload — fine on /orders, but on /inbox it would drop
  // the open conversation. Replace it with an in-place refresh instead.
  window.softReload = function () {
    var pending = null;
    try {
      var raw = sessionStorage.getItem('__pending_toast');
      if (raw) { pending = JSON.parse(raw); sessionStorage.removeItem('__pending_toast'); }
    } catch (e) {}
    if (window.bootstrap) {
      [].forEach.call(document.querySelectorAll('.modal.show'), function (m) {
        var inst = bootstrap.Modal.getInstance(m);
        if (inst) inst.hide();
      });
    }
    if (pending && pending.msg) showToast(pending.msg, pending.type);
    pollList();
    if (S.activeId) { fetchThread(false); fetchClientPanel(S.activeId); }
  };

  function chIcon(t) { return t === 'instagram' ? 'instagram' : (t === 'whatsapp' ? 'whatsapp' : 'telegram'); }
  function chCornerHtml(t) { return t === 'viber' ? 'V' : '<i class="bi bi-' + chIcon(t) + '"></i>'; }
  // Only Telegram's send APIs (Business + personal MTProto) support quoting
  // an arbitrary message; other providers' send APIs don't.
  function canReplyChannel(t) { return t === 'telegram' || t === 'telegram_personal'; }
  function chBadge(t) {
    if (t === 'viber') return '<span title="Viber" style="display:inline-flex;align-items:center;justify-content:center;width:13px;height:13px;border-radius:50%;background:#7360F2;color:#fff;font-size:0.55rem;font-weight:700;">V</span>';
    var label = t === 'instagram' ? 'Instagram' : (t === 'whatsapp' ? 'WhatsApp' : (t === 'telegram_personal' ? 'Telegram (особистий)' : 'Telegram'));
    return '<i class="bi bi-' + chIcon(t) + '" title="' + label + '"></i>';
  }

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
  // Patches existing .conv nodes in place (keyed by data-id) instead of
  // tearing down and rebuilding the whole list on every poll/SSE tick —
  // avoids the flicker and re-bound-listener churn of a full innerHTML swap.
  function convBody(c) {
    return '<div class="conv__avatar" style="background:' + avaColor(c.name) + '">' + esc(initials(c.name)) +
      '<span class="conv__ch ' + esc(c.channel_type) + '">' + chCornerHtml(c.channel_type) + '</span></div>' +
      '<div class="conv__body">' +
      '<div class="conv__top"><span class="conv__name">' + esc(c.name) + '</span>' +
      '<span class="conv__time">' + relTime(c.last_message_at) + '</span></div>' +
      '<div class="conv__preview">' + (c.direction === 'out' ? '<i class="bi bi-reply"></i> ' : '') +
      esc(c.preview) + (c.unread ? '<span class="conv__badge">' + c.unread + '</span>' : '') + '</div>' +
      (c.assigned_user_id ? '<div class="conv__assigned"><i class="bi bi-person-fill"></i>' +
        (c.assigned_user_id === ME ? 'ви' : 'інший менеджер') + '</div>' : '') +
      '</div>';
  }
  function renderList() {
    var items = S.convs.filter(function (c) {
      return !S.search || (c.name || '').toLowerCase().indexOf(S.search) !== -1
        || (c.username || '').toLowerCase().indexOf(S.search) !== -1;
    });
    if (!items.length) {
      listEl.innerHTML = '<p style="padding:1.2rem;color:#a8a29e;font-size:0.85rem;text-align:center;">Порожньо</p>';
      return;
    }
    var existing = {};
    [].forEach.call(listEl.querySelectorAll('.conv'), function (el) { existing[el.dataset.id] = el; });
    var seen = {}, prev = null;
    items.forEach(function (c) {
      var key = String(c.id);
      seen[key] = true;
      var el = existing[key];
      if (!el) {
        el = document.createElement('div');
        el.dataset.id = c.id;
        el.addEventListener('click', function () { openConv(+el.dataset.id); });
      }
      el.className = 'conv' + (c.id === S.activeId ? ' active' : '') + (c.unread ? ' unread' : '');
      el.innerHTML = convBody(c);
      var wantAfter = prev ? prev.nextSibling : listEl.firstChild;
      if (wantAfter !== el) listEl.insertBefore(el, wantAfter);
      prev = el;
    });
    Object.keys(existing).forEach(function (key) {
      if (!seen[key]) existing[key].remove();
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
    if (!b) return;
    var next = n > 99 ? '99+' : String(n);
    if (b.textContent !== next) {
      b.textContent = next;
      b.classList.remove('ib-pop');
      void b.offsetWidth; // restart the animation even if it's already mid-play
      b.classList.add('ib-pop');
    }
    b.style.display = n > 0 ? '' : 'none';
  }

  // ---- thread -----------------------------------------------------
  // Consecutive messages from the same sender within a minute are visually
  // grouped (tighter spacing) — checked against whatever is currently the
  // last rendered node, so it stays correct across SSE/poll/optimistic races
  // without any extra state to keep in sync.
  function shouldGroup(m) {
    var last = msgsEl.lastElementChild;
    if (!last || !last.classList.contains('msg')) return false;
    if (last.dataset.dir !== m.direction) return false;
    if (m.direction === 'out' && last.dataset.sender !== String(m.sender_user_id == null ? '' : m.sender_user_id)) return false;
    var gap = new Date(m.created_at).getTime() - (+last.dataset.ts || 0);
    return gap >= 0 && gap < 60000;
  }

  // 'read' only ever comes from a provider that reports it (telegram_personal);
  // elsewhere an outbound message stays 'sent' and keeps the single tick.
  function tickHtml(status, direction) {
    if (direction !== 'out') return '';
    if (status === 'failed') return '<i class="bi bi-exclamation-circle" style="color:#ef4444"></i>';
    if (status === 'pending') return '<i class="bi bi-clock" style="opacity:.5"></i>';
    if (status === 'read') return '<i class="bi bi-check2-all" style="color:#0ea5e9"></i>';
    return '<i class="bi bi-check2"></i>';
  }

  function reactionsHtml(list) {
    if (!list || !list.length) return '';
    return '<div class="msg__reactions">' + list.map(function (r) {
      return '<span class="msg__reaction' + (r.mine ? ' mine' : '') + '">' + esc(r.emoji) +
        (r.count > 1 ? ' ' + r.count : '') + '</span>';
    }).join('') + '</div>';
  }

  // Reactions and read marks change messages already on screen, which the
  // after_id poll never returns — patch them in place instead.
  function applyStates(states) {
    (states || []).forEach(function (st) {
      var node = msgsEl.querySelector('[data-mid="' + st.id + '"]');
      if (!node) return;
      var tickEl = node.querySelector('.msg__tick');
      if (tickEl) tickEl.innerHTML = tickHtml(st.status, node.dataset.dir);
      var bubble = node.querySelector('.msg__bubble');
      if (!bubble) return;
      var current = bubble.querySelector('.msg__reactions');
      var html = reactionsHtml(st.reactions);
      if (!html) { if (current) current.remove(); return; }
      if (current) current.outerHTML = html;
      else bubble.insertAdjacentHTML('beforeend', html);
    });
  }

  function msgNode(m, opts) {
    opts = opts || {};
    var wrapEl = document.createElement('div');
    wrapEl.className = 'msg ' + m.direction + (m.status === 'failed' ? ' failed' : '') +
      (m.status === 'pending' ? ' pending' : '') + (opts.grouped ? ' grouped' : '') + (opts.animate === false ? ' no-anim' : '');
    if (m.id != null) wrapEl.dataset.mid = m.id;
    wrapEl.dataset.dir = m.direction;
    wrapEl.dataset.sender = m.sender_user_id == null ? '' : String(m.sender_user_id);
    wrapEl.dataset.ts = String(new Date(m.created_at).getTime());
    wrapEl.dataset.text = m.text || '';
    var inner = '<div class="msg__bubble">';
    if (m.reply_to) inner += '<div class="msg__quote">' + esc(m.reply_to.text) + '</div>';
    if (m.text) inner += esc(m.text);
    (m.media || []).forEach(function (md) {
      if (md.type === 'uploading') inner += '<div class="msg__file"><i class="bi bi-arrow-repeat"></i> ' + esc(md.filename || 'файл') + '</div>';
      else if (md.expired) inner += '<div class="msg__file" style="color:#a8a29e"><i class="bi bi-slash-circle"></i> Вкладення видалено (14 днів)</div>';
      else if (md.type === 'photo') inner += '<img class="msg__img" data-full="/inbox/media/' + m.id + '/' + md.idx + '" src="/inbox/media/' + m.id + '/' + md.idx + '" alt="">';
      else inner += '<a class="msg__file" href="/inbox/media/' + m.id + '/' + md.idx + '" target="_blank"><i class="bi bi-paperclip"></i> ' + esc(md.type) + '</a>';
    });
    inner += reactionsHtml(m.reactions);
    inner += '</div>';
    inner += '<div class="msg__meta">' + chBadge(m.channel_type) + ' ' +
      new Date(m.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) +
      ' <span class="msg__tick">' + tickHtml(m.status, m.direction) + '</span>' +
      (m.id != null && canReplyChannel(m.channel_type) ? ' <i class="bi bi-reply msg__reply-btn" title="Відповісти"></i>' : '') +
      (m.status === 'failed' && m.error ? ' <span style="color:#ef4444">' + esc(m.error) + '</span>' : '') + '</div>';
    wrapEl.innerHTML = inner;
    return wrapEl;
  }

  function scrollToBottom(smooth) {
    if (smooth) msgsEl.scrollTo({ top: msgsEl.scrollHeight, behavior: 'smooth' });
    else msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  // animate=false for the initial page of a just-opened thread (a wall of
  // fade-ins looks like jank, not polish); true for genuinely new messages
  // arriving live (poll/SSE/reply response).
  function appendMsgs(list, animate) {
    var atBottom = msgsEl.scrollHeight - msgsEl.scrollTop - msgsEl.clientHeight < 80;
    list.forEach(function (m) {
      // A message can reach us twice — once via the SSE-triggered refetch,
      // once via the reply request's own response — whichever lands first
      // wins, the other is a cursor-bookkeeping no-op.
      if (m.id != null && msgsEl.querySelector('[data-mid="' + m.id + '"]')) {
        if (m.id > S.lastMsgId) S.lastMsgId = m.id;
        if (!S.firstMsgId || m.id < S.firstMsgId) S.firstMsgId = m.id;
        return;
      }
      var grouped = shouldGroup(m);
      var dk = dateKey(m.created_at);
      if (dk !== S.lastDateKey) {
        grouped = false;
        var sep = document.createElement('div'); sep.className = 'ib-date'; sep.textContent = dk;
        msgsEl.appendChild(sep); S.lastDateKey = dk;
      }
      msgsEl.appendChild(msgNode(m, { grouped: grouped, animate: animate }));
      if (m.id > S.lastMsgId) S.lastMsgId = m.id;
      if (!S.firstMsgId || m.id < S.firstMsgId) { S.firstMsgId = m.id; S.firstDateKey = dk; }
    });
    if (atBottom) scrollToBottom(!!animate);
  }

  // ---- optimistic outbound bubble ----------------------------------
  function appendOptimistic(m) {
    var atBottom = msgsEl.scrollHeight - msgsEl.scrollTop - msgsEl.clientHeight < 80;
    var grouped = shouldGroup(m);
    var dk = dateKey(m.created_at);
    if (dk !== S.lastDateKey) {
      grouped = false;
      var sep = document.createElement('div'); sep.className = 'ib-date'; sep.textContent = dk;
      msgsEl.appendChild(sep); S.lastDateKey = dk;
    }
    var node = msgNode(m, { grouped: grouped, animate: true });
    node.dataset.tid = m.tid;
    msgsEl.appendChild(node);
    if (atBottom) scrollToBottom(true);
  }
  function removeOptimistic(tid) {
    var node = msgsEl.querySelector('[data-tid="' + tid + '"]');
    if (node) node.remove();
  }
  function markOptimisticFailed(tid, errText) {
    var node = msgsEl.querySelector('[data-tid="' + tid + '"]');
    if (!node) return;
    node.className = 'msg out failed';
    var meta = node.querySelector('.msg__meta');
    if (meta) meta.innerHTML += ' <span style="color:#ef4444">' + esc(errText) + '</span>';
  }

  // Older messages, prepended on scroll-to-top (see loadOlderMessages).
  function prependMsgs(list) {
    if (!list.length) return;
    var oldScrollHeight = msgsEl.scrollHeight;
    var oldScrollTop = msgsEl.scrollTop;
    var firstDateKeyBefore = S.firstDateKey;
    var frag = document.createDocumentFragment();
    var localLastDateKey = null;
    list.forEach(function (m) {
      var dk = dateKey(m.created_at);
      if (dk !== localLastDateKey) {
        if (dk !== firstDateKeyBefore) {
          var sep = document.createElement('div'); sep.className = 'ib-date'; sep.textContent = dk;
          frag.appendChild(sep);
        }
        localLastDateKey = dk;
      }
      frag.appendChild(msgNode(m, { animate: false }));
    });
    msgsEl.insertBefore(frag, msgsEl.firstChild);
    S.firstMsgId = list[0].id;
    S.firstDateKey = dateKey(list[0].created_at);
    msgsEl.scrollTop = msgsEl.scrollHeight - oldScrollHeight + oldScrollTop;
  }

  function loadOlderMessages() {
    if (!S.activeId || S.loadingOlder || !S.hasMore || !S.firstMsgId) return;
    S.loadingOlder = true;
    fetch('/inbox/conversations/' + S.activeId + '/messages?before=' + S.firstMsgId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.conversation || data.conversation.id !== S.activeId) return;
        S.hasMore = !!data.has_more;
        prependMsgs(data.messages || []);
      })
      .catch(function () {})
      .finally(function () { S.loadingOlder = false; });
  }
  msgsEl.addEventListener('scroll', function () {
    if (msgsEl.scrollTop < 40) loadOlderMessages();
  });

  function openConv(id) {
    var c = S.convs.find(function (x) { return x.id === id; });
    S.activeId = id; S.activeConv = c; S.lastMsgId = 0; S.lastDateKey = null;
    S.firstMsgId = 0; S.firstDateKey = null; S.hasMore = false; S.loadingOlder = false;
    clearReplyTarget();
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
    fetchClientPanel(id);
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
        if (initial) S.hasMore = !!data.has_more;
        appendMsgs(data.messages || [], !initial);
        applyStates(data.states);
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

  // ---- client panel -----------------------------------------------
  var clientSearchDebounce = null;

  function fetchClientPanel(convId) {
    clientPanelEl.innerHTML = '';
    fetch('/inbox/conversations/' + convId + '/client-panel')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (convId === S.activeId) renderClientPanel(data);
      })
      .catch(function () {});
  }

  function ddmmyyyy(iso) {
    if (!iso) return '';
    var p = iso.split('-');
    return p.length === 3 ? p[2] + '.' + p[1] + '.' + p[0] : iso;
  }
  function deliveryNode(d) {
    return '<div class="icp-delivery" data-order-id="' + (d.order_id || '') + '" data-subscription-id="' + (d.subscription_id || '') + '">' +
      '<div class="icp-delivery__top"><span>' + esc(ddmmyyyy(d.date)) + '</span><span>' + esc(d.status || '') + '</span></div>' +
      '<div class="icp-delivery__addr">' + esc([d.size, d.address].filter(Boolean).join(' · ')) + '</div></div>';
  }

  // Opens the shared order-composer modal (also used by /orders and
  // /integrations/wix-leads) in place, so a delivery/subscription can be
  // edited without leaving the conversation.
  function openSubscriptionEditorById(subId) {
    if (!subId || !window.orderComposerApi) return;
    fetch('/subscriptions/' + subId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.id) window.orderComposerApi.openSubscriptionEditor(data);
        else showToast(data.error || 'Не вдалося завантажити підписку', 'error');
      })
      .catch(function () { showToast('Помилка мережі', 'error'); });
  }
  function openDeliveryEditor(orderId, subscriptionId) {
    if (!window.orderComposerApi) return;
    if (subscriptionId) openSubscriptionEditorById(subscriptionId);
    else if (orderId) window.orderComposerApi.openOrderEditor(orderId);
  }

  function renderClientPanel(data) {
    if (data.linked && data.client) {
      var c = data.client;
      var html = '<div class="icp-title">Клієнт</div>' +
        '<div class="icp-name">' + esc(c.name) + '</div>';
      if (c.phone) html += '<div class="icp-row"><i class="bi bi-telephone"></i> ' + esc(c.phone) + '</div>';
      if (c.instagram) html += '<div class="icp-row"><i class="bi bi-instagram"></i> ' + esc(c.instagram) + '</div>';
      if (c.telegram) html += '<div class="icp-row"><i class="bi bi-telegram"></i> ' + esc(c.telegram) + '</div>';
      html += '<div class="icp-stats">' +
        '<div class="icp-stat"><b>' + esc(c.personal_discount || '0') + '%</b><span>знижка</span></div>' +
        '<div class="icp-stat"><b>' + c.credits.toFixed(0) + '</b><span>баланс</span></div>' +
        '</div>' +
        '<button type="button" class="icp-link" id="icp-open-client" style="background:none;border:none;padding:0;font:inherit;cursor:pointer;"><i class="bi bi-box-arrow-up-right"></i> Картка клієнта</button>';
      if (data.subscription) {
        var s = data.subscription;
        html += '<div class="icp-title" style="margin-top:1rem;">Підписка</div>' +
          '<div class="icp-sub" id="icp-sub-edit" data-id="' + s.id + '" style="cursor:pointer;"><i class="bi bi-arrow-repeat"></i> ' + esc(s.type) +
          (s.is_wedding ? ' · весільна' : '') + ', ' + esc(s.size) +
          '<div class="icp-delivery__addr">Доставка щотижня: ' + esc(s.delivery_day) + '</div></div>';
      }
      html += '<div class="icp-title" style="margin-top:1rem;">Доставки</div>';
      if (data.deliveries.length) {
        html += data.deliveries.map(deliveryNode).join('');
      } else {
        html += '<div class="icp-empty" style="margin-top:0.5rem;">Ще не було доставок</div>';
      }
      html += '<span class="icp-unlink" id="icp-unlink"><i class="bi bi-x-circle"></i> Відв\'язати клієнта</span>';
      clientPanelEl.innerHTML = html;
      $('icp-open-client').addEventListener('click', function () {
        if (window.loadClientData) window.loadClientData(c.id);
        else window.open('/clients/' + c.id, '_blank');
      });
      var subEditEl = $('icp-sub-edit');
      if (subEditEl) subEditEl.addEventListener('click', function () { openSubscriptionEditorById(+subEditEl.dataset.id); });
      [].forEach.call(clientPanelEl.querySelectorAll('.icp-delivery'), function (el) {
        el.addEventListener('click', function () {
          openDeliveryEditor(el.dataset.orderId ? +el.dataset.orderId : null,
                             el.dataset.subscriptionId ? +el.dataset.subscriptionId : null);
        });
      });
      $('icp-unlink').addEventListener('click', function () {
        if (!S.activeId) return;
        fetch('/inbox/conversations/' + S.activeId + '/unlink-client', { method: 'POST' })
          .then(function () { fetchClientPanel(S.activeId); });
      });
    } else {
      clientPanelEl.innerHTML = '<div class="icp-title">Клієнт не привʼязаний</div>' +
        '<div class="icp-search"><input type="text" id="icp-search-input" placeholder="Пошук за іменем/телефоном..."></div>' +
        '<div id="icp-search-results"></div>';
      var input = $('icp-search-input');
      input.addEventListener('input', function () {
        var q = input.value.trim();
        clearTimeout(clientSearchDebounce);
        clientSearchDebounce = setTimeout(function () { runClientSearch(q); }, 300);
      });
    }
  }

  function runClientSearch(q) {
    var resEl = $('icp-search-results');
    if (!resEl) return;
    if (!q) { resEl.innerHTML = ''; return; }
    fetch('/inbox/clients/search?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!resEl) return;
        var again = $('icp-search-results');
        if (!again) return;
        var clients = data.clients || [];
        if (!clients.length) { again.innerHTML = '<div class="icp-empty">Нічого не знайдено</div>'; return; }
        again.innerHTML = clients.map(function (c) {
          var contacts = [
            c.phone ? '<span class="icp-result__contact"><i class="bi bi-telephone"></i>' + esc(c.phone) + '</span>' : '',
            c.instagram ? '<span class="icp-result__contact"><i class="bi bi-instagram"></i>' + esc(c.instagram) + '</span>' : '',
            c.telegram ? '<span class="icp-result__contact"><i class="bi bi-telegram"></i>' + esc(c.telegram) + '</span>' : '',
          ].filter(Boolean).join('');
          return '<div class="icp-result" data-id="' + c.id + '">' +
            '<div class="icp-result__name">' + esc(c.name) + '</div>' +
            (contacts ? '<div class="icp-result__sub">' + contacts + '</div>' : '') + '</div>';
        }).join('');
        [].forEach.call(again.querySelectorAll('.icp-result'), function (el) {
          el.addEventListener('click', function () {
            if (!S.activeId) return;
            fetch('/inbox/conversations/' + S.activeId + '/link-client', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ client_id: +el.dataset.id }),
            })
              .then(function (r) { return r.json(); })
              .then(function (resp) {
                if (resp.ok) renderClientPanel(resp.panel);
                else showToast(resp.error || 'Помилка', 'error');
              });
          });
        });
      })
      .catch(function () {});
  }

  // ---- reply target -----------------------------------------------
  function setReplyTarget(id, text) {
    S.replyTo = { id: id, text: text || '(без тексту)' };
    renderReplyPreview();
    textEl.focus();
  }
  function clearReplyTarget() {
    S.replyTo = null;
    renderReplyPreview();
  }
  function renderReplyPreview() {
    var el = $('ib-reply-preview');
    if (!el) return;
    if (S.replyTo) {
      el.querySelector('.ib-reply-preview__text').textContent = S.replyTo.text;
      el.classList.add('show');
    } else {
      el.classList.remove('show');
    }
  }
  $('ib-reply-cancel').addEventListener('click', clearReplyTarget);

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
    var file = fileEl.files[0];
    if (!txt && !file) return;
    var fd = new FormData();
    fd.append('text', textEl.value);
    if (file) fd.append('file', file);
    if (S.replyTo) fd.append('reply_to', S.replyTo.id);

    // Show the bubble immediately (Telegram-Desktop-style instant echo)
    // instead of waiting for the round trip; reconciled or marked failed
    // once the real response (or the SSE ping for it) comes back.
    var tid = 'tmp' + Date.now() + Math.random().toString(36).slice(2);
    appendOptimistic({
      tid: tid, direction: 'out', status: 'pending', sender_user_id: ME,
      text: txt || null,
      reply_to: S.replyTo ? { id: S.replyTo.id, text: S.replyTo.text } : null,
      media: file ? [{ type: 'uploading', filename: file.name }] : [],
      channel_type: S.activeConv ? S.activeConv.channel_type : '',
      created_at: new Date().toISOString(),
    });

    sendBtn.disabled = true;
    textEl.value = ''; autoGrow();
    fileEl.value = ''; filePrev.style.display = 'none';
    clearReplyTarget();

    fetch('/inbox/conversations/' + S.activeId + '/reply', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        removeOptimistic(tid);
        if (data.message) appendMsgs([data.message], true);
        if (!data.ok) showToast(data.error || 'Не вдалося надіслати', 'error');
        else pollList();
      })
      .catch(function () {
        markOptimisticFailed(tid, 'Помилка мережі');
        showToast('Помилка мережі', 'error');
      })
      .finally(function () { sendBtn.disabled = false; });
  });

  // ---- header actions -----------------------------------------
  $('ib-back').addEventListener('click', function () { wrap.classList.remove('mobile-thread'); });

  function refreshActiveThread() {
    var btn = $('ib-refresh');
    btn.classList.remove('spinning');
    void btn.offsetWidth;
    btn.classList.add('spinning');
    fetchThread(false);
    fetchClientPanel(S.activeId);
    pollList();
  }

  // telegram_personal is a real MTProto session with full server-side
  // history — other channels are webhook-only and only ever see what
  // arrived after the webhook was registered, so there's nothing to backfill.
  $('ib-refresh').addEventListener('click', function () {
    if (!S.activeId) return;
    if (S.activeConv && S.activeConv.channel_type === 'telegram_personal') {
      $('ib-backfill-menu').classList.toggle('show');
      return;
    }
    refreshActiveThread();
  });
  [].forEach.call(document.querySelectorAll('#ib-backfill-menu button'), function (btn) {
    btn.addEventListener('click', function () {
      $('ib-backfill-menu').classList.remove('show');
      if (!S.activeId) return;
      fetch('/inbox/conversations/' + S.activeId + '/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: +btn.dataset.days }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) showToast('Запит надіслано — повідомлення підтягнуться за кілька секунд', 'success');
          else showToast(data.error || 'Помилка', 'error');
        })
        .catch(function () { showToast('Помилка мережі', 'error'); });
    });
  });
  document.addEventListener('click', function (e) {
    var menu = $('ib-backfill-menu');
    if (menu.classList.contains('show') && !menu.contains(e.target) && e.target.closest('#ib-refresh') == null) {
      menu.classList.remove('show');
    }
  });

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
      newModal.classList.add('show');
    });
    newModal.addEventListener('click', function (e) { if (e.target === newModal) newModal.classList.remove('show'); });
    $('ib-new-cancel').addEventListener('click', function () { newModal.classList.remove('show'); });
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
          newModal.classList.remove('show');
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

  // ---- lightbox / failed-message retry ------------------------
  msgsEl.addEventListener('click', function (e) {
    if (e.target.classList.contains('msg__img')) {
      lightbox.querySelector('img').src = e.target.dataset.full;
      lightbox.classList.add('show');
      return;
    }
    var replyBtn = e.target.closest('.msg__reply-btn');
    if (replyBtn) {
      var replyMsgEl = replyBtn.closest('.msg');
      if (replyMsgEl && replyMsgEl.dataset.mid) setReplyTarget(+replyMsgEl.dataset.mid, replyMsgEl.dataset.text);
      return;
    }
    // Tap a failed outgoing bubble to get its text back in the composer —
    // the original File object (if any) is gone after upload, so a photo
    // send still needs re-attaching by hand.
    var failedEl = e.target.closest('.msg.failed');
    if (failedEl && S.activeId) {
      var text = failedEl.dataset.text || '';
      if (text) {
        textEl.value = text;
        autoGrow();
        textEl.focus();
      }
      showToast(text ? 'Текст повернуто в поле — надішліть ще раз' : 'Прикріпіть файл і надішліть ще раз', 'error');
    }
  });
  lightbox.addEventListener('click', function () {
    lightbox.classList.remove('show');
    setTimeout(function () { lightbox.querySelector('img').src = ''; }, 200);
  });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { pollList(); if (S.activeId) fetchThread(false); }
  });

  // ---- live push (SSE) ------------------------------------------
  // Carries no payload beyond channel/conversation ids — just tells us
  // *something* changed so we refetch instantly instead of waiting up to
  // 10s/5s for the next poll. The polling loops above stay as-is and keep
  // things correct even if this connection is unavailable or drops.
  var sseListTimer = null, sseThreadTimer = null;
  function connectStream() {
    if (!window.EventSource) return;
    var es = new EventSource('/inbox/stream');
    es.onmessage = function (e) {
      if (!e.data) return;
      var data;
      try { data = JSON.parse(e.data); } catch (err) { return; }
      if (data.type === 'backfill_done') {
        showToast(data.imported ? 'Підтягнуто повідомлень: ' + data.imported : 'Нових повідомлень за цей період немає', 'success');
      } else if (data.type === 'backfill_error') {
        showToast('Не вдалося підтягнути історію: ' + (data.error || 'помилка'), 'error');
      }
      clearTimeout(sseListTimer);
      sseListTimer = setTimeout(pollList, 200);
      if (data.conversation_id && data.conversation_id === S.activeId) {
        clearTimeout(sseThreadTimer);
        sseThreadTimer = setTimeout(function () { fetchThread(false); }, 200);
      }
    };
    // EventSource retries on its own; nothing to do on error besides let it.
  }
  connectStream();

  pollList();
})();
