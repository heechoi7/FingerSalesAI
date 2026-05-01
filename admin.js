const adminMenuButtons = document.querySelectorAll("[data-admin-menu]");
const adminTitle = document.querySelector("#admin-page-title");
const adminDescription = document.querySelector("#admin-page-description");
const adminView = document.querySelector("#admin-view");
const adminMessage = document.querySelector("#admin-message");
const adminSummaryGrid = document.querySelector("#admin-summary-grid");
const adminRefreshButton = document.querySelector("#admin-refresh-button");
const adminSessionLabel = document.querySelector("#admin-session-label");

const adminState = {
  menu: "company",
  roles: [
    { value: "owner", label: "소유자" },
    { value: "admin", label: "관리자" },
    { value: "manager", label: "매니저" },
    { value: "sales", label: "영업" },
    { value: "viewer", label: "조회" },
  ],
  statuses: ["active", "invited", "locked", "disabled"],
  teams: [],
  users: [],
  stageCodes: ["lead", "prospect", "opportunity", "proposal", "contract", "success"],
  codeGroups: [],
};

const menuMeta = {
  company: ["회사 정보", "현재 로그인한 테넌트의 기본 정보를 관리합니다."],
  users: ["사용자 관리", "테넌트 사용자, 역할, 상태, 소속 팀을 관리합니다."],
  teams: ["팀 관리", "팀 구조와 정렬 순서를 관리합니다."],
  roles: ["권한 관리", "현재 역할 정의와 역할별 사용자 수를 확인합니다."],
  codes: ["코드 관리", "테넌트별 사용자 정의 코드 그룹과 코드 항목을 관리합니다."],
  stages: ["영업 단계 설정", "파이프라인 단계, 성공 확률, 활성 여부를 관리합니다."],
  logs: ["사용로그", "관리자 변경 이력과 감사 로그를 확인합니다."],
};

const settingsPathByMenu = {
  users: "/settings/users",
  teams: "/settings/teams",
  stages: "/settings/pipeline",
};

const menuBySettingsPath = {
  "/settings/users": "users",
  "/settings/teams": "teams",
  "/settings/pipeline": "stages",
};

function menuFromLocation() {
  return menuBySettingsPath[window.location.pathname] || "company";
}

function setActiveMenuButton(menu) {
  adminMenuButtons.forEach((item) => item.classList.toggle("active", item.dataset.adminMenu === menu));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function adminApi(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
  });
  if (response.status === 401) {
    window.location.href = "/login.html";
    throw new Error("로그인이 필요합니다.");
  }
  if (response.status === 403) {
    window.location.href = "/";
    throw new Error("관리자 권한이 필요합니다.");
  }
  return response;
}

function showAdminMessage(message, type = "info") {
  adminMessage.hidden = false;
  adminMessage.className = `admin-message ${type}`;
  adminMessage.textContent = message;
}

function clearAdminMessage() {
  adminMessage.hidden = true;
  adminMessage.textContent = "";
}

function handleAdminSubmit(handler) {
  return async (event) => {
    try {
      await handler(event);
    } catch (error) {
      showAdminMessage(error.message, "error");
    }
  };
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", { hour12: false });
}

function optionHtml(items, selected, emptyLabel = "선택 안 함") {
  const empty = `<option value="">${escapeHtml(emptyLabel)}</option>`;
  return (
    empty +
    items
      .map((item) => {
        const value = typeof item === "string" ? item : item.value;
        const label = typeof item === "string" ? item : item.label;
        return `<option value="${escapeHtml(value)}" ${String(value) === String(selected ?? "") ? "selected" : ""}>${escapeHtml(label)}</option>`;
      })
      .join("")
  );
}

function teamOptions(selected) {
  const items = adminState.teams.map((team) => ({ value: team.id, label: team.name }));
  return optionHtml(items, selected, "소속 없음");
}

function userOptions(selected, emptyLabel = "선택 안 함") {
  const items = adminState.users.map((user) => ({
    value: user.id,
    label: `${user.name || user.email} (${user.email})`,
  }));
  return optionHtml(items, selected, emptyLabel);
}

