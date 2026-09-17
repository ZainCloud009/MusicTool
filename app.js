// Automatically detect backend API base URL
// Agar local chal raha ho to local server, warna Render backend URL use karega:
const IS_LOCAL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const BACKEND_SERVICE_URL = "https://musictool.onrender.com";

const API_BASE = IS_LOCAL
  ? window.location.origin
  : BACKEND_SERVICE_URL;

const API_URL = `${API_BASE}/api/download`;

const urlInput = document.getElementById("url");
const downloadBtn = document.getElementById("downloadBtn");
const pasteBtn = document.getElementById("pasteBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progressWrap");
const progressEl = document.getElementById("progress");
const resultEl = document.getElementById("result");
const activePlatformLabel = document.getElementById("activePlatformLabel");

// Mobile Drawer Elements
const mobileMenuToggle = document.getElementById("mobileMenuToggle");
const mobileDrawer = document.getElementById("mobileDrawer");
const mobileDrawerBackdrop = document.getElementById("mobileDrawerBackdrop");
const mobileDrawerClose = document.getElementById("mobileDrawerClose");
const mobileFeatureItems = document.querySelectorAll(".mobile-feature-item");
const mobileDrawerLinks = document.querySelectorAll(".mobile-drawer-link");

let progressInterval = null;

// Platform place-holders and labels
const platformConfigs = {
  all: {
    label: "Free Music Download & Video Supported",
    placeholder: "Just paste music link, song URL, TikTok, YouTube Shorts, or Instagram link..."
  },
  music: {
    label: "Free Music Download (Just Paste Music Link)",
    placeholder: "Just paste music link, song URL, or video link to download free music..."
  },
  tiktok: {
    label: "TikTok Downloader (No Watermark)",
    placeholder: "Paste TikTok video link (e.g. https://www.tiktok.com/@...)..."
  },
  youtube: {
    label: "YouTube Shorts & Video Downloader",
    placeholder: "Paste YouTube or Shorts URL (e.g. https://youtube.com/shorts/...)..."
  },
  instagram: {
    label: "Instagram Reels & Story Downloader",
    placeholder: "Paste Instagram Reel or Post link (e.g. https://instagram.com/reel/...)..."
  },
  facebook: {
    label: "Facebook Video & Reels Downloader",
    placeholder: "Paste Facebook video or reel URL..."
  },
  twitter: {
    label: "Twitter / X Video Downloader",
    placeholder: "Paste Twitter/X post URL containing a video..."
  },
  snapchat: {
    label: "Snapchat Spotlight Downloader",
    placeholder: "Paste Snapchat video or story link..."
  }
};

// Open & Close Mobile Features Drawer
function openMobileMenu() {
  if (!mobileDrawer) return;
  mobileDrawer.classList.add("open");
  if (mobileDrawerBackdrop) mobileDrawerBackdrop.classList.add("active");
  if (mobileMenuToggle) mobileMenuToggle.setAttribute("aria-expanded", "true");
  mobileDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");
}

function closeMobileMenu() {
  if (!mobileDrawer) return;
  mobileDrawer.classList.remove("open");
  if (mobileDrawerBackdrop) mobileDrawerBackdrop.classList.remove("active");
  if (mobileMenuToggle) mobileMenuToggle.setAttribute("aria-expanded", "false");
  mobileDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("drawer-open");
}

if (mobileMenuToggle) {
  mobileMenuToggle.addEventListener("click", () => {
    if (mobileDrawer && mobileDrawer.classList.contains("open")) {
      closeMobileMenu();
    } else {
      openMobileMenu();
    }
  });
}

if (mobileDrawerClose) {
  mobileDrawerClose.addEventListener("click", closeMobileMenu);
}

if (mobileDrawerBackdrop) {
  mobileDrawerBackdrop.addEventListener("click", closeMobileMenu);
}

// Close drawer on Escape key press
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && mobileDrawer && mobileDrawer.classList.contains("open")) {
    closeMobileMenu();
  }
});

// Close drawer when clicking internal guide / FAQ links
mobileDrawerLinks.forEach(link => {
  link.addEventListener("click", () => {
    closeMobileMenu();
  });
});

