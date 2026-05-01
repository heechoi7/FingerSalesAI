const workspace = document.querySelector(".workspace");
const chatInput = document.querySelector(".chat-input");
const commandInput = document.querySelector("[data-command-input]");
const chatStream = document.querySelector(".chat-stream");
const canvasTitle = document.querySelector("#canvas-title");
const canvasArea = document.querySelector(".canvas-area");
const menuButtons = document.querySelectorAll(".main-nav button");
const panelFocusButtons = document.querySelectorAll(".maximize-panel-btn");
const attachButton = document.querySelector(".attach-btn");
const fileInput = document.querySelector("#chat-file-input");
const attachmentPreview = document.querySelector(".attachment-preview");
const agentStack = document.querySelector(".agent-stack");
const logList = document.querySelector(".log-list");
const sendButton = document.querySelector(".send-btn");
let customerTableBody = document.querySelector("#customer-table-body");
let customerDetailList = document.querySelector("#customer-detail-list");
let customerDetailTitle = document.querySelector("#customer-detail-title");
const sessionUserLabel = document.querySelector("#session-user-label");
const logoutButton = document.querySelector("#logout-button");
const adminLink = document.querySelector("#admin-link");
const dropTargets = [document.querySelector(".chat-panel"), document.querySelector(".chat-input"), chatStream].filter(Boolean);

let dragState = null;
let pendingFiles = [];
const pendingCustomerCommands = new Map();
let isSubmitting = false;
let isLoadingCustomers = false;
let questionSequence = 0;
let currentSession = null;
const memory = {
  cards: [],
  messages: [],
  selectedCustomer: null,
};

function pendingFileKey(file) {
  return [file?.name || "", file?.size || 0, file?.lastModified || 0].join(":");
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function startResize(event, side) {
  if (window.innerWidth <= 1024) return;

  const pointerX = event.clientX ?? event.touches?.[0]?.clientX;
  const rect = workspace.getBoundingClientRect();
  const styles = getComputedStyle(document.documentElement);

  dragState = {
    side,
    rect,
    left: parseFloat(styles.getPropertyValue("--left-size")) || 50,
    top: parseFloat(styles.getPropertyValue("--left-top-size")) || 65,
    right: parseFloat(styles.getPropertyValue("--right-size")) || 20,
    pointerX,
    pointerY: event.clientY ?? event.touches?.[0]?.clientY,
  };

  event.currentTarget.classList.add("active");
  document.body.style.userSelect = "none";
}

function resizePanels(event) {
  if (!dragState) return;

  const pointerX = event.clientX ?? event.touches?.[0]?.clientX;
  const pointerY = event.clientY ?? event.touches?.[0]?.clientY;
  const deltaPercent = ((pointerX - dragState.pointerX) / dragState.rect.width) * 100;
  const deltaYPercent = ((pointerY - dragState.pointerY) / dragState.rect.height) * 100;

  if (dragState.side === "left") {
    document.documentElement.style.setProperty("--left-size", `${clamp(dragState.left + deltaPercent, 30, 60)}%`);
  }

  if (dragState.side === "left-vertical") {
    document.documentElement.style.setProperty("--left-top-size", `${clamp(dragState.top + deltaYPercent, 45, 78)}%`);
  }

  if (dragState.side === "right") {
    document.documentElement.style.setProperty("--right-size", `${clamp(dragState.right - deltaPercent, 16, 36)}%`);
  }
}

function stopResize() {
  if (!dragState) return;
  document.querySelectorAll(".splitter.active").forEach((splitter) => splitter.classList.remove("active"));
  document.body.style.userSelect = "";
  dragState = null;
}

function nudgePanel(side, direction) {
  if (window.innerWidth <= 1024) return;

  const styles = getComputedStyle(document.documentElement);
  const left = parseFloat(styles.getPropertyValue("--left-size")) || 50;
  const right = parseFloat(styles.getPropertyValue("--right-size")) || 20;

  if (side === "left") {
    document.documentElement.style.setProperty("--left-size", `${clamp(left + direction * 2, 30, 60)}%`);
  }

  if (side === "left-vertical") {
    const top = parseFloat(styles.getPropertyValue("--left-top-size")) || 65;
    document.documentElement.style.setProperty("--left-top-size", `${clamp(top + direction * 2, 45, 78)}%`);
  }

  if (side === "right") {
    document.documentElement.style.setProperty("--right-size", `${clamp(right - direction * 2, 16, 36)}%`);
  }
}

document.querySelector(".splitter-left")?.addEventListener("pointerdown", (event) => {
  event.currentTarget.setPointerCapture(event.pointerId);
  startResize(event, "left");
});

document.querySelector(".splitter-left-vertical")?.addEventListener("pointerdown", (event) => {
  event.currentTarget.setPointerCapture(event.pointerId);
  startResize(event, "left-vertical");
});

document.querySelector(".splitter-right")?.addEventListener("pointerdown", (event) => {
  event.currentTarget.setPointerCapture(event.pointerId);
  startResize(event, "right");
});

document.querySelector(".splitter-left")?.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  nudgePanel("left", event.key === "ArrowRight" ? 1 : -1);
});

document.querySelector(".splitter-left-vertical")?.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
  event.preventDefault();
  nudgePanel("left-vertical", event.key === "ArrowDown" ? 1 : -1);
});

document.querySelector(".splitter-right")?.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  nudgePanel("right", event.key === "ArrowRight" ? 1 : -1);
});

window.addEventListener("pointermove", resizePanels);
window.addEventListener("pointerup", stopResize);

function clearPanelFocus() {
  workspace.classList.remove("focus-left", "focus-chat");
}

panelFocusButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (window.innerWidth <= 1024) return;
    const focusClass = `focus-${button.dataset.focusPanel}`;
    const isFocused = workspace.classList.contains(focusClass);
    clearPanelFocus();
    if (!isFocused) {
      workspace.classList.add(focusClass);
    }
  });
});

window.addEventListener("resize", () => {
  if (window.innerWidth <= 1024) {
    clearPanelFocus();
  }
});

function activateMainMenu(menu) {
  const target = Array.from(menuButtons).find((button) => button.dataset.menu === menu);
  if (!target) return;
  menuButtons.forEach((item) => item.classList.remove("active"));
  target.classList.add("active");
  canvasTitle.textContent = target.dataset.canvasTitle;
}

menuButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const menu = button.dataset.menu || "customers";
    activateMainMenu(menu);
    loadMenu(menu);
  });
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function redirectToLogin() {
  window.location.replace("/login.html");
}

function apiErrorMessage(result, fallback) {
  const parts = [result?.message || result?.detail || result?.error || fallback];
  if (result?.error_code) parts.push(`에러코드: ${result.error_code}`);
  if (result?.details?.situation) parts.push(`상황: ${result.details.situation}`);
  if (result?.details?.db_errno) parts.push(`DB 오류번호: ${result.details.db_errno}`);
  if (result?.request_id) parts.push(`요청ID: ${result.request_id}`);
  return parts.filter(Boolean).join(" / ");
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
  });
  if (response.status === 401) {
    redirectToLogin();
    throw new Error("로그인이 필요합니다.");
  }
  return response;
}

function updateSessionHeader(session) {
  currentSession = session;
  if (!sessionUserLabel) return;
  const roleText = session.role_label || session.role || "";
  const tenantText = session.tenant_name || session.tenant_code || "테넌트";
  const userText = session.user_name || session.email || "사용자";
  sessionUserLabel.innerHTML = `${escapeHtml(tenantText)} <span>/ ${escapeHtml(userText)} / ${escapeHtml(roleText)}</span>`;
  if (adminLink) {
    adminLink.hidden = !["owner", "admin"].includes(session.role);
  }
}

async function loadCurrentSession() {
  if (window.__FSAI_SESSION__) {
    updateSessionHeader(window.__FSAI_SESSION__);
  }
  const response = await apiFetch("/api/auth/me");
  const result = await response.json();
  if (!response.ok || !result.success) {
    throw new Error(result.detail || result.error || "로그인 정보를 불러오지 못했습니다.");
  }
  updateSessionHeader(result.session);
}

async function logout() {
  window.location.href = "/logout";
}

function appendMessage(role, content, options = {}) {
  const message = document.createElement("article");
  message.className = `message ${role}`;

  if (options.html) {
    const body = document.createElement("div");
    body.className = "message-body";
    body.innerHTML = content;
    message.append(body);
  } else if (options.richText) {
    const body = document.createElement("div");
    body.className = "message-body";
    body.innerHTML = renderRichText(content);
    message.append(body);
  } else {
    const paragraph = document.createElement("p");
    paragraph.textContent = content;
    message.append(paragraph);
  }

  chatStream.append(message);
  chatStream.scrollTop = chatStream.scrollHeight;
  return message;
}

