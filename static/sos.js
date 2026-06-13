const form = document.getElementById("sosForm");
const submitBtn = document.getElementById("submitBtn");
const tracker = document.getElementById("tracker");
const gpsStatus = document.getElementById("gpsStatus");
const gpsBtn = document.getElementById("gpsBtn");
const mediaInput = document.getElementById("mediaInput");
const mediaPreview = document.getElementById("mediaPreview");

const MAX_MEDIA_BYTES = 8 * 1024 * 1024;
let lastGpsFix = null;

gpsBtn.addEventListener("click", async () => {
  gpsStatus.textContent = "Requesting current GPS location...";
  gpsBtn.disabled = true;
  gpsBtn.textContent = "Locating...";

  if (!navigator.geolocation) {
    gpsStatus.textContent = "GPS unavailable on this device/browser. Please enter coordinates manually.";
    gpsBtn.textContent = "Locate me";
    gpsBtn.disabled = false;
    return;
  }

  if (!window.isSecureContext) {
    gpsStatus.textContent = "GPS requires a secure browser context. Use http://127.0.0.1:8000/sos or HTTPS.";
    gpsBtn.textContent = "Locate me";
    gpsBtn.disabled = false;
    return;
  }

  try {
    gpsStatus.textContent = "Trying high-accuracy GPS...";
    const position = await getGpsPosition({ enableHighAccuracy: true, maximumAge: 0, timeout: 15000 });
    applyGpsPosition(position, "high accuracy GPS");
  } catch (firstError) {
    if (firstError.code === 1) {
      gpsStatus.textContent = "Location permission is blocked. Allow location access in the browser and try again.";
      gpsBtn.textContent = "Locate me";
      gpsBtn.disabled = false;
      return;
    }

    try {
      gpsStatus.textContent = "High-accuracy GPS timed out. Trying standard GPS...";
      const fallbackPosition = await getGpsPosition({ enableHighAccuracy: false, maximumAge: 0, timeout: 20000 });
      applyGpsPosition(fallbackPosition, "standard GPS fallback");
    } catch (secondError) {
      try {
        gpsStatus.textContent = "Standard GPS also failed. Listening for a live GPS update...";
        const watchedPosition = await watchGpsPosition({ enableHighAccuracy: true, maximumAge: 0, timeout: 30000 });
        applyGpsPosition(watchedPosition, "live GPS listener");
      } catch (thirdError) {
        gpsStatus.textContent = `${gpsErrorMessage(thirdError)} ${locationHelpText()}`;
        gpsBtn.textContent = "Try locate again";
        gpsBtn.disabled = false;
      }
    }
  }
});

mediaInput.addEventListener("change", () => {
  const file = mediaInput.files[0];
  mediaPreview.classList.add("hidden");
  mediaPreview.innerHTML = "";
  if (!file) return;
  if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
    alert("Please attach only an image or video file.");
    mediaInput.value = "";
    return;
  }
  if (file.size > MAX_MEDIA_BYTES) {
    alert("Please attach a smaller file. Limit is 8 MB for this prototype.");
    mediaInput.value = "";
    return;
  }

  const url = URL.createObjectURL(file);
  const preview = file.type.startsWith("image/")
    ? `<img src="${url}" alt="Selected disaster evidence preview">`
    : `<video src="${url}" controls muted></video>`;
  mediaPreview.innerHTML = `
    ${preview}
    <div>
      <strong>${file.name}</strong>
      <span>${file.type || "media"} · ${(file.size / 1024 / 1024).toFixed(2)} MB</span>
    </div>
  `;
  mediaPreview.classList.remove("hidden");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = document.getElementById("sosText").value.trim();
  if (!text) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Uploading secure payload...";

  const incidentId = `SOS-${Math.floor(Math.random() * 90000 + 10000)}`;
  const media = await readSelectedMedia();
  const payload = {
    incident_id: incidentId,
    location: {
      latitude: Number(document.getElementById("latInput").value),
      longitude: Number(document.getElementById("lonInput").value),
      accuracy_meters: lastGpsFix ? lastGpsFix.accuracy : 0,
      source: lastGpsFix ? lastGpsFix.source : "manual",
    },
    raw_text: text,
    media_attached: Boolean(media),
    media,
    timestamp: new Date().toISOString(),
  };

  try {
    const response = await fetch("/api/sos-alert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Backend error");
    showTracker(data.incident);
  } catch (error) {
    alert(`Transmission failed: ${error.message}`);
    submitBtn.disabled = false;
    submitBtn.textContent = "Initiate Emergency Protocol";
  }
});

