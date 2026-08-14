const state = {
  mode: "video",
  pollTimer: null,
  tiktokPollTimer: null,
};

const modeCopy = {
  video: {
    label: "Link video Douyin · mỗi dòng một link",
    placeholder: "https://www.douyin.com/video/...\nhttps://www.douyin.com/video/...",
    hint: "Dán nhiều link, mỗi dòng một link. Có thể dùng cả link dạng <code>modal_id=...</code>.",
  },
  user: {
    label: "Link profile Douyin",
    placeholder: "www.douyin.com/user/...",
    hint: "Cliproom sẽ lấy các video mới nhất từ profile này rồi tải theo giới hạn bạn chọn.",
  },
  keyword: {
    label: "Từ khóa tìm kiếm",
    placeholder: "truyện ngắn, nấu ăn, phong cảnh...",
    hint: "Kết quả sẽ được sắp xếp theo ngày đăng mới nhất trước.",
  },
};

const $ = (selector) => document.querySelector(selector);

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-button").forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });

  const copy = modeCopy[mode];
  $("#sourceLabel").textContent = copy.label;
  $("#sourceInput").placeholder = copy.placeholder;
  $("#fieldHint").innerHTML = copy.hint;
  $("#limitField").classList.toggle("is-hidden", mode === "video");
  $("#inputPrefix").classList.toggle("is-hidden", mode === "keyword");
  $("#sourceInput").focus();
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 3400);
}

function setTikTokPolling(active) {
  window.clearInterval(state.tiktokPollTimer);
  state.tiktokPollTimer = null;
  if (active) {
    state.tiktokPollTimer = window.setInterval(loadTikTokStatus, 1200);
  }
}

function renderTikTokStatus(snapshot) {
  const status = snapshot.status || "closed";
  const job = snapshot.job || {};
  const stepLogin = $("#tiktokStepLogin");
  const stepUpload = $("#tiktokStepUpload");
  const stepPost = $("#tiktokStepPost");
  [stepLogin, stepUpload, stepPost].forEach((step) => step.classList.remove("is-current", "is-complete"));

  if (["browser_open", "queued", "uploading", "processing", "ready_to_post"].includes(status)) {
    stepLogin.classList.add("is-complete");
  } else {
    stepLogin.classList.add("is-current");
  }
  if (["uploading", "processing"].includes(status)) stepUpload.classList.add("is-current");
  if (status === "ready_to_post") {
    stepUpload.classList.add("is-complete");
    stepPost.classList.add("is-current");
  }
  if (status === "failed") stepUpload.classList.add("is-current");

  const labels = {
    closed: ["Chưa mở Chrome", "Bấm “Mở Chrome và tự upload” để bắt đầu."],
    starting: ["Đang mở Chrome", "Chrome thường đang được khởi động."],
    browser_open: ["Chrome đã kết nối", "Đăng nhập Gmail/TikTok trên Chrome, Cliproom sẽ tự tiếp tục."],
    waiting_login: ["Đang chờ đăng nhập", "Đăng nhập Gmail/TikTok và xử lý xác minh. Cliproom sẽ tự tiếp tục."],
    queued: ["Đang xếp lượt upload", job.message || "Đang chuẩn bị video."],
    uploading: ["Đang upload video", job.message || "TikTok đang nhận video."],
    processing: ["TikTok đang xử lý", job.message || "Đợi TikTok hoàn tất xử lý video."],
    ready_to_post: ["Đã sẵn sàng để Post", "Kiểm tra video và caption trên Chrome, rồi tự bấm Post."],
    failed: ["Có lỗi khi chuẩn bị", snapshot.message || job.message || "Hãy kiểm tra cửa sổ Chrome và thử lại."],
  };
  const [title, description] = labels[status] || [status, snapshot.message || ""];
  const stateIcon = status === "ready_to_post" ? "✓" : status === "failed" ? "!" : String(job.progress || 1);
  $("#tiktokState").innerHTML = `<span class="publish-state-icon">${stateIcon}</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div>`;

  const dot = $("#tiktokStatusDot");
  dot.classList.toggle("is-busy", ["starting", "browser_open", "waiting_login", "queued", "uploading", "processing"].includes(status));
  dot.classList.toggle("is-error", status === "failed");
  $("#tiktokCloseButton").classList.toggle("is-hidden", status === "closed");
  const busy = ["starting", "browser_open", "waiting_login", "queued", "uploading", "processing", "ready_to_post"].includes(status);
  $("#tiktokOpenButton").disabled = busy;
  $("#tiktokOpenButton").querySelector(".button-label").textContent = busy ? "Đang chờ Chrome..." : "Mở Chrome và tự upload";
}

async function loadTikTokStatus() {
  try {
    const response = await fetch("/api/tiktok/status");
    const snapshot = await response.json();
    renderTikTokStatus(snapshot);
    if (snapshot.status === "closed") setTikTokPolling(false);
  } catch (error) {
    showToast("Không đọc được trạng thái TikTok.");
    setTikTokPolling(false);
  }
}

async function openTikTok() {
  const button = $("#tiktokOpenButton");
  button.disabled = true;
  try {
    const response = await fetch("/api/tiktok/start", { method: "POST" });
    const snapshot = await response.json();
    if (!response.ok) throw new Error(snapshot.error || "Không mở được TikTok.");
    renderTikTokStatus(snapshot);
    setTikTokPolling(true);
    showToast("Đã mở Chrome thường. Hãy đăng nhập Gmail/TikTok thủ công.");
  } catch (error) {
    showToast(error.message);
  } finally {
    if (!state.tiktokPollTimer) button.disabled = false;
  }
}

