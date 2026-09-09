// Starosta Interactive Grid and Admin Actions

let currentPairId = null;
let currentGridData = null;
let selectedStudentForModal = null;

const STATUS_CYCLE = [
  "PRESENT",
  "ABSENT_UNEXCUSED",
  "LATE",
  "MANUAL_CONFIRM"
];

async function loadGridForSelectedPair() {
  const selectEl = document.getElementById("grid-pair-select");
  if (!selectEl || !selectEl.value) return;

  currentPairId = parseInt(selectEl.value);
  const container = document.getElementById("starosta-grid");
  if (container) container.innerHTML = "<div class='skeleton-card'></div>";

  try {
    const data = await API.getGrid(currentPairId);
    currentGridData = data;
    renderGrid(data);
  } catch (err) {
    showAlert(`Не удалось загрузить шахматку: ${err.message}`, "error");
  }
}

function renderGrid(data) {
  const container = document.getElementById("starosta-grid");
  if (!container) return;

  // Update summary chips
  document.getElementById("chip-present").textContent = data.summary.present_count;
  document.getElementById("chip-manual").textContent = data.summary.manual_confirmed_count;
  document.getElementById("chip-late").textContent = data.summary.late_count;
  document.getElementById("chip-excused").textContent = data.summary.absent_excused_count;
  document.getElementById("chip-unexcused").textContent = data.summary.absent_unexcused_count;

  // Update Lock button
  const lockBtn = document.getElementById("btn-lock-pair");
  if (lockBtn) {
    if (data.is_locked) {
      lockBtn.textContent = "🔒 Заперто";
      lockBtn.disabled = true;
      lockBtn.style.opacity = "0.6";
    } else {
      lockBtn.textContent = "🔓 Зафиксировать";
      lockBtn.disabled = false;
      lockBtn.style.opacity = "1";
    }
  }

  // Render student rows
  container.innerHTML = "";
  data.students.forEach((s) => {
    const row = document.createElement("div");
    row.className = "grid-student-row";
    row.dataset.studentId = s.student_id;

    const pillClass = `pill-${s.badge_color || 'gray'}`;
    const statusLabel = {
      "PRESENT": "🟢 Присутствовал",
      "ABSENT_UNEXCUSED": "🔴 Пропуск (Н)",
      "ABSENT_EXCUSED": "🟣 Уважит. (У)",
      "MANUAL_CONFIRM": "🟡 Вручную",
      "LATE": "🔵 Опоздание (О)"
    }[s.status] || s.status;

    const subInfo = s.excuse_reason
      ? `Уваж: ${s.excuse_reason}`
      : (s.distance !== null ? `Дистанция: ${s.distance} м` : `Подгруппа ${s.subgroup}`);

    row.innerHTML = `
      <div class="student-name-col">
        <strong>${s.full_name}</strong>
        <small>${subInfo}</small>
      </div>
      <div class="status-pill ${pillClass}">
        ${statusLabel}
      </div>
    `;

    // Click handler: fast cycle
    row.addEventListener("click", () => {
      handleStudentClick(s);
    });

    // Context menu / long click handler for modal
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      openOverrideModal(s);
    });

    container.appendChild(row);
  });
}

async function handleStudentClick(student) {
  if (!currentPairId) return;

  // Find next status in cycle
  const currentIdx = STATUS_CYCLE.indexOf(student.status);
  const nextStatus = STATUS_CYCLE[(currentIdx + 1) % STATUS_CYCLE.length];

  GeoEngine.triggerHaptic("selection");

  try {
    await API.overrideStatus(currentPairId, student.student_id, nextStatus);
    // Reload grid
    await loadGridForSelectedPair();
  } catch (err) {
    showAlert(`Ошибка изменения статуса: ${err.message}`, "error");
  }
}

function openOverrideModal(student) {
  selectedStudentForModal = student;
  document.getElementById("modal-student-name").textContent = student.full_name;
  document.getElementById("modal-status-select").value = student.status;
  document.getElementById("modal-excuse-text").value = student.excuse_reason || "";
  document.getElementById("modal-override").style.display = "flex";
}

async function submitModalOverride() {
  if (!selectedStudentForModal || !currentPairId) return;

  const newStatus = document.getElementById("modal-status-select").value;
  const excuseText = document.getElementById("modal-excuse-text").value.trim();

  try {
    await API.overrideStatus(currentPairId, selectedStudentForModal.student_id, newStatus, excuseText || null);
    closeModal("modal-override");
    GeoEngine.triggerHaptic("success");
    await loadGridForSelectedPair();
  } catch (err) {
    showAlert(`Ошибка сохранения: ${err.message}`, "error");
  }
}

async function lockCurrentPair() {
  if (!currentPairId) return;
  if (!confirm("Зафиксировать журнал пары? После этого студенты не смогут отмечаться.")) return;

  try {
    await API.lockPair(currentPairId);
    GeoEngine.triggerHaptic("success");
    showAlert("🔒 Журнал пары успешно зафиксирован!", "success");
    await loadGridForSelectedPair();
  } catch (err) {
    showAlert(`Ошибка: ${err.message}`, "error");
  }
}

function openBroadcastModal() {
  document.getElementById("modal-broadcast").style.display = "flex";
}

async function submitBroadcast() {
  const type = document.getElementById("broadcast-type-select").value;
  const title = document.getElementById("broadcast-title").value.trim();
  const body = document.getElementById("broadcast-body").value.trim();

  if (!title || !body) {
    alert("Заполните заголовок и текст сообщения!");
    return;
  }

  try {
    await API.sendBroadcast(type, title, body);
    closeModal("modal-broadcast");
    GeoEngine.triggerHaptic("success");
    showAlert("📢 Оповещение успешно отправлено группе!", "success");
  } catch (err) {
    showAlert(`Ошибка отправки: ${err.message}`, "error");
  }
}

async function exportReportWeekly() {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const monday = new Date(today);
  monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));

  const fromStr = monday.toISOString().split("T")[0];
  const toStr = today.toISOString().split("T")[0];

  try {
    showAlert("⏳ Формирую рапортичку за неделю...", "info");
    const res = await API.exportReport(fromStr, toStr, "TELEGRAM_DM");
    GeoEngine.triggerHaptic("success");
    showAlert(`📥 Рапортичка (${res.file_name}) успешно отправлена в ваш Telegram!`, "success");
  } catch (err) {
    showAlert(`Ошибка выгрузки: ${err.message}`, "error");
  }
}

window.loadGridForSelectedPair = loadGridForSelectedPair;
window.submitModalOverride = submitModalOverride;
window.lockCurrentPair = lockCurrentPair;
window.openBroadcastModal = openBroadcastModal;
window.submitBroadcast = submitBroadcast;
window.exportReportWeekly = exportReportWeekly;
