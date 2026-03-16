document.addEventListener('DOMContentLoaded', function () {
  const addForm = document.getElementById('addClientForm');
  const errorDiv = document.getElementById('client-error');
  const phoneInput = document.getElementById('edit-phone');
  const modal = document.getElementById('clientModal');
  const modalTitle = document.getElementById('clientModalLabel');
  const submitBtn = document.getElementById('submit-btn');
  const clientIdInput = document.getElementById('client-id');
  const clearPhoneBtn = document.getElementById('clear-phone-btn');

  let isEditMode = false;

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
        modalTitle.textContent = 'Редагувати клієнта';
        submitBtn.textContent = 'Зберегти';
        clientIdInput.value = clientId;
        new bootstrap.Modal(modal).show();
      }
    } catch (error) {
      console.error('Помилка завантаження даних клієнта:', error);
    }
  }

  function fillFormWithClientData(client) {
    document.getElementById('edit-instagram').value = client.instagram;
    document.getElementById('edit-phone').value = client.phone;
    document.getElementById('edit-telegram').value = client.telegram;
    document.getElementById('edit-credits').value = client.credits;
    document.getElementById('edit-marketing-source').value = client.marketing_source;
    document.getElementById('edit-personal-discount').value = client.personal_discount;
  }

  modal.addEventListener('show.bs.modal', function () {
    if (!isEditMode) resetForm();
  });

  function resetForm() {
    addForm.reset();
    clientIdInput.value = '';
    isEditMode = false;
    modalTitle.textContent = 'Додати клієнта';
    submitBtn.textContent = 'Додати';
    errorDiv.classList.add('hidden');
  }

  // Phone mask
  phoneInput.addEventListener('input', function (e) {
    let value = e.target.value.replace(/\D/g, '');
    if (value.length === 0) { e.target.value = '+38'; return; }
    if (value.startsWith('380')) {
      e.target.value = '+' + value;
    } else if (value.startsWith('38')) {
      e.target.value = '+' + value;
    } else if (value.startsWith('0')) {
      e.target.value = '+38' + value;
    } else {
      e.target.value = '+380' + value;
    }
    if (e.target.value.length > 13) e.target.value = e.target.value.substring(0, 13);
  });

  if (clearPhoneBtn && phoneInput) {
    clearPhoneBtn.addEventListener('click', function () {
      phoneInput.value = '';
      phoneInput.focus();
    });
  }

  addForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    errorDiv.classList.add('hidden');
    const phoneValue = phoneInput.value.trim();
    const phonePattern = /^\+380[0-9]{9}$/;
    if (phoneValue && phoneValue !== '+38' && !phonePattern.test(phoneValue)) {
      errorDiv.textContent = 'Невірний формат: +380XXXXXXXXX';
      errorDiv.classList.remove('hidden');
      return;
    }

    const formData = new FormData(addForm);
    const url = isEditMode ? `/clients/${clientIdInput.value}` : '/clients/new';
    const resp = await fetch(url, { method: 'POST', body: formData });
    const data = await resp.json();

    if (resp.ok && data.success) {
      showToast('Клієнта успішно збережено!', 'success');
      bootstrap.Modal.getInstance(modal).hide();
      setTimeout(() => location.reload(), 1000);
    } else {
      errorDiv.textContent = data.error || 'Помилка збереження';
      errorDiv.classList.remove('hidden');
    }
  });
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
