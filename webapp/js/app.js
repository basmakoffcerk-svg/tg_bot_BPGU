// Main App Router and View Initializer

let currentUser = null;
let currentPermissions = null;
let todayPairs = [];

// Initialize Telegram WebApp
if (window.Telegram?.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}

function showAlert(text, type = "error") {
  const banner = document.getElementById("alert-banner");
  const textEl = document.getElementById("alert-text");
  if (!banner || !textEl) return;

  banner.style.display = "flex";
  banner.className = `alert-banner ${type === 'success' ? 'bg-green' : (type === 'info' ? 'bg-blue' : 'bg-red')}`;
  textEl.textContent = text;

  if (type === "success" || type === "info") {
    setTimeout(() => {
      closeAlert();
    }, 4000);
  }
}

function closeAlert() {
  const banner = document.getElementById("alert-banner");
  if (banner) banner.style.display = "none";
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = "none";
}

// Tab Switching
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetTabId = btn.dataset.tab;

    // Toggle active tab buttons
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    // Toggle active tab content
    document.querySelectorAll(".tab-content").forEach((content) => {
      content.classList.remove("active");
    });
    const targetContent = document.getElementById(targetTabId);
    if (targetContent) targetContent.classList.add("active");

    GeoEngine.triggerHaptic("selection");
  });
});

async function initializeApp() {
  try {
    const authData = await API.auth();
    currentUser = authData.user;
    currentPermissions = authData.permissions;

    if (currentUser) {
      document.getElementById("user-full-name").textContent = currentUser.full_name;
      const roleLabel = {
        "STAROSTA": "👑 Староста",
        "ZAM": "⭐ Замстаросты",
        "STUDENT": "🎓 Студент"
      }[currentUser.role] || "Студент";
      document.getElementById("user-role-subgroup").textContent = `${roleLabel} • ${currentUser.subgroup} подгруппа`;

      // Set avatar initials
      const parts = currentUser.full_name.split(" ");
      const initials = (parts[0][0] || "") + (parts[1] ? parts[1][0] : "");
      document.getElementById("user-avatar").textContent = initials;
    }

    // Set week badge
    if (authData.current_week) {
      document.getElementById("week-type-label").textContent = authData.current_week.week_type === "ODD" ? "Числитель" : "Знаменатель";
      document.getElementById("week-num-label").textContent = `Неделя ${authData.current_week.week_number}`;
    }

    // Show Starosta tab if user has permissions
    if (currentPermissions?.can_view_grid) {
      document.getElementById("tab-btn-starosta").style.display = "flex";
    }

    // Load today's schedule
    await loadSchedule();
  } catch (err) {
    showAlert(`Ошибка авторизации: ${err.message}`, "error");
  }
}

async function loadSchedule() {
  const container = document.getElementById("schedule-cards");
  if (container) container.innerHTML = "<div class='skeleton-card'></div><div class='skeleton-card'></div>";

  try {
    const data = await API.getTodaySchedule();
    todayPairs = data.pairs;
    renderScheduleCards(todayPairs);
    populatePairSelectorForStarosta(todayPairs);
    updateStatsSummary(todayPairs);
  } catch (err) {
    showAlert(`Не удалось загрузить расписание: ${err.message}`, "error");
    if (container) container.innerHTML = "<p style='color: var(--hint-color); text-align: center; padding: 20px;'>Нет занятий на сегодня или ошибка загрузки.</p>";
  }
}

function renderScheduleCards(pairs) {
  const container = document.getElementById("schedule-cards");
  if (!container) return;

  if (pairs.length === 0) {
    container.innerHTML = `
      <div style="background: var(--secondary-bg); padding: 24px; border-radius: 12px; text-align: center; border: 1px solid var(--card-border);">
        <p style="font-size: 16px; font-weight: 600;">🎉 Сегодня нет занятий!</p>
        <small style="color: var(--hint-color);">Отдыхайте или готовьтесь к лабораторным работам.</small>
      </div>
    `;
    return;
  }

  container.innerHTML = "";
  pairs.forEach((pair) => {
    const card = document.createElement("div");
    card.className = "pair-card";

    const isCheckedIn = pair.my_attendance && (pair.my_attendance.status === "PRESENT" || pair.my_attendance.status === "MANUAL_CONFIRM");
    if (isCheckedIn) card.classList.add("checked-in");
    if (pair.checkin_status.is_active) card.classList.add("active-slot");

    let actionContent = "";
    if (isCheckedIn) {
      actionContent = `
        <div class="status-badge-lg badge-present">
          🟢 Вы отметились (дистанция: ${pair.my_attendance.distance ? pair.my_attendance.distance + ' м' : 'ОК'})
        </div>
      `;
    } else if (pair.checkin_status.is_active) {
      actionContent = `
        <div class="checkin-action-row">
          <button class="btn-checkin" onclick="GeoEngine.performCheckin(${pair.pair_id}, this)">
            📍 Отметиться на паре
          </button>
        </div>
        <div class="timer-tag" style="margin-top: 6px;">
          ⏱️ Окно открыто (осталось ${Math.floor((pair.checkin_status.seconds_remaining || 0) / 60)} мин)
        </div>
      `;
    } else {
      let reasonText = "Окно отметки закрыто";
      if (pair.checkin_status.reason_closed === "NOT_STARTED_YET") {
        reasonText = `Откроется в ${pair.checkin_status.window_start} (за 5 мин до пары)`;
      } else if (pair.checkin_status.reason_closed === "TIME_EXPIRED") {
        reasonText = `Закрылось в ${pair.checkin_status.window_end}`;
      } else if (pair.checkin_status.reason_closed === "PAIR_LOCKED") {
        reasonText = `Зафиксировано старостой`;
      }
      actionContent = `
        <button class="btn-checkin disabled" disabled>
          🔒 ${reasonText}
        </button>
      `;
    }

    card.innerHTML = `
      <div class="pair-header">
        <span class="pair-time">№${pair.pair_number} • ${pair.time_start} - ${pair.time_end}</span>
        <span class="pair-type-tag">${pair.type}</span>
      </div>
      <div class="pair-title">${pair.subject}</div>
      <div class="pair-meta">
        <span>👨‍🏫 ${pair.teacher || 'Преподаватель кафедры'}</span>
        <span>📍 ${pair.building}, Ауд. ${pair.room}</span>
      </div>
      ${actionContent}
    `;

    container.appendChild(card);
  });
}

function populatePairSelectorForStarosta(pairs) {
  const select = document.getElementById("grid-pair-select");
  if (!select) return;

  select.innerHTML = "<option value=''>-- Выберите пару для шахматки --</option>";
  pairs.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.pair_id;
    opt.textContent = `№${p.pair_number} ${p.subject} (${p.time_start})`;
    select.appendChild(opt);
  });

  if (pairs.length > 0) {
    select.value = pairs[0].pair_id;
    loadGridForSelectedPair();
  }
}

function updateStatsSummary(pairs) {
  const presentCount = pairs.filter((p) => p.my_attendance?.status === "PRESENT" || p.my_attendance?.status === "MANUAL_CONFIRM").length;
  document.getElementById("stat-present-count").textContent = presentCount;
}

window.loadSchedule = loadSchedule;
window.closeAlert = closeAlert;
window.closeModal = closeModal;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  initializeApp();
});
