/* タスク管理 TODO アプリ
 * 依存なし・localStorage で永続化するシンプルなクライアントサイドアプリ。
 */
(function () {
  "use strict";

  const STORAGE_KEY = "todo.tasks.v1";
  const THEME_KEY = "todo.theme.v1";
  const PRIORITY_ORDER = { high: 3, medium: 2, low: 1 };
  const PRIORITY_LABEL = { high: "優先度: 高", medium: "優先度: 中", low: "優先度: 低" };

  /** アプリの状態 */
  let tasks = load();
  let filter = "all";
  let sort = "created-desc";
  let query = "";

  // --- DOM 参照 ---
  const el = {
    form: document.getElementById("taskForm"),
    input: document.getElementById("taskInput"),
    priority: document.getElementById("prioritySelect"),
    category: document.getElementById("categoryInput"),
    due: document.getElementById("dueInput"),
    list: document.getElementById("taskList"),
    empty: document.getElementById("emptyState"),
    search: document.getElementById("searchInput"),
    filters: document.getElementById("filters"),
    sort: document.getElementById("sortSelect"),
    catList: document.getElementById("categoryList"),
    themeToggle: document.getElementById("themeToggle"),
    clearDone: document.getElementById("clearDoneBtn"),
    footerCount: document.getElementById("footerCount"),
    stats: {
      total: document.getElementById("statTotal"),
      active: document.getElementById("statActive"),
      done: document.getElementById("statDone"),
      overdue: document.getElementById("statOverdue"),
    },
    progressBar: document.getElementById("progressBar"),
    progressText: document.getElementById("progressText"),
  };

  // --- 永続化 ---
  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn("読み込みに失敗しました", e);
      return [];
    }
  }
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch (e) {
      console.warn("保存に失敗しました", e);
    }
  }

  // --- ユーティリティ ---
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }
  function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function pad(n) { return String(n).padStart(2, "0"); }
  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  /** 期限を「あと N 日」などの読みやすい文字列にする */
  function dueInfo(due) {
    if (!due) return null;
    const today = todayStr();
    const diffDays = Math.round(
      (new Date(due + "T00:00:00") - new Date(today + "T00:00:00")) / 86400000
    );
    let cls = "";
    let text = due;
    if (diffDays < 0) { cls = "due-overdue"; text = `期限切れ (${-diffDays}日超過)`; }
    else if (diffDays === 0) { cls = "due-soon"; text = "今日まで"; }
    else if (diffDays === 1) { cls = "due-soon"; text = "明日まで"; }
    else if (diffDays <= 3) { cls = "due-soon"; text = `あと${diffDays}日`; }
    else { text = `${due}`; }
    return { cls, text };
  }

  // --- CRUD ---
  function addTask(data) {
    tasks.unshift({
      id: uid(),
      title: data.title,
      done: false,
      priority: data.priority || "medium",
      category: data.category || "",
      due: data.due || "",
      createdAt: Date.now(),
    });
    save();
    render();
  }
  function updateTask(id, patch) {
    const t = tasks.find((t) => t.id === id);
    if (!t) return;
    Object.assign(t, patch);
    save();
    render();
  }
  function deleteTask(id) {
    tasks = tasks.filter((t) => t.id !== id);
    save();
    render();
  }

  // --- 絞り込みと並べ替え ---
  function visibleTasks() {
    let list = tasks.slice();

    if (filter === "active") list = list.filter((t) => !t.done);
    else if (filter === "done") list = list.filter((t) => t.done);

    if (query) {
      const q = query.toLowerCase();
      list = list.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          (t.category && t.category.toLowerCase().includes(q))
      );
    }

    list.sort((a, b) => {
      switch (sort) {
        case "created-asc": return a.createdAt - b.createdAt;
        case "due-asc":
          if (!a.due) return 1;
          if (!b.due) return -1;
          return a.due.localeCompare(b.due);
        case "priority-desc":
          return PRIORITY_ORDER[b.priority] - PRIORITY_ORDER[a.priority];
        case "alpha": return a.title.localeCompare(b.title, "ja");
        case "created-desc":
        default: return b.createdAt - a.createdAt;
      }
    });
    return list;
  }

  // --- 描画 ---
  function render() {
    const list = visibleTasks();
    el.list.innerHTML = "";

    list.forEach((t) => el.list.appendChild(renderItem(t)));

    el.empty.hidden = list.length !== 0;
    updateStats();
    updateCategoryList();
    el.footerCount.textContent = `${list.length} 件`;
  }

  function renderItem(t) {
    const li = document.createElement("li");
    li.className = `task-item priority-${t.priority}` + (t.done ? " done" : "");
    li.dataset.id = t.id;

    // チェックボックス
    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "task-check";
    check.checked = t.done;
    check.title = "完了/未完了";
    check.addEventListener("change", () => updateTask(t.id, { done: check.checked }));

    // 本文
    const body = document.createElement("div");
    body.className = "task-body";

    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = t.title;
    title.title = "ダブルクリックで編集";
    title.addEventListener("dblclick", () => startEdit(title, t.id));

    const meta = document.createElement("div");
    meta.className = "task-meta";
    meta.innerHTML = buildMeta(t);

    body.appendChild(title);
    body.appendChild(meta);

    // 操作
    const actions = document.createElement("div");
    actions.className = "task-actions";
    const editBtn = document.createElement("button");
    editBtn.innerHTML = "✏️";
    editBtn.title = "編集";
    editBtn.addEventListener("click", () => startEdit(title, t.id));
    const delBtn = document.createElement("button");
    delBtn.className = "del";
    delBtn.innerHTML = "🗑️";
    delBtn.title = "削除";
    delBtn.addEventListener("click", () => {
      if (confirm("このタスクを削除しますか？")) deleteTask(t.id);
    });
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);

    li.appendChild(check);
    li.appendChild(body);
    li.appendChild(actions);
    return li;
  }

  function buildMeta(t) {
    const parts = [];
    parts.push(`<span class="badge" title="${PRIORITY_LABEL[t.priority]}">${priorityIcon(t.priority)} ${priorityText(t.priority)}</span>`);
    if (t.category) parts.push(`<span class="badge cat">🏷️ ${escapeHtml(t.category)}</span>`);
    const d = dueInfo(t.due);
    if (d) parts.push(`<span class="badge ${d.cls}">📅 ${escapeHtml(d.text)}</span>`);
    return parts.join("");
  }
  function priorityIcon(p) { return p === "high" ? "🔴" : p === "medium" ? "🟡" : "🟢"; }
  function priorityText(p) { return p === "high" ? "高" : p === "medium" ? "中" : "低"; }

  /** タイトルのインライン編集 */
  function startEdit(titleEl, id) {
    titleEl.setAttribute("contenteditable", "true");
    titleEl.focus();
    // カーソルを末尾へ
    const range = document.createRange();
    range.selectNodeContents(titleEl);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    function finish(saveEdit) {
      titleEl.removeAttribute("contenteditable");
      titleEl.removeEventListener("keydown", onKey);
      titleEl.removeEventListener("blur", onBlur);
      const text = titleEl.textContent.trim();
      if (saveEdit && text) updateTask(id, { title: text });
      else render();
    }
    function onKey(e) {
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      else if (e.key === "Escape") { finish(false); }
    }
    function onBlur() { finish(true); }
    titleEl.addEventListener("keydown", onKey);
    titleEl.addEventListener("blur", onBlur);
  }

  function updateStats() {
    const total = tasks.length;
    const done = tasks.filter((t) => t.done).length;
    const active = total - done;
    const today = todayStr();
    const overdue = tasks.filter(
      (t) => !t.done && t.due && t.due < today
    ).length;

    el.stats.total.textContent = total;
    el.stats.active.textContent = active;
    el.stats.done.textContent = done;
    el.stats.overdue.textContent = overdue;

    const pct = total ? Math.round((done / total) * 100) : 0;
    el.progressBar.style.width = pct + "%";
    el.progressText.textContent = pct + "%";
  }

  function updateCategoryList() {
    const cats = [...new Set(tasks.map((t) => t.category).filter(Boolean))];
    el.catList.innerHTML = cats.map((c) => `<option value="${escapeHtml(c)}">`).join("");
  }

  // --- テーマ ---
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    el.themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
  }
  function initTheme() {
    let theme;
    try { theme = localStorage.getItem(THEME_KEY); } catch (e) {}
    if (!theme) {
      theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    applyTheme(theme);
  }

  // --- イベント ---
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = el.input.value.trim();
    if (!title) return;
    addTask({
      title,
      priority: el.priority.value,
      category: el.category.value.trim(),
      due: el.due.value,
    });
    el.form.reset();
    el.priority.value = "medium";
    el.input.focus();
  });

  el.search.addEventListener("input", () => {
    query = el.search.value.trim();
    render();
  });

  el.filters.addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-btn");
    if (!btn) return;
    filter = btn.dataset.filter;
    el.filters.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    render();
  });

  el.sort.addEventListener("change", () => {
    sort = el.sort.value;
    render();
  });

  el.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    applyTheme(current === "dark" ? "light" : "dark");
  });

  el.clearDone.addEventListener("click", () => {
    const doneCount = tasks.filter((t) => t.done).length;
    if (doneCount === 0) { alert("完了済みのタスクはありません。"); return; }
    if (confirm(`完了済みの ${doneCount} 件を削除しますか？`)) {
      tasks = tasks.filter((t) => !t.done);
      save();
      render();
    }
  });

  // --- 起動 ---
  initTheme();
  render();
})();