function memberOptions(selectedIds = []) {
  const selected = new Set((selectedIds || []).map((id) => String(id)));
  return adminState.users
    .map((user) => {
      const label = `${user.name || user.email} (${user.email})`;
      return `<option value="${escapeHtml(user.id)}" ${selected.has(String(user.id)) ? "selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

function renderSummary(summary) {
  const counts = summary?.counts || {};
  const tenant = summary?.tenant || {};
  adminSummaryGrid.innerHTML = [
    ["테넌트", tenant.name || tenant.tenant_code || "-"],
    ["사용자", counts.users ?? 0],
    ["팀", counts.teams ?? 0],
    ["코드", counts.code_items ?? 0],
    ["영업 단계", counts.pipeline_stages ?? 0],
    ["감사 로그", counts.audit_logs ?? 0],
  ]
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

async function loadSummary() {
  const response = await adminApi("/api/admin/summary");
  const result = await response.json();
  if (!response.ok || !result.success) {
    throw new Error(result.detail || result.error || "관리자 요약을 불러오지 못했습니다.");
  }
  renderSummary(result);
  const session = result.session || window.__FSAI_SESSION__ || {};
  adminSessionLabel.textContent = `${session.tenant_name || session.tenant_code || "테넌트"} / ${session.user_name || session.email || "사용자"} / ${session.role_label || session.role || "역할"}`;
}

function setLoading() {
  adminView.innerHTML = `<div class="admin-loading">데이터를 불러오는 중입니다.</div>`;
}

async function renderCompany() {
  setLoading();
  const response = await adminApi("/api/admin/company");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "회사 정보를 불러오지 못했습니다.");
  const company = result.company || {};
  const settings = result.settings || [];
  adminView.innerHTML = `
    <form class="admin-form" id="company-form">
      <label>테넌트 코드<input name="tenant_code" value="${escapeHtml(company.tenant_code)}" disabled /></label>
      <label>회사명<input name="name" value="${escapeHtml(company.name)}" required /></label>
      <label>사업자등록번호<input name="business_no" value="${escapeHtml(company.business_no)}" /></label>
      <label>요금제 코드<input name="plan_code" value="${escapeHtml(company.plan_code)}" /></label>
      <label>상태<input name="status" value="${escapeHtml(company.status)}" disabled /></label>
      <label>시간대<input name="timezone" value="${escapeHtml(company.timezone || "Asia/Seoul")}" /></label>
      <label>로케일<input name="locale" value="${escapeHtml(company.locale || "ko-KR")}" /></label>
      <div class="admin-form-actions">
        <button type="submit">저장</button>
      </div>
    </form>
    <section class="admin-subsection">
      <h3>테넌트 설정</h3>
      ${renderSimpleTable(
        ["설정 키", "설정 값", "설명", "수정 일시"],
        settings.map((item) => [item.setting_key, JSON.stringify(item.setting_value ?? ""), item.description, formatDate(item.updated_at)])
      )}
    </section>
  `;
  document.querySelector("#company-form")?.addEventListener("submit", handleAdminSubmit(saveCompany));
}

async function saveCompany(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  const response = await adminApi("/api/admin/company", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "회사 정보를 저장하지 못했습니다.");
  showAdminMessage("회사 정보를 저장했습니다.", "success");
  await loadSummary();
  await renderCompany();
}

async function loadTeams() {
  const response = await adminApi("/api/admin/teams");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀 목록을 불러오지 못했습니다.");
  adminState.teams = result.teams || [];
  adminState.users = result.users || adminState.users;
  return adminState.teams;
}

async function renderUsers() {
  setLoading();
  await loadTeams();
  const response = await adminApi("/api/admin/users");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "사용자 목록을 불러오지 못했습니다.");
  adminState.roles = result.roles || adminState.roles;
  adminState.statuses = result.statuses || adminState.statuses;
  adminState.users = result.users || [];
  const rows = (result.users || [])
    .map(
      (user) => `
        <tr data-user-id="${escapeHtml(user.id)}">
          <td><input name="name" value="${escapeHtml(user.name)}" /></td>
          <td>${escapeHtml(user.email)}</td>
          <td><input name="phone" value="${escapeHtml(user.phone)}" /></td>
          <td><select name="team_id">${teamOptions(user.team_id)}</select></td>
          <td><select name="role">${optionHtml(adminState.roles, user.role, "역할")}</select></td>
          <td><select name="status">${optionHtml(adminState.statuses, user.status, "상태")}</select></td>
          <td>${escapeHtml(formatDate(user.last_login_at))}</td>
          <td><button type="button" data-action="save-user">저장</button></td>
        </tr>
      `
    )
    .join("");
  adminView.innerHTML = `
    <form class="admin-inline-form admin-invite-form" id="invite-user-form">
      <input name="name" placeholder="사용자 이름" required />
      <input name="email" type="email" placeholder="이메일" required />
      <input name="phone" placeholder="전화번호" />
      <select name="team_id">${teamOptions("")}</select>
      <select name="role">${optionHtml(adminState.roles.filter((role) => role.value !== "owner"), "sales", "역할")}</select>
      <button type="submit">초대</button>
    </form>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>이름</th><th>이메일</th><th>전화번호</th><th>팀</th><th>역할</th><th>상태</th><th>마지막 로그인</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="8">등록된 사용자가 없습니다.</td></tr>`}</tbody>
      </table>
    </div>
  `;
  document.querySelector("#invite-user-form")?.addEventListener("submit", handleAdminSubmit(inviteUser));
}

async function inviteUser(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    name: form.get("name"),
    email: form.get("email"),
    phone: form.get("phone"),
    team_id: form.get("team_id") ? Number(form.get("team_id")) : null,
    role: form.get("role"),
  };
  const response = await adminApi("/api/admin/users/invite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "사용자를 초대하지 못했습니다.");
  showAdminMessage(`사용자를 초대했습니다. 임시 비밀번호: ${result.temporary_password}`, "success");
  await loadSummary();
  await renderUsers();
}

async function saveUser(row) {
  const userId = row.dataset.userId;
  const payload = {
    name: row.querySelector('[name="name"]').value,
    phone: row.querySelector('[name="phone"]').value,
    team_id: row.querySelector('[name="team_id"]').value ? Number(row.querySelector('[name="team_id"]').value) : null,
    role: row.querySelector('[name="role"]').value,
    status: row.querySelector('[name="status"]').value,
  };
  const response = await adminApi(`/api/admin/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "사용자 정보를 저장하지 못했습니다.");
  showAdminMessage("사용자 정보를 저장했습니다.", "success");
  await renderUsers();
}

function renderTeamForm() {
  return `
    <form class="admin-inline-form" id="team-form">
      <input name="name" placeholder="팀 이름" required />
      <select name="parent_team_id">${teamOptions("")}</select>
      <input name="description" placeholder="팀 설명" />
      <input name="sort_order" type="number" value="0" aria-label="정렬 순서" />
      <button type="submit">추가</button>
    </form>
  `;
}

async function renderTeams() {
  setLoading();
  const teams = await loadTeams();
  const rows = teams
    .map(
      (team) => `
        <tr data-team-id="${escapeHtml(team.id)}">
          <td><input name="name" value="${escapeHtml(team.name)}" /></td>
          <td><select name="parent_team_id">${teamOptions(team.parent_team_id)}</select></td>
          <td><input name="description" value="${escapeHtml(team.description)}" /></td>
          <td><input name="sort_order" type="number" value="${escapeHtml(team.sort_order || 0)}" /></td>
          <td>${escapeHtml(team.member_count || 0)}</td>
          <td>
            <button type="button" data-action="save-team">저장</button>
            <button type="button" data-action="delete-team">삭제</button>
          </td>
        </tr>
      `
    )
    .join("");
  adminView.innerHTML = `
    ${renderTeamForm()}
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>팀 이름</th><th>상위 팀</th><th>설명</th><th>정렬</th><th>사용자</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="6">등록된 팀이 없습니다.</td></tr>`}</tbody>
      </table>
    </div>
  `;
  document.querySelector("#team-form")?.addEventListener("submit", handleAdminSubmit(createTeam));
}

async function createTeam(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    name: form.get("name"),
    parent_team_id: form.get("parent_team_id") ? Number(form.get("parent_team_id")) : null,
    description: form.get("description"),
    sort_order: Number(form.get("sort_order") || 0),
  };
  const response = await adminApi("/api/admin/teams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀을 추가하지 못했습니다.");
  showAdminMessage("팀을 추가했습니다.", "success");
  await loadSummary();
  await renderTeams();
}

async function saveTeam(row) {
  const teamId = row.dataset.teamId;
  const payload = {
    name: row.querySelector('[name="name"]').value,
    parent_team_id: row.querySelector('[name="parent_team_id"]').value ? Number(row.querySelector('[name="parent_team_id"]').value) : null,
    description: row.querySelector('[name="description"]').value,
    sort_order: Number(row.querySelector('[name="sort_order"]').value || 0),
  };
  const response = await adminApi(`/api/admin/teams/${teamId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀을 저장하지 못했습니다.");
  showAdminMessage("팀 정보를 저장했습니다.", "success");
  await renderTeams();
}

async function deleteTeam(row) {
  if (!confirm("팀을 삭제하고 소속 사용자의 팀 정보를 비울까요?")) return;
  const response = await adminApi(`/api/admin/teams/${row.dataset.teamId}`, { method: "DELETE" });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀을 삭제하지 못했습니다.");
  showAdminMessage("팀을 삭제했습니다.", "success");
  await loadSummary();
  await renderTeams();
}

function selectedValues(select) {
  return Array.from(select?.selectedOptions || []).map((option) => Number(option.value)).filter(Boolean);
}

function renderTeamForm() {
  return `
    <form class="admin-inline-form admin-team-form" id="team-form">
      <input name="name" placeholder="팀 이름" required />
      <select name="parent_team_id">${teamOptions("")}</select>
      <select name="leader_user_id">${userOptions("", "팀장 없음")}</select>
      <select name="member_user_ids" multiple size="3">${memberOptions([])}</select>
      <input name="description" placeholder="팀 설명" />
      <input name="sort_order" type="number" value="0" aria-label="정렬 순서" />
      <button type="submit">추가</button>
    </form>
  `;
}

function teamPayloadFrom(container) {
  return {
    name: container.querySelector('[name="name"]').value,
    parent_team_id: container.querySelector('[name="parent_team_id"]').value ? Number(container.querySelector('[name="parent_team_id"]').value) : null,
    leader_user_id: container.querySelector('[name="leader_user_id"]').value ? Number(container.querySelector('[name="leader_user_id"]').value) : null,
    member_user_ids: selectedValues(container.querySelector('[name="member_user_ids"]')),
    description: container.querySelector('[name="description"]').value,
    sort_order: Number(container.querySelector('[name="sort_order"]').value || 0),
  };
}

async function renderTeams() {
  setLoading();
  const teams = await loadTeams();
  const rows = teams
    .map(
      (team) => `
        <tr data-team-id="${escapeHtml(team.id)}">
          <td><input name="name" value="${escapeHtml(team.name)}" /></td>
          <td><select name="parent_team_id">${teamOptions(team.parent_team_id)}</select></td>
          <td><select name="leader_user_id">${userOptions(team.leader_user_id, "팀장 없음")}</select></td>
          <td><select name="member_user_ids" multiple size="4">${memberOptions(team.member_user_ids || [])}</select></td>
          <td><input name="description" value="${escapeHtml(team.description)}" /></td>
          <td><input name="sort_order" type="number" value="${escapeHtml(team.sort_order || 0)}" /></td>
          <td>${escapeHtml(team.member_count || 0)}</td>
          <td>
            <button type="button" data-action="save-team">저장</button>
            <button type="button" data-action="delete-team">삭제</button>
          </td>
        </tr>
      `
    )
    .join("");
  adminView.innerHTML = `
    ${renderTeamForm()}
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>팀 이름</th><th>상위 팀</th><th>팀장</th><th>팀원</th><th>설명</th><th>정렬</th><th>사용자</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="8">등록된 팀이 없습니다.</td></tr>`}</tbody>
      </table>
    </div>
  `;
  document.querySelector("#team-form")?.addEventListener("submit", handleAdminSubmit(createTeam));
}

async function createTeam(event) {
  event.preventDefault();
  const response = await adminApi("/api/admin/teams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(teamPayloadFrom(event.currentTarget)),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀을 추가하지 못했습니다.");
  showAdminMessage("팀을 추가했습니다.", "success");
  await loadSummary();
  await renderTeams();
}

async function saveTeam(row) {
  const response = await adminApi(`/api/admin/teams/${row.dataset.teamId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(teamPayloadFrom(row)),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "팀을 저장하지 못했습니다.");
  showAdminMessage("팀 정보를 저장했습니다.", "success");
  await renderTeams();
}

async function renderRoles() {
  setLoading();
  const response = await adminApi("/api/admin/roles");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "권한 정보를 불러오지 못했습니다.");
  adminView.innerHTML = `
    <div class="admin-role-grid">
      ${(result.roles || [])
        .map(
          (role) => `
            <section>
              <h3>${escapeHtml(role.label)} <span>${escapeHtml(role.value)}</span></h3>
              <strong>${escapeHtml(role.user_count || 0)}명</strong>
              <ul>${(role.permissions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
          `
        )
        .join("")}
    </div>
  `;
}

function codeGroupPayloadFrom(form) {
  return {
    group_code: form.querySelector('[name="group_code"]').value,
    name: form.querySelector('[name="name"]').value,
    description: form.querySelector('[name="description"]').value,
    sort_order: Number(form.querySelector('[name="sort_order"]').value || 0),
    is_active: form.querySelector('[name="is_active"]').checked,
    items: [],
  };
}

function codeItemPayloadFrom(form) {
  return {
    code: form.querySelector('[name="code"]').value,
    name: form.querySelector('[name="name"]').value,
    description: form.querySelector('[name="description"]').value,
    sort_order: Number(form.querySelector('[name="sort_order"]').value || 0),
    is_active: form.querySelector('[name="is_active"]').checked,
  };
}

async function saveCodeGroups(message = "코드 정보를 저장했습니다.") {
  const response = await adminApi("/api/admin/codes", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ groups: adminState.codeGroups }),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "코드 정보를 저장하지 못했습니다.");
  adminState.codeGroups = result.codes?.groups || [];
  showAdminMessage(message, "success");
  await loadSummary();
  await renderCodes(false);
}

function renderCodeGroupForm() {
  return `
    <form class="admin-inline-form code-group-form" id="code-group-form">
      <input name="group_code" placeholder="그룹 코드" required />
      <input name="name" placeholder="그룹 이름" required />
      <input name="description" placeholder="그룹 설명" />
      <input name="sort_order" type="number" value="0" aria-label="정렬 순서" />
      <label class="admin-checkbox"><input name="is_active" type="checkbox" checked /> 활성</label>
      <button type="submit">그룹 추가</button>
    </form>
  `;
}

function renderCodeItemForm(groupCode) {
  return `
    <form class="admin-inline-form code-item-form" data-code-item-form="${escapeHtml(groupCode)}">
      <input name="code" placeholder="코드" required />
      <input name="name" placeholder="코드명" required />
      <input name="description" placeholder="설명" />
      <input name="sort_order" type="number" value="0" aria-label="정렬 순서" />
      <label class="admin-checkbox"><input name="is_active" type="checkbox" checked /> 활성</label>
      <button type="submit">항목 추가</button>
    </form>
  `;
}

function renderCodeGroup(group) {
  const rows = (group.items || [])
    .map(
      (item) => `
        <tr data-code-group="${escapeHtml(group.group_code)}" data-code-item="${escapeHtml(item.code)}">
          <td><input name="code" value="${escapeHtml(item.code)}" /></td>
          <td><input name="name" value="${escapeHtml(item.name)}" /></td>
          <td><input name="description" value="${escapeHtml(item.description)}" /></td>
          <td><input name="sort_order" type="number" value="${escapeHtml(item.sort_order || 0)}" /></td>
          <td><input name="is_active" type="checkbox" ${item.is_active ? "checked" : ""} /></td>
          <td>
            <button type="button" data-action="save-code-item">저장</button>
            <button type="button" data-action="delete-code-item">삭제</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <section class="admin-code-group" data-code-group-card="${escapeHtml(group.group_code)}">
      <div class="admin-code-group-header">
        <form class="admin-inline-form code-group-edit-form" data-code-group-form="${escapeHtml(group.group_code)}">
          <input name="group_code" value="${escapeHtml(group.group_code)}" />
          <input name="name" value="${escapeHtml(group.name)}" />
          <input name="description" value="${escapeHtml(group.description)}" />
          <input name="sort_order" type="number" value="${escapeHtml(group.sort_order || 0)}" aria-label="정렬 순서" />
          <label class="admin-checkbox"><input name="is_active" type="checkbox" ${group.is_active ? "checked" : ""} /> 활성</label>
          <button type="submit">그룹 저장</button>
        </form>
        <button type="button" class="admin-danger-button" data-action="delete-code-group" data-code-group="${escapeHtml(group.group_code)}">그룹 삭제</button>
      </div>
      ${renderCodeItemForm(group.group_code)}
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>코드</th><th>코드명</th><th>설명</th><th>정렬</th><th>활성</th><th></th></tr></thead>
          <tbody>${rows || `<tr><td colspan="6">등록된 코드 항목이 없습니다.</td></tr>`}</tbody>
        </table>
      </div>
    </section>
  `;
}

async function renderCodes(fetchLatest = true) {
  setLoading();
  if (fetchLatest) {
    const response = await adminApi("/api/admin/codes");
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.detail || result.error || "코드 정보를 불러오지 못했습니다.");
    adminState.codeGroups = result.codes?.groups || [];
  }
  adminView.innerHTML = `
    ${renderCodeGroupForm()}
    <div class="admin-code-groups">
      ${
        adminState.codeGroups.length
          ? adminState.codeGroups.map(renderCodeGroup).join("")
          : `<div class="admin-empty">등록된 사용자 정의 코드 그룹이 없습니다.</div>`
      }
    </div>
  `;
  document.querySelector("#code-group-form")?.addEventListener("submit", handleAdminSubmit(createCodeGroup));
  document.querySelectorAll("[data-code-group-form]").forEach((form) => {
    form.addEventListener("submit", handleAdminSubmit(saveCodeGroup));
  });
  document.querySelectorAll("[data-code-item-form]").forEach((form) => {
    form.addEventListener("submit", handleAdminSubmit(createCodeItem));
  });
}

async function createCodeGroup(event) {
  event.preventDefault();
  const group = codeGroupPayloadFrom(event.currentTarget);
  if (adminState.codeGroups.some((item) => item.group_code === group.group_code)) {
    throw new Error("이미 같은 그룹 코드가 있습니다.");
  }
  adminState.codeGroups.push(group);
  await saveCodeGroups("코드 그룹을 추가했습니다.");
}

async function saveCodeGroup(event) {
  event.preventDefault();
  const oldGroupCode = event.currentTarget.dataset.codeGroupForm;
  const group = adminState.codeGroups.find((item) => item.group_code === oldGroupCode);
  if (!group) throw new Error("코드 그룹을 찾지 못했습니다.");
  const next = codeGroupPayloadFrom(event.currentTarget);
  if (next.group_code !== oldGroupCode && adminState.codeGroups.some((item) => item.group_code === next.group_code)) {
    throw new Error("이미 같은 그룹 코드가 있습니다.");
  }
  Object.assign(group, next, { items: group.items || [] });
  await saveCodeGroups("코드 그룹을 저장했습니다.");
}

async function deleteCodeGroup(groupCode) {
  if (!confirm("코드 그룹과 하위 항목을 삭제할까요?")) return;
  adminState.codeGroups = adminState.codeGroups.filter((group) => group.group_code !== groupCode);
  await saveCodeGroups("코드 그룹을 삭제했습니다.");
}

async function createCodeItem(event) {
  event.preventDefault();
  const groupCode = event.currentTarget.dataset.codeItemForm;
  const group = adminState.codeGroups.find((item) => item.group_code === groupCode);
  if (!group) throw new Error("코드 그룹을 찾지 못했습니다.");
  const item = codeItemPayloadFrom(event.currentTarget);
  group.items = group.items || [];
  if (group.items.some((row) => row.code === item.code)) {
    throw new Error("이미 같은 코드 항목이 있습니다.");
  }
  group.items.push(item);
  await saveCodeGroups("코드 항목을 추가했습니다.");
}

async function saveCodeItem(row) {
  const groupCode = row.dataset.codeGroup;
  const itemCode = row.dataset.codeItem;
  const group = adminState.codeGroups.find((item) => item.group_code === groupCode);
  if (!group) throw new Error("코드 그룹을 찾지 못했습니다.");
  const item = group.items.find((rowItem) => rowItem.code === itemCode);
  if (!item) throw new Error("코드 항목을 찾지 못했습니다.");
  const next = codeItemPayloadFrom(row);
  if (next.code !== itemCode && group.items.some((rowItem) => rowItem.code === next.code)) {
    throw new Error("이미 같은 코드 항목이 있습니다.");
  }
  Object.assign(item, next);
  await saveCodeGroups("코드 항목을 저장했습니다.");
}

async function deleteCodeItem(row) {
  if (!confirm("코드 항목을 삭제할까요?")) return;
  const group = adminState.codeGroups.find((item) => item.group_code === row.dataset.codeGroup);
  if (!group) throw new Error("코드 그룹을 찾지 못했습니다.");
  group.items = (group.items || []).filter((item) => item.code !== row.dataset.codeItem);
  await saveCodeGroups("코드 항목을 삭제했습니다.");
}

function stageOptions(selected) {
  return optionHtml(adminState.stageCodes, selected, "단계 코드");
}

function renderStageForm() {
  return `
    <form class="admin-inline-form" id="stage-form">
      <select name="stage_code">${stageOptions("lead")}</select>
      <input name="name" placeholder="단계 이름" required />
      <input name="description" placeholder="단계 설명" />
      <input name="probability_percent" type="number" min="0" max="100" value="0" aria-label="성공 확률" />
      <input name="sort_order" type="number" value="0" aria-label="정렬 순서" />
      <label class="admin-checkbox"><input name="is_active" type="checkbox" checked /> 활성</label>
      <button type="submit">추가</button>
    </form>
  `;
}

async function renderStages() {
  setLoading();
  const response = await adminApi("/api/admin/pipeline-stages");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "영업 단계를 불러오지 못했습니다.");
  adminState.stageCodes = result.stage_codes || adminState.stageCodes;
  const rows = (result.stages || [])
    .map(
      (stage) => `
        <tr data-stage-id="${escapeHtml(stage.id)}">
          <td><select name="stage_code">${stageOptions(stage.stage_code)}</select></td>
          <td><input name="name" value="${escapeHtml(stage.name)}" /></td>
          <td><input name="description" value="${escapeHtml(stage.description)}" /></td>
          <td><input name="probability_percent" type="number" min="0" max="100" value="${escapeHtml(stage.probability_percent || 0)}" /></td>
          <td><input name="sort_order" type="number" value="${escapeHtml(stage.sort_order || 0)}" /></td>
          <td><input name="is_active" type="checkbox" ${stage.is_active ? "checked" : ""} /></td>
          <td>
            <button type="button" data-action="save-stage">저장</button>
            <button type="button" data-action="delete-stage">삭제</button>
          </td>
        </tr>
      `
    )
    .join("");
  adminView.innerHTML = `
    ${renderStageForm()}
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>코드</th><th>이름</th><th>설명</th><th>확률</th><th>정렬</th><th>활성</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="7">등록된 영업 단계가 없습니다.</td></tr>`}</tbody>
      </table>
    </div>
  `;
  document.querySelector("#stage-form")?.addEventListener("submit", handleAdminSubmit(createStage));
}

function stagePayloadFrom(container) {
  return {
    stage_code: container.querySelector('[name="stage_code"]').value,
    name: container.querySelector('[name="name"]').value,
    description: container.querySelector('[name="description"]').value,
    probability_percent: Number(container.querySelector('[name="probability_percent"]').value || 0),
    sort_order: Number(container.querySelector('[name="sort_order"]').value || 0),
    is_active: container.querySelector('[name="is_active"]').checked,
  };
}

async function createStage(event) {
  event.preventDefault();
  const response = await adminApi("/api/admin/pipeline-stages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(stagePayloadFrom(event.currentTarget)),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "영업 단계를 추가하지 못했습니다.");
  showAdminMessage("영업 단계를 추가했습니다.", "success");
  await loadSummary();
  await renderStages();
}

async function saveStage(row) {
  const response = await adminApi(`/api/admin/pipeline-stages/${row.dataset.stageId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(stagePayloadFrom(row)),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "영업 단계를 저장하지 못했습니다.");
  showAdminMessage("영업 단계를 저장했습니다.", "success");
  await renderStages();
}

async function deleteStage(row) {
  if (!confirm("영업 단계를 삭제할까요?")) return;
  const response = await adminApi(`/api/admin/pipeline-stages/${row.dataset.stageId}`, { method: "DELETE" });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "영업 단계를 삭제하지 못했습니다.");
  showAdminMessage("영업 단계를 삭제했습니다.", "success");
  await loadSummary();
  await renderStages();
}

async function renderStages() {
  setLoading();
  const response = await adminApi("/api/admin/pipeline-stages");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "영업 단계를 불러오지 못했습니다.");
  adminState.stageCodes = result.stage_codes || adminState.stageCodes;
  const defaultRows = (result.default_stages || [])
    .map((stage) => `<li><code>${escapeHtml(stage.stage_code)}</code> ${escapeHtml(stage.name)}</li>`)
    .join("");
  const rows = (result.stages || [])
    .map(
      (stage) => `
        <tr data-stage-id="${escapeHtml(stage.id)}">
          <td><select name="stage_code">${stageOptions(stage.stage_code)}</select></td>
          <td><input name="name" value="${escapeHtml(stage.name)}" /></td>
          <td><input name="description" value="${escapeHtml(stage.description)}" /></td>
          <td><input name="probability_percent" type="number" min="0" max="100" value="${escapeHtml(stage.probability_percent || 0)}" /></td>
          <td><input name="sort_order" type="number" value="${escapeHtml(stage.sort_order || 0)}" /></td>
          <td><input name="is_active" type="checkbox" ${stage.is_active ? "checked" : ""} /></td>
          <td>
            <button type="button" data-action="save-stage">저장</button>
            <button type="button" data-action="delete-stage">삭제</button>
          </td>
        </tr>
      `
    )
    .join("");
  adminView.innerHTML = `
    <div class="admin-default-stage-box">
      <div>
        <strong>기본 영업 단계</strong>
        <ul>${defaultRows}</ul>
      </div>
      <button type="button" data-action="create-default-stages">기본 단계 생성</button>
    </div>
    ${renderStageForm()}
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>코드</th><th>이름</th><th>설명</th><th>확률</th><th>정렬</th><th>활성</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="7">등록된 영업 단계가 없습니다.</td></tr>`}</tbody>
      </table>
    </div>
  `;
  document.querySelector("#stage-form")?.addEventListener("submit", handleAdminSubmit(createStage));
}

async function createDefaultStages() {
  const response = await adminApi("/api/admin/pipeline-stages/defaults", { method: "POST" });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "기본 영업 단계를 생성하지 못했습니다.");
  showAdminMessage(`${result.count || 0}개의 기본 영업 단계를 생성했습니다.`, "success");
  await loadSummary();
  await renderStages();
}

function renderSimpleTable(headers, rows) {
  return `
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
        <tbody>
          ${
            rows.length
              ? rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")
              : `<tr><td colspan="${headers.length}">데이터가 없습니다.</td></tr>`
          }
        </tbody>
      </table>
    </div>
  `;
}

async function renderLogs() {
  setLoading();
  const response = await adminApi("/api/admin/logs?limit=200");
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.detail || result.error || "사용로그를 불러오지 못했습니다.");
  const rows = (result.logs || []).map((log) => [
    formatDate(log.created_at),
    log.actor_name || log.actor_email || log.actor_user_id || "-",
    log.action,
    log.entity_type,
    log.entity_id || "-",
    log.ip_address || "-",
  ]);
  adminView.innerHTML = renderSimpleTable(["일시", "사용자", "행위", "대상", "대상 ID", "IP"], rows);
}

async function renderCurrentMenu() {
  clearAdminMessage();
  const [title, description] = menuMeta[adminState.menu];
  adminTitle.textContent = title;
  adminDescription.textContent = description;
  try {
    if (adminState.menu === "company") await renderCompany();
    if (adminState.menu === "users") await renderUsers();
    if (adminState.menu === "teams") await renderTeams();
    if (adminState.menu === "roles") await renderRoles();
    if (adminState.menu === "codes") await renderCodes();
    if (adminState.menu === "stages") await renderStages();
    if (adminState.menu === "logs") await renderLogs();
  } catch (error) {
    adminView.innerHTML = "";
    showAdminMessage(error.message, "error");
  }
}

adminMenuButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    adminState.menu = button.dataset.adminMenu;
    setActiveMenuButton(adminState.menu);
    const nextPath = settingsPathByMenu[adminState.menu] || "/admin";
    if (window.location.pathname !== nextPath) {
      window.history.pushState({ menu: adminState.menu }, "", nextPath);
    }
    await renderCurrentMenu();
  });
});