function renderRichText(value) {
  const withoutBoldMarkers = String(value || "")
    .replaceAll("**", "")
    .replace(/(^|\n)(\s*)\*\s+/g, "$1$2• ");
  const escaped = escapeHtml(withoutBoldMarkers);
  const linked = escaped
    .split("\n")
    .map((line) => {
      const markdownLink = line.match(/^\s*\[([^\]]+)\]\((https?:\/\/.*)\)\s*$/);
      if (markdownLink) {
        const label = markdownLink[1];
        const url = markdownLink[2].replace(/&amp;/g, "&");
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      }

      if (/^\s*https?:\/\/\S+\s*$/.test(line)) {
        return "";
      }

      return line.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => {
        return `<a href="${url.replace(/&amp;/g, "&")}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      });
    })
    .filter((line) => line.trim() !== "");

  return linked
    .join("\n")
    .split(/\n{2,}/)
    .map((block) => `<p>${block.replace(/\n/g, "<br />")}</p>`)
    .join("");
}

function rememberMessage(role, content) {
  memory.messages.push({
    role,
    content: String(content || "").slice(0, 3000),
    createdAt: new Date().toISOString(),
  });

  if (memory.messages.length > 20) {
    memory.messages = memory.messages.slice(-20);
  }
}

function rememberCardInfo(file, data, briefing, customer = null) {
  memory.cards.unshift({
    id: customer?.id || null,
    fileName: file.name,
    data: data || {},
    briefing: briefing || "",
    createdAt: customer?.created_at || new Date().toISOString(),
  });

  if (memory.cards.length > 10) {
    memory.cards = memory.cards.slice(0, 10);
  }
}

function renderCustomerView() {
  if (!canvasArea) return;
  canvasArea.innerHTML = `
    <div class="module-view">
      <form class="module-filter" id="customer-filter-form">
        ${filterInput("company_name", "회사명")}
        ${filterInput("contact_name", "고객명")}
        ${searchIconButton()}
      </form>
      <div class="customer-table-wrap" aria-label="고객 정보 그리드">
        <table class="customer-table">
          <thead>
            <tr>
              <th>회사명</th>
              <th>이름</th>
              <th>직무</th>
              <th>직위</th>
              <th>휴대전화</th>
              <th>이메일</th>
              <th>홈페이지</th>
              <th>추가 정보</th>
              <th>등록 시간</th>
            </tr>
          </thead>
          <tbody id="customer-table-body">
            <tr class="empty-row"><td colspan="9">조회할 고객 조건을 입력하거나 조회 버튼을 눌러 주세요.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
  customerTableBody = document.querySelector("#customer-table-body");
  customerDetailList = document.querySelector("#customer-detail-list");
  customerDetailTitle = document.querySelector("#customer-detail-title");
  document.querySelector("#customer-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadCustomers();
  });
}

function filterQuery(formId) {
  const form = document.querySelector(formId);
  const params = new URLSearchParams();
  if (!form) return params;
  new FormData(form).forEach((value, key) => {
    const text = String(value || "").trim();
    if (text) params.set(key, text);
  });
  return params;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateOnly(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function formatAmount(amount, currency = "KRW") {
  if (amount === null || amount === undefined || amount === "") return "-";
  const number = Number(amount);
  if (Number.isNaN(number)) return String(amount);
  return `${currency || "KRW"} ${number.toLocaleString("ko-KR")}`;
}

function documentLinkValue(row) {
  if (!row?.document_url) return "-";
  return {
    html: `<a class="document-download-link" href="${escapeHtml(row.document_url)}" target="_blank" rel="noopener">${escapeHtml(row.document_filename || "파일 다운로드")}</a>`,
  };
}

function detailRowsHtml(rows) {
  return rows
    .map(([label, value]) => {
      const content = value && typeof value === "object" && value.html ? value.html : escapeHtml(value || "-");
      return `<div class="detail-field-row"><dt>${escapeHtml(label)}</dt><dd>${content}</dd></div>`;
    })
    .join("");
}

function showDetail(title, rows) {
  if (customerDetailTitle) customerDetailTitle.textContent = title || "상세 정보";
  if (!customerDetailList) return;
  customerDetailList.classList.remove("detail-list-tabbed");
  customerDetailList.innerHTML = detailRowsHtml(rows);
}

function documentViewerHtml(row, typeLabel) {
  if (!row?.document_id) {
    return `<div class="document-viewer-empty">${escapeHtml(typeLabel)}에 연결된 업로드 문서가 없습니다.</div>`;
  }
  const filename = row.document_filename || "업로드 문서";
  const downloadUrl = row.document_url || `/api/documents/${row.document_id}/download`;
  const viewUrl = row.document_view_url || `/api/documents/${row.document_id}/view`;
  const contentType = String(row.document_content_type || "").toLowerCase();
  const canEmbed =
    contentType.startsWith("application/pdf") ||
    contentType.startsWith("image/") ||
    contentType.startsWith("text/");
  const extractedText = String(row.document_text || "").trim();
  const preview = canEmbed
    ? `<iframe class="document-viewer-frame" src="${escapeHtml(viewUrl)}" title="${escapeHtml(filename)}"></iframe>`
    : `<div class="document-text-preview">${
        extractedText
          ? escapeHtml(extractedText)
          : "이 문서 형식은 브라우저 내부 미리보기를 지원하지 않습니다. 원본 다운로드로 확인해 주세요."
      }</div>`;
  return `
    <div class="document-viewer">
      <div class="document-viewer-toolbar">
        <span>${escapeHtml(filename)}</span>
        <a class="document-download-link" href="${escapeHtml(downloadUrl)}" target="_blank" rel="noopener">다운로드</a>
      </div>
      ${preview}
    </div>
  `;
}

function showTabbedDetail(title, tabs) {
  if (customerDetailTitle) customerDetailTitle.textContent = title || "상세 정보";
  if (!customerDetailList) return;
  const safeTabs = tabs.filter(Boolean);
  customerDetailList.classList.add("detail-list-tabbed");
  customerDetailList.innerHTML = `
    <div class="detail-tabs">
      <div class="detail-tab-list" role="tablist">
        ${safeTabs
          .map(
            (tab, index) => `
              <button class="detail-tab-button${index === 0 ? " active" : ""}" type="button" role="tab"
                aria-selected="${index === 0 ? "true" : "false"}" data-detail-tab="${escapeHtml(tab.id)}">
                ${escapeHtml(tab.label)}
              </button>
            `
          )
          .join("")}
      </div>
      ${safeTabs
        .map((tab, index) => {
          const content = tab.html || detailRowsHtml(tab.rows || []);
          return `<section class="detail-tab-panel${index === 0 ? " active" : ""}" role="tabpanel" data-detail-panel="${escapeHtml(tab.id)}">${content}</section>`;
        })
        .join("")}
    </div>
  `;

  customerDetailList.querySelectorAll("[data-detail-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tabId = button.dataset.detailTab;
      customerDetailList.querySelectorAll("[data-detail-tab]").forEach((item) => {
        const isActive = item.dataset.detailTab === tabId;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      customerDetailList.querySelectorAll("[data-detail-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.detailPanel === tabId);
      });
    });
  });
}

function searchIconButton(label = "조회") {
  return `
    <button class="module-search-button" type="submit" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="7"></circle>
        <path d="m20 20-3.5-3.5"></path>
      </svg>
    </button>
  `;
}

function filterInput(name, placeholder) {
  return `<input name="${escapeHtml(name)}" placeholder="${escapeHtml(placeholder)}" aria-label="${escapeHtml(placeholder)}" />`;
}

function renderDataTable({ rows, columns, emptyMessage, onSelect }) {
  const bodyRows = rows.length
    ? rows
        .map((row, index) => {
          const cells = columns.map((column) => `<td>${escapeHtml(column.value(row) || "-")}</td>`).join("");
          return `<tr class="data-row" data-row-index="${index}">${cells}</tr>`;
        })
        .join("")
    : `<tr class="empty-row"><td colspan="${columns.length}">${escapeHtml(emptyMessage)}</td></tr>`;
  return `
    <div class="customer-table-wrap module-table-wrap">
      <table class="customer-table">
        <thead><tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>
  `;
}

function bindDataRows(rows, detailFactory, options = {}) {
  const selectRow = (row) => {
    document.querySelectorAll(".data-row.selected").forEach((item) => item.classList.remove("selected"));
    row.classList.add("selected");
    const item = rows[Number(row.dataset.rowIndex)];
    const detail = detailFactory(item);
    if (detail.tabs) {
      showTabbedDetail(detail.title, detail.tabs);
    } else {
      showDetail(detail.title, detail.rows);
    }
    if (options.scroll !== false) row.scrollIntoView({ block: "nearest" });
  };

  document.querySelectorAll(".data-row").forEach((row) => {
    row.addEventListener("click", () => selectRow(row));
  });

  if (rows.length && options.autoSelect !== false) {
    const firstRow = document.querySelector(".data-row");
    if (firstRow) selectRow(firstRow);
  } else if (!rows.length && options.autoSelect !== false) {
    showDetail(options.emptyTitle || "상세 정보", [["상태", "조회된 데이터가 없습니다."]]);
  }
}

function renderPipelineView(rows = []) {
  const columns = [
    { label: "영업기회명", value: (row) => row.name },
    { label: "상태", value: (row) => row.status },
    { label: "단계", value: (row) => row.stage_name || row.stage_code },
    { label: "회사명", value: (row) => row.company_name },
    { label: "고객명", value: (row) => row.contact_name },
    { label: "금액", value: (row) => formatAmount(row.amount, row.currency) },
    { label: "확률", value: (row) => (row.probability_percent ? `${row.probability_percent}%` : "-") },
    { label: "종료예정일", value: (row) => formatDateOnly(row.close_date) },
  ];
  canvasArea.innerHTML = `
    <div class="module-view">
      <form class="module-filter" id="pipeline-filter-form">
        ${filterInput("name", "영업기회명")}
        ${filterInput("status", "영업기회 상태")}
        ${filterInput("company_name", "회사명")}
        ${searchIconButton()}
      </form>
      ${renderDataTable({ rows, columns, emptyMessage: "조회된 영업기회가 없습니다." })}
    </div>
  `;
  document.querySelector("#pipeline-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadPipeline();
  });
  bindDataRows(rows, (row) => ({
    title: row.name || "영업기회 상세",
    rows: [
      ["영업기회명", row.name],
      ["회사명", row.company_name],
      ["고객명", row.contact_name],
      ["상태", row.status],
      ["단계", row.stage_name || row.stage_code],
      ["확률", row.probability_percent ? `${row.probability_percent}%` : "-"],
      ["금액", formatAmount(row.amount, row.currency)],
      ["종료예정일", formatDateOnly(row.close_date)],
    ],
  }));
}

