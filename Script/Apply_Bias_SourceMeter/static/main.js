const POLL_MS = 700;

const stateLabels = {
  idle: "pronto",
  ramp_up: "salita in tensione",
  hold: "bias applicato",
  ramp_down: "discesa a 0 V",
  error: "errore",
};

const modeLabels = {
  iv_curve: "Curva IV",
  bias: "Applico BIAS",
};

let dataPointCount = 0;
let chart = null;

// ---------------- tabs ----------------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// ---------------- chart ----------------

function initChart() {
  if (typeof Chart === "undefined") {
    console.error("Chart.js non disponibile: il grafico resta disattivato, ma i controlli funzionano lo stesso.");
    return;
  }
  const canvas = document.getElementById("current-chart");
  const ctx = canvas.getContext("2d");

  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 320);
  gradient.addColorStop(0, "rgba(82, 221, 203, 0.30)");
  gradient.addColorStop(1, "rgba(82, 221, 203, 0.00)");

  chart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Corrente [A]",
          data: [],
          borderColor: "#5CE6D3",
          backgroundColor: gradient,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: "#5CE6D3",
          pointHoverBorderColor: "#0C1015",
          cubicInterpolationMode: "monotone",
          fill: true,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      interaction: { intersect: false, mode: "nearest", axis: "x" },
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: "Tempo [s]", color: "#5B6472", font: { family: "JetBrains Mono", size: 11 } },
          ticks: { color: "#8892A0", font: { family: "JetBrains Mono", size: 11 } },
          grid: { color: "rgba(42, 50, 63, 0.6)" },
          border: { color: "#29323F" },
        },
        y: {
          title: { display: true, text: "Corrente [A]", color: "#5B6472", font: { family: "JetBrains Mono", size: 11 } },
          ticks: { color: "#8892A0", font: { family: "JetBrains Mono", size: 11 } },
          grid: { color: "rgba(42, 50, 63, 0.6)" },
          border: { color: "#29323F" },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1C2530",
          borderColor: "#29323F",
          borderWidth: 1,
          titleColor: "#8892A0",
          bodyColor: "#EAEFF5",
          bodyFont: { family: "JetBrains Mono", size: 12 },
          titleFont: { family: "JetBrains Mono", size: 11 },
          padding: 10,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title: (items) => "t = " + items[0].parsed.x.toFixed(2) + " s",
            label: (item) => "I = " + item.parsed.y.toExponential(3) + " A",
          },
        },
      },
    },
  });
}

function resetChart() {
  if (!chart) return;
  chart.data.datasets[0].data = [];
  chart.update();
  dataPointCount = 0;
}

function appendChartData(t, i) {
  if (!chart) return;
  const points = t.map((tv, idx) => ({ x: tv, y: i[idx] }));
  chart.data.datasets[0].data.push(...points);
  chart.update("none");
}

// ---------------- formatting helpers ----------------

function fmtVoltage(v) {
  if (v === null || v === undefined) return "— . — — —";
  return v.toFixed(3);
}

function fmtCurrent(i) {
  if (i === null || i === undefined) return "—.———e—";
  return i.toExponential(3);
}