function showTracker(incident) {
  form.classList.add("hidden");
  tracker.classList.remove("hidden");
  document.getElementById("incidentId").textContent = incident.incident_id;
  document.getElementById("incidentSeverity").textContent =
    `${incident.ai_analysis.severity} ${incident.ai_analysis.disaster_type}`;
  document.getElementById("aiBriefing").textContent = incident.briefing;

  const phases = [
    ["Payload received", "SOS packet verified by command center API."],
    ["AI analysis complete", `${incident.ai_analysis.engine} generated DSS ${incident.ai_analysis.severity_score}/100.`],
    ["Evidence transferred", incident.media_attached ? "Photo/video evidence attached for rescue team review." : "No media evidence attached."],
    ["Resources allocated", "Ambulance, medical, rescue, volunteer, food, water and shelter allocation calculated."],
    ["Dashboard synchronized", "Rescue control center now sees this incident live."],
  ];
  const timeline = document.getElementById("timeline");
  timeline.innerHTML = phases.map(([title, body]) => `
    <article>
      <span></span>
      <div><strong>${title}</strong><p>${body}</p></div>
    </article>
  `).join("");
}

function getGpsPosition(options) {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });
}

function watchGpsPosition(options) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        if (settled) return;
        settled = true;
        navigator.geolocation.clearWatch(watchId);
        resolve(position);
      },
      (error) => {
        if (error.code === 1 && !settled) {
          settled = true;
          navigator.geolocation.clearWatch(watchId);
          reject(error);
        }
      },
      options
    );

    window.setTimeout(() => {
      if (settled) return;
      settled = true;
      navigator.geolocation.clearWatch(watchId);
      reject({ code: 3 });
    }, options.timeout || 30000);
  });
}

function applyGpsPosition(position, source) {
  const lat = position.coords.latitude;
  const lon = position.coords.longitude;
  const accuracy = Math.round(position.coords.accuracy || 0);
  document.getElementById("latInput").value = lat.toFixed(6);
  document.getElementById("lonInput").value = lon.toFixed(6);
  lastGpsFix = { accuracy, source, captured_at: new Date().toISOString() };
  gpsStatus.textContent = `Current location captured by ${source}. Accuracy about ${accuracy || "unknown"} meters.`;
  gpsBtn.textContent = "Location updated";
  gpsBtn.disabled = false;
}

function gpsErrorMessage(error) {
  if (error.code === 1) return "Location permission is blocked.";
  if (error.code === 2) return "The device/browser could not determine current location.";
  if (error.code === 3) return "GPS request timed out after permission was allowed.";
  return "GPS could not read current location.";
}

function locationHelpText() {
  const browserName = navigator.userAgent.includes("Safari") && !navigator.userAgent.includes("Chrome")
    ? "Safari"
    : navigator.userAgent.includes("Chrome")
      ? "Chrome"
      : "this browser";
  return `Check that ${browserName} has Location permission in browser site settings and in macOS System Settings > Privacy & Security > Location Services. If testing on phone, open the SOS app from HTTPS or localhost on that phone.`;
}

function readSelectedMedia() {
  const file = mediaInput.files[0];
  if (!file) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({
      name: file.name,
      type: file.type,
      size: file.size,
      data_url: reader.result,
    });
    reader.onerror = () => reject(new Error("Could not read selected media file"));
    reader.readAsDataURL(file);
  });
}
