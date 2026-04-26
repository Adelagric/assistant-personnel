import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
_LOCK_FILE = DATA_FILE + ".lock"

# FileLock : empêche les écritures concurrentes depuis différents threads/jobs
# qui pourraient perdre des données (un _save() écrasant un autre _save()).
try:
    from filelock import FileLock
    _lock = FileLock(_LOCK_FILE, timeout=10)
except ImportError:
    # Fallback silencieux si filelock n'est pas installé (compat rétro).
    class _NoLock:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    _lock = _NoLock()


def _empty() -> dict:
    return {
        "notes": [], "tasks": [], "conversations": {}, "brief_users": [],
        "expenses": [], "email_templates": [], "email_alerts": [], "reminders": [],
        "automations": [], "email_followups": [],
        "processed_emails": [], "prepared_events": [],
        "web_monitors": [], "budgets": {}, "github_repos": [],
        "completed_events": [],
    }


def _load() -> dict:
    with _lock:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                # Fichier corrompu : on repart d'une structure vide
                backup = DATA_FILE + ".bak"
                try:
                    import shutil
                    shutil.copy2(DATA_FILE, backup)
                except Exception:
                    pass
                return _empty()
        return _empty()


def _save(data: dict):
    """Écriture atomique + verrou : on écrit dans un .tmp puis on rename."""
    with _lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)


def _next_id(items: list) -> int:
    return max((i["id"] for i in items), default=0) + 1


# ── NOTES ───────────────────────────────────────────────────────────────────