// Unified Platform Selection (for both Desktop navbar & Mobile drawer)
function selectPlatform(platform) {
  const config = platformConfigs[platform] || platformConfigs.all;

  // Sync Desktop buttons
  document.querySelectorAll(".nav-platform-btn").forEach(btn => {
    if (btn.getAttribute("data-platform") === platform) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Sync Mobile drawer items
  document.querySelectorAll(".mobile-feature-item").forEach(item => {
    const indicator = item.querySelector(".feature-item-indicator");
    if (item.getAttribute("data-platform") === platform) {
      item.classList.add("active");
      if (indicator) indicator.textContent = "Active";
    } else {
      item.classList.remove("active");
      if (indicator) indicator.textContent = "Select";
    }
  });

  // Update input placeholder & label
  if (activePlatformLabel) {
    activePlatformLabel.textContent = config.label;
  }
  if (urlInput) {
    urlInput.placeholder = config.placeholder;
    urlInput.focus();
  }

  // Close mobile drawer smoothly if open
  closeMobileMenu();

  // Smooth scroll down to downloader card
  const downloaderCard = document.querySelector(".downloader-card");
  if (downloaderCard) {
    downloaderCard.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

// Desktop platform buttons click
document.querySelectorAll(".nav-platform-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const platform = btn.getAttribute("data-platform");
    selectPlatform(platform);
  });
});

// Mobile platform items click
document.querySelectorAll(".mobile-feature-item").forEach(item => {
  item.addEventListener("click", () => {
    const platform = item.getAttribute("data-platform");
    selectPlatform(platform);
  });
});

// Show/hide Clear button based on input
urlInput.addEventListener("input", () => {
  if (urlInput.value.trim().length > 0) {
    clearBtn.classList.remove("hidden");
  } else {
    clearBtn.classList.add("hidden");
  }
});

clearBtn.addEventListener("click", () => {
  urlInput.value = "";
  clearBtn.classList.add("hidden");
  statusEl.textContent = "Ready to download";
  resultEl.classList.add("hidden");
  urlInput.focus();
});

// Paste button
pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      urlInput.value = text.trim();
      clearBtn.classList.remove("hidden");
      statusEl.textContent = "Link pasted ✓ Ready to download";
      urlInput.focus();
    }
  } catch {
    statusEl.textContent = "Clipboard permission denied. Please paste manually (Ctrl+V).";
  }
});

// Allow pressing Enter in URL input to trigger download
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    downloadBtn.click();
  }
});

function startProgressAnimation() {
  progressEl.style.width = "15%";
  statusEl.textContent = "Connecting to video source...";

  let currentPercent = 15;
  const stages = [
    { at: 35, text: "Extracting high-definition video & audio streams..." },
    { at: 65, text: "Downloading best quality media..." },
    { at: 85, text: "Merging streams into MP4 file..." }
  ];

  progressInterval = setInterval(() => {
    if (currentPercent < 88) {
      currentPercent += Math.random() * 7 + 2;
      if (currentPercent > 88) currentPercent = 88;
      progressEl.style.width = `${Math.round(currentPercent)}%`;

      for (const stage of stages) {
        if (currentPercent >= stage.at) {
          statusEl.textContent = stage.text;
        }
      }
    }
  }, 700);
}

function stopProgressAnimation(isSuccess = true) {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  progressEl.style.width = isSuccess ? "100%" : "0%";
}

function triggerDownload(fileUrl, filename) {
  const link = document.createElement("a");
  link.href = fileUrl;
  link.download = filename || "video.mp4";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function formatDuration(seconds) {
  if (!seconds || isNaN(seconds)) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

downloadBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();

  if (!url) {
    statusEl.textContent = "Please paste a video URL first.";
    urlInput.focus();
    return;
  }

  try {
    new URL(url);
  } catch {
    statusEl.textContent = "Please enter a valid URL (e.g. https://...)";
    return;
  }

  downloadBtn.disabled = true;
  resultEl.classList.add("hidden");
  resultEl.innerHTML = "";
  progressWrap.classList.remove("hidden");
  startProgressAnimation();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server returned error (${response.status})`);
    }

    const data = await response.json();

    if (!data.download_url) {
      throw new Error("Server processed video but returned no download link.");
    }

    stopProgressAnimation(true);
    statusEl.textContent = "Video ready! Downloading ✓";

    const fileUrl = data.download_url.startsWith("http")
      ? data.download_url
      : `${API_BASE}${data.download_url}`;

    // Build rich video preview card
    let cardContent = `
      <div class="preview-card">
        ${data.thumbnail ? `<div class="preview-thumb-wrap"><img src="${escapeHtml(data.thumbnail)}" alt="Thumbnail" class="preview-thumb" onerror="this.parentElement.style.display='none'"></div>` : ""}
        <div class="preview-details">
          <div class="preview-title">${escapeHtml(data.title || "Social Video")}</div>
          <div class="preview-meta">
            ${data.uploader ? `<span class="meta-tag">👤 ${escapeHtml(data.uploader)}</span>` : ""}
            ${data.duration ? `<span class="meta-tag">⏱ ${formatDuration(data.duration)}</span>` : ""}
            <span class="meta-tag meta-format">MP4 HD</span>
          </div>
          <a href="${escapeHtml(fileUrl)}" download="${escapeHtml(data.filename || 'video.mp4')}" class="direct-download-btn">
            ⬇ Save Video to Device
          </a>
        </div>
      </div>
    `;

    resultEl.innerHTML = cardContent;
    resultEl.className = "result success";
    resultEl.classList.remove("hidden");

    // Automatically trigger browser download
    triggerDownload(fileUrl, data.filename);

  } catch (err) {
    stopProgressAnimation(false);
    statusEl.textContent = "Download failed ✕";

    let errorMsg = err.message || "An unexpected error occurred.";
    if (errorMsg.includes("Failed to fetch") || errorMsg.includes("NetworkError")) {
      errorMsg = `Cannot connect to server at <strong>${API_BASE}</strong>.<br><br>Make sure the backend is running: <code>uvicorn main:app --reload</code> or double-click <code>start.bat</code>.`;
    }

    resultEl.innerHTML = `<div class="error-msg">${errorMsg}</div>`;
    resultEl.className = "result error";
    resultEl.classList.remove("hidden");
  } finally {
    downloadBtn.disabled = false;
  }
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