async function loadPipeline() {
  const params = filterQuery("#pipeline-filter-form");
  const response = await apiFetch(`/api/opportunities?${params.toString()}`);
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(apiErrorMessage(result, "영업기회를 불러오지 못했습니다."));
  renderPipelineView(result.opportunities || []);
}

function renderQuoteView(rows = []) {
  const columns = [
    { label: "견적번호", value: (row) => row.quote_no },
    { label: "견적명", value: (row) => row.title },
    { label: "회사명", value: (row) => row.company_name },
    { label: "고객명", value: (row) => row.contact_name },
    { label: "상태", value: (row) => row.status },
    { label: "금액", value: (row) => formatAmount(row.total_amount, row.currency) },
    { label: "유효일", value: (row) => formatDateOnly(row.valid_until) },
    { label: "영업기회", value: (row) => row.opportunity_name },
  ];
  canvasArea.innerHTML = `
    <div class="module-view">
      <form class="module-filter" id="quote-filter-form">
        ${filterInput("company_name", "회사명")}
        ${filterInput("contact_name", "고객명")}
        ${searchIconButton()}
      </form>
      ${renderDataTable({ rows, columns, emptyMessage: "조회된 견적이 없습니다." })}
    </div>
  `;
  document.querySelector("#quote-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadQuotes();
  });
  bindDataRows(rows, (row) => ({
    title: row.title || row.quote_no || "견적 상세",
    tabs: [
      {
        id: "summary",
        label: "상세",
        rows: [
          ["견적번호", row.quote_no],
          ["견적일", formatDateOnly(row.created_at)],
          ["견적명", row.title],
          ["회사명", row.company_name],
          ["고객명", row.contact_name],
          ["상태", row.status],
          ["금액", formatAmount(row.total_amount, row.currency)],
        ],
      },
      {
        id: "document",
        label: "업로드 문서",
        html: documentViewerHtml(row, "견적"),
      },
    ],
  }));
}

async function loadQuotes() {
  const params = filterQuery("#quote-filter-form");
  const response = await apiFetch(`/api/quotes?${params.toString()}`);
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(apiErrorMessage(result, "견적을 불러오지 못했습니다."));
  renderQuoteView(result.quotes || []);
}

function renderContractView(rows = []) {
  const columns = [
    { label: "계약번호", value: (row) => row.contract_no },
    { label: "계약명", value: (row) => row.title },
    { label: "회사명", value: (row) => row.company_name },
    { label: "고객명", value: (row) => row.contact_name },
    { label: "상태", value: (row) => row.status },
    { label: "금액", value: (row) => formatAmount(row.contract_amount, row.currency) },
    { label: "시작일", value: (row) => formatDateOnly(row.start_date) },
    { label: "종료일", value: (row) => formatDateOnly(row.end_date) },
  ];
  canvasArea.innerHTML = `
    <div class="module-view">
      <form class="module-filter" id="contract-filter-form">
        ${filterInput("company_name", "회사명")}
        ${filterInput("contact_name", "고객명")}
        ${searchIconButton()}
      </form>
      ${renderDataTable({ rows, columns, emptyMessage: "조회된 계약이 없습니다." })}
    </div>
  `;
  document.querySelector("#contract-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadContracts();
  });
  bindDataRows(rows, (row) => ({
    title: row.title || row.contract_no || "계약 상세",
    tabs: [
      {
        id: "summary",
        label: "상세",
        rows: [
          ["계약번호", row.contract_no],
          ["계약명", row.title],
          ["회사명", row.company_name],
          ["고객명", row.contact_name],
          ["상태", row.status],
          ["금액", formatAmount(row.contract_amount, row.currency)],
          ["시작일", formatDateOnly(row.start_date)],
          ["종료일", formatDateOnly(row.end_date)],
        ],
      },
      {
        id: "document",
        label: "업로드 문서",
        html: documentViewerHtml(row, "계약"),
      },
    ],
  }));
}

async function loadContracts() {
  const params = filterQuery("#contract-filter-form");
  const response = await apiFetch(`/api/contracts?${params.toString()}`);
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(apiErrorMessage(result, "계약을 불러오지 못했습니다."));
  renderContractView(result.contracts || []);
}

let calendarCursor = new Date();
let pendingCalendarSelection = null;

function eventDateKey(event) {
  const value = event.starts_at;
  if (!value) return "";
  return String(value).slice(0, 10);
}

function calendarTodayKey() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

function calendarEventMatchesSelection(event, selection) {
  if (!event || !selection) return false;
  const sameId = String(event.id || "") === String(selection.id || "");
  const sameType = !selection.source_type || String(event.source_type || "") === String(selection.source_type);
  return sameId && sameType;
}

function calendarDetailRows(item) {
  return [
    ["회사명", item.company_name],
    ["고객명", item.contact_name],
    ["활동 유형", item.activity_type || item.location || item.source_type],
    ["활동 내용", item.content || item.title],
    ["활동 상태", item.status],
    ["예정 일시", formatDateTime(item.starts_at)],
    ["완료 일시", formatDateTime(item.ends_at)],
  ];
}

function showCalendarDetail(item) {
  showDetail(item.title || "일정 상세", calendarDetailRows(item));
}

