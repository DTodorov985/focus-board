"use strict";
const elements = {
  list: document.getElementById("task-list"),
  empty: document.getElementById("empty-state"),
  search: document.getElementById("task-search"),
  form: document.getElementById("task-form"),
  message: document.getElementById("form-message"),
  submit: document.getElementById("submit"),
};
let tasks = [];
let currentFilter = "all";

async function request(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let body;
  try { body = await res.json(); } catch { throw new Error("Unexpected server response."); }
  if (!res.ok) throw new Error(body.error || "Request failed.");
  return body;
}

function dateLabel(isoDate) {
  if (!isoDate) return "No due date";
  const [year, month, day] = isoDate.split("-");
  return `Due ${day}/${month}/${year}`;
}

function render() {
  const total = tasks.length;
  const done = tasks.filter(task => task.is_done).length;
  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-done").textContent = done;
  document.getElementById("stat-open").textContent = total - done;
  const pct = total ? Math.round(100 * done / total) : 0;
  document.getElementById("stat-progress").textContent = pct + "%";
  document.getElementById("progress-bar").style.width = pct + "%";

  const query = elements.search.value.trim().toLowerCase();
  const visible = tasks.filter(task => {
    const matchesStatus = currentFilter === "all" ||
      (currentFilter === "done" ? task.is_done : !task.is_done);
    const matchesSearch = task.title.toLowerCase().includes(query) ||
      task.course.toLowerCase().includes(query);
    return matchesStatus && matchesSearch;
  });
  elements.list.replaceChildren();
  elements.empty.hidden = visible.length > 0;
  elements.empty.textContent = query
    ? "No matching tasks. Try another title or course, clear your search, or select All tasks."
    : currentFilter === "open"
      ? "No tasks to do here. Add a task or select All tasks."
      : currentFilter === "done"
        ? "No completed tasks yet. Complete a task or select All tasks."
        : "No tasks here yet. Add one to get started.";
  visible.forEach(task => {
    const row = document.createElement("article");
    row.className = "task-row" + (task.is_done ? " completed" : "");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "task-checkbox";
    checkbox.checked = task.is_done;
    checkbox.setAttribute("aria-label", `Complete ${task.title}`);
    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;
      try {
        await request(`/api/tasks/${task.id}`, {
          method: "PATCH", body: JSON.stringify({ is_done: checkbox.checked }),
        });
        await refresh();
      } catch (err) { alert(err.message); await refresh(); }
    });
    const main = document.createElement("div");
    main.className = "task-main";
    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = task.title;
    const meta = document.createElement("div");
    meta.className = "task-meta";
    const course = document.createElement("span");
    course.textContent = task.course || "General";
    const dot = document.createElement("span");
    dot.className = "sep"; dot.textContent = "•";
    const due = document.createElement("span");
    due.textContent = dateLabel(task.due_date);
    meta.append(course, dot, due);
    main.append(title, meta);
    const priority = document.createElement("span");
    priority.className = `priority ${task.priority}`;
    priority.textContent = task.priority;
    const deleteButton = document.createElement("button");
    deleteButton.className = "delete";
    deleteButton.title = `Delete ${task.title}`;
    deleteButton.setAttribute("aria-label", `Delete ${task.title}`);
    deleteButton.textContent = "×";
    deleteButton.addEventListener("click", async () => {
      if (!confirm(`Delete "${task.title}"?`)) return;
      try { await request(`/api/tasks/${task.id}`, { method: "DELETE" }); await refresh(); }
      catch (err) { alert(err.message); }
    });
    row.append(checkbox, main, priority, deleteButton);
    elements.list.append(row);
  });
}

async function refresh() {
  const body = await request("/api/tasks");
  tasks = body.tasks;
  render();
}

elements.form.addEventListener("submit", async event => {
  event.preventDefault();
  const payload = {
    title: document.getElementById("title").value,
    course: document.getElementById("course").value,
    due_date: document.getElementById("due_date").value || null,
    priority: document.getElementById("priority").value,
  };
  elements.submit.disabled = true;
  elements.message.textContent = "";
  try {
    await request("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
    elements.form.reset();
    elements.message.style.color = "#279e78";
    elements.message.textContent = "Task added successfully!";
    currentFilter = "all";
    document.querySelectorAll(".filter").forEach(button => {
      const active = button.dataset.filter === currentFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    await refresh();
  } catch (err) {
    elements.message.style.color = "#a3435b";
    elements.message.textContent = err.message;
  } finally { elements.submit.disabled = false; }
});

elements.search.addEventListener("input", render);

document.querySelectorAll(".filter").forEach(button => {
  button.addEventListener("click", () => {
    currentFilter = button.dataset.filter;
    document.querySelectorAll(".filter").forEach(tab => {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    });
    render();
  });
});

refresh().catch(err => {
  elements.empty.hidden = false;
  elements.empty.textContent = `Could not load tasks: ${err.message}`;
});
