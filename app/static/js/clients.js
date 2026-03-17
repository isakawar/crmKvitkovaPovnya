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
  const instagramInput = document.getElementById('edit-instagram');
  const phoneInput = document.getElementById('edit-phone');
  const telegramInput = document.getElementById('edit-telegram');
  const creditsInput = document.getElementById('edit-credits');
  const marketingSourceInput = document.getElementById('edit-marketing-source');
  const personalDiscountInput = document.getElementById('edit-personal-discount');
  const clearPhoneBtn = document.getElementById('clear-phone-btn');
  const modalInstance = bootstrap.Modal.getOrCreateInstance(modal);
  const phonePattern = /^\+380[0-9]{9}$/;

  let isEditMode = false;
  let isSubmitting = false;
  let currentClientLabel = '';

  const modeContent = {
    create: {
      badge: '<i class="bi bi-person-plus"></i> Новий клієнт',
      title: 'Створити клієнта',
      description: 'Заповніть контактні дані та параметри лояльності, щоб одразу використовувати картку в замовленнях і підписках.',
      submit: 'Створити клієнта',
      loading: 'Створюємо...',
      footer: 'Поля зі зірочкою потрібні для створення картки. Інші дані можна оновити будь-коли.',
    },
    edit: {
      badge: '<i class="bi bi-pencil-square"></i> Редагування',
      title: 'Редагувати клієнта',
      description: 'Оновіть контакти або параметри лояльності. Зміни одразу збережуться в картці клієнта.',
      submit: 'Зберегти зміни',
      loading: 'Зберігаємо...',
      footer: 'Збереження оновить наявну картку клієнта. Історія замовлень та підписок залишиться без змін.',
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
        currentClientLabel = client.instagram || '';
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
    instagramInput.value = client.instagram || '';
    phoneInput.value = client.phone || '';
    telegramInput.value = client.telegram || '';
    creditsInput.value = client.credits ?? 0;
    marketingSourceInput.value = client.marketing_source || '';
    personalDiscountInput.value = client.personal_discount || '';
    clearAllErrors();
    toggleClearPhoneButton();
  }

  modal.addEventListener('show.bs.modal', function () {
    document.body.classList.add('client-modal-open');
    if (!isEditMode) {
      renderMode();
      clearAllErrors();
      toggleClearPhoneButton();
    }
  });

  modal.addEventListener('hidden.bs.modal', function () {
    document.body.classList.remove('client-modal-open');
    resetForm();
  });

  function renderMode() {
    const content = isEditMode ? modeContent.edit : modeContent.create;
    modalTitle.textContent = isEditMode && currentClientLabel
      ? `${content.title} (${currentClientLabel})`
      : content.title;
    modalDescription.textContent = content.description;
    modeBadge.innerHTML = content.badge;
    footerCopy.textContent = content.footer;
    if (!isSubmitting) {
      submitBtnText.textContent = content.submit;
    }
    updateSubscriptionButtonState();
  }

  function resetForm() {
    addForm.reset();
    clientIdInput.value = '';
    isEditMode = false;
    isSubmitting = false;
    currentClientLabel = '';
    setSubmitState(false);
    clearAllErrors();
    toggleClearPhoneButton();
    renderMode();
  }

  function isSubscriptionActionAvailable() {
    const instagramFilled = Boolean(instagramInput.value.trim());
    const phoneValue = phoneInput.value.trim();
    const phoneValid = !phoneValue || phonePattern.test(phoneValue);
    const creditsValue = creditsInput.value.trim();
    const creditsValid = !creditsValue || Number(creditsValue) >= 0;
    const discountValue = personalDiscountInput.value.trim();
    const discountValid = !discountValue || (!Number.isNaN(Number(discountValue)) && Number(discountValue) >= 0 && Number(discountValue) <= 100);

    return instagramFilled && phoneValid && creditsValid && discountValid;
  }

  function updateSubscriptionButtonState() {
    if (!addSubscriptionBtn) return;
    addSubscriptionBtn.disabled = isSubmitting || !isSubscriptionActionAvailable();
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
    [instagramInput, phoneInput, telegramInput, creditsInput, marketingSourceInput, personalDiscountInput].forEach(clearFieldError);
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
    clearPhoneBtn.classList.toggle('hidden', !phoneInput.value.trim());
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
    if (addSubscriptionBtn) {
      addSubscriptionBtn.disabled = true;
    }
    submitBtnText.textContent = submitting
      ? (isEditMode ? modeContent.edit.loading : modeContent.create.loading)
      : (isEditMode ? modeContent.edit.submit : modeContent.create.submit);
    if (!submitting) {
      updateSubscriptionButtonState();
    }
  }

  async function persistClient({ redirectToSubscription = false } = {}) {
    setSubmitState(true);

    const formData = new FormData(addForm);
    const url = isEditMode ? `/clients/${clientIdInput.value}` : '/clients/new';
    const resp = await fetch(url, { method: 'POST', body: formData });
    const data = await resp.json().catch(() => ({}));

    if (!(resp.ok && data.success)) {
      const message = data.error || 'Помилка збереження';
      const isDuplicate = data.type === 'duplicate' && data.client_id;
      if (data.field === 'instagram' || message.toLowerCase().includes('instagram')) {
        setFieldError(instagramInput, message);
      } else if (data.field === 'telegram' || message.toLowerCase().includes('telegram')) {
        setFieldError(telegramInput, message);
      } else if (data.field === 'phone' || message.toLowerCase().includes('телефон') || message.toLowerCase().includes('номер')) {
        setFieldError(phoneInput, message);
      }

      if (isDuplicate && !isEditMode) {
        showDuplicatePrompt(message, data.client_id);
      } else if (!getFieldErrorElement(instagramInput)?.textContent && !getFieldErrorElement(phoneInput)?.textContent && !getFieldErrorElement(telegramInput)?.textContent) {
        showFormError(message);
      }
      return false;
    }

    if (redirectToSubscription) {
      const instagramValue = instagramInput.value.trim();
      window.location.href = `/subscriptions?compose=subscription&client_instagram=${encodeURIComponent(instagramValue)}`;
      return true;
    }

    showToast(isEditMode ? 'Клієнта успішно оновлено!' : 'Клієнта успішно створено!', 'success');
    modalInstance.hide();
    setTimeout(() => location.reload(), 900);
    return true;
  }

  function validateForm() {
    let isValid = true;
    clearAllErrors();

    if (!instagramInput.value.trim()) {
      setFieldError(instagramInput, 'Вкажіть Instagram клієнта');
      isValid = false;
    }

    const phoneValue = phoneInput.value.trim();
    if (phoneValue && !phonePattern.test(phoneValue)) {
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

    return isValid;
  }

  // Phone mask
  phoneInput.addEventListener('input', function (e) {
    clearFieldError(phoneInput);
    e.target.value = normalizePhoneValue(e.target.value);
    toggleClearPhoneButton();
  });

  if (clearPhoneBtn && phoneInput) {
    clearPhoneBtn.addEventListener('click', function () {
      phoneInput.value = '';
      clearFieldError(phoneInput);
      toggleClearPhoneButton();
      phoneInput.focus();
    });
  }

  [instagramInput, telegramInput, creditsInput, personalDiscountInput].forEach(input => {
    input.addEventListener('input', function () {
      clearFieldError(input);
      updateSubscriptionButtonState();
    });
  });

  marketingSourceInput.addEventListener('change', function () {
    clearFieldError(marketingSourceInput);
    updateSubscriptionButtonState();
  });

  phoneInput.addEventListener('blur', function () {
    if (phoneInput.value.trim() && !phonePattern.test(phoneInput.value.trim())) {
      setFieldError(phoneInput, 'Невірний формат: +380XXXXXXXXX');
    }
    updateSubscriptionButtonState();
  });

  addForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

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
      if (!validateForm()) {
        return;
      }

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

  renderMode();
  toggleClearPhoneButton();
  updateSubscriptionButtonState();
});

function showToast(message, type = 'info') {
  const toast = document.getElementById('notification-toast');
  if (!toast) return;
  const toastBody = toast.querySelector('.toast-body');
  const toastHeader = toast.querySelector('.toast-header');
  const icon = toast.querySelector('.toast-header i');
  toastBody.textContent = message;
  toastHeader.className = 'toast-header';
  icon.className = 'me-2';
  switch (type) {
    case 'success':
      toastHeader.classList.add('bg-success', 'text-white');
      icon.classList.add('bi', 'bi-check-circle-fill');
      break;
    case 'danger': case 'error':
      toastHeader.classList.add('bg-danger', 'text-white');
      icon.classList.add('bi', 'bi-exclamation-triangle-fill');
      break;
    default:
      toastHeader.classList.add('bg-primary', 'text-white');
      icon.classList.add('bi', 'bi-info-circle');
  }
  new bootstrap.Toast(toast, { autohide: true, delay: 4000 }).show();
}
