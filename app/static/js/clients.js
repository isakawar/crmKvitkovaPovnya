document.addEventListener('DOMContentLoaded', function () {
  const addForm = document.getElementById('addClientForm');
  const modal = document.getElementById('clientModal');
  if (!addForm || !modal) return;

  const errorDiv = document.getElementById('client-error');
  const modalTitle = document.getElementById('clientModalLabel');
  const modalDescription = document.getElementById('clientModalDescription');
  const modeBadge = document.getElementById('client-modal-mode-badge');
  const footerCopy = document.getElementById('client-footer-copy');
  const submitBtn = document.getElementById('submit-btn');
  const submitBtnText = document.getElementById('submit-btn-text');
  const addSubscriptionBtn = document.getElementById('add-subscription-btn');
  const clientIdInput = document.getElementById('client-id');
  const previewAvatar = document.getElementById('client-preview-avatar');
  const previewStatus = document.getElementById('client-preview-status');
  const previewTitle = document.getElementById('client-preview-title');
  const previewSubtitle = document.getElementById('client-preview-subtitle');
  const previewContacts = document.getElementById('client-preview-contacts');
  const previewCredits = document.getElementById('client-preview-credits');
  const previewDiscount = document.getElementById('client-preview-discount');
  const phoneInput = document.getElementById('edit-phone');
  const nameInput = document.getElementById('edit-name');
  const creditsInput = document.getElementById('edit-credits');
  const marketingSourceInput = document.getElementById('edit-marketing-source');
  const personalDiscountInput = document.getElementById('edit-personal-discount');
  const clearPhoneBtn = document.getElementById('clear-phone-btn');
  const emailInput = document.getElementById('edit-email');

  // Nick slots
  const nickSlot1 = document.getElementById('nick-slot-1');
  const nickSlot2 = document.getElementById('nick-slot-2');
  const nickInput1 = document.getElementById('nick-input-1');
  const nickInput2 = document.getElementById('nick-input-2');
  const nickPlatformBtn1 = document.getElementById('nick-platform-btn-1');
  const nickPlatformBtn2 = document.getElementById('nick-platform-btn-2');
  const nickPlatformVal1 = document.getElementById('nick-platform-val-1');
  const nickPlatformVal2 = document.getElementById('nick-platform-val-2');
  const nickPlatformIcon1 = document.getElementById('nick-platform-icon-1');
  const nickPlatformIcon2 = document.getElementById('nick-platform-icon-2');
  const addNickBtn = document.getElementById('add-nick-btn'); // may be null now
  const removeNick2Btn = document.getElementById('remove-nick-2-btn'); // may be null now

  // Hidden actual fields
  const fieldInstagram = document.getElementById('field-instagram');
  const fieldTelegram = document.getElementById('field-telegram');

  // Messenger checkboxes
  const phoneViberCheck = document.getElementById('phone-viber');
  const phoneTelegramCheck = document.getElementById('phone-telegram-check');
  const phoneWhatsappCheck = document.getElementById('phone-whatsapp');

  const modalInstance = bootstrap.Modal.getOrCreateInstance(modal);
  const phonePattern = /^\+380[0-9]{9}$/;

  let isEditMode = false;
  let isSubmitting = false;
  let currentClientLabel = '';

  // Platform icons map
  const platformConfig = {
    instagram: { icon: 'bi-instagram', label: 'Instagram', placeholder: 'username' },
    telegram:  { icon: 'bi-telegram',  label: 'Telegram',  placeholder: '@username' },
  };

  const nickInputs = [null, nickInput1, nickInput2];

  function setPlatform(slot, platform) {
    const btn  = slot === 1 ? nickPlatformBtn1 : nickPlatformBtn2;
    const icon = slot === 1 ? nickPlatformIcon1 : nickPlatformIcon2;
    const val  = slot === 1 ? nickPlatformVal1  : nickPlatformVal2;
    const input = nickInputs[slot];
    const cfg  = platformConfig[platform];
    icon.className = `bi ${cfg.icon} text-base`;
    val.value = platform;
    btn.title = cfg.label;
    if (input) input.placeholder = cfg.placeholder;
    syncNickFields();
  }

  function togglePlatform(slot) {
    const otherPlatform = slot === 1 ? nickPlatformVal2.value : nickPlatformVal1.value;
    const newPlatform = otherPlatform === 'instagram' ? 'telegram' : 'instagram';
    setPlatform(slot, newPlatform);
  }

  function syncNickFields() {
    const p1 = nickPlatformVal1.value;
    const v1 = nickInput1.value.trim().replace(/^@/, '');
    const p2 = nickPlatformVal2.value;
    const v2 = nickInput2.value.trim().replace(/^@/, '');

    fieldInstagram.value = '';
    fieldTelegram.value = '';

    if (p1 === 'instagram') fieldInstagram.value = v1;
    if (p1 === 'telegram') fieldTelegram.value = v1;
    if (p2 === 'instagram') fieldInstagram.value = v2;
    if (p2 === 'telegram') fieldTelegram.value = v2;

    updatePreviewCard();
  }

  function pluralizeContacts(count) {
    if (count === 1) return '1 канал';
    if (count >= 2 && count <= 4) return `${count} канали`;
    return `${count} каналів`;
  }

  function getPreviewIdentity() {
    const name = nameInput.value.trim();
    const instagram = fieldInstagram.value.trim().replace(/^@/, '');
    const telegram = fieldTelegram.value.trim().replace(/^@/, '');
    const phone = phoneInput.value.trim();

    if (name) return name;
    if (instagram) return `@${instagram}`;
    if (telegram) return `@${telegram}`;
    if (phone) return phone;
    return 'Новий клієнт';
  }

  function getPreviewAvatarLetter(identity) {
    const normalized = identity.replace(/^[@+\d\s()-]+/, '').trim();
    if (normalized) return normalized.charAt(0).toUpperCase();
    return isEditMode ? 'К' : 'Н';
  }

  function getPreviewSubtitle(contactCount) {
    if (!contactCount) {
      return 'Без контакту';
    }
    if (nameInput.value.trim()) {
      return nameInput.value.trim();
    }
    return pluralizeContacts(contactCount);
  }

  function updatePreviewCard() {
    if (!previewAvatar || !previewTitle || !previewSubtitle) return;

    const instagram = fieldInstagram.value.trim();
    const telegram = fieldTelegram.value.trim();
    const phone = phoneInput.value.trim();
    const contacts = [instagram, telegram, phone].filter(Boolean).length;
    const identity = getPreviewIdentity();
    const credits = creditsInput.value.trim() || '0';
    const discount = personalDiscountInput.value.trim() || '0';

    previewAvatar.textContent = getPreviewAvatarLetter(identity);
    previewStatus.textContent = isEditMode ? 'Картка клієнта' : 'Нова картка';
    previewTitle.textContent = identity;
    previewSubtitle.textContent = getPreviewSubtitle(contacts);
    previewContacts.textContent = pluralizeContacts(contacts);
    previewCredits.textContent = `${credits} ₴`;
    previewDiscount.textContent = `${discount}%`;
  }

  nickPlatformBtn1.addEventListener('click', () => togglePlatform(1));
  nickPlatformBtn2.addEventListener('click', () => togglePlatform(2));

  nickInput1.addEventListener('input', function () {
    clearNickError(1);
    syncNickFields();
    updateSubscriptionButtonState();
  });
  nickInput2.addEventListener('input', function () {
    clearNickError(2);
    syncNickFields();
    updateSubscriptionButtonState();
  });

  // Mode content
  const modeContent = {
    create: {
      badge: '<i class="bi bi-person-plus"></i> Новий клієнт',
      title: 'Створити клієнта',
      submit: 'Створити клієнта',
      loading: 'Створюємо...',
      footer: '',
    },
    edit: {
      badge: '<i class="bi bi-pencil-square"></i> Редагування',
      title: 'Редагувати клієнта',
      description: 'Редагування картки клієнта.',
      submit: 'Зберегти зміни',
      loading: 'Зберігаємо...',
      footer: '',
    },
  };

  // Click on card to edit
  document.querySelectorAll('[data-client-id]').forEach(card => {
    card.addEventListener('click', function () {
      const clientId = this.getAttribute('data-client-id');
      loadClientData(clientId);
    });
  });

  async function loadClientData(clientId) {
    try {
      const response = await fetch(`/clients/${clientId}`);
      if (response.ok) {
        const client = await response.json();
        fillFormWithClientData(client);
        isEditMode = true;
        currentClientLabel = client.instagram || client.telegram || client.phone || '';
        clientIdInput.value = clientId;
        renderMode();
        modalInstance.show();
      } else {
        showToast('Не вдалося завантажити дані клієнта', 'error');
      }
    } catch (error) {
      console.error('Помилка завантаження даних клієнта:', error);
      showToast('Не вдалося завантажити дані клієнта', 'error');
    }
  }

  function fillFormWithClientData(client) {
    // Reset nick slots first
    nickInput1.value = '';
    nickInput2.value = '';

    const hasInstagram = Boolean(client.instagram);
    const hasTelegram = Boolean(client.telegram);

    const tgWithAt = (v) => v ? (v.startsWith('@') ? v : `@${v}`) : '';

    if (hasInstagram && hasTelegram) {
      // Both: slot 1 = instagram, slot 2 = telegram
      setPlatform(1, 'instagram');
      nickInput1.value = client.instagram;
      setPlatform(2, 'telegram');
      nickInput2.value = tgWithAt(client.telegram);
    } else if (hasInstagram) {
      setPlatform(1, 'instagram');
      nickInput1.value = client.instagram;
    } else if (hasTelegram) {
      setPlatform(1, 'telegram');
      nickInput1.value = tgWithAt(client.telegram);
    }

    syncNickFields();

    phoneInput.value = client.phone || '+380';
    phoneViberCheck.checked = Boolean(client.phone_viber);
    phoneTelegramCheck.checked = Boolean(client.phone_telegram);
    phoneWhatsappCheck.checked = Boolean(client.phone_whatsapp);
    nameInput.value = client.name || '';
    if (emailInput) emailInput.value = client.email || '';
    creditsInput.value = client.credits ?? 0;
    marketingSourceInput.value = client.marketing_source || '';
    personalDiscountInput.value = client.personal_discount || '';

    const createdAtDisplay = document.getElementById('client-created-at-display');
    if (createdAtDisplay) createdAtDisplay.value = client.created_at || '—';

    clearAllErrors();
    toggleClearPhoneButton();
    updateMessengerState();
    updatePreviewCard();
  }

  modal.addEventListener('show.bs.modal', function () {
    document.body.classList.add('client-modal-open');
    if (!isEditMode) {
      renderMode();
      clearAllErrors();
      toggleClearPhoneButton();
      updateMessengerState();
      updatePreviewCard();
    }
  });

  modal.addEventListener('hidden.bs.modal', function () {
    document.body.classList.remove('client-modal-open');
    resetForm();
  });

  const deleteClientBtn = document.getElementById('delete-client-btn');

  function renderMode() {
    const content = isEditMode ? modeContent.edit : modeContent.create;
    modalTitle.textContent = isEditMode && currentClientLabel
      ? `${content.title} (${currentClientLabel})`
      : content.title;
    modalDescription.textContent = content.description;
    modeBadge.innerHTML = content.badge;
    footerCopy.textContent = content.footer;
    footerCopy.classList.toggle('hidden', !content.footer);
    if (!isSubmitting) {
      submitBtnText.textContent = content.submit;
    }
    updateSubscriptionButtonState();
    const createdAtRow = document.getElementById('client-created-at-row');
    if (createdAtRow) createdAtRow.classList.toggle('hidden', !isEditMode);
    if (deleteClientBtn) {
      deleteClientBtn.classList.toggle('hidden', !isEditMode);
      deleteClientBtn.classList.toggle('inline-flex', isEditMode);
    }
    updatePreviewCard();
  }

  if (deleteClientBtn) {
    deleteClientBtn.addEventListener('click', async function () {
      const clientId = clientIdInput.value;
      if (!clientId) return;
      if (!confirm(`Видалити клієнта "${currentClientLabel}"? Цю дію не можна скасувати.`)) return;
      try {
        const resp = await fetch(`/clients/${clientId}/delete`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
          alert(data.error || 'Не вдалося видалити клієнта');
          return;
        }
        modalInstance.hide();
        softReloadWithToast('Клієнта видалено', 'success');
      } catch (e) {
        alert('Помилка з\'єднання');
      }
    });
  }

  function resetForm() {
    addForm.reset();
    clientIdInput.value = '';
    isEditMode = false;
    isSubmitting = false;
    currentClientLabel = '';

    // Reset nick slots
    nickInput1.value = '';
    nickInput2.value = '';
    setPlatform(1, 'instagram');
    setPlatform(2, 'telegram');
    syncNickFields();

    phoneViberCheck.checked = false;
    phoneTelegramCheck.checked = false;
    phoneWhatsappCheck.checked = false;

    setSubmitState(false);
    clearAllErrors();
    toggleClearPhoneButton();
    updateMessengerState();
    renderMode();
    updatePreviewCard();
  }

  function hasAnyContact() {
    const nick1 = nickInput1.value.trim();
    const nick2 = nickInput2.value.trim();
    const phone = phoneInput.value.trim();
    return Boolean(nick1 || nick2 || (phone && phone !== '+380'));
  }

  function isSubscriptionActionAvailable() {
    if (!hasAnyContact()) return false;
    const phoneValue = phoneInput.value.trim();
    const phoneValid = !phoneValue || phonePattern.test(phoneValue);
    const creditsValue = creditsInput.value.trim();
    const creditsValid = !creditsValue || Number(creditsValue) >= 0;
    const discountValue = personalDiscountInput.value.trim();
    const discountValid = !discountValue || (!Number.isNaN(Number(discountValue)) && Number(discountValue) >= 0 && Number(discountValue) <= 100);
    return phoneValid && creditsValid && discountValid;
  }

  function updateSubscriptionButtonState() {
    if (!addSubscriptionBtn) return;
    addSubscriptionBtn.disabled = isSubmitting || !isSubscriptionActionAvailable();
  }

  function clearNickError(slot) {
    const errEl = document.getElementById(`nick-error-${slot}`);
    const input = slot === 1 ? nickInput1 : nickInput2;
    if (errEl) { errEl.textContent = ''; errEl.classList.remove('is-visible'); }
    input.classList.remove('is-invalid');
  }

  function setNickError(slot, message) {
    const errEl = document.getElementById(`nick-error-${slot}`);
    const input = slot === 1 ? nickInput1 : nickInput2;
    if (errEl) { errEl.textContent = message; errEl.classList.add('is-visible'); }
    input.classList.add('is-invalid');
  }

  function getFieldErrorElement(field) {
    return field.closest('.client-field')?.querySelector('.client-field-error');
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove('is-invalid');
    const fieldError = getFieldErrorElement(field);
    if (fieldError) {
      fieldError.textContent = '';
      fieldError.classList.remove('is-visible');
    }
  }

  function setFieldError(field, message) {
    if (!field) return;
    field.classList.add('is-invalid');
    const fieldError = getFieldErrorElement(field);
    if (fieldError) {
      fieldError.textContent = message;
      fieldError.classList.add('is-visible');
    }
  }

  function clearAllErrors() {
    errorDiv.textContent = '';
    errorDiv.innerHTML = '';
    errorDiv.classList.remove('is-visible');
    clearNickError(1);
    clearNickError(2);
    [phoneInput, creditsInput, marketingSourceInput, personalDiscountInput, nameInput].forEach(clearFieldError);
  }

  function showFormError(message) {
    errorDiv.textContent = message;
    errorDiv.classList.add('is-visible');
  }

  function showDuplicatePrompt(message, clientId) {
    errorDiv.innerHTML = '';
    const text = document.createElement('div');
    text.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'client-error-actions';
    const openBtn = document.createElement('button');
    openBtn.type = 'button';
    openBtn.className = 'client-error-action-btn';
    openBtn.textContent = 'Відкрити клієнта';
    openBtn.addEventListener('click', () => loadClientData(clientId));
    actions.appendChild(openBtn);
    errorDiv.appendChild(text);
    errorDiv.appendChild(actions);
    errorDiv.classList.add('is-visible');
  }

  function toggleClearPhoneButton() {
    if (!clearPhoneBtn) return;
    clearPhoneBtn.classList.toggle('hidden', phoneInput.value.trim().length <= 4);
  }

  function updateMessengerState() {
    const grid = document.getElementById('phone-messengers');
    if (!grid) return;
    const v = phoneInput.value.trim();
    const hasPhone = Boolean(v) && v !== '+380';
    grid.classList.toggle('opacity-40', !hasPhone);
    grid.classList.toggle('pointer-events-none', !hasPhone);
  }

  function normalizePhoneValue(value) {
    const digits = value.replace(/\D/g, '');
    if (!digits) return '';
    let normalizedDigits;
    if (digits.startsWith('380')) {
      normalizedDigits = digits;
    } else if (digits.startsWith('0')) {
      normalizedDigits = `38${digits}`;
    } else {
      normalizedDigits = `380${digits}`;
    }
    return `+${normalizedDigits.slice(0, 12)}`;
  }

  function setSubmitState(submitting) {
    isSubmitting = submitting;
    submitBtn.disabled = submitting;
    if (addSubscriptionBtn) addSubscriptionBtn.disabled = true;
    submitBtnText.textContent = submitting
      ? (isEditMode ? modeContent.edit.loading : modeContent.create.loading)
      : (isEditMode ? modeContent.edit.submit : modeContent.create.submit);
    if (!submitting) updateSubscriptionButtonState();
  }

  async function persistClient({ redirectToSubscription = false } = {}) {
    syncNickFields();
    setSubmitState(true);

    const phoneIsPrefix = phoneInput.value.trim() === '+380';
    if (phoneIsPrefix) phoneInput.value = '';
    const formData = new FormData(addForm);
    if (phoneIsPrefix) phoneInput.value = '+380';
    const url = isEditMode ? `/clients/${clientIdInput.value}` : '/clients/new';
    const resp = await fetch(url, { method: 'POST', body: formData });
    const data = await resp.json().catch(() => ({}));

    if (!(resp.ok && data.success)) {
      const message = data.error || 'Помилка збереження';
      const isDuplicate = data.type === 'duplicate' && data.client_id;

      if (data.field === 'instagram' || (typeof message === 'string' && message.toLowerCase().includes('instagram'))) {
        // Find which slot has instagram
        const slot = nickPlatformVal1.value === 'instagram' ? 1 : 2;
        setNickError(slot, message);
      } else if (data.field === 'telegram' || (typeof message === 'string' && message.toLowerCase().includes('telegram'))) {
        const slot = nickPlatformVal1.value === 'telegram' ? 1 : 2;
        setNickError(slot, message);
      } else if (data.field === 'phone' || (typeof message === 'string' && (message.toLowerCase().includes('телефон') || message.toLowerCase().includes('номер')))) {
        setFieldError(phoneInput, message);
      }

      if (isDuplicate && !isEditMode) {
        showDuplicatePrompt(message, data.client_id);
      } else if (!document.querySelector('.client-field-error.is-visible') && !getFieldErrorElement(phoneInput)?.textContent) {
        showFormError(typeof message === 'string' ? message : (message.error || 'Помилка збереження'));
      }
      return false;
    }

    if (redirectToSubscription) {
      const instagramValue = fieldInstagram.value.trim();
      const telegramValue = fieldTelegram.value.trim();
      const phoneValue = phoneInput.value.trim();
      const clientIdentifier = instagramValue || telegramValue || phoneValue;
      window.location.href = `/subscriptions?compose=subscription&client_instagram=${encodeURIComponent(clientIdentifier)}`;
      return true;
    }

    modalInstance.hide();
    softReloadWithToast(isEditMode ? 'Клієнта успішно оновлено!' : 'Клієнта успішно створено!', 'success');
    return true;
  }

  function validateForm() {
    let isValid = true;
    clearAllErrors();

    if (!hasAnyContact()) {
      setNickError(1, 'Вкажіть Instagram або Telegram нік');
      showFormError('Потрібен хоча б один контакт: Instagram, Telegram або номер телефону');
      isValid = false;
    }

    // Check both nicks don't use the same platform
    const slot2Visible = !nickSlot2.classList.contains('hidden');
    if (slot2Visible && nickInput2.value.trim() && nickPlatformVal1.value === nickPlatformVal2.value) {
      setNickError(2, 'Обидва нікнейми мають однакову платформу');
      isValid = false;
    }

    const phoneValue = phoneInput.value.trim();
    const phoneHasValue = phoneValue && phoneValue !== '+380';
    if (phoneHasValue && !phonePattern.test(phoneValue)) {
      setFieldError(phoneInput, 'Невірний формат: +380XXXXXXXXX');
      isValid = false;
    }

    const creditsValue = creditsInput.value.trim();
    if (creditsValue && Number(creditsValue) < 0) {
      setFieldError(creditsInput, 'Баланс не може бути меншими за 0');
      isValid = false;
    }

    const discountValue = personalDiscountInput.value.trim();
    if (discountValue) {
      const discount = Number(discountValue);
      if (Number.isNaN(discount) || discount < 0 || discount > 100) {
        setFieldError(personalDiscountInput, 'Знижка має бути в межах від 0 до 100');
        isValid = false;
      }
    }

    if (emailInput) {
      const emailValue = emailInput.value.trim();
      if (emailValue && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
        setFieldError(emailInput, 'Невірний формат email');
        isValid = false;
      }
    }

    return isValid;
  }

  // Phone mask
  phoneInput.addEventListener('input', function (e) {
    clearFieldError(phoneInput);
    e.target.value = normalizePhoneValue(e.target.value);
    toggleClearPhoneButton();
    updateMessengerState();
    updateSubscriptionButtonState();
    updatePreviewCard();
  });

  phoneInput.addEventListener('blur', function () {
    const v = phoneInput.value.trim();
    if (v && v !== '+380' && !phonePattern.test(v)) {
      setFieldError(phoneInput, 'Невірний формат: +380XXXXXXXXX');
    }
    updateSubscriptionButtonState();
  });

  if (clearPhoneBtn && phoneInput) {
    clearPhoneBtn.addEventListener('click', function () {
      phoneInput.value = '+380';
      clearFieldError(phoneInput);
      toggleClearPhoneButton();
      updateMessengerState();
      updateSubscriptionButtonState();
      updatePreviewCard();
      phoneInput.focus();
    });
  }

  [creditsInput, personalDiscountInput, nameInput].forEach(input => {
    input.addEventListener('input', function () {
      clearFieldError(input);
      updateSubscriptionButtonState();
      updatePreviewCard();
    });
  });

  marketingSourceInput.addEventListener('change', function () {
    clearFieldError(marketingSourceInput);
    updateSubscriptionButtonState();
    updatePreviewCard();
  });

  addForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (!validateForm()) return;
    try {
      await persistClient();
    } catch (error) {
      console.error('Помилка збереження клієнта:', error);
      showFormError('Не вдалося зберегти клієнта. Спробуйте ще раз.');
    } finally {
      setSubmitState(false);
    }
  });

  if (addSubscriptionBtn) {
    addSubscriptionBtn.addEventListener('click', async function () {
      if (!validateForm()) return;
      try {
        await persistClient({ redirectToSubscription: true });
      } catch (error) {
        console.error('Помилка під час переходу до підписки:', error);
        showFormError('Не вдалося підготувати підписку. Спробуйте ще раз.');
      } finally {
        setSubmitState(false);
      }
    });
  }

  // Init
  setPlatform(1, 'instagram');
  setPlatform(2, 'telegram');
  syncNickFields();
  renderMode();
  toggleClearPhoneButton();
  updateMessengerState();
  updateSubscriptionButtonState();
  updatePreviewCard();
});