def add_note(content: str) -> str:
    data = _load()
    note_id = _next_id(data["notes"])
    data["notes"].append({
        "id": note_id,
        "content": content,
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    _save(data)
    return f"Note #{note_id} enregistrée."


def list_notes() -> list:
    return _load()["notes"]


def delete_note(note_id: int) -> str:
    data = _load()
    before = len(data["notes"])
    data["notes"] = [n for n in data["notes"] if n["id"] != note_id]
    _save(data)
    return f"Note #{note_id} supprimée." if len(data["notes"]) < before else f"Note #{note_id} introuvable."


# ── TÂCHES ──────────────────────────────────────────────────────────────────

def add_task(title: str, due_date: str = None) -> str:
    data = _load()
    task_id = _next_id(data["tasks"])
    data["tasks"].append({
        "id": task_id,
        "title": title,
        "due_date": due_date,
        "done": False,
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    _save(data)
    return f"Tâche #{task_id} ajoutée."


def list_tasks(include_done: bool = False) -> list:
    tasks = _load()["tasks"]
    return tasks if include_done else [t for t in tasks if not t["done"]]


def complete_task(task_id: int) -> str:
    data = _load()
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["done"] = True
            _save(data)
            return f"Tâche #{task_id} marquée comme terminée ✅"
    return f"Tâche #{task_id} introuvable."


def delete_task(task_id: int) -> str:
    data = _load()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    _save(data)
    return f"Tâche #{task_id} supprimée." if len(data["tasks"]) < before else f"Tâche #{task_id} introuvable."


# ── DÉPENSES ─────────────────────────────────────────────────────────────────

def add_expense(amount: float, category: str, description: str = "") -> str:
    data = _load()
    exp_id = _next_id(data["expenses"])
    data["expenses"].append({
        "id": exp_id,
        "amount": amount,
        "category": category,
        "description": description,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save(data)
    return f"Dépense de {amount}€ ({category}) enregistrée (#{exp_id})."


def list_expenses(month: str = None) -> list:
    """month format: '2026-04'"""
    expenses = _load()["expenses"]
    if month:
        expenses = [e for e in expenses if e["date"].startswith(month)]
    return expenses


def expense_summary(month: str = None) -> dict:
    expenses = list_expenses(month)
    total = sum(e["amount"] for e in expenses)
    by_category: dict = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]
    return {"total": total, "par_categorie": by_category, "nb_depenses": len(expenses)}


def delete_expense(expense_id: int) -> str:
    data = _load()
    before = len(data["expenses"])
    data["expenses"] = [e for e in data["expenses"] if e["id"] != expense_id]
    _save(data)
    return f"Dépense #{expense_id} supprimée." if len(data["expenses"]) < before else f"Dépense #{expense_id} introuvable."


# ── TEMPLATES EMAIL ──────────────────────────────────────────────────────────

def save_email_template(name: str, subject: str, body: str) -> str:
    data = _load()
    tpl_id = _next_id(data["email_templates"])
    data["email_templates"].append({
        "id": tpl_id,
        "name": name,
        "subject": subject,
        "body": body,
    })
    _save(data)
    return f"Template '{name}' sauvegardé (#{tpl_id})."


def list_email_templates() -> list:
    return _load()["email_templates"]


def get_email_template(template_id: int) -> dict:
    for t in _load()["email_templates"]:
        if t["id"] == template_id:
            return t
    return {}


def delete_email_template(template_id: int) -> str:
    data = _load()
    before = len(data["email_templates"])
    data["email_templates"] = [t for t in data["email_templates"] if t["id"] != template_id]
    _save(data)
    return f"Template #{template_id} supprimé." if len(data["email_templates"]) < before else f"Template #{template_id} introuvable."


# ── ALERTES EMAIL ────────────────────────────────────────────────────────────

def add_email_alert(sender: str = "", keyword: str = "") -> str:
    data = _load()
    alert_id = _next_id(data["email_alerts"])
    data["email_alerts"].append({
        "id": alert_id,
        "sender": sender.lower(),
        "keyword": keyword.lower(),
        "active": True,
    })
    _save(data)
    desc = []
    if sender:
        desc.append(f"expéditeur : {sender}")
    if keyword:
        desc.append(f"mot-clé : {keyword}")
    return f"Alerte #{alert_id} créée ({', '.join(desc)})."


def list_email_alerts() -> list:
    return _load()["email_alerts"]


def remove_email_alert(alert_id: int) -> str:
    data = _load()
    before = len(data["email_alerts"])
    data["email_alerts"] = [a for a in data["email_alerts"] if a["id"] != alert_id]
    _save(data)
    return f"Alerte #{alert_id} supprimée." if len(data["email_alerts"]) < before else f"Alerte #{alert_id} introuvable."


# ── RAPPELS ──────────────────────────────────────────────────────────────────

def add_reminder(user_id: int, message: str, remind_at: str) -> dict:
    """remind_at: ISO 8601 ex: '2026-04-13T09:00:00'"""
    data = _load()
    rem_id = _next_id(data["reminders"])
    reminder = {
        "id": rem_id,
        "user_id": user_id,
        "message": message,
        "remind_at": remind_at,
        "sent": False,
    }
    data["reminders"].append(reminder)
    _save(data)
    return reminder


def list_reminders(user_id: int) -> list:
    return [r for r in _load()["reminders"] if r["user_id"] == user_id and not r["sent"]]


def cancel_reminder(reminder_id: int) -> str:
    data = _load()
    before = len(data["reminders"])
    data["reminders"] = [r for r in data["reminders"] if r["id"] != reminder_id]
    _save(data)
    return f"Rappel #{reminder_id} annulé." if len(data["reminders"]) < before else f"Rappel #{reminder_id} introuvable."


def get_pending_reminders() -> list:
    return [r for r in _load()["reminders"] if not r["sent"]]


def mark_reminder_sent(reminder_id: int):
    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            r["sent"] = True
    _save(data)


# ── MÉMOIRE CONTEXTUELLE ─────────────────────────────────────────────────────

def save_memory(key: str, value: str) -> str:
    data = _load()
    if "memory" not in data:
        data["memory"] = {}
    data["memory"][key] = {
        "value": value,
        "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    _save(data)
    return f"Mémorisé : {key} = {value}"


def get_memory() -> dict:
    return _load().get("memory", {})


def delete_memory(key: str) -> str:
    data = _load()
    if key in data.get("memory", {}):
        del data["memory"][key]
        _save(data)
        return f"Souvenir '{key}' supprimé."
    return f"Souvenir '{key}' introuvable."


# ── AUTOMATIONS ──────────────────────────────────────────────────────────────

def add_automation(user_id: int, description: str, schedule: str,
                   instruction: str, condition: str = None) -> dict:
    data = _load()
    if "automations" not in data:
        data["automations"] = []
    auto_id = _next_id(data["automations"])
    automation = {
        "id": auto_id,
        "user_id": user_id,
        "description": description,
        "schedule": schedule,
        "instruction": instruction,
        "condition": condition,
        "active": True,
        "last_run": None,
    }
    data["automations"].append(automation)
    _save(data)
    return automation


def list_automations(user_id: int = None) -> list:
    automations = _load().get("automations", [])
    if user_id is not None:
        automations = [a for a in automations if a["user_id"] == user_id]
    return automations


def delete_automation(auto_id: int) -> str:
    data = _load()
    before = len(data.get("automations", []))
    data["automations"] = [a for a in data.get("automations", []) if a["id"] != auto_id]
    _save(data)
    return f"Automation #{auto_id} supprimée." if len(data.get("automations", [])) < before else f"Automation #{auto_id} introuvable."


def get_due_automations() -> list:
    """Retourne les automations actives dont l'heure d'exécution est atteinte."""
    now = datetime.now()
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    current_day = day_names[now.weekday()]
    current_time = now.strftime("%H:%M")
    current_minute = now.strftime("%Y-%m-%d %H:%M")

    due = []
    for a in _load().get("automations", []):
        if not a.get("active"):
            continue
        if a.get("last_run") == current_minute:
            continue
        schedule = a.get("schedule", "")
        if schedule.startswith("daily:") and schedule[6:] == current_time:
            due.append(a)
        elif schedule.startswith("weekly:"):
            parts = schedule.split(":", 2)
            if len(parts) == 3 and parts[1].lower() == current_day and parts[2] == current_time:
                due.append(a)
    return due


def mark_automation_run(auto_id: int):
    data = _load()
    for a in data.get("automations", []):
        if a["id"] == auto_id:
            a["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save(data)


# ── SUIVI DE RELANCE EMAIL ───────────────────────────────────────────────────

def add_followup(user_id: int, email_id: str, thread_id: str, to: str,
                 subject: str, followup_days: int = 3) -> dict:
    data = _load()
    if "email_followups" not in data:
        data["email_followups"] = []
    fup_id = _next_id(data["email_followups"])
    followup = {
        "id": fup_id,
        "user_id": user_id,
        "email_id": email_id,
        "thread_id": thread_id,
        "to": to,
        "subject": subject,
        "sent_at": datetime.now().strftime("%Y-%m-%d"),
        "followup_days": followup_days,
        "reminded": False,
    }
    data["email_followups"].append(followup)
    _save(data)
    return followup


def list_followups(user_id: int) -> list:
    return [f for f in _load().get("email_followups", [])
            if f["user_id"] == user_id and not f["reminded"]]


def cancel_followup(followup_id: int) -> str:
    data = _load()
    before = len(data.get("email_followups", []))
    data["email_followups"] = [f for f in data.get("email_followups", [])
                               if f["id"] != followup_id]
    _save(data)
    return (f"Suivi #{followup_id} annulé."
            if len(data.get("email_followups", [])) < before
            else f"Suivi #{followup_id} introuvable.")


def get_pending_followups() -> list:
    return [f for f in _load().get("email_followups", []) if not f["reminded"]]


def mark_followup_reminded(followup_id: int):
    data = _load()
    for f in data.get("email_followups", []):
        if f["id"] == followup_id:
            f["reminded"] = True
    _save(data)


# ── EMAILS TRAITÉS (scan intelligent) ───────────────────────────────────────

def is_email_processed(email_id: str) -> bool:
    return email_id in _load().get("processed_emails", [])


def mark_email_processed(email_id: str):
    data = _load()
    if "processed_emails" not in data:
        data["processed_emails"] = []
    if email_id not in data["processed_emails"]:
        data["processed_emails"].append(email_id)
        data["processed_emails"] = data["processed_emails"][-500:]
    _save(data)


# ── ÉVÉNEMENTS PRÉPARÉS ─────────────────────────────────────────────────────

def is_event_prepared(event_id: str, date: str) -> bool:
    return f"{event_id}_{date}" in _load().get("prepared_events", [])


def mark_event_prepared(event_id: str, date: str):
    data = _load()
    if "prepared_events" not in data:
        data["prepared_events"] = []
    key = f"{event_id}_{date}"
    if key not in data["prepared_events"]:
        data["prepared_events"].append(key)
        data["prepared_events"] = data["prepared_events"][-200:]
    _save(data)


def format_memory_for_prompt() -> str:
    memory = get_memory()
    if not memory:
        return ""
    lines = []
    for key, entry in memory.items():
        lines.append(f"- {key} : {entry['value']}")
    return "\n".join(lines)


# ── CONVERSATIONS ────────────────────────────────────────────────────────────

def save_conversation(user_id: int, messages: list):
    data = _load()
    data["conversations"][str(user_id)] = messages[-20:]
    _save(data)


def load_conversation(user_id: int) -> list:
    return _load()["conversations"].get(str(user_id), [])


# ── BRIEF USERS ──────────────────────────────────────────────────────────────

def register_brief_user(user_id: int):
    data = _load()
    if user_id not in data["brief_users"]:
        data["brief_users"].append(user_id)
        _save(data)


def get_brief_users() -> list:
    return _load()["brief_users"]


# ── GMAIL HISTORY ────────────────────────────────────────────────────────────

def get_last_history_id() -> str | None:
    return _load().get("last_history_id")


def set_last_history_id(history_id: str):
    data = _load()
    data["last_history_id"] = str(history_id)
    _save(data)


# ── WEB MONITORS ────────────────────────────────────────────────────────────

def add_web_monitor(user_id: int, url: str, description: str,
                    css_selector: str = None, interval_minutes: int = 60) -> dict:
    data = _load()
    if "web_monitors" not in data:
        data["web_monitors"] = []
    mon_id = _next_id(data["web_monitors"])
    monitor = {
        "id": mon_id,
        "user_id": user_id,
        "url": url,
        "description": description,
        "css_selector": css_selector,
        "interval_minutes": interval_minutes,
        "last_hash": None,
        "last_text": None,
        "last_check": None,
        "active": True,
    }
    data["web_monitors"].append(monitor)
    _save(data)
    return monitor


def list_web_monitors(user_id: int = None) -> list:
    monitors = _load().get("web_monitors", [])
    if user_id is not None:
        monitors = [m for m in monitors if m["user_id"] == user_id]
    return [m for m in monitors if m.get("active", True)]


def delete_web_monitor(monitor_id: int) -> str:
    data = _load()
    before = len(data.get("web_monitors", []))
    data["web_monitors"] = [m for m in data.get("web_monitors", []) if m["id"] != monitor_id]
    _save(data)
    return f"Surveillance #{monitor_id} supprimée." if len(data.get("web_monitors", [])) < before else f"Surveillance #{monitor_id} introuvable."


def update_web_monitor_snapshot(monitor_id: int, content_hash: str, text: str):
    data = _load()
    for m in data.get("web_monitors", []):
        if m["id"] == monitor_id:
            m["last_hash"] = content_hash
            m["last_text"] = text[:2000]
            m["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save(data)


# ── BUDGETS ─────────────────────────────────────────────────────────────────

def set_budget(category: str, amount: float, month: str = None) -> str:
    """Définit un budget pour une catégorie. month format: '2026-04' ou None pour récurrent."""
    data = _load()
    if "budgets" not in data:
        data["budgets"] = {}
    key = f"{category}:{month}" if month else f"{category}:*"
    data["budgets"][key] = {"category": category, "amount": amount, "month": month}
    _save(data)
    scope = f"pour {month}" if month else "mensuel récurrent"
    return f"Budget {category} fixé à {amount}€ ({scope})."


def get_budgets() -> dict:
    return _load().get("budgets", {})


def delete_budget(category: str, month: str = None) -> str:
    data = _load()
    key = f"{category}:{month}" if month else f"{category}:*"
    if key in data.get("budgets", {}):
        del data["budgets"][key]
        _save(data)
        return f"Budget {category} supprimé."
    return f"Budget {category} introuvable."


def check_budget_alerts(month: str = None) -> list:
    """Retourne les catégories qui dépassent 80% du budget."""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    budgets = get_budgets()
    expenses = list_expenses(month)
    by_cat: dict = {}
    for e in expenses:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]

    alerts = []
    for key, budget in budgets.items():
        cat = budget["category"]
        bud_month = budget.get("month")
        if bud_month and bud_month != month:
            continue
        spent = by_cat.get(cat, 0)
        pct = (spent / budget["amount"] * 100) if budget["amount"] > 0 else 0
        if pct >= 80:
            alerts.append({
                "category": cat,
                "budget": budget["amount"],
                "spent": spent,
                "percent": round(pct, 1),
                "over": pct >= 100,
            })
    return alerts


# ── GITHUB REPOS ────────────────────────────────────────────────────────────

def add_github_repo(user_id: int, owner: str, repo: str) -> str:
    data = _load()
    if "github_repos" not in data:
        data["github_repos"] = []
    for r in data["github_repos"]:
        if r["owner"] == owner and r["repo"] == repo:
            return f"Repo {owner}/{repo} déjà surveillé."
    repo_id = _next_id(data["github_repos"])
    data["github_repos"].append({
        "id": repo_id,
        "user_id": user_id,
        "owner": owner,
        "repo": repo,
        "last_check": None,
    })
    _save(data)
    return f"Repo {owner}/{repo} ajouté à la surveillance (#{repo_id})."


def list_github_repos(user_id: int = None) -> list:
    repos = _load().get("github_repos", [])
    if user_id is not None:
        repos = [r for r in repos if r["user_id"] == user_id]
    return repos


def delete_github_repo(repo_id: int) -> str:
    data = _load()
    before = len(data.get("github_repos", []))
    data["github_repos"] = [r for r in data.get("github_repos", []) if r["id"] != repo_id]
    _save(data)
    return f"Repo #{repo_id} retiré." if len(data.get("github_repos", [])) < before else f"Repo #{repo_id} introuvable."


# ── COMPLETED EVENTS (post-réunion) ────────────────────────────────────────

def is_event_completed(event_id: str, date: str) -> bool:
    return f"{event_id}_{date}" in _load().get("completed_events", [])


def mark_event_completed(event_id: str, date: str):
    data = _load()
    if "completed_events" not in data:
        data["completed_events"] = []
    key = f"{event_id}_{date}"
    if key not in data["completed_events"]:
        data["completed_events"].append(key)
        data["completed_events"] = data["completed_events"][-200:]
    _save(data)
