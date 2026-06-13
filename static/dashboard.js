let incidents = [];
let resourcePool = {};
let selectedId = null;
let eventMessages = ["Command center online. Waiting for citizen SOS packets."];

const feedEl = document.getElementById("incidentFeed");
const eventFeedEl = document.getElementById("eventFeed");
const deployBtn = document.getElementById("deployBtn");
const mediaModal = document.getElementById("mediaModal");
const mediaModalContent = document.getElementById("mediaModalContent");
const mediaModalClose = document.getElementById("mediaModalClose");

setInterval(updateClock, 1000);
setInterval(fetchIncidents, 15000);
updateClock();
fetchIncidents();
connectIncidentSocket();

deployBtn.addEventListener("click", async () => {
  if (!selectedId) return;
  await fetch(`/api/incidents/${selectedId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "Dispatched" }),
  });
  addEvent(`Dispatch confirmed for ${selectedId}.`);
  fetchIncidents();
});

mediaModalClose.addEventListener("click", closeMediaModal);
mediaModal.addEventListener("click", (event) => {
  if (event.target === mediaModal) closeMediaModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMediaModal();
});

function updateClock() {
  document.getElementById("clock").textContent = new Date().toLocaleTimeString("en-IN", { hour12: false });
}

async function fetchIncidents() {
  try {
    const response = await fetch("/api/incidents");
    const data = await response.json();
    incidents = data.incidents || [];
    resourcePool = data.resource_pool || {};
    document.getElementById("syncState").textContent = "Live sync active";
    if (!selectedId && incidents[0]) selectedId = incidents[0].incident_id;
    renderAll();
  } catch (error) {
    document.getElementById("syncState").textContent = "Backend offline";
  }
}

function renderAll() {
  renderKpis();
  renderOverallUsage();
  renderIncidentFeed();
  renderDetail();
  renderMap();
  renderEvents();
}

function renderKpis() {
  const critical = incidents.filter((inc) => inc.ai_analysis.severity === "CRITICAL").length;
  const teams = incidents.reduce(
    (sum, inc) => sum + Number(inc.allocation.medical_units || 0) + Number(inc.allocation.rescue_teams || 0),
    0
  );
  const people = incidents.reduce((sum, inc) => sum + inc.ai_analysis.estimated_people, 0);
  document.getElementById("kpiActive").textContent = incidents.length;
  document.getElementById("kpiCritical").textContent = critical;
  document.getElementById("kpiTeams").textContent = teams;
  document.getElementById("kpiPeople").textContent = people.toLocaleString("en-IN");
}

function renderOverallUsage() {
  const totals = {};
  Object.keys(resourcePool).forEach((key) => totals[key] = 0);
  incidents.forEach((inc) => {
    Object.entries(inc.allocation || {}).forEach(([key, value]) => {
      totals[key] = (totals[key] || 0) + value;
    });
  });

  const usageEl = document.getElementById("overallUsage");
  usageEl.innerHTML = Object.entries(resourcePool).map(([key, pool]) => {
    const used = totals[key] || 0;
    const percent = Math.min(100, Math.round((used / pool) * 100));
    return `
      <article class="usage-card">
        <div><span>${label(key)}</span><strong>${used.toLocaleString("en-IN")} / ${pool.toLocaleString("en-IN")}</strong></div>
        <div class="bar"><span style="width:${percent}%"></span></div>
      </article>
    `;
  }).join("");
}

function renderIncidentFeed() {
  if (!incidents.length) {
    feedEl.innerHTML = `<div class="empty-state small">No SOS transmissions yet. This rescue dashboard receives alerts only from the citizen SOS app.</div>`;
    return;
  }
  feedEl.innerHTML = incidents.map((inc) => `
    <button class="incident-card ${inc.incident_id === selectedId ? "active" : ""}" data-id="${inc.incident_id}">
      <span class="sev-dot ${inc.ai_analysis.severity.toLowerCase()}"></span>
      <div>
        <strong>${inc.ai_analysis.disaster_type}</strong>
        <p>${inc.raw_text}</p>
        <small>${inc.incident_id} · DSS ${inc.ai_analysis.severity_score}/100 · ${inc.status}</small>
      </div>
    </button>
  `).join("");
  feedEl.querySelectorAll(".incident-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectedId = card.dataset.id;
      addEvent(`Incident selected: ${selectedId}.`);
      renderAll();
    });
  });
}

function renderDetail() {
  const incident = incidents.find((inc) => inc.incident_id === selectedId);
  document.getElementById("emptyState").classList.toggle("hidden", Boolean(incident));
  document.getElementById("incidentDetail").classList.toggle("hidden", !incident);
  deployBtn.disabled = !incident;
  if (!incident) return;

  document.getElementById("detailId").textContent = incident.incident_id;
  document.getElementById("detailType").textContent = incident.ai_analysis.disaster_type;
  document.getElementById("detailSeverity").textContent = `${incident.ai_analysis.severity} · DSS ${incident.ai_analysis.severity_score}`;
  document.getElementById("detailSeverity").className = `severity-pill ${incident.ai_analysis.severity.toLowerCase()}`;
  document.getElementById("detailMessage").textContent = incident.raw_text;
  document.getElementById("detailBriefing").textContent = incident.briefing;
  renderMedia(incident);
  renderSummary(incident);
  renderLocation(incident);
  renderNotifications(incident);

  const resources = Object.entries(incident.allocation);
  document.getElementById("resourceGrid").innerHTML = resources.map(([key, value]) => `
    <article class="resource-card">
      <span>${label(key)}</span>
      <strong>${value.toLocaleString("en-IN")}</strong>
    </article>
  `).join("");
}

function renderSummary(incident) {
  const summary = incident.summary || {};
  const analysis = incident.ai_analysis;
  const outputs = incident.agent_outputs || {};
  const commander = incident.commander_decision || {};
  const trust = outputs.verification?.trust_score ?? 0;
  const satellite = outputs.satellite?.satellite_confidence_score ?? 0;
  const needs = summary.needs || analysis.immediate_needs || [];
  document.getElementById("summaryList").innerHTML = `
    <div><span>Headline</span><strong>${summary.headline || `${analysis.severity} ${analysis.disaster_type}`}</strong></div>
    <div><span>Affected</span><strong>${(summary.people || analysis.estimated_people).toLocaleString("en-IN")} people</strong></div>
    <div><span>Trust / command confidence</span><strong>${trust}/100 / ${commander.confidence_score ?? 0}/100</strong></div>
    <div><span>Satellite confirmation</span><strong>${outputs.satellite?.status || "not required"} (${satellite}/100)</strong></div>
    <div><span>Active response plan</span><strong>${commander.active_response_plan || "Pending command review"}</strong></div>
    <div><span>Incident status</span><strong>${incident.status}</strong></div>
    <div><span>Evidence</span><strong>${summary.media_status || (incident.media_attached ? "Photo/video received" : "No media evidence")}</strong></div>
    <div><span>Immediate needs</span><strong>${needs.join(", ")}</strong></div>
  `;
}

function renderLocation(incident) {
  const lat = Number(incident.location.latitude);
  const lon = Number(incident.location.longitude);
  const accuracy = Number(incident.location.accuracy_meters || 0);
  const source = incident.location.source || "manual";
  const mapsUrl = `https://www.google.com/maps?q=${lat},${lon}`;
  document.getElementById("locationBox").innerHTML = `
    <strong>${lat.toFixed(6)}, ${lon.toFixed(6)}</strong>
    <span>Source: ${source}${accuracy ? ` · Accuracy about ${Math.round(accuracy)} meters` : ""}</span>
    <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer">Open in Maps</a>
  `;
}

function renderNotifications(incident) {
  const items = incident.notifications || [];
  document.getElementById("notificationList").innerHTML = items.map((item) => `
    <article class="notification-card ${item.priority.toLowerCase()}">
      <div>
        <span>${item.unit} · ${item.priority}</span>
        <strong>${item.name}</strong>
        <p>${item.message}</p>
      </div>
      <small>${item.channel} · ${item.status}</small>
    </article>
  `).join("");
}

function renderMedia(incident) {
  const mediaBox = document.getElementById("detailMedia");
  mediaBox.classList.add("hidden");
  mediaBox.innerHTML = "";
  if (!incident.media_attached || !incident.media) return;

  const media = incident.media;
  const source = media.url || media.data_url;
  if (!source) return;
  const preview = media.type && media.type.startsWith("video/")
    ? `<video src="${source}" controls></video>`
    : `<img src="${source}" alt="SOS evidence from citizen">`;
  mediaBox.innerHTML = `
    <button class="media-open-btn" type="button" aria-label="Open citizen evidence full size">${preview}</button>
    <div>
      <span>Citizen evidence</span>
      <strong>${media.name || "Attached media"}</strong>
      <small>${media.type || "media"} · ${media.size ? (media.size / 1024 / 1024).toFixed(2) + " MB" : "size unknown"}</small>
      <button class="text-action" type="button">View full size</button>
    </div>
  `;
  mediaBox.querySelector(".media-open-btn").addEventListener("click", () => openMediaModal(media));
  mediaBox.querySelector(".text-action").addEventListener("click", () => openMediaModal(media));
  mediaBox.classList.remove("hidden");
}

function openMediaModal(media) {
  const source = media.url || media.data_url;
  const fullMedia = media.type && media.type.startsWith("video/")
    ? `<video src="${source}" controls autoplay></video>`
    : `<img src="${source}" alt="Full size SOS evidence from citizen">`;
  mediaModalContent.innerHTML = `
    ${fullMedia}
    <div class="media-modal-caption">
      <strong>${media.name || "Attached media"}</strong>
      <span>${media.type || "media"} · ${media.size ? (media.size / 1024 / 1024).toFixed(2) + " MB" : "size unknown"}</span>
    </div>
  `;
  mediaModal.classList.remove("hidden");
}

function closeMediaModal() {
  mediaModal.classList.add("hidden");
  mediaModalContent.innerHTML = "";
}

function renderMap() {
  const map = document.getElementById("mapCanvas");
  const markers = incidents.map((inc, index) => {
    const x = 18 + ((Math.abs(inc.location.longitude) * 7 + index * 17) % 64);
    const y = 18 + ((Math.abs(inc.location.latitude) * 5 + index * 13) % 54);
    const selected = inc.incident_id === selectedId ? "selected" : "";
    return `<button class="map-marker ${inc.ai_analysis.severity.toLowerCase()} ${selected}" style="left:${x}%;top:${y}%;" title="${inc.incident_id} · ${Number(inc.location.latitude).toFixed(4)}, ${Number(inc.location.longitude).toFixed(4)}" data-id="${inc.incident_id}">${index + 1}</button>`;
  }).join("");
  map.innerHTML = `
    <div class="map-grid"></div>
    <span class="map-label odisha">ODISHA RESPONSE GRID</span>
    ${markers}
  `;
  map.querySelectorAll(".map-marker").forEach((marker) => {
    marker.addEventListener("click", () => {
      selectedId = marker.dataset.id;
      renderAll();
    });
  });
}

function renderEvents() {
  eventFeedEl.innerHTML = eventMessages.slice(0, 10).map((msg) => `
    <article><span>${new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}</span><p>${msg}</p></article>
  `).join("");
}

function addEvent(message) {
  eventMessages.unshift(message);
  renderEvents();
}

function connectIncidentSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/api/ws/incidents`);
  socket.addEventListener("open", () => {
    document.getElementById("syncState").textContent = "WebSocket live";
  });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.incident) {
      const index = incidents.findIndex((item) => item.incident_id === message.incident.incident_id);
      if (index >= 0) incidents[index] = message.incident;
      else incidents.unshift(message.incident);
      if (!selectedId) selectedId = message.incident.incident_id;
      addEvent(`${message.event}: ${message.incident.incident_id}`);
      renderAll();
    }
  });
  socket.addEventListener("close", () => {
    document.getElementById("syncState").textContent = "Reconnecting";
    window.setTimeout(connectIncidentSocket, 3000);
  });
}

function label(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
