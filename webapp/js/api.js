// API Client for Starosta Mini App

const API = {
  baseUrl: "/api/v1",

  getInitData() {
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
      return window.Telegram.WebApp.initData;
    }
    // Fallback for browser testing
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("initData") || "";
  },

  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
      "Accept": "application/json"
    };
    const initData = this.getInitData();
    if (initData) {
      headers["X-Telegram-Init-Data"] = initData;
    }
    return headers;
  },

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultOptions = {
      headers: this.getHeaders()
    };

    const finalOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, finalOptions);
      const data = await response.json();

      if (!response.ok) {
        const errorMsg = data.detail || (data.data && data.data.detail) || "Ошибка сервера";
        throw new Error(typeof errorMsg === "string" ? errorMsg : JSON.stringify(errorMsg));
      }

      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  },

  // Endpoints
  auth() {
    return this.request("/auth/telegram", { method: "POST" });
  },

  getTodaySchedule() {
    return this.request("/schedule/today", { method: "GET" });
  },

  submitCheckin(pairId, lat, lon, accuracy, timestamp) {
    return this.request("/attendance/checkin", {
      method: "POST",
      body: JSON.stringify({
        pair_id: pairId,
        client_lat: lat,
        client_lon: lon,
        accuracy: accuracy,
        timestamp: timestamp || Date.now() / 1000
      })
    });
  },

  getGrid(pairId) {
    return this.request(`/attendance/grid/${pairId}`, { method: "GET" });
  },

  overrideStatus(pairId, studentId, newStatus, excuseReason = null) {
    return this.request("/attendance/override", {
      method: "PATCH",
      body: JSON.stringify({
        pair_id: pairId,
        student_id: studentId,
        new_status: newStatus,
        excuse_reason: excuseReason
      })
    });
  },

  lockPair(pairId) {
    return this.request(`/attendance/lock/${pairId}`, { method: "POST" });
  },

  sendBroadcast(type, title, body) {
    return this.request("/alerts/broadcast", {
      method: "POST",
      body: JSON.stringify({ type, title, body })
    });
  },

  exportReport(dateFrom, dateTo, deliveryMethod = "TELEGRAM_DM") {
    return this.request("/reports/export", {
      method: "POST",
      body: JSON.stringify({
        date_from: dateFrom,
        date_to: dateTo,
        delivery_method: deliveryMethod
      })
    });
  }
};
