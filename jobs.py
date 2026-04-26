import asyncio
from datetime import datetime

from telegram.ext import ContextTypes

import storage
from config import gmail, calendar, conversations, logger
from handlers import _run_claude
from tools import get_new_message_ids


# -- Résilience jobs ----------------------------------------------------------

_job_failures: dict[str, int] = {}


async def _notify_job_failure(bot, job_name: str, error: str):
    _job_failures[job_name] = _job_failures.get(job_name, 0) + 1
    if _job_failures[job_name] >= 3:
        for user_id in storage.get_brief_users():
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Job *{job_name}* en échec depuis 3 tentatives.\nDernière erreur : `{str(error)[:200]}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        _job_failures[job_name] = 0


def _reset_job_failure(job_name: str):
    _job_failures[job_name] = 0


# -- Jobs ---------------------------------------------------------------------

async def send_daily_brief(context: ContextTypes.DEFAULT_TYPE):
    for user_id in storage.get_brief_users():
        try:
            if user_id not in conversations:
                conversations[user_id] = storage.load_conversation(user_id)
            conversations[user_id].append({
                "role": "user",
                "content": (
                    "Brief matinal : emails non lus importants (max 5) avec résumé, "
                    "événements d'aujourd'hui et demain, météo Paris, tâches urgentes."
                )
            })
            await _run_claude(user_id, context.bot, user_id)
        except Exception as e:
            logger.error(f"Erreur brief matinal {user_id}: {e}")


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    for reminder in storage.get_pending_reminders():
        try:
            remind_at = datetime.fromisoformat(reminder["remind_at"])
            if now >= remind_at:
                await context.bot.send_message(
                    chat_id=reminder["user_id"],
                    text=f"⏰ Rappel : {reminder['message']}"
                )
                storage.mark_reminder_sent(reminder["id"])
        except Exception as e:
            logger.error(f"Erreur rappel #{reminder['id']}: {e}")


def _check_condition(condition: str) -> bool:
    if not condition:
        return True
    parts = condition.split(":")
    try:
        if parts[0] == "tasks" and len(parts) >= 2 and parts[1] == "overdue":
            tasks = storage.list_tasks(include_done=False)
            today = datetime.now().strftime("%Y-%m-%d")
            return any(t.get("due_date") and t["due_date"] < today for t in tasks)

        if parts[0] == "weather" and len(parts) >= 3:
            from features.weather import get_weather as _get_wx
            keyword = parts[1].lower()
            city = parts[2]
            wx = _get_wx(city)
            return keyword in wx.get("condition", "").lower()

        if parts[0] == "emails" and len(parts) >= 3 and parts[1] == "unread":
            op_val = parts[2]
            result = gmail.users().messages().list(
                userId="me", maxResults=50, q="is:unread"
            ).execute()
            count = result.get("resultSizeEstimate", 0)
            if op_val.startswith(">"):
                return count > int(op_val[1:])
            if op_val.startswith("<"):
                return count < int(op_val[1:])
            return True
    except Exception:
        return True
    return True


async def check_automations(context: ContextTypes.DEFAULT_TYPE):
    for automation in storage.get_due_automations():
        user_id = automation["user_id"]
        try:
            storage.mark_automation_run(automation["id"])
            condition = automation.get("condition")
            if condition and not _check_condition(condition):
                continue
            if user_id not in conversations:
                conversations[user_id] = storage.load_conversation(user_id)
            conversations[user_id].append({"role": "user", "content": automation["instruction"]})
            # Automation : souvent "surveille et dis-moi SI quelque chose" → on filtre les réponses vides
            await _run_claude(user_id, context.bot, user_id, silent_if_nothing=True)
        except Exception as e:
            logger.error(f"Erreur automation #{automation['id']}: {e}")


async def check_email_alerts(context: ContextTypes.DEFAULT_TYPE):
    alerts = storage.list_email_alerts()
    if not alerts:
        return
    user_ids = storage.get_brief_users()
    try:
        new_ids = await asyncio.to_thread(get_new_message_ids, gmail)
        if not new_ids:
            return
        new_emails = []
        for msg_id in new_ids[:10]:
            m = gmail.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            new_emails.append({
                "id": msg_id,
                "subject": headers.get("Subject", "(sans objet)"),
                "from": headers.get("From", ""),
                "snippet": m.get("snippet", ""),
            })
        for alert in alerts:
            for msg in new_emails:
                match = True
                if alert["sender"] and alert["sender"].lower() not in msg["from"].lower():
                    match = False
                if alert["keyword"] and alert["keyword"].lower() not in (msg["subject"] + " " + msg["snippet"]).lower():
                    match = False
                if match:
                    for user_id in user_ids:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"🔔 *Alerte email* (règle #{alert['id']})\n"
                                f"De : {msg['from']}\n"
                                f"Sujet : {msg['subject']}\n"
                                f"_{msg['snippet'][:150]}_"
                            ),
                            parse_mode="Markdown"
                        )
        _reset_job_failure("email_alerts")
    except Exception as e:
        logger.error(f"Erreur alertes email: {e}")
        await _notify_job_failure(context.bot, "email_alerts", e)


async def check_followups(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    for followup in storage.get_pending_followups():
        try:
            sent_date = datetime.strptime(followup["sent_at"], "%Y-%m-%d")
            if (now - sent_date).days < followup["followup_days"]:
                continue
            thread = gmail.users().threads().get(
                userId="me", id=followup["thread_id"],
                format="metadata", metadataHeaders=["From"]
            ).execute()
            messages = thread.get("messages", [])
            has_reply = False
            found_sent = False
            for msg in messages:
                if msg["id"] == followup["email_id"]:
                    found_sent = True
                    continue
                if found_sent:
                    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
                    if followup["to"].lower() in headers.get("From", "").lower():
                        has_reply = True
                        break
            storage.mark_followup_reminded(followup["id"])
            if has_reply:
                continue
            days = (now - sent_date).days
            await context.bot.send_message(
                chat_id=followup["user_id"],
                text=(
                    f"📬 *Relance suggérée*\n"
                    f"Email à `{followup['to']}` sans réponse depuis {days} jours.\n"
                    f"Sujet : _{followup['subject']}_\n\n"
                    f"Dis-moi si tu veux que je relance."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Erreur followup #{followup['id']}: {e}")


async def prepare_meetings(context: ContextTypes.DEFAULT_TYPE):
    from datetime import timezone, timedelta
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(minutes=25)
    window_end = now + timedelta(minutes=35)
    try:
        result = calendar.events().list(
            calendarId="primary",
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True, orderBy="startTime"
        ).execute()
        for event in result.get("items", []):
            event_id = event["id"]
            date = event["start"].get("dateTime", event["start"].get("date", ""))[:10]
            if storage.is_event_prepared(event_id, date):
                continue
            storage.mark_event_prepared(event_id, date)
            title = event.get("summary", "(sans titre)")
            attendees = [a.get("email", "") for a in event.get("attendees", [])]
            location = event.get("location", "")
            description = event.get("description", "")
            attendee_text = ", ".join(attendees) if attendees else "aucun"

            tasks_data = storage.list_tasks()
            pending_tasks = [t for t in tasks_data if not t.get("done")]
            tasks_text = ", ".join(t["title"] for t in pending_tasks[:5]) if pending_tasks else "aucune"

            notes_data = storage.list_notes()
            relevant_notes = [n for n in notes_data if title.lower().split()[0] in n.get("content", "").lower()][:3]
            notes_text = " | ".join(n["content"][:80] for n in relevant_notes) if relevant_notes else "aucune"

            instruction = (
                f"📅 Prépare-moi pour ma réunion '{title}' qui commence dans 30 min.\n"
                f"Participants : {attendee_text}.\n"
            )
            if location:
                instruction += f"Lieu : {location}.\n"
            if description:
                instruction += f"Description : {description}.\n"
            instruction += f"Tâches en cours : {tasks_text}.\n"
            if relevant_notes != "aucune":
                instruction += f"Notes potentiellement liées : {notes_text}.\n"
            if attendees:
                instruction += "Cherche les derniers emails de ces participants et résume le contexte.\n"
            instruction += (
                "Fais un brief structuré : 1) Contexte 2) Points à préparer 3) Actions suggérées. "
                "Sois concis et actionable."
            )
            for user_id in storage.get_brief_users():
                try:
                    if user_id not in conversations:
                        conversations[user_id] = storage.load_conversation(user_id)
                    conversations[user_id].append({"role": "user", "content": instruction})
                    await _run_claude(user_id, context.bot, user_id)
                except Exception as e:
                    logger.error(f"Erreur prépa réunion {user_id}: {e}")
        _reset_job_failure("prepare_meetings")
    except Exception as e:
        logger.error(f"Erreur prepare_meetings: {e}")
        await _notify_job_failure(context.bot, "prepare_meetings", e)


async def smart_email_scan(context: ContextTypes.DEFAULT_TYPE):
    try:
        result = gmail.users().messages().list(
            userId="me", maxResults=5, q="is:unread newer_than:30m"
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return
        new_emails = []
        for msg in messages:
            if storage.is_email_processed(msg["id"]):
                continue
            storage.mark_email_processed(msg["id"])
            m = gmail.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            new_emails.append({
                "id": msg["id"],
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "snippet": m.get("snippet", ""),
            })
        if not new_emails:
            return
        email_list = "\n".join(
            f"- ID:{e['id']} | De: {e['from']} | Sujet: {e['subject']} | {e['snippet'][:100]}"
            for e in new_emails
        )
        instruction = (
            f"🔍 Analyse automatique de {len(new_emails)} nouveaux emails :\n{email_list}\n\n"
            "Pour chaque email, détecte UNIQUEMENT si c'est :\n"
            "- Une facture/reçu → propose d'ajouter comme dépense (montant, catégorie)\n"
            "- Une invitation à une réunion avec date → propose de créer un événement\n"
            "- Un email avec une deadline claire → propose de créer une tâche\n"
            "- Un email urgent nécessitant une réponse rapide → signale-le\n\n"
            "**IMPORTANT : si AUCUN email n'est actionable, réponds UNIQUEMENT le mot 'SILENT' "
            "(sans rien d'autre, pas de 'rien à signaler', pas de RAS, juste 'SILENT'). "
            "Ce mot sera automatiquement filtré et rien ne sera envoyé à l'utilisateur.**\n"
            "Sois très concis. Propose les actions, ne les exécute pas sans confirmation."
        )
        for user_id in storage.get_brief_users():
            try:
                if user_id not in conversations:
                    conversations[user_id] = storage.load_conversation(user_id)
                conversations[user_id].append({"role": "user", "content": instruction})
                # Scan email : si rien d'actionnable, ne rien envoyer à l'utilisateur
                await _run_claude(user_id, context.bot, user_id, silent_if_nothing=True)
            except Exception as e:
                logger.error(f"Erreur smart scan {user_id}: {e}")
        _reset_job_failure("smart_email_scan")
    except Exception as e:
        logger.error(f"Erreur smart_email_scan: {e}")
        await _notify_job_failure(context.bot, "smart_email_scan", e)


async def analyze_habits(context: ContextTypes.DEFAULT_TYPE):
    for user_id in storage.get_brief_users():
        try:
            conv = storage.load_conversation(user_id)
            if len(conv) < 6:
                continue
            user_msgs = [m["content"] for m in conv if m["role"] == "user" and isinstance(m["content"], str)]
            if not user_msgs:
                continue
            recent = "\n".join(f"- {m[:120]}" for m in user_msgs[-15:])
            existing_autos = storage.list_automations(user_id)
            auto_list = ", ".join(a["description"] for a in existing_autos) if existing_autos else "aucune"
            instruction = (
                f"🧠 Analyse de mes habitudes récentes :\n{recent}\n\n"
                f"Automations déjà en place : {auto_list}\n\n"
                "Détecte des patterns répétitifs dans mes demandes. "
                "Si tu identifies une action que je fais souvent manuellement et qui pourrait être automatisée, "
                "propose-moi de créer une automation.\n\n"
                "**IMPORTANT : si aucune suggestion pertinente, réponds UNIQUEMENT 'SILENT' "
                "(sans autre texte). Ce mot sera filtré automatiquement.**\n"
                "Sois très concis. Max 2-3 suggestions pertinentes."
            )
            if user_id not in conversations:
                conversations[user_id] = storage.load_conversation(user_id)
            conversations[user_id].append({"role": "user", "content": instruction})
            # Analyse hebdo : pas de spam si rien à proposer
            await _run_claude(user_id, context.bot, user_id, silent_if_nothing=True)
        except Exception as e:
            logger.error(f"Erreur analyze_habits {user_id}: {e}")


async def check_web_monitors(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie les pages web surveillées pour détecter des changements."""
    from features.web_monitor import fetch_page_text, compare_snapshots
    now = datetime.now()
    for monitor in storage.list_web_monitors():
        try:
            # Vérifier si l'intervalle est atteint
            if monitor.get("last_check"):
                last = datetime.strptime(monitor["last_check"], "%Y-%m-%d %H:%M")
                if (now - last).total_seconds() < monitor.get("interval_minutes", 60) * 60:
                    continue

            result = await asyncio.to_thread(
                fetch_page_text, monitor["url"], monitor.get("css_selector")
            )
            if "error" in result:
                logger.error(f"Web monitor #{monitor['id']}: {result['error']}")
                continue

            old_hash = monitor.get("last_hash")
            new_hash = result["hash"]
            storage.update_web_monitor_snapshot(monitor["id"], new_hash, result["text"])

            if old_hash and old_hash != new_hash:
                old_text = monitor.get("last_text", "")
                diff = compare_snapshots(old_text, result["text"])
                for user_id in storage.get_brief_users():
                    if monitor["user_id"] != user_id:
                        continue
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🔄 *Changement détecté* — {monitor['description']}\n"
                            f"URL : {monitor['url']}\n\n"
                            f"_{diff[:500]}_"
                        ),
                        parse_mode="Markdown"
                    )
        except Exception as e:
            logger.error(f"Erreur web monitor #{monitor['id']}: {e}")


async def post_meeting_followup(context: ContextTypes.DEFAULT_TYPE):
    """Après une réunion terminée, propose de faire un compte-rendu."""
    from datetime import timezone, timedelta
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=15)
    window_end = now - timedelta(minutes=5)
    try:
        result = calendar.events().list(
            calendarId="primary",
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True, orderBy="startTime"
        ).execute()
        for event in result.get("items", []):
            # Vérifier que l'événement est TERMINÉ (end time passé)
            end_str = event["end"].get("dateTime", event["end"].get("date", ""))
            if not end_str:
                continue
            try:
                from datetime import datetime as dt
                end_time = dt.fromisoformat(end_str.replace("Z", "+00:00"))
                if end_time > now:
                    continue  # pas encore terminé
            except Exception:
                continue

            event_id = event["id"]
            date = event["start"].get("dateTime", event["start"].get("date", ""))[:10]
            if storage.is_event_completed(event_id, date):
                continue
            storage.mark_event_completed(event_id, date)

            title = event.get("summary", "(sans titre)")
            attendees = [a.get("email", "") for a in event.get("attendees", [])]
            attendee_text = ", ".join(attendees) if attendees else "aucun"

            for user_id in storage.get_brief_users():
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"📝 La réunion *{title}* vient de se terminer.\n"
                            f"Participants : {attendee_text}\n\n"
                            "Veux-tu que je rédige un compte-rendu ? "
                            "Dis-moi les points clés et je génère un doc structuré sur Drive."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Erreur post-meeting {user_id}: {e}")
    except Exception as e:
        logger.error(f"Erreur post_meeting_followup: {e}")


async def check_budget_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie quotidiennement si des budgets sont proches d'être dépassés."""
    alerts = storage.check_budget_alerts()
    if not alerts:
        return
    for user_id in storage.get_brief_users():
        try:
            lines = ["💰 *Alerte budget*\n"]
            for a in alerts:
                status = "🔴 DÉPASSÉ" if a["over"] else "🟠 Attention"
                lines.append(
                    f"• {status} — {a['category']} : {a['spent']}€ / {a['budget']}€ ({a['percent']}%)"
                )
            await context.bot.send_message(
                chat_id=user_id,
                text="\n".join(lines),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Erreur budget alert {user_id}: {e}")


async def reindex_rag(context: ContextTypes.DEFAULT_TYPE):
    """Réindexe périodiquement les nouvelles conversations, notes et mémoire dans le RAG."""
    try:
        from features.rag import index_documents
        docs = []
        # Conversations de tous les brief_users
        for user_id in storage.get_brief_users():
            conv = storage.load_conversation(user_id)
            for m in conv:
                if isinstance(m.get("content"), str) and len(m["content"]) > 20:
                    docs.append({
                        "content": m["content"],
                        "source": f"conversation_{m['role']}",
                        "timestamp": "",
                        "metadata": {"user_id": str(user_id)},
                    })
        # Notes
        for n in storage.list_notes():
            docs.append({
                "content": n["content"],
                "source": "note",
                "timestamp": n.get("created_at", ""),
            })
        # Mémoire
        for k, v in storage.get_memory().items():
            docs.append({
                "content": f"{k} : {v}",
                "source": "memory_kv",
                "timestamp": "",
            })
        count = await asyncio.to_thread(index_documents, docs)
        if count:
            logger.info(f"RAG : {count} documents (ré)indexés")
    except Exception as e:
        logger.error(f"Erreur reindex_rag: {e}")


async def check_github_repos(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie les repos GitHub surveillés pour nouvelles PRs / CI cassé."""
    from features.github_monitor import get_repo_status
    repos = storage.list_github_repos()
    if not repos:
        return
    for repo_entry in repos:
        try:
            status = await asyncio.to_thread(
                get_repo_status, repo_entry["owner"], repo_entry["repo"]
            )
            if "error" in status:
                continue

            # Détecter les CI en échec
            failed_ci = [r for r in status.get("recent_ci", []) if r.get("conclusion") == "failure"]
            new_prs = status.get("open_prs", [])

            if not failed_ci and not new_prs:
                continue

            parts = [f"📊 *{repo_entry['owner']}/{repo_entry['repo']}*\n"]
            if failed_ci:
                for ci in failed_ci:
                    parts.append(f"🔴 CI échouée : {ci['name']} ({ci['branch']})")
            if new_prs:
                parts.append(f"\n📋 {len(new_prs)} PR(s) ouvertes")
                for pr in new_prs[:3]:
                    draft = " [draft]" if pr.get("draft") else ""
                    parts.append(f"  • #{pr['number']} {pr['title']}{draft} — @{pr['author']}")

            for user_id in storage.get_brief_users():
                if repo_entry["user_id"] != user_id:
                    continue
                await context.bot.send_message(
                    chat_id=user_id,
                    text="\n".join(parts),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Erreur GitHub monitor {repo_entry.get('owner')}/{repo_entry.get('repo')}: {e}")
