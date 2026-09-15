document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("hudContainer");
  const orbCluster = document.getElementById("orbCluster");
  const pillTitle = document.getElementById("pillTitle");
  const pillSubtitle = document.getElementById("pillSubtitle");
  const toolBadge = document.getElementById("toolBadge");
  const timerBadge = document.getElementById("timerBadge");
  const expandBtn = document.getElementById("expandBtn");
  const sessionCount = document.getElementById("sessionCount");
  const sessionList = document.getElementById("sessionList");

  // Settings elements
  const selOrientation = document.getElementById("selOrientation");
  const selScale = document.getElementById("selScale");
  const selTheme = document.getElementById("selTheme");
  const chkSound = document.getElementById("chkSound");
  const selSoundStyle = document.getElementById("selSoundStyle");
  const rngVolume = document.getElementById("rngVolume");
  const btnTestSound = document.getElementById("btnTestSound");
  const selAutoDismiss = document.getElementById("selAutoDismiss");

  // Action elements
  const btnHooks = document.getElementById("btnHooks");
  const btnCenter = document.getElementById("btnCenter");
  const btnSimMulti = document.getElementById("btnSimMulti");

  let isExpanded = false;
  let timerInterval = null;
  let currentAggregateStatus = "idle";
  let activeStartedAt = null;
  let currentSessions = [];
  let defaultHeadlineTitle = "Vibe HUD Ready";
  let defaultHeadlineSubtitle = "Standing by for Claude...";

  let settings = {
    theme: "dark-glass",
    orientation: "horizontal",
    scale: "medium",
    soundEnabled: true,
    soundStyle: "marimba",
    soundVolume: 0.8,
    autoDismissSec: 60,
    alwaysOnTop: true,
  };

  function formatTime(seconds) {
    if (seconds === undefined || seconds === null || isNaN(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  function startLiveTimer(startedAt) {
    stopLiveTimer();
    activeStartedAt = startedAt || Date.now();
    updateTimerText();
    timerInterval = setInterval(updateTimerText, 1000);
  }

  function stopLiveTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function updateTimerText() {
    if (!activeStartedAt) return;
    const elapsed = Math.max(0, Math.floor((Date.now() - activeStartedAt) / 1000));
    timerBadge.textContent = formatTime(elapsed);
  }

  window.applySettings = function (newSettings) {
    settings = Object.assign(settings, newSettings);
    document.body.setAttribute("data-theme", settings.theme || "dark-glass");
    document.body.setAttribute("data-orientation", settings.orientation || "horizontal");
    document.body.setAttribute("data-scale", settings.scale || "medium");

    if (selTheme) selTheme.value = settings.theme || "dark-glass";
    if (selOrientation) selOrientation.value = settings.orientation || "horizontal";
    if (selScale) selScale.value = settings.scale || "medium";
    if (chkSound) chkSound.checked = settings.soundEnabled;
    if (selSoundStyle) selSoundStyle.value = settings.soundStyle || "marimba";
    if (rngVolume) rngVolume.value = settings.soundVolume !== undefined ? settings.soundVolume : 0.8;
    if (selAutoDismiss) selAutoDismiss.value = String(settings.autoDismissSec || 60);

    window.hudAudio?.configure({
      enabled: settings.soundEnabled,
      style: settings.soundStyle,
      volume: settings.soundVolume,
    });
  };

  function persistSettings() {
    window.hudAudio?.configure({
      enabled: settings.soundEnabled,
      style: settings.soundStyle,
      volume: settings.soundVolume,
    });
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.save_settings(JSON.stringify(settings));
    }
  }

  window.updateState = function (stateData) {
    const prevStatus = currentAggregateStatus;
    currentAggregateStatus = stateData.aggregate_status || "idle";
    currentSessions = stateData.sessions || [];

    defaultHeadlineTitle = stateData.headline_title || "Vibe HUD Ready";
    defaultHeadlineSubtitle = stateData.headline_subtitle || "";

    container.setAttribute("data-status", currentAggregateStatus);
    pillTitle.textContent = defaultHeadlineTitle;
    pillSubtitle.textContent = defaultHeadlineSubtitle;

    if (stateData.active_tool && currentAggregateStatus === "working") {
      toolBadge.textContent = stateData.active_tool.toUpperCase();
      toolBadge.classList.add("visible");
    } else {
      toolBadge.classList.remove("visible");
    }

    if (currentAggregateStatus === "working") {
      if (prevStatus !== "working") {
        startLiveTimer(Date.now() - (stateData.active_timer ? stateData.active_timer * 1000 : 0));
      }
    } else if (currentAggregateStatus === "complete") {
      stopLiveTimer();
      if (stateData.active_timer !== undefined && stateData.active_timer !== null) {
        timerBadge.textContent = formatTime(stateData.active_timer);
      }
      if (prevStatus === "working") {
        window.hudAudio?.playComplete();
      }
    } else if (currentAggregateStatus === "attention") {
      if (prevStatus !== "attention") {
        window.hudAudio?.playAttention();
      }
    } else if (currentAggregateStatus === "idle") {
      stopLiveTimer();
      timerBadge.textContent = "00:00";
    }

    renderOrbCluster(currentSessions);
    renderSessionList(currentSessions);
  };

  function renderOrbCluster(sessions) {
    orbCluster.innerHTML = "";
    if (sessionCount) sessionCount.textContent = sessions ? sessions.length : 0;

    if (!sessions || sessions.length === 0) {
      const emptyOrb = document.createElement("div");
      emptyOrb.className = "orb-item";
      emptyOrb.setAttribute("data-status", "idle");
      emptyOrb.innerHTML = `
        <div class="orb-ring"></div>
        <div class="orb-dot"></div>
        <div class="orb-tooltip">📁 Standing by for Claude</div>
      `;
      orbCluster.appendChild(emptyOrb);
      return;
    }

    sessions.forEach((s) => {
      const orb = document.createElement("div");
      orb.className = "orb-item";
      orb.setAttribute("data-status", s.status);

      const shortId = s.id ? s.id.slice(0, 7) : "";
      const tooltipText = `📁 ${s.repo_name} (${shortId ? "#" + shortId : s.status}) · Click to jump`;

      orb.innerHTML = `
        <div class="orb-ring"></div>
        <div class="orb-dot"></div>
        <div class="orb-tooltip">${escapeHtml(tooltipText)}</div>
      `;

      // Hover feedback: preview in pill title/subtitle
      orb.addEventListener("mouseenter", () => {
        pillTitle.textContent = `📁 ${s.repo_name} (${s.status.toUpperCase()})`;
        pillSubtitle.textContent = s.prompt || s.detail || "Click dot to jump to terminal";
      });

      orb.addEventListener("mouseleave", () => {
        pillTitle.textContent = defaultHeadlineTitle;
        pillSubtitle.textContent = defaultHeadlineSubtitle;
      });

      // Click to focus terminal!
      orb.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.pywebview && window.pywebview.api) {
          window.pywebview.api.focus_session(s.id);
        }
      });

      orbCluster.appendChild(orb);
    });
  }

  function renderSessionList(sessions) {
    if (!sessions || sessions.length === 0) {
      sessionList.innerHTML = `
        <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 12px;">
          No active terminal sessions.<br>Submit a prompt to Claude Code to see live tracking.
        </div>
      `;
      return;
    }

    sessionList.innerHTML = "";
    sessions.forEach((s) => {
      const card = document.createElement("div");
      card.className = "session-card";
      card.title = "Click to jump to this terminal window";

      const shortId = s.id ? s.id.slice(0, 7) : "";
      const now = Date.now();
      let timerStr = "";
      if (s.status === "working" && s.started_at) {
        timerStr = formatTime(Math.floor((now - s.started_at) / 1000));
      } else if (s.duration) {
        timerStr = `${s.duration}s`;
      } else {
        timerStr = s.status;
      }

      card.innerHTML = `
        <div class="session-card-left">
          <div class="session-dot ${s.status}"></div>
          <div class="session-meta">
            <div class="session-repo">
              <span>📁 ${escapeHtml(s.repo_name)}</span>
              ${shortId ? `<span class="session-id-tag">#${shortId}</span>` : ""}
            </div>
            <div class="session-task-preview">
              ${escapeHtml(s.prompt || s.detail || s.title)}
            </div>
          </div>
        </div>
        <div class="session-card-right">
          <span class="jump-hint">Jump ↗</span>
          ${s.tool_name ? `<span class="tool-badge visible">${escapeHtml(s.tool_name)}</span>` : ""}
          <span class="timer-badge">${timerStr}</span>
          <button class="session-dismiss-btn" title="Dismiss Session" data-id="${s.id}">✖</button>
        </div>
      `;

      // Click card to jump to terminal!
      card.addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api) {
          window.pywebview.api.focus_session(s.id);
        }
      });

      card.querySelector(".session-dismiss-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.pywebview && window.pywebview.api) {
          window.pywebview.api.dismiss_session(s.id);
        }
      });

      sessionList.appendChild(card);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Expansion
  expandBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    isExpanded = !isExpanded;
    container.classList.toggle("expanded", isExpanded);
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_expanded(isExpanded, settings.orientation);
    }
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById("tab" + tabId.charAt(0).toUpperCase() + tabId.slice(1));
      if (targetContent) targetContent.classList.add("active");
    });
  });

  // Orientation setting
  selOrientation?.addEventListener("change", () => {
    settings.orientation = selOrientation.value;
    document.body.setAttribute("data-orientation", settings.orientation);
    persistSettings();
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_orientation(settings.orientation);
    }
  });

  // Scale setting
  selScale?.addEventListener("change", () => {
    settings.scale = selScale.value;
    document.body.setAttribute("data-scale", settings.scale);
    persistSettings();
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_scale(settings.scale);
    }
  });

  // Theme setting
  selTheme?.addEventListener("change", () => {
    settings.theme = selTheme.value;
    document.body.setAttribute("data-theme", settings.theme);
    persistSettings();
  });

  // Sound settings
  chkSound?.addEventListener("change", () => {
    settings.soundEnabled = chkSound.checked;
    persistSettings();
  });

  selSoundStyle?.addEventListener("change", () => {
    settings.soundStyle = selSoundStyle.value;
    persistSettings();
    window.hudAudio?.playTest();
  });

  rngVolume?.addEventListener("input", () => {
    settings.soundVolume = parseFloat(rngVolume.value);
    persistSettings();
  });

  btnTestSound?.addEventListener("click", () => {
    window.hudAudio?.playTest();
  });

  selAutoDismiss?.addEventListener("change", () => {
    settings.autoDismissSec = parseInt(selAutoDismiss.value, 10);
    persistSettings();
  });

  // Actions
  btnHooks?.addEventListener("click", async () => {
    btnHooks.innerHTML = "<span>Installing...</span>";
    if (window.pywebview && window.pywebview.api) {
      const res = await window.pywebview.api.install_hooks();
      if (res && res.success) {
        btnHooks.innerHTML = "<span>✓ Installed!</span>";
        btnHooks.classList.remove("primary");
        btnHooks.disabled = true;
      } else {
        btnHooks.innerHTML = "<span>Error</span>";
      }
    }
  });

  btnCenter?.addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.center_window();
    }
  });

  btnSimMulti?.addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.simulate("multi");
    }
  });

  document.querySelectorAll(".sim-dot-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const state = btn.getAttribute("data-sim");
      if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.simulate(state);
      }
    });
  });
});
