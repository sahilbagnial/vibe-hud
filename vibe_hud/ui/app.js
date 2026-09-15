document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("hudContainer");
  const pillTitle = document.getElementById("pillTitle");
  const pillSubtitle = document.getElementById("pillSubtitle");
  const toolBadge = document.getElementById("toolBadge");
  const timerBadge = document.getElementById("timerBadge");
  const expandBtn = document.getElementById("expandBtn");
  const promptBox = document.getElementById("promptBox");
  const btnHooks = document.getElementById("btnHooks");
  const btnCenter = document.getElementById("btnCenter");
  const chkSound = document.getElementById("chkSound");

  let isExpanded = false;
  let timerInterval = null;
  let currentStatus = "idle";
  let startTime = null;

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  function startTimer(startedAt) {
    stopTimer();
    startTime = startedAt || Date.now();
    updateTimerDisplay();
    timerInterval = setInterval(updateTimerDisplay, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function updateTimerDisplay() {
    if (!startTime) return;
    const elapsed = Math.max(0, Math.floor((Date.now() - startTime) / 1000));
    timerBadge.textContent = formatTime(elapsed);
  }

  // Exposed globally for Python to call via evaluate_js
  window.updateState = function (state) {
    const prevStatus = currentStatus;
    currentStatus = state.status || "idle";

    container.setAttribute("data-status", currentStatus);
    pillTitle.textContent = state.title || "Vibe HUD Ready";
    pillSubtitle.textContent = state.detail || "";

    if (state.prompt) {
      promptBox.textContent = state.prompt;
    } else if (state.detail) {
      promptBox.textContent = state.detail;
    }

    if (state.tool_name && currentStatus === "working") {
      toolBadge.textContent = state.tool_name.toUpperCase();
      toolBadge.classList.add("visible");
    } else {
      toolBadge.classList.remove("visible");
    }

    if (currentStatus === "working") {
      if (prevStatus !== "working") {
        startTimer(state.started_at);
      }
    } else if (currentStatus === "complete") {
      stopTimer();
      if (state.duration !== undefined) {
        timerBadge.textContent = formatTime(state.duration);
      }
      if (prevStatus === "working") {
        window.hudAudio?.playComplete();
      }
    } else if (currentStatus === "attention") {
      window.hudAudio?.playAttention();
    } else if (currentStatus === "idle") {
      stopTimer();
      timerBadge.textContent = "00:00";
    }
  };

  expandBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    isExpanded = !isExpanded;
    container.classList.toggle("expanded", isExpanded);
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_expanded(isExpanded);
    }
  });

  btnHooks.addEventListener("click", async () => {
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

  btnCenter.addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.center_window();
    }
  });

  chkSound.addEventListener("change", () => {
    window.hudAudio?.setEnabled(chkSound.checked);
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