function fmtElapsed(t, dataLen) {
  if (dataLen === 0) return "00:00:00";
  const total = Math.max(0, Math.floor(t));
  const h = String(Math.floor(total / 3600)).padStart(2, "0");
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

// ---------------- status / data polling ----------------

let lastTSeen = 0;
let pollFailures = 0;

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    const st = await res.json();
    pollFailures = 0;

    document.getElementById("state-text").textContent = stateLabels[st.state] || st.state;

    const dot = document.getElementById("conn-dot");
    dot.classList.toggle("led--on", st.state !== "idle" && st.state !== "error");
    dot.classList.toggle("led--off", st.state === "idle" || st.state === "error");

    document.getElementById("led-output").classList.toggle("led--on", st.state !== "idle");
    document.getElementById("led-output").classList.toggle("led--off", st.state === "idle");

    document.getElementById("led-bias").classList.toggle("led--on", st.state === "hold");
    document.getElementById("led-bias").classList.toggle("led--off", st.state !== "hold");

    document.getElementById("led-error").classList.toggle("led--on", st.state === "error");
    document.getElementById("led-error").classList.toggle("led--off", st.state !== "error");

    const isOn = st.state !== "idle" && st.state !== "error";
    const powerBtn = document.getElementById("btn-power");
    const powerLabel = document.getElementById("power-label");
    powerBtn.classList.toggle("btn-power--on", isOn);
    powerBtn.classList.toggle("btn-power--off", !isOn);
    powerBtn.disabled = (st.state === "ramp_down"); // in discesa non si può interrompere di nuovo
    powerLabel.textContent = isOn ? "ON" : "OFF";
    powerLabel.classList.toggle("is-on", isOn);
    powerLabel.classList.toggle("is-off", !isOn);

    document.getElementById("display-v").textContent = fmtVoltage(st.last_voltage);
    document.getElementById("display-i").textContent = fmtCurrent(st.last_current);
    document.getElementById("read-n").textContent = st.n_points;
    document.getElementById("file-path").textContent = st.file || "nessuna misura avviata";

    document.getElementById("chart-mode-badge").textContent = st.mode ? modeLabels[st.mode] : "—";

    const errorBox = document.getElementById("error-box");
    if (st.error) {
      errorBox.hidden = false;
      errorBox.textContent = st.error;
    } else {
      errorBox.hidden = true;
    }

    // se una nuova misura e' partita (contatore azzerato), pulisci il grafico
    if (st.n_points < dataPointCount) {
      resetChart();
      lastTSeen = 0;
    }
    dataPointCount = st.n_points;

    // riempi i campi impostazioni solo se non li sto editando (idle e non a fuoco)
    if (st.state === "idle" && document.activeElement.tagName !== "INPUT") {
      fillConfigForm(st.config);
    }
  } catch (e) {
    // server non raggiungibile: dopo un paio di tentativi falliti lo segnalo,
    // invece di far sembrare che i pulsanti non facciano nulla
    pollFailures += 1;
    if (pollFailures >= 3) {
      showTransientError("Connessione al server persa. Controlla che 'python app.py' sia ancora in esecuzione.");
    }
  }
}

async function pollData() {
  try {
    const res = await fetch("/api/data?since=" + lastTSeen);
    const d = await res.json();
    if (d.t && d.t.length > 0) {
      appendChartData(d.t, d.i);
      lastTSeen = d.n_points;
      const elapsed = d.t[d.t.length - 1];
      document.getElementById("read-t").textContent = fmtElapsed(elapsed, d.n_points);
    }
  } catch (e) {
    // ignora, riprovera' al prossimo giro
  }
}

// ---------------- config form ----------------

function fillConfigForm(cfg) {
  for (const key of Object.keys(cfg)) {
    const el = document.getElementById("cfg-" + key);
    if (el) el.value = cfg[key];
  }
}

document.getElementById("config-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = {
    sample_name: form.sample_name.value,
    instrument_resource: form.instrument_resource.value,
    v_set: form.v_set.value,
    step_voltage: form.step_voltage.value,
    delay: form.delay.value,
    current_compliance: form.current_compliance.value,
    hold_sample_period: form.hold_sample_period.value,
  };

  const res = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await res.json();

  const msgBox = document.getElementById("config-msg");
  msgBox.hidden = false;
  if (result.ok) {
    msgBox.className = "config-msg ok";
    msgBox.textContent = "Parametri applicati.";
  } else {
    msgBox.className = "config-msg err";
    msgBox.textContent = result.error || "Errore durante il salvataggio.";
  }
  setTimeout(() => { msgBox.hidden = true; }, 3000);
});

// ---------------- start / stop ----------------

document.getElementById("btn-power").addEventListener("click", async () => {
  const isOn = document.getElementById("btn-power").classList.contains("btn-power--on");
  try {
    if (isOn) {
      const res = await fetch("/api/stop", { method: "POST" });
      const result = await res.json();
      if (!result.ok) showTransientError(result.error || "Impossibile fermare la misura.");
    } else {
      const mode = document.getElementById("mode-select").value;
      resetChart();
      lastTSeen = 0;
      const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const result = await res.json();
      if (!result.ok) showTransientError(result.error || "Impossibile avviare la misura.");
    }
    pollStatus(); // aggiorna subito, senza aspettare il prossimo giro di polling
  } catch (e) {
    showTransientError("Impossibile contattare il server. Controlla che 'python app.py' sia in esecuzione.");
  }
});

function showTransientError(msg) {
  const errorBox = document.getElementById("error-box");
  errorBox.hidden = false;
  errorBox.textContent = msg;
}

// ---------------- init ----------------

initChart();

fetch("/api/config")
  .then((r) => r.json())
  .then((d) => fillConfigForm(d.config));

setInterval(pollStatus, POLL_MS);
setInterval(pollData, POLL_MS);
pollStatus();
pollData();
