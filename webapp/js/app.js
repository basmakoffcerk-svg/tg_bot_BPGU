/**
 * JavaScript клиент Telegram Mini App для АРМ Старосты.
 * Группа 240326 Матинф БГПУ.
 */
document.addEventListener("DOMContentLoaded", async () => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const API_BASE = window.location.origin + "/api/v1";
  let initData = tg?.initData || sessionStorage.getItem("dev_init_data") || "";

  let currentUser = null;
  let currentPairIdForGrid = null;
  let selectedStudentForModal = null;

  // Инициализация вкладок
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");

      if (btn.dataset.tab === "tab-grid" && currentPairIdForGrid) {
        loadAttendanceGrid(currentPairIdForGrid);
      }
    });
  });

  // Утилита запросов с initData
  async function apiFetch(endpoint, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
      ...(options.headers || {}),
    };
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail?.message || err.detail || "Ошибка сервера");
    }
    return res.json();
  }

  function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3500);
  }

  // Проверка режима отладки в браузере (если запущено не в Telegram)
  async function checkDevMode() {
    if (!tg?.initData) {
      const devBar = document.getElementById("dev-bar");
      if (devBar) devBar.style.display = "flex";

      try {
        const usersRes = await fetch(`${API_BASE}/auth/dev-users`);
        if (!usersRes.ok) return;
        const devUsers = await usersRes.json();
        const select = document.getElementById("dev-user-select");
        select.innerHTML = "";

        devUsers.forEach(u => {
          const opt = document.createElement("option");
          opt.value = u.telegram_id;
          const roleLabel = u.role === "STAROSTA" ? "⭐ Староста" : (u.role === "ZAM" ? "⭐ Зам" : "👤 Студент");
          opt.textContent = `${roleLabel}: ${u.full_name} (п/г ${u.subgroup})`;
          select.appendChild(opt);
        });

        const savedTgId = sessionStorage.getItem("dev_tg_id") || (devUsers[0]?.telegram_id);
        if (savedTgId) {
          select.value = savedTgId;
        }

        select.addEventListener("change", async () => {
          await switchDevUser(select.value);
        });

        if (!initData && savedTgId) {
          await switchDevUser(savedTgId);
          return;
        }
      } catch (err) {
        console.warn("Dev users unavailable:", err);
      }
    }
  }

  async function switchDevUser(tgId) {
    try {
      const res = await fetch(`${API_BASE}/auth/dev-login?telegram_id=${tgId}`, { method: "POST" });
      const data = await res.json();
      initData = data.init_data;
      sessionStorage.setItem("dev_init_data", initData);
      sessionStorage.setItem("dev_tg_id", tgId);
      await initAuth();
    } catch (e) {
      showToast("Ошибка смены профиля: " + e.message);
    }
  }

  // 1. Авторизация и профиль
  async function initAuth() {
    try {
      const data = await apiFetch("/auth/telegram", { method: "POST" });
      currentUser = data.user;

      document.getElementById("user-name").textContent = currentUser.full_name;
      document.getElementById("user-subgroup").textContent = `Подгруппа ${currentUser.subgroup}`;
      document.getElementById("user-role").textContent = currentUser.role === "STAROSTA" ? "Староста" : (currentUser.role === "ZAM" ? "Замстаросты" : "Студент");
      document.getElementById("week-badge").textContent = `${data.current_week.week_number} нед (${data.current_week.week_type === "ODD" ? "числ" : "знам"})`;

      // Админские вкладки
      if (data.permissions.can_view_grid) {
        document.getElementById("tab-btn-grid").style.display = "block";
      } else {
        document.getElementById("tab-btn-grid").style.display = "none";
      }

      if (data.permissions.can_broadcast_critical || currentUser.role === "ZAM") {
        document.getElementById("tab-btn-alerts").style.display = "block";
      } else {
        document.getElementById("tab-btn-alerts").style.display = "none";
      }

      await loadSchedule();
    } catch (e) {
      console.error(e);
      document.getElementById("user-name").textContent = "Ошибка авторизации";
      showToast(e.message);
    }
  }

  // 2. Загрузка расписания
  async function loadSchedule() {
    try {
      const data = await apiFetch("/schedule/today");
      renderSchedule(data.pairs);
    } catch (e) {
      showToast("Не удалось загрузить расписание: " + e.message);
    }
  }

  function renderSchedule(pairs) {
    const list = document.getElementById("schedule-list");
    list.innerHTML = "";

    if (!pairs || pairs.length === 0) {
      list.innerHTML = `<div class="pair-card"><p style="text-align:center; padding:20px; color:var(--hint-color);">На сегодня занятий нет. Отдыхайте!</p></div>`;
      return;
    }

    pairs.forEach(pair => {
      const card = document.createElement("div");
      card.className = `pair-card ${pair.checkin_status.is_active ? "active-now" : ""}`;

      let checkinBlock = "";
      if (pair.my_attendance) {
        checkinBlock = `<div class="btn btn-success" style="cursor: default;">
          ✅ Вы отметились (${pair.my_attendance.distance ? pair.my_attendance.distance.toFixed(0) : 0} м от корпуса)
        </div>`;
      } else if (pair.checkin_status.is_active) {
        checkinBlock = `<button class="btn btn-primary btn-checkin" data-pair-id="${pair.pair_id}" data-lat="${pair.building_coordinates.lat}" data-lon="${pair.building_coordinates.lon}">
          📍 Отметиться на паре (GPS)
        </button>`;
      } else {
        const reasonText = pair.checkin_status.reason_closed === "NOT_STARTED_YET" 
          ? `Отметка откроется в ${pair.checkin_status.window_start}` 
          : (pair.checkin_status.reason_closed === "LOCKED_BY_ADMIN" ? "Журнал зафиксирован старостой" : "Окно чекина закрыто");
        checkinBlock = `<button class="btn btn-secondary" disabled>${reasonText}</button>`;
      }

      card.innerHTML = `
        <div class="pair-header">
          <span class="pair-time">${pair.time_start} – ${pair.time_end} (Пара №${pair.pair_number})</span>
          <span class="pair-type">${pair.type}</span>
        </div>
        <div class="pair-subject">${pair.subject}</div>
        <div class="pair-teacher">${pair.teacher || "Преподаватель уточняется"}</div>
        <div class="pair-place">🏢 ${pair.building}, ауд. ${pair.room}</div>
        ${checkinBlock}
      `;

      if (!currentPairIdForGrid) {
        currentPairIdForGrid = pair.pair_id;
      }

      list.appendChild(card);
    });

    document.querySelectorAll(".btn-checkin").forEach(btn => {
      btn.addEventListener("click", () => {
        const pairId = parseInt(btn.dataset.pairId);
        const targetLat = parseFloat(btn.dataset.lat);
        const targetLon = parseFloat(btn.dataset.lon);
        handleCheckin(pairId, targetLat, targetLon);
      });
    });
  }

  // 3. Геочекин с возможностью тестирования
  async function handleCheckin(pairId, targetLat, targetLon) {
    if (!navigator.geolocation) {
      if (confirm("Браузер не поддерживает Geolocation. Отметиться с координатами корпуса БГПУ (53.8945, 27.5447)?")) {
        await executeCheckin(pairId, targetLat || 53.894510, targetLon || 27.544720, 15.0);
      }
      return;
    }

    showToast("Определение GPS координат...");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        await executeCheckin(pairId, pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
      },
      (err) => {
        console.warn("GPS error:", err);
        if (confirm("Не удалось получить GPS с датчика (или вы тестируете с ПК). Отметиться с тестовыми координатами корпуса БГПУ?")) {
          executeCheckin(pairId, targetLat || 53.894510, targetLon || 27.544720, 15.0);
        } else {
          showToast("Чекин отменен");
        }
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
    );
  }

  async function executeCheckin(pairId, lat, lon, acc) {
    try {
      const res = await apiFetch("/attendance/checkin", {
        method: "POST",
        body: JSON.stringify({
          pair_id: pairId,
          client_lat: lat,
          client_lon: lon,
          accuracy: acc,
        }),
      });
      showToast(`🟢 ${res.message} Дистанция: ${res.distance_meters} м`);
      if (tg) tg.HapticFeedback?.notificationOccurred("success");
      await loadSchedule();
    } catch (e) {
      showToast(`❌ ${e.message}`);
      if (tg) tg.HapticFeedback?.notificationOccurred("error");
    }
  }

  // 4. Шахматка старосты
  async function loadAttendanceGrid(pairId) {
    try {
      const grid = await apiFetch(`/attendance/grid/${pairId}`);
      document.getElementById("grid-pair-title").textContent = `Шахматка: ${grid.subject}`;

      const sum = grid.summary;
      document.getElementById("grid-summary").innerHTML = `
        <div class="summary-pill">Всего: ${sum.total_students}</div>
        <div class="summary-pill" style="color: #27ae60;">Было: ${sum.present_count + sum.manual_confirmed_count}</div>
        <div class="summary-pill" style="color: #e74c3c;">Пропусков: ${sum.absent_unexcused_count}</div>
        <div class="summary-pill" style="color: #8e44ad;">Уваж: ${sum.absent_excused_count}</div>
      `;

      const list = document.getElementById("grid-students-list");
      list.innerHTML = "";

      grid.students.forEach(st => {
        const row = document.createElement("div");
        row.className = "student-row";
        row.innerHTML = `
          <div>
            <div class="student-name">${st.full_name}</div>
            <div style="font-size: 11px; color: var(--hint-color);">
              п/г ${st.subgroup} ${st.distance ? `• ${st.distance.toFixed(0)} м` : ""} ${st.excuse_reason ? `• ${st.excuse_reason}` : ""}
            </div>
          </div>
          <div class="status-badge ${st.badge_color}">${formatStatusBadge(st.status)}</div>
        `;

        row.addEventListener("click", () => openExcuseModal(st, pairId));
        list.appendChild(row);
      });

      // Лок пары
      const lockBtn = document.getElementById("btn-lock-pair");
      if (grid.is_locked) {
        lockBtn.textContent = "🔒 Журнал зафиксирован";
        lockBtn.disabled = true;
      } else {
        lockBtn.textContent = "🔒 Зафиксировать";
        lockBtn.disabled = false;
        lockBtn.onclick = async () => {
          if (confirm("Зафиксировать пару? После этого студенты не смогут отмечаться.")) {
            await apiFetch(`/attendance/lock/${pairId}`, { method: "POST" });
            showToast("Пара зафиксирована!");
            await loadAttendanceGrid(pairId);
          }
        };
      }

      // Экспорт Excel
      const excelBtn = document.getElementById("btn-export-excel");
      if (excelBtn) {
        excelBtn.onclick = () => {
          const today = new Date().toISOString().split("T")[0];
          window.open(`${API_BASE}/reports/download?date_from=2026-09-01&date_to=${today}`, "_blank");
        };
      }
    } catch (e) {
      showToast("Ошибка загрузки шахматки: " + e.message);
    }
  }

  function formatStatusBadge(st) {
    switch (st) {
      case "PRESENT": return "Был";
      case "MANUAL_CONFIRM": return "Вручную";
      case "ABSENT_EXCUSED": return "Уваж. (У)";
      case "LATE": return "Опоздал";
      default: return "Пропуск (Н)";
    }
  }

  // 5. Модалка оверрайда
  function openExcuseModal(student, pairId) {
    selectedStudentForModal = { student, pairId };
    document.getElementById("modal-student-name").textContent = student.full_name;
    document.getElementById("modal-status-select").value = student.status;
    document.getElementById("modal-excuse-reason").value = student.excuse_reason || "";
    document.getElementById("excuse-modal").style.display = "flex";
  }

  document.getElementById("btn-modal-cancel").addEventListener("click", () => {
    document.getElementById("excuse-modal").style.display = "none";
  });

  document.getElementById("btn-modal-save").addEventListener("click", async () => {
    if (!selectedStudentForModal) return;
    const newStatus = document.getElementById("modal-status-select").value;
    const reason = document.getElementById("modal-excuse-reason").value;

    try {
      await apiFetch("/attendance/override", {
        method: "PATCH",
        body: JSON.stringify({
          pair_id: selectedStudentForModal.pairId,
          student_id: selectedStudentForModal.student.student_id,
          new_status: newStatus,
          excuse_reason: reason,
        }),
      });
      document.getElementById("excuse-modal").style.display = "none";
      showToast("Статус обновлен");
      await loadAttendanceGrid(selectedStudentForModal.pairId);
    } catch (e) {
      showToast("Ошибка: " + e.message);
    }
  });

  // 6. Отправка алерта
  document.getElementById("btn-send-alert").addEventListener("click", async () => {
    const type = document.getElementById("alert-type").value;
    const title = document.getElementById("alert-title").value.trim();
    const body = document.getElementById("alert-body").value.trim();

    if (!title || !body) {
      showToast("Заполните тему и текст");
      return;
    }

    try {
      const res = await apiFetch("/alerts/broadcast", {
        method: "POST",
        body: JSON.stringify({ type, title, body }),
      });
      showToast(`📢 Оповещение отправлено (${res.queued_recipients} чел.)`);
      document.getElementById("alert-title").value = "";
      document.getElementById("alert-body").value = "";
    } catch (e) {
      showToast("Ошибка отправки: " + e.message);
    }
  });

  // Старт
  await checkDevMode();
  if (initData) {
    await initAuth();
  }
});