window.addEventListener("popstate", async () => {
  adminState.menu = menuFromLocation();
  setActiveMenuButton(adminState.menu);
  await renderCurrentMenu();
});

adminRefreshButton?.addEventListener("click", async () => {
  await loadSummary();
  await renderCurrentMenu();
});

adminView.addEventListener("click", async (event) => {
  const action = event.target?.dataset?.action;
  if (!action) return;
  try {
    const row = event.target.closest("tr");
    if (action === "save-user") await saveUser(row);
    if (action === "save-team") await saveTeam(row);
    if (action === "delete-team") await deleteTeam(row);
    if (action === "delete-code-group") await deleteCodeGroup(event.target.dataset.codeGroup);
    if (action === "save-code-item") await saveCodeItem(row);
    if (action === "delete-code-item") await deleteCodeItem(row);
    if (action === "create-default-stages") await createDefaultStages();
    if (action === "save-stage") await saveStage(row);
    if (action === "delete-stage") await deleteStage(row);
  } catch (error) {
    showAdminMessage(error.message, "error");
  }
});

async function initAdmin() {
  adminState.menu = menuFromLocation();
  setActiveMenuButton(adminState.menu);
  if (window.__FSAI_SESSION__) {
    const session = window.__FSAI_SESSION__;
    adminSessionLabel.textContent = `${session.tenant_name || session.tenant_code || "테넌트"} / ${session.user_name || session.email || "사용자"} / ${session.role_label || session.role || "역할"}`;
  }
  try {
    await loadSummary();
    await renderCurrentMenu();
  } catch (error) {
    showAdminMessage(error.message, "error");
  }
}

initAdmin();