function renderCalendarView(events = [], cursor = calendarCursor, selection = pendingCalendarSelection) {
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(1 - first.getDay());
  const byDate = events.reduce((acc, event) => {
    const key = eventDateKey(event);
    if (!key) return acc;
    acc[key] = acc[key] || [];
    acc[key].push(event);
    return acc;
  }, {});
  const days = Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
  canvasArea.innerHTML = `
    <div class="calendar-view">
      <div class="calendar-toolbar">
        <div class="calendar-nav">
          <button type="button" data-calendar-action="today">오늘</button>
          <button type="button" aria-label="이전 달" data-calendar-action="prev">‹</button>
          <button type="button" aria-label="다음 달" data-calendar-action="next">›</button>
          <strong>${year}년 ${month + 1}월</strong>
        </div>
        <form class="calendar-picker" id="calendar-filter-form">
          <input name="year" type="number" min="2000" max="2100" value="${year}" aria-label="년도" />
          <select name="month" aria-label="월">
            ${Array.from({ length: 12 }, (_, index) => `<option value="${index + 1}" ${index === month ? "selected" : ""}>${index + 1}월</option>`).join("")}
          </select>
          <button type="submit">이동</button>
        </form>
      </div>
      <div class="calendar-grid">
        ${["일", "월", "화", "수", "목", "금", "토"].map((day) => `<div class="calendar-weekday">${day}</div>`).join("")}
        ${days
          .map((day) => {
            const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
            const dayEvents = byDate[key] || [];
            const muted = day.getMonth() !== month ? " muted" : "";
            const today = calendarTodayKey() === key ? " today" : "";
            const selectedDate = selection?.date === key || (!selection && today) ? " selected" : "";
            return `
              <div class="calendar-cell${muted}${today}${selectedDate}" data-date="${key}">
                <div class="calendar-day-number">${day.getDate()}</div>
                <div class="calendar-events">
                  ${dayEvents.slice(0, 4).map((event, eventIndex) => `<button type="button" class="calendar-event" data-event-date="${key}" data-event-index="${eventIndex}" data-event-id="${escapeHtml(event.id)}" data-source-type="${escapeHtml(event.source_type || "")}">${escapeHtml(event.title || event.source_type)}</button>`).join("")}
                  ${dayEvents.length > 4 ? `<span class="calendar-more">+${dayEvents.length - 4}</span>` : ""}
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    </div>
  `;
  document.querySelector("#calendar-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    calendarCursor = new Date(Number(form.get("year")), Number(form.get("month")) - 1, 1);
    loadCalendar();
  });
  document.querySelectorAll("[data-calendar-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.calendarAction;
      if (action === "today") calendarCursor = new Date();
      if (action === "prev") calendarCursor = new Date(year, month - 1, 1);
      if (action === "next") calendarCursor = new Date(year, month + 1, 1);
      loadCalendar();
    });
  });
  document.querySelectorAll(".calendar-event").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".calendar-cell.selected").forEach((item) => item.classList.remove("selected"));
      document.querySelectorAll(".calendar-event.selected").forEach((item) => item.classList.remove("selected"));
      button.closest(".calendar-cell")?.classList.add("selected");
      button.classList.add("selected");
      const item = (byDate[button.dataset.eventDate] || [])[Number(button.dataset.eventIndex)];
      pendingCalendarSelection = {
        id: item?.id,
        source_type: item?.source_type,
        date: button.dataset.eventDate,
      };
      showCalendarDetail(item);
    });
  });

  const todayKey = calendarTodayKey();
  const selectedEvent = selection
    ? events.find((event) => calendarEventMatchesSelection(event, selection))
    : (byDate[todayKey] || [])[0];
  const selectedDate = selectedEvent ? eventDateKey(selectedEvent) : selection?.date || todayKey;
  document.querySelectorAll(".calendar-cell.selected").forEach((item) => item.classList.remove("selected"));
  document.querySelector(`.calendar-cell[data-date="${selectedDate}"]`)?.classList.add("selected");
  if (selectedEvent) {
    const selectedButton = Array.from(document.querySelectorAll(".calendar-event")).find((button) => {
      const event = (byDate[button.dataset.eventDate] || [])[Number(button.dataset.eventIndex)];
      return calendarEventMatchesSelection(event, {
        id: selectedEvent.id,
        source_type: selectedEvent.source_type,
      });
    });
    selectedButton?.classList.add("selected");
    showCalendarDetail(selectedEvent);
    pendingCalendarSelection = null;
  } else {
    showDetail("오늘 일정", [
      ["회사명", "-"],
      ["고객명", "-"],
      ["활동 유형", "-"],
      ["활동 내용", "오늘 날짜에 등록된 첫 일정이 없습니다."],
      ["활동 상태", "-"],
      ["예정 일시", selectedDate],
      ["완료 일시", "-"],
    ]);
    pendingCalendarSelection = null;
  }
}

async function loadCalendar() {
  const year = calendarCursor.getFullYear();
  const month = calendarCursor.getMonth() + 1;
  const response = await apiFetch(`/api/calendar?year=${year}&month=${month}`);
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(apiErrorMessage(result, "캘린더를 불러오지 못했습니다."));
  renderCalendarView(result.events || [], calendarCursor);
}

async function loadMenu(menu) {
  try {
    if (menu === "customers") {
      renderCustomerView();
      await loadCustomers();
      return;
    }
    if (menu === "pipeline") {
      renderPipelineView();
      await loadPipeline();
      return;
    }
    if (menu === "calendar") {
      if (!pendingCalendarSelection) {
        calendarCursor = new Date();
      }
      await loadCalendar();
      return;
    }
    if (menu === "quotes") {
      renderQuoteView();
      await loadQuotes();
      return;
    }
    if (menu === "contracts") {
      renderContractView();
      await loadContracts();
      return;
    }
  } catch (error) {
    addLog("Menu", error.message, "error");
  }
}

function customerToCardData(customer) {
  if (customer?.card_data && Object.keys(customer.card_data).length) {
    return customer.card_data;
  }

  return {
    "회사명": customer?.company_name || "",
    "이름": customer?.contact_name || "",
    "직무": customer?.job_title || "",
    "직위": customer?.job_position || "",
    "휴대전화": customer?.mobile_phone || "",
    "이메일": customer?.email || "",
    "홈페이지": customer?.homepage || "",
    ...(customer?.extra_info || {}),
  };
}

function customerSource(customer) {
  return customer?.source_file ? `DB · ${customer.source_file}` : "DB";
}

function setSelectedCustomer(data, source, customer = null) {
  memory.selectedCustomer = {
    id: customer?.id || customer?.contact_id || null,
    contactId: customer?.contact_id || customer?.id || null,
    accountId: customer?.account_id || null,
    tenantId: customer?.tenant_id || null,
    ownerUserId: customer?.owner_user_id || null,
    source,
    data: data || {},
    customer: customer || null,
    selectedAt: new Date().toISOString(),
  };
}

function compactExtraInfo(data) {
  const baseKeys = new Set(["회사명", "이름", "직무", "직위", "휴대전화", "이메일", "홈페이지"]);
  return Object.entries(data || {})
    .filter(([key, value]) => !baseKeys.has(key) && value)
    .map(([key, value]) => `${key}: ${value}`)
    .join(" / ");
}

function addCustomerRow(data, source = "명함 인식", options = {}) {
  if (!customerTableBody) return;

  customerTableBody.querySelector(".empty-row")?.remove();
  const row = document.createElement("tr");
  row.className = "customer-row";
  if (options.id) {
    row.dataset.customerId = String(options.id);
  }
  const registeredDate = options.createdAt ? new Date(options.createdAt) : new Date();
  const registeredAt = registeredDate.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const fields = [
    data["회사명"] || "",
    data["이름"] || "",
    data["직무"] || "",
    data["직위"] || "",
    data["휴대전화"] || "",
    data["이메일"] || "",
    data["홈페이지"] || "",
    compactExtraInfo(data),
    registeredAt,
  ];

  row.innerHTML = fields.map((value) => `<td>${escapeHtml(value || "-")}</td>`).join("");
  row.title = source;
  row.addEventListener("click", () => {
    customerTableBody.querySelectorAll(".customer-row.selected").forEach((item) => item.classList.remove("selected"));
    row.classList.add("selected");
    setSelectedCustomer(data, source, options.customer || null);
    updateCustomerDetail(data, source, options.customer || null);
  });
  customerTableBody.append(row);
  if (options.autoSelect !== false) {
    row.click();
    row.scrollIntoView({ block: "nearest" });
  }
}

function renderCustomerRows(customers) {
  if (!customerTableBody) return;
  customerTableBody.innerHTML = "";

  if (!customers.length) {
    memory.selectedCustomer = null;
    customerTableBody.innerHTML = `<tr class="empty-row"><td colspan="9">저장된 고객 정보가 없습니다.</td></tr>`;
    return;
  }

  memory.cards = customers.slice(0, 10).map((customer) => ({
    id: customer.id,
    fileName: customer.source_file || "DB",
    data: customerToCardData(customer),
    briefing: customer.briefing || "",
    createdAt: customer.created_at,
  }));

  customers
    .forEach((customer) => {
      addCustomerRow(customerToCardData(customer), customerSource(customer), {
        id: customer.id,
        createdAt: customer.created_at,
        customer,
        autoSelect: false,
      });
    });
  customerTableBody.querySelector(".customer-row")?.click();
}

async function loadCustomers() {
  if (isLoadingCustomers) return;
  isLoadingCustomers = true;
  try {
    const params = filterQuery("#customer-filter-form");
    const response = await apiFetch(`/api/customers?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.error || "고객 목록을 불러오지 못했습니다.");
    }
    renderCustomerRows(result.customers || []);
  } catch (error) {
    addLog("DB", error.message, "error");
  } finally {
    isLoadingCustomers = false;
  }
}

