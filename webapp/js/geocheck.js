// Geolocation and Anti-Spoofing Check-in Module

const GeoEngine = {
  lastPosition: null,
  CAMPUS_LAT: 53.893769,
  CAMPUS_LON: 27.544440,

  triggerHaptic(type = "success") {
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        if (type === "success") {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } else if (type === "error") {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
        } else {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
        }
      }
    } catch (e) {
      console.warn("Haptics not supported:", e);
    }
  },

  calculateDistanceMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000; // meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c);
  },

  getCurrentLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Геолокация не поддерживается вашим устройством."));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          this.lastPosition = pos;
          resolve(pos);
        },
        (err) => {
          let errorMsg = "Ошибка получения GPS координат.";
          if (err.code === 1) errorMsg = "Доступ к геопозиции отклонен. Включите геолокацию в настройках телефона/Telegram.";
          else if (err.code === 2) errorMsg = "Слабый сигнал спутников GPS. Подойдите к окну.";
          else if (err.code === 3) errorMsg = "Превышено время ожидания ответа GPS датчика.";
          reject(new Error(errorMsg));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        }
      );
    });
  },

  async probeGPS() {
    const statusEl = document.getElementById("gps-accuracy-text");
    if (statusEl) statusEl.textContent = "Измерение координат...";

    try {
      const pos = await this.getCurrentLocation();
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = pos.coords.accuracy;
      const dist = this.calculateDistanceMeters(lat, lon, this.CAMPUS_LAT, this.CAMPUS_LON);

      if (statusEl) {
        if (dist <= 150) {
          statusEl.innerHTML = `<span style="color: #10b981; font-weight: 700;">🟢 В корпусе! (${dist} м до БГПУ, ±${acc.toFixed(1)} м)</span>`;
        } else {
          statusEl.innerHTML = `<span style="color: #ef4444; font-weight: 700;">🔴 Вне корпуса (${dist} м до БГПУ, лимит 150м)</span>`;
        }
      }
      this.triggerHaptic("selection");
    } catch (err) {
      if (statusEl) {
        statusEl.innerHTML = `<span style="color: #ef4444;">🔴 ${err.message}</span>`;
      }
      this.triggerHaptic("error");
    }
  },

  async performCheckin(pairId, btnElement) {
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.innerHTML = `
        <span class="spinner-icon">⏳</span> Снятие геопозиции...
      `;
    }

    try {
      const pos = await this.getCurrentLocation();
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = pos.coords.accuracy;
      const ts = pos.timestamp ? pos.timestamp / 1000 : Date.now() / 1000;

      // Anti-spoofing client-side checks
      if (acc > 50) {
        throw new Error(`Точность GPS (±${acc.toFixed(0)} м) слишком низкая. Для чекина требуется точность не хуже 50 м.`);
      }

      const dist = this.calculateDistanceMeters(lat, lon, this.CAMPUS_LAT, this.CAMPUS_LON);
      if (dist > 150) {
        throw new Error(`Вы находитесь в ${dist} м от Корпуса 2 БГПУ. Отметка разрешена строго в радиусе 150 м.`);
      }

      if (btnElement) {
        btnElement.innerHTML = `📡 Криптографическая проверка...`;
      }

      const res = await API.submitCheckin(pairId, lat, lon, acc, ts);

      this.triggerHaptic("success");
      showAlert(`🟢 Присутствие подтверждено! Дистанция: ${res.distance_meters} м. Статус обновлен.`, "success");

      // Update button state immediately
      if (btnElement) {
        btnElement.className = "status-badge-lg badge-present";
        btnElement.innerHTML = `🟢 Вы отметились (${res.distance_meters} м)`;
        btnElement.disabled = true;
      }

      // Reload schedule to update UI
      if (window.loadSchedule) {
        setTimeout(window.loadSchedule, 1500);
      }
    } catch (err) {
      this.triggerHaptic("error");
      showAlert(`🔴 ${err.message}`, "error");
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.innerHTML = `📍 Отметиться на паре`;
      }
    }
  }
};

window.probeGPS = () => GeoEngine.probeGPS();