async function closeTikTok() {
  await fetch("/api/tiktok/close", { method: "POST" });
  setTikTokPolling(false);
  await loadTikTokStatus();
  showToast("Đã đóng phiên TikTok.");
}

function setActivityVisible(visible) {
  $("#activityEmpty").classList.toggle("is-hidden", visible);
  $("#activityRunning").classList.toggle("is-hidden", !visible);
}

function setButtonBusy(busy) {
  const button = $("#downloadButton");
  button.disabled = busy;
  button.querySelector(".button-label").textContent = busy ? "Đang tải..." : "Tải video xuống";
}

function renderJob(job) {
  setActivityVisible(true);
  const percent = Math.max(0, Math.min(100, job.progress || 0));
  $("#jobPercent").textContent = `${percent}%`;
  $("#progressBar").style.width = `${percent}%`;
  $("#jobMessage").textContent = job.message || "Đang xử lý...";

  const waitingForVerification = ["waiting_verification", "needs_verification"].includes(job.status);
  $("#manualVerification").classList.toggle("is-hidden", !waitingForVerification);
  if (waitingForVerification) {
    $("#verificationButton").dataset.url = job.verification_url || "";
    $("#verificationButton").dataset.browser = job.verification_browser || "chrome";
  }

  const chip = $("#jobStatusChip");
  chip.classList.toggle("is-success", job.status === "completed");
  chip.classList.toggle("is-error", job.status === "failed");
  chip.textContent = {
    queued: "Đang xếp hàng",
    running: "Đang tải",
    waiting_verification: "Đang chờ xác minh",
    completed: "Hoàn tất",
    failed: "Có lỗi",
    needs_verification: "Cần xác minh",
  }[job.status] || job.status;

  $("#jobItems").innerHTML = (job.items || []).map((item) => `
    <div class="job-item">
      <span class="job-item-icon">${item.status === "downloaded" ? "✓" : "!"}</span>
      <span class="job-item-text" title="${escapeHtml(item.file || item.url || item.error || "")}">${escapeHtml(item.file || item.error || item.url || "")}</span>
      <span class="job-item-state">${item.status === "downloaded" ? "Sẵn sàng" : "Lỗi"}</span>
    </div>
  `).join("");
  $("#jobLog").textContent = (job.logs || []).slice(-3).join("\n");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[character]));
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    renderJob(job);

    if (["completed", "failed", "needs_verification"].includes(job.status)) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
      setButtonBusy(false);
      await loadLibrary();
      if (job.status === "completed") showToast("Video đã sẵn sàng trong local library.");
      if (job.status === "failed") showToast(job.message || "Tải video thất bại.");
      if (job.status === "needs_verification") showToast("Hãy xác minh CAPTCHA trên Chrome rồi tải lại.");
    }
  } catch (error) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
    setButtonBusy(false);
    showToast("Không kết nối được với Cliproom.");
  }
}

async function submitDownload(event) {
  event.preventDefault();
  const value = $("#sourceInput").value.trim();
  if (!value) {
    $("#sourceInput").focus();
    showToast("Hãy dán link hoặc nhập từ khóa trước.");
    return;
  }

  const payload = {
    mode: state.mode,
    value,
    limit: Number($("#limitInput").value) || 10,
    browser: $("#browserSelect").value,
  };

  setButtonBusy(true);
  setActivityVisible(true);
  renderJob({ status: "queued", progress: 0, message: "Đang kết nối với downloader...", items: [], logs: [] });

  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Không thể tạo lượt tải.");
    window.clearInterval(state.pollTimer);
    state.pollTimer = window.setInterval(() => pollJob(data.job_id), 800);
    await pollJob(data.job_id);
  } catch (error) {
    setButtonBusy(false);
    showToast(error.message);
  }
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

async function loadLibrary() {
  const list = $("#libraryList");
  try {
    const response = await fetch("/api/videos");
    const data = await response.json();
    if (!data.videos.length) {
      list.innerHTML = '<div class="library-empty">Chưa có video nào. Dán link đầu tiên ở phía trên.</div>';
      return;
    }
    list.innerHTML = data.videos.map((video) => `
      <div class="library-item">
        <span class="file-icon">▶</span>
        <div>
          <div class="file-name" title="${escapeHtml(video.name)}">${escapeHtml(video.name)}</div>
          <div class="file-meta">Đã thêm ${formatDate(video.modified)}</div>
        </div>
        <span class="file-size">${formatBytes(video.size)}</span>
      </div>
    `).join("");
  } catch (error) {
    list.innerHTML = '<div class="library-empty">Không đọc được thư mục video.</div>';
  }
}

$("#downloadForm").addEventListener("submit", submitDownload);
$("#tiktokOpenButton").addEventListener("click", openTikTok);
$("#tiktokCloseButton").addEventListener("click", closeTikTok);
$("#clearInput").addEventListener("click", () => { $("#sourceInput").value = ""; $("#sourceInput").focus(); });
$("#refreshLibrary").addEventListener("click", loadLibrary);
$("#openFolder").addEventListener("click", async () => {
  await fetch("/api/open-folder", { method: "POST" });
  showToast("Đã mở thư mục video.");
});
$("#verificationButton").addEventListener("click", async () => {
  const button = $("#verificationButton");
  const url = button.dataset.url;
  if (!url) return;

  try {
    const response = await fetch("/api/open-browser", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, browser: button.dataset.browser || "chrome" }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Không mở được Douyin.");
    showToast("Đã mở trang Douyin để xác minh thủ công.");
  } catch (error) {
    showToast(error.message);
  }
});
document.querySelectorAll(".mode-button").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
loadLibrary();
loadTikTokStatus();