function updateCustomerDetail(data, source, customer = null) {
  if (!customerDetailList) return;
  if (customerDetailTitle) {
    const company = data["회사명"] || "회사명 미확인";
    const name = data["이름"] || "이름 미확인";
    customerDetailTitle.textContent = `${company} / ${name}`;
  }

  const detailRows = [
    ["회사", data["회사명"] || "-"],
    ["이름", data["이름"] || "-"],
    ["직무/직위", [data["직무"], data["직위"]].filter(Boolean).join(" / ") || "-"],
    ["휴대전화", data["휴대전화"] || "-"],
    ["이메일", data["이메일"] || "-"],
    ["주소", customer?.address || data["주소"] || "-"],
    ["홈페이지", data["홈페이지"] || "-"],
  ];

  customerDetailList.innerHTML = detailRows
    .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function getConversationContext() {
  return {
    selectedCustomer: memory.selectedCustomer,
    cards: memory.cards,
    history: memory.messages.slice(-12),
  };
}

function customerSelectionLabel(customer) {
  const company = customer?.company_name || customer?.card_data?.["회사명"] || "회사명 미확인";
  const name = customer?.contact_name || customer?.card_data?.["이름"] || "이름 미확인";
  return `${company} / ${name}`;
}

function customerSelectionMeta(customer) {
  return [
    customer?.job_title,
    customer?.job_position,
    customer?.mobile_phone,
    customer?.email,
  ]
    .filter(Boolean)
    .join(" · ");
}

function buildCustomerSelectionHtml(result) {
  const commandId = window.crypto?.randomUUID ? window.crypto.randomUUID() : `cmd-${Date.now()}-${Math.random()}`;
  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  pendingCustomerCommands.set(commandId, {
    message: result.pending_message || "",
    candidates,
  });

  const rows = candidates
    .map((customer, index) => {
      const label = customerSelectionLabel(customer);
      const meta = customerSelectionMeta(customer) || "상세 정보 없음";
      return `
        <button class="customer-select-btn" type="button" data-command-id="${escapeHtml(commandId)}" data-customer-index="${index}">
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(meta)}</span>
        </button>
      `;
    })
    .join("");

  return `
    <div class="customer-selection">
      <p class="customer-selection-header">${escapeHtml(result.reply || "고객을 선택해 주세요.")}</p>
      <div class="customer-selection-list">${rows}</div>
    </div>
  `;
}

async function continueChatWithSelectedCustomer(commandId, index) {
  const pending = pendingCustomerCommands.get(commandId);
  const customer = pending?.candidates?.[index];
  if (!pending || !customer || isSubmitting) return;

  pendingCustomerCommands.delete(commandId);
  const data = customerToCardData(customer);
  const source = "DB · 명령 고객 선택";
  setSelectedCustomer(data, source, customer);
  updateCustomerDetail(data, source, customer);
  appendMessage("user", `고객 선택: ${customerSelectionLabel(customer)}`);
  rememberMessage("user", `고객 선택: ${customerSelectionLabel(customer)}`);

  isSubmitting = true;
  sendButton.disabled = true;
  try {
    await requestChatReply(pending.message, {
      appendUser: false,
      context: getConversationContext(),
    });
  } finally {
    isSubmitting = false;
    sendButton.disabled = false;
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function renderAttachmentPreview() {
  attachmentPreview.innerHTML = "";
  attachmentPreview.classList.toggle("has-files", pendingFiles.length > 0);

  pendingFiles.forEach((file, index) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "attachment-chip";
    chip.title = "첨부 제거";
    chip.innerHTML = `<span>${escapeHtml(file.name)}</span><small>${formatFileSize(file.size)}</small>`;
    chip.addEventListener("click", () => {
      pendingFiles.splice(index, 1);
      renderAttachmentPreview();
    });
    attachmentPreview.append(chip);
  });
}

function clearPendingFiles() {
  pendingFiles = [];
  renderAttachmentPreview();
}

function scrollPanelToBottom(panel) {
  if (!panel) return;
  requestAnimationFrame(() => {
    panel.scrollTop = panel.scrollHeight;
  });
}

function addLog(agent, detail, status = "active") {
  const item = document.createElement("li");
  item.className = status;

  const label = document.createElement("time");
  label.textContent = agent;

  const body = document.createElement("span");
  body.textContent = detail;

  item.append(label, body);
  logList.append(item);
  scrollPanelToBottom(logList);
  return item;
}

function addLogDivider(title) {
  const item = document.createElement("li");
  item.className = "log-divider";
  item.innerHTML = `<time>${title}</time><span></span>`;
  logList.append(item);
  scrollPanelToBottom(logList);
}

function createPlan(file, imageUrl) {
  agentStack.innerHTML = "";

  const imageCard = document.createElement("article");
  imageCard.className = "agent-card upload-plan-card";
  imageCard.innerHTML = `
    <img src="${imageUrl}" alt="${escapeHtml(file.name)} 미리보기" />
    <div>
      <span class="agent-mark red"></span>
      <strong>${escapeHtml(file.name)}</strong>
    </div>
    <p>업로드 이미지를 기준으로 명함 인식과 회사 브리핑 작업을 실행합니다.</p>
  `;
  agentStack.append(imageCard);

  const steps = [
    ["planner", "플래닝", "이미지 입력을 분석 작업으로 등록하고 실행 순서를 구성합니다.", 16],
    ["vision", "명함 인식", "Vision Agent가 명함 여부와 텍스트 필드를 추출합니다.", 8],
    ["research", "정보 보강", "Research Agent가 누락된 연락처와 회사 정보를 검색합니다.", 0],
    ["briefing", "브리핑 생성", "Analyst Agent가 영업 관점의 회사 브리핑을 작성합니다.", 0],
  ].map(([id, title, description, value]) => {
    const card = document.createElement("article");
    card.className = "agent-card pending";
    card.dataset.step = id;
    card.innerHTML = `
      <div>
        <span class="agent-mark blue"></span>
        <strong>${title}</strong>
        <small class="step-state">대기</small>
      </div>
      <p>${description}</p>
      <progress value="${value}" max="100"></progress>
    `;
    agentStack.append(card);
    return card;
  });

  addLog("Planner", `${file.name} 파일을 실행 대상으로 등록했습니다.`);
  scrollPanelToBottom(agentStack);
  return steps;
}

function createConversationPlan(text) {
  agentStack.innerHTML = "";
  const summary = text.length > 42 ? `${text.slice(0, 42)}...` : text;

  const requestCard = document.createElement("article");
  requestCard.className = "agent-card upload-plan-card";
  requestCard.innerHTML = `
    <div>
      <span class="agent-mark red"></span>
      <strong>대화 요청</strong>
    </div>
    <p>${escapeHtml(summary)}</p>
  `;
  agentStack.append(requestCard);

  const steps = [
    ["context", "컨텍스트 확인", "최근 명함 정보와 이전 대화 중 현재 질문에 필요한 내용을 선별합니다.", 20],
    ["research", "리서치 검색", "질문에 필요한 최신 외부 정보를 검색하고 출처 후보를 정리합니다.", 0],
    ["answer", "답변 생성", "컨텍스트와 검색 결과를 통합해 실행 가능한 답변을 작성합니다.", 0],
  ].map(([id, title, description, value]) => {
    const card = document.createElement("article");
    card.className = "agent-card pending";
    card.dataset.step = id;
    card.innerHTML = `
      <div>
        <span class="agent-mark blue"></span>
        <strong>${title}</strong>
        <small class="step-state">대기</small>
      </div>
      <p>${description}</p>
      <progress value="${value}" max="100"></progress>
    `;
    agentStack.append(card);
    return card;
  });

  scrollPanelToBottom(agentStack);
  return steps;
}

function extractSocialUrls(text) {
  const matches =
    String(text || "").match(
      /(?:https?:\/\/)?(?:[a-z0-9-]+\.)*(?:linkedin\.com|facebook\.com|fb\.com|instagram\.com|x\.com|twitter\.com|threads\.net|youtube\.com|youtu\.be|tiktok\.com|github\.com|naver\.com|medium\.com)\/[^\s<>()"']*/gi,
    ) || [];
  const socialHostPattern =
    /(^|\.)((linkedin|facebook|instagram|threads|youtube|youtu|tiktok|github|medium)\.com|fb\.com|x\.com|twitter\.com|youtu\.be|blog\.naver\.com)$/i;
  const urls = [];
  const seen = new Set();

  matches.forEach((value) => {
    const cleaned = value.replace(/[.,;:!?)]}>。；：，]+$/g, "");
    try {
      const parsed = new URL(/^https?:\/\//i.test(cleaned) ? cleaned : `https://${cleaned}`);
      const host = parsed.hostname.replace(/^www\./i, "").replace(/^m\./i, "");
      if (!socialHostPattern.test(host)) return;
      const normalized = `${parsed.protocol}//${host}${parsed.pathname.replace(/\/$/, "")}${parsed.search}`;
      if (seen.has(normalized)) return;
      seen.add(normalized);
      urls.push(normalized);
    } catch (_error) {
      // URL 생성에 실패한 텍스트는 일반 대화로 처리합니다.
    }
  });

  return urls;
}

function createSnsPlan(text, urls) {
  agentStack.innerHTML = "";
  const summary = text.length > 52 ? `${text.slice(0, 52)}...` : text;

  const requestCard = document.createElement("article");
  requestCard.className = "agent-card upload-plan-card";
  requestCard.innerHTML = `
    <div>
      <span class="agent-mark red"></span>
      <strong>SNS 링크 입력</strong>
    </div>
    <p>${escapeHtml(summary)}</p>
  `;
  agentStack.append(requestCard);

  const steps = [
    ["detect", "SNS 구분", `${urls.length}개의 SNS 링크를 플랫폼별로 분류합니다.`, 20],
    ["normalize", "정보 가져오기", "플랫폼별 공개 메타데이터와 URL 기반 이름 후보를 확인합니다.", 0],
    ["save", "저장 판단", "가져온 SNS 정보를 확인하고 고객 저장 가능 여부를 판단합니다.", 0],
  ].map(([id, title, description, value]) => {
    const card = document.createElement("article");
    card.className = "agent-card pending";
    card.dataset.step = id;
    card.innerHTML = `
      <div>
        <span class="agent-mark blue"></span>
        <strong>${title}</strong>
        <small class="step-state">대기</small>
      </div>
      <p>${description}</p>
      <progress value="${value}" max="100"></progress>
    `;
    agentStack.append(card);
    return card;
  });

  scrollPanelToBottom(agentStack);
  return steps;
}

function updatePlanStep(steps, stepId, state, value, logDetail) {
  const card = steps.find((item) => item.dataset.step === stepId);
  if (!card) return;

  card.classList.remove("pending", "active", "done", "error", "skipped");
  card.classList.add(state);
  card.querySelector(".step-state").textContent = state === "done" ? "완료" : state === "error" ? "오류" : state === "skipped" ? "생략" : "실행 중";
  card.querySelector("progress").value = value;

  if (logDetail) {
    addLog(card.querySelector("strong").textContent, logDetail, state);
  }
  scrollPanelToBottom(agentStack);
}

function buildUploadedImageHtml(file, imageUrl) {
  return `
    <figure class="uploaded-image-message">
      <img src="${imageUrl}" alt="${escapeHtml(file.name)}" />
      <figcaption>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</figcaption>
    </figure>
  `;
}

function buildUploadedFileHtml(file) {
  return `
    <div class="uploaded-file-message">
      <strong>${escapeHtml(file.name)}</strong>
      <span>${formatFileSize(file.size)}</span>
    </div>
  `;
}

function isDocumentFile(file) {
  const name = (file.name || "").toLowerCase();
  return /\.(pdf|doc|docx|xls|xlsx|csv|txt)$/.test(name);
}

async function analyzeSalesDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  appendMessage("user", buildUploadedFileHtml(file), { html: true });
  const loadingMessage = appendMessage("ai", "문서 내용을 분석해 견적/계약 여부를 확인하고 있습니다.");
  questionSequence += 1;
  addLogDivider(`문서 ${questionSequence}`);
  addLog("Document Agent", `${file.name} 파일을 문서 분석 파이프라인으로 전달했습니다.`);

  try {
    const response = await apiFetch("/api/extract/document", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(apiErrorMessage(result, "문서 분석 중 오류가 발생했습니다."));
    }

    loadingMessage.remove();
    appendMessage("ai", result.reply || "문서 분석을 완료했습니다.");
    if (!result.saved) {
      addLog("Document Agent", "견적/계약 문서로 확정하지 못해 저장하지 않았습니다.", "skipped");
      return;
    }

    addLog("Document Agent", "문서 분석 결과를 DB에 저장하고 원본 파일 다운로드 링크를 연결했습니다.", "done");
    if (result.target_menu === "quotes") {
      activateMainMenu("quotes");
      await loadMenu("quotes");
    } else if (result.target_menu === "contracts") {
      activateMainMenu("contracts");
      await loadMenu("contracts");
    }
  } catch (error) {
    loadingMessage.remove();
    appendMessage("ai", `문서 분석을 완료하지 못했습니다. ${error.message}`);
    addLog("Document Agent", error.message, "error");
  }
}

function buildCardInfoHtml(data) {
  const preferredLabels = ["회사명", "이름", "직무", "직위", "휴대전화", "이메일", "홈페이지"];
  const rows = preferredLabels.filter((label) => Object.prototype.hasOwnProperty.call(data, label)).map((label) => [label, data[label]]);

  Object.entries(data).forEach(([label, value]) => {
    if (!preferredLabels.includes(label) && value) rows.push([label, value]);
  });

  const items = rows
    .map(([label, value]) => `<li><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value || "정보 없음")}</span></li>`)
    .join("");

  return `<p>명함 이미지를 인식했습니다. 추출된 정보는 아래와 같습니다.</p><ul class="card-result-list">${items}</ul>`;
}

function buildSnsImportHtml(items) {
  const savedItems = (items || []).filter((item) => item.saved);
  const pendingItems = (items || []).filter((item) => item.needs_confirmation);
  const rows = (items || [])
    .map((item) => {
      const data = item.data || {};
      const status = item.saved ? "저장 완료" : "이름 확인 필요";
      const nameText = data["이름"] || item.name_candidate || "";
      const label = data["회사명"] || nameText || "프로필 이름 미확정";
      const reason = item.saved
        ? item.url || data["홈페이지"] || "-"
        : item.name_candidate
          ? `이름 후보: ${item.name_candidate} · ${item.reason || "사용자 확인이 필요합니다."}`
          : item.reason || "프로필 이름을 확정하지 못했습니다.";
      return `
        <li class="sns-result-item">
          <strong>${escapeHtml(status)}</strong>
          <span class="sns-result-title">${escapeHtml(item.platform || "SNS")} · ${escapeHtml(label)}</span>
          <small>${escapeHtml(item.url || data["홈페이지"] || "-")}</small>
          <span class="sns-result-reason">${escapeHtml(reason)}</span>
        </li>
      `;
    })
    .join("");

  const summary =
    pendingItems.length > 0
      ? `SNS 링크를 확인했습니다. 이름이 확인된 ${savedItems.length}건은 저장했고, ${pendingItems.length}건은 프로필 이름을 확정하지 못해 저장하지 않았습니다.`
      : `SNS 링크 ${savedItems.length}건을 고객 정보로 저장했습니다.`;
  return `<p>${escapeHtml(summary)}</p><ul class="card-result-list sns-result-list">${rows}</ul>`;
}

function buildSnsInspectHtml(items) {
  const rows = (items || [])
    .map((item) => {
      const nameText = item.profile_name || item.name_candidate || "이름 후보 없음";
      const confidence = item.name_confidence === "high" ? "높음" : item.name_confidence === "medium" ? "보통" : "없음";
      const summary = item.metadata_summary || "공개 메타데이터를 충분히 가져오지 못했습니다.";
      return `
        <li class="sns-result-item">
          <strong>${escapeHtml(item.platform || "SNS")} · ${escapeHtml(item.entity_label || item.entity_type || "프로필")}</strong>
          <span class="sns-result-title">${escapeHtml(nameText)}</span>
          <small>${escapeHtml(item.url || "-")}</small>
          <span class="sns-result-reason">이름 신뢰도: ${escapeHtml(confidence)} · ${escapeHtml(summary)}</span>
        </li>
      `;
    })
    .join("");

  return `<p>SNS 링크의 종류와 공개 정보를 확인했습니다. 아직 고객 정보로 저장하지 않았습니다.</p><ul class="card-result-list sns-result-list">${rows}</ul>`;
}

function buildBriefingHtml(briefing) {
  const paragraphs = String(briefing || "")
    .split(/\n{2,}/)
    .map((text) => text.trim())
    .filter(Boolean)
    .map((text) => `<p>${escapeHtml(text)}</p>`)
    .join("");

  return `<p class="briefing-kicker">브리핑 자료</p>${paragraphs || "<p>브리핑 자료를 생성하지 못했습니다.</p>"}`;
}

async function analyzeBusinessCard(file, imageUrl, options = {}) {
  const skipBriefing = Boolean(options.skipBriefing);
  const planSteps = createPlan(file, imageUrl);
  appendMessage("user", buildUploadedImageHtml(file, imageUrl), { html: true });
  const loadingMessage = appendMessage(
    "ai",
    skipBriefing
      ? "이미지를 분석하고 있습니다. 여러 장을 한꺼번에 처리하므로 고객 정보 추출까지만 진행합니다."
      : "이미지를 분석하고 있습니다. 명함 정보 추출 후 회사 브리핑까지 이어서 표시하겠습니다.",
  );

  updatePlanStep(planSteps, "planner", "done", 100, "파일 형식과 작업 목적을 확인하고 Vision, Research, Analyst 단계로 분해했습니다.");
  updatePlanStep(planSteps, "vision", "active", 48, "이미지에서 이름, 회사명, 직위, 연락처 후보를 추출하고 있습니다.");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await apiFetch(`/api/extract?skip_briefing=${skipBriefing ? "true" : "false"}`, {
      method: "POST",
      body: formData,
    });
    const result = await response.json();

    if (!response.ok || !result.success) {
      throw new Error(apiErrorMessage(result, "명함 분석 중 오류가 발생했습니다."));
    }

    loadingMessage.remove();

    if (!result.is_business_card && result.is_social_profile) {
      const company = result.data?.["회사명"] || "회사명 미확인";
      const name = result.data?.["이름"] || "이름 미확인";
      updatePlanStep(planSteps, "vision", "done", 100, `${name} 프로필 이름을 화면 캡처에서 확인했습니다.`);
      updatePlanStep(planSteps, "research", "done", 100, "검색 결과가 아닌 화면에 보이는 이름을 직접 근거로 사용했습니다.");
      updatePlanStep(planSteps, "briefing", "done", 100, "SNS 프로필 화면 캡처 기반 고객 정보를 저장했습니다.");
      appendMessage("ai", buildCardInfoHtml(result.data || {}), { html: true });
      if (result.briefing) {
        appendMessage("ai", buildBriefingHtml(result.briefing), { html: true });
      }
      rememberCardInfo(file, result.data || {}, result.briefing || "", result.customer || null);
      addCustomerRow(result.data || {}, `SNS 프로필 캡처 · ${file.name}`, {
        id: result.customer?.id,
        createdAt: result.customer?.created_at,
        customer: result.customer || null,
      });
      rememberMessage("assistant", `SNS 프로필 캡처 인식 결과: ${JSON.stringify(result.data || {})}\n브리핑: ${result.briefing || ""}`);
      return;
    }

    if (!result.is_business_card) {
      updatePlanStep(planSteps, "vision", "error", 100, "이미지를 명함으로 확정하지 못했습니다.");
      appendMessage("ai", "이미지를 확인했지만 명함이나 SNS 프로필 화면으로 판단되지는 않습니다. 프로필 이름이 보이는 화면 캡처나 명함 이미지를 첨부해 주세요.");
      return;
    }

    const company = result.data?.["회사명"] || "회사명 미확인";
    const name = result.data?.["이름"] || "이름 미확인";
    const hasBriefing = Boolean(result.briefing && !result.briefing.includes("오류"));

    updatePlanStep(planSteps, "vision", "done", 100, `${name}, ${company} 정보를 명함에서 추출했습니다.`);
    updatePlanStep(planSteps, "research", "done", 100, "추출 필드와 누락 가능 필드를 대조하고 검색 보강 결과를 반영했습니다.");
    updatePlanStep(
      planSteps,
      "briefing",
      skipBriefing ? "skipped" : hasBriefing ? "done" : "error",
      skipBriefing ? 0 : 100,
      skipBriefing
        ? "여러 장 동시 처리 조건에 따라 고객별 브리핑 생성을 생략했습니다."
        : hasBriefing
          ? `${company} 기준의 영업 브리핑을 생성했습니다.`
          : "브리핑 생성 단계에서 보강 가능한 공개 정보를 충분히 확보하지 못했습니다.",
    );

    appendMessage("ai", buildCardInfoHtml(result.data || {}), { html: true });
    if (!skipBriefing) {
      appendMessage("ai", buildBriefingHtml(result.briefing), { html: true });
    }
    rememberCardInfo(file, result.data || {}, result.briefing || "", result.customer || null);
    addCustomerRow(result.data || {}, `명함 인식 · ${file.name}`, {
      id: result.customer?.id,
      createdAt: result.customer?.created_at,
      customer: result.customer || null,
    });
    rememberMessage("assistant", `명함 인식 결과: ${JSON.stringify(result.data || {})}\n브리핑: ${result.briefing || ""}`);
  } catch (error) {
    loadingMessage.remove();
    updatePlanStep(planSteps, "vision", "error", 100, error.message);
    updatePlanStep(planSteps, "research", "error", 0, "이전 단계 오류로 정보 보강을 중단했습니다.");
    updatePlanStep(planSteps, "briefing", "error", 0, "이전 단계 오류로 브리핑 생성을 중단했습니다.");
    appendMessage("ai", `분석을 완료하지 못했습니다. ${error.message}`);
  }
}

async function processPendingFiles() {
  const files = [...pendingFiles];
  const imageFiles = files.filter((file) => file.type.startsWith("image/"));
  const skipBriefing = imageFiles.length >= 2;
  clearPendingFiles();

  for (const file of files) {
    if (!file.type.startsWith("image/")) {
      if (isDocumentFile(file)) {
        await analyzeSalesDocument(file);
      } else {
        appendMessage("user", `${file.name} 파일을 첨부했습니다.`);
        appendMessage("ai", "지원하지 않는 파일 형식입니다. 이미지, PDF, DOCX, XLSX, CSV, TXT 파일을 첨부해 주세요.");
        addLog("File Agent", `${file.name} 파일은 지원하지 않는 형식입니다.`, "done");
      }
      continue;
    }

    const imageUrl = await readFileAsDataUrl(file);
    await analyzeBusinessCard(file, imageUrl, { skipBriefing });
  }
}

async function importSnsLinks(text) {
  const urls = extractSocialUrls(text);
  appendMessage("user", text);
  rememberMessage("user", text);
  questionSequence += 1;
  addLogDivider(`SNS ${questionSequence}`);
  const planSteps = createSnsPlan(text, urls);
  addLog("SNS Agent", `${urls.length}개의 SNS 링크를 플랫폼 구분 및 정보 확인 대상으로 감지했습니다.`);
  const loadingMessage = appendMessage("ai", "SNS 링크를 플랫폼별로 구분하고 공개 정보를 가져오고 있습니다.");

  updatePlanStep(planSteps, "detect", "done", 100, "LinkedIn, Instagram, Facebook, X, YouTube 등 지원 SNS 링크를 분류했습니다.");
  updatePlanStep(planSteps, "normalize", "active", 50, "공개 프로필 메타데이터와 URL 구조를 확인하고 있습니다.");

  try {
    const response = await apiFetch("/api/inspect/sns", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: text, context: getConversationContext() }),
    });
    const result = await response.json();

    if (!response.ok || !result.success) {
      throw new Error(apiErrorMessage(result, "SNS 링크 처리 중 오류가 발생했습니다."));
    }

    loadingMessage.remove();
    if (result.customer_selection_required) {
      updatePlanStep(planSteps, "normalize", "done", 100, "SNS 링크 확인 전에 대상 고객 후보를 먼저 확인했습니다.");
      updatePlanStep(planSteps, "save", "skipped", 0, "고객을 선택하면 같은 명령을 이어서 처리합니다.");
      appendMessage("ai", buildCustomerSelectionHtml(result), { html: true });
      rememberMessage("assistant", result.reply || "고객 선택이 필요합니다.");
      addLog("SNS Agent", "SNS 명령 대상 고객 후보를 확인하고 선택 UI를 표시했습니다.", "done");
      return;
    }
    const namedItems = (result.items || []).filter((item) => item.profile_name);
    updatePlanStep(planSteps, "normalize", "done", 100, `${result.count || 0}개의 SNS 링크 정보를 확인했고, ${namedItems.length}건에서 이름 후보를 찾았습니다.`);
    updatePlanStep(
      planSteps,
      "save",
      "skipped",
      0,
      "이번 단계에서는 SNS 종류와 공개 정보 확인에 집중하고 고객 DB 저장은 수행하지 않았습니다."
    );

    appendMessage("ai", buildSnsInspectHtml(result.items || []), { html: true });
    if (result.resolved_customer) {
      const data = customerToCardData(result.resolved_customer);
      setSelectedCustomer(data, "DB · 명령 자동 선택", result.resolved_customer);
      updateCustomerDetail(data, "DB · 명령 자동 선택", result.resolved_customer);
    }
    rememberMessage("assistant", `SNS 링크 정보 확인 결과: ${JSON.stringify(result.items || [])}`);
  } catch (error) {
    loadingMessage.remove();
    updatePlanStep(planSteps, "normalize", "error", 100, error.message);
    updatePlanStep(planSteps, "save", "error", 0, "이전 단계 오류로 SNS 정보 확인을 완료하지 못했습니다.");
    appendMessage("ai", `SNS 링크 정보를 확인하지 못했습니다. ${error.message}`);
    addLog("SNS Agent", error.message, "error");
  }
}

function addFiles(files) {
  const nextFiles = Array.from(files ?? []);
  if (!nextFiles.length) return;

  const existing = new Set(pendingFiles.map(pendingFileKey));
  const uniqueFiles = nextFiles.filter((file) => {
    const key = pendingFileKey(file);
    if (existing.has(key)) return false;
    existing.add(key);
    return true;
  });
  if (!uniqueFiles.length) return;

  pendingFiles = [...pendingFiles, ...uniqueFiles];
  renderAttachmentPreview();
}

async function requestChatReply(text, options = {}) {
  if (options.appendUser !== false) {
    appendMessage("user", text);
    rememberMessage("user", text);
  }
  questionSequence += 1;
  addLogDivider(`질문 ${questionSequence}`);
  const planSteps = createConversationPlan(text);
  addLog("Conversation Agent", "사용자 지시를 수신하고 LLM 대화 응답을 요청했습니다.");
  const loadingMessage = appendMessage("ai", "답변을 생성하고 있습니다.");
  updatePlanStep(planSteps, "context", "done", 100, "최근 명함 인식 결과와 대화 기록을 질문 기준으로 정리했습니다.");
  updatePlanStep(planSteps, "research", "active", 55, "외부 검색이 필요한 정보 범위를 판단하고 리서치를 수행합니다.");

  try {
    const response = await apiFetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: text,
        context: options.context || getConversationContext(),
      }),
    });
    const result = await response.json();

    if (!response.ok || !result.success) {
      throw new Error(apiErrorMessage(result, "대화 응답 생성 중 오류가 발생했습니다."));
    }

    loadingMessage.remove();
    if (result.customer_selection_required) {
      updatePlanStep(planSteps, "research", "done", 100, "명령을 처리하기 전에 대상 고객 후보를 먼저 확인했습니다.");
      updatePlanStep(planSteps, "answer", "done", 100, "사용자가 고객을 선택하면 같은 명령을 이어서 처리합니다.");
      appendMessage("ai", buildCustomerSelectionHtml(result), { html: true });
      rememberMessage("assistant", result.reply || "고객 선택이 필요합니다.");
      addLog("Conversation Agent", "명령 대상 고객 후보를 확인하고 선택 UI를 표시했습니다.", "done");
      return;
    }
    updatePlanStep(planSteps, "research", "done", 100, "검색 결과와 기존 컨텍스트를 답변 근거로 정리했습니다.");
    updatePlanStep(planSteps, "answer", "done", 100, "최신 정보 우선 규칙을 적용해 답변을 생성했습니다.");
    const reply = result.reply || "응답을 생성하지 못했습니다.";
    appendMessage("ai", reply, { richText: true });
    if (result.resolved_customer) {
      const data = customerToCardData(result.resolved_customer);
      setSelectedCustomer(data, "DB · 명령 자동 선택", result.resolved_customer);
      updateCustomerDetail(data, "DB · 명령 자동 선택", result.resolved_customer);
      addLog("Conversation Agent", "명령에 언급된 단일 고객을 자동 선택했습니다.", "done");
    }
    if (result.db_list_query && result.target_menu) {
      updatePlanStep(planSteps, "research", "done", 100, "요청한 화면의 DB 리스트를 조회했습니다.");
      updatePlanStep(planSteps, "answer", "done", 100, "해당 메뉴를 열어 조회 화면과 함께 확인합니다.");
      activateMainMenu(result.target_menu);
      await loadMenu(result.target_menu);
      addLog("List Agent", `${result.target_menu} 메뉴의 DB 리스트 조회 명령을 처리했습니다.`, "done");
    }
    if (result.activity_schedule) {
      if (result.activity_saved && result.calendar) {
        updatePlanStep(planSteps, "research", "done", 100, "영업활동 일정 관리 요청을 DB에 반영했습니다.");
        updatePlanStep(planSteps, "answer", "done", 100, "캘린더 메뉴를 열어 반영된 일정을 확인합니다.");
        calendarCursor = new Date(Number(result.calendar.year), Number(result.calendar.month) - 1, 1);
        if (result.activity?.id) {
          pendingCalendarSelection = {
            id: result.activity.id,
            source_type: "activity",
            date: eventDateKey({ starts_at: result.activity.due_at || result.activity.starts_at }),
          };
        }
        activateMainMenu("calendar");
        await loadMenu("calendar");
        addLog("Schedule Agent", "영업활동 일정 관리 요청을 처리하고 캘린더를 열었습니다.", "done");
      } else {
        updatePlanStep(planSteps, "research", "done", 100, "일정 등록에 필요한 추가 정보를 확인했습니다.");
        updatePlanStep(planSteps, "answer", "done", 100, "추가 입력 요청을 채팅창에 표시했습니다.");
      }
    }
    if (result.sns_imported && Array.isArray(result.items)) {
      result.items.filter((item) => item.saved).forEach((item) => {
        const source = `SNS · ${item.platform || "Unknown"}`;
        rememberCardInfo({ name: source }, item.data || {}, item.briefing || "", item.customer || null);
        addCustomerRow(item.data || {}, source, {
          id: item.customer?.id,
          createdAt: item.customer?.created_at,
          customer: item.customer || null,
        });
      });
    }
    if (result.sns_inspected && Array.isArray(result.items)) {
      appendMessage("ai", buildSnsInspectHtml(result.items), { html: true });
    }
    rememberMessage("assistant", reply);
    addLog("Conversation Agent", "LLM 응답을 채팅창에 반영했습니다.", "done");
  } catch (error) {
    loadingMessage.remove();
    updatePlanStep(planSteps, "research", "error", 100, error.message);
    updatePlanStep(planSteps, "answer", "error", 0, "이전 단계 오류로 답변 생성을 완료하지 못했습니다.");
    appendMessage("ai", `답변을 생성하지 못했습니다. ${error.message}`);
    addLog("Conversation Agent", error.message, "error");
  }
}

attachButton?.addEventListener("click", () => fileInput?.click());

fileInput?.addEventListener("change", (event) => {
  addFiles(event.target.files);
  event.target.value = "";
});

logoutButton?.addEventListener("click", logout);

dropTargets.forEach((target) => {
  target.addEventListener("dragenter", (event) => {
    event.preventDefault();
    event.stopPropagation();
    chatInput?.classList.add("drag-over");
  });

  target.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.stopPropagation();
  });

  target.addEventListener("dragleave", (event) => {
    event.stopPropagation();
    if (!event.currentTarget.contains(event.relatedTarget)) {
      chatInput?.classList.remove("drag-over");
    }
  });

  target.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    chatInput?.classList.remove("drag-over");
    addFiles(event.dataTransfer.files);
  });
});

function resizeCommandInput() {
  if (!commandInput) return;
  commandInput.style.height = "auto";
  commandInput.style.height = `${Math.min(commandInput.scrollHeight, 132)}px`;
}

commandInput?.addEventListener("input", resizeCommandInput);

commandInput?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) return;
  event.preventDefault();
  chatInput?.requestSubmit();
});

chatStream?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-command-id][data-customer-index]");
  if (!button) return;
  const index = Number(button.dataset.customerIndex);
  continueChatWithSelectedCustomer(button.dataset.commandId, index);
});

chatInput?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSubmitting) return;

  const input = commandInput || chatInput.querySelector("[data-command-input]");
  const text = input.value.trim();
  const hasFiles = pendingFiles.length > 0;
  if (!text && !hasFiles) return;

  isSubmitting = true;
  sendButton.disabled = true;

  try {
    if (hasFiles) {
      if (text) {
        appendMessage("user", text);
        rememberMessage("user", text);
      }
      input.value = "";
      resizeCommandInput();
      await processPendingFiles();
      return;
    }

    input.value = "";
    resizeCommandInput();
    if (extractSocialUrls(text).length > 0) {
      await importSnsLinks(text);
    } else {
      await requestChatReply(text);
    }
  } finally {
    isSubmitting = false;
    sendButton.disabled = false;
  }
});

async function initApp() {
  try {
    await loadCurrentSession();
    await loadMenu("customers");
  } catch (error) {
    addLog("Session", error.message, "error");
  }
}

initApp();
