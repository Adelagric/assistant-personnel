"""
Registre centralisé des outils Claude.

Chaque outil est défini UNE SEULE FOIS : son schéma JSON + sa fonction d'exécution.
Pour ajouter un outil, il suffit d'ajouter une entrée dans TOOL_DEFS.
"""
import json
import os
import sys
import time as _time

from config import gmail, calendar, people, drive
import tools
import storage

# Apple Notes : nécessite macOS (osascript).
# Désactivé par défaut — mets ENABLE_APPLE_NOTES=true dans .env pour réactiver.
_MACOS = sys.platform == "darwin"
_APPLE_NOTES_ENABLED = _MACOS and os.getenv("ENABLE_APPLE_NOTES", "false").lower() == "true"
if _APPLE_NOTES_ENABLED:
    from features.apple_notes import (
        create_apple_note, list_apple_notes, search_apple_notes,
    )
else:
    create_apple_note = list_apple_notes = search_apple_notes = None


def _retry(func, *args, max_retries=2, **kwargs):
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception:
            if attempt == max_retries:
                raise
            _time.sleep(2 ** attempt)


def _to_json(obj):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json(i) for i in obj]
    if hasattr(obj, "model_dump"):
        return _to_json(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return _to_json(obj.__dict__)
    return str(obj)


# -- Helpers d'exécution (injectent les services Google) ----------------------

def _exec_list_emails(**kw):
    return json.dumps(_retry(tools.list_emails, gmail, **kw), ensure_ascii=False)

def _exec_read_email(**kw):
    return json.dumps(_retry(tools.read_email, gmail, **kw), ensure_ascii=False)

def _exec_get_attachment(**kw):
    return _retry(tools.get_attachment, gmail, **kw)

def _exec_send_email(**kw):
    return tools.send_email(gmail, **kw)

def _exec_reply_email(**kw):
    return tools.reply_email(gmail, **kw)

def _exec_create_draft(**kw):
    return tools.create_draft(gmail, **kw)

def _exec_archive_email(**kw):
    return tools.archive_email(gmail, **kw)

def _exec_trash_email(**kw):
    return tools.trash_email(gmail, **kw)

def _exec_bulk_trash(**kw):
    return tools.bulk_trash(gmail, **kw)

def _exec_mark_email(**kw):
    return tools.mark_email(gmail, **kw)

def _exec_mark_all_read(**kw):
    return tools.mark_all_read(gmail, **kw)

def _exec_set_vacation_reply(**kw):
    return tools.set_vacation_reply(gmail, **kw)

def _exec_disable_vacation_reply(**kw):
    return tools.disable_vacation_reply(gmail)

def _exec_send_from_template(**kw):
    return tools.send_from_template(gmail, **kw)

def _exec_save_email_template(**kw):
    return tools.save_email_template(**kw)

def _exec_list_email_templates(**kw):
    return json.dumps(tools.list_email_templates(), ensure_ascii=False)

def _exec_delete_email_template(**kw):
    return tools.delete_email_template(**kw)

def _exec_add_email_alert(**kw):
    return tools.add_email_alert(**kw)

def _exec_list_email_alerts(**kw):
    return json.dumps(tools.list_email_alerts(), ensure_ascii=False)

def _exec_remove_email_alert(**kw):
    return tools.remove_email_alert(**kw)

def _exec_list_calendars(**kw):
    return json.dumps(_retry(tools.list_calendars, calendar), ensure_ascii=False)

def _exec_list_events(**kw):
    return json.dumps(_retry(tools.list_events, calendar, **kw), ensure_ascii=False)

def _exec_create_event(**kw):
    return _retry(tools.create_event, calendar, **kw)

def _exec_update_event(**kw):
    return _retry(tools.update_event, calendar, **kw)

def _exec_delete_event(**kw):
    return _retry(tools.delete_event, calendar, **kw)

def _exec_search_contacts(**kw):
    return json.dumps(_retry(tools.search_contacts, people, **kw), ensure_ascii=False)

def _exec_search_drive(**kw):
    return json.dumps(_retry(tools.search_drive, drive, **kw), ensure_ascii=False)

def _exec_read_drive_file(**kw):
    return _retry(tools.read_drive_file, drive, **kw)

def _exec_create_drive_doc(**kw):
    return tools.create_drive_doc(drive, **kw)

def _exec_update_drive_doc(**kw):
    return tools.update_drive_doc(drive, **kw)

def _exec_search_web(**kw):
    return json.dumps(tools.search_web(**kw), ensure_ascii=False)

def _exec_get_weather(**kw):
    return json.dumps(tools.get_weather(**kw), ensure_ascii=False)

def _exec_get_news(**kw):
    return json.dumps(tools.get_news(**kw), ensure_ascii=False)

def _exec_add_note(**kw):
    return tools.add_note(**kw)

def _exec_list_notes(**kw):
    return json.dumps(tools.list_notes(), ensure_ascii=False)

def _exec_delete_note(**kw):
    return tools.delete_note(**kw)

def _exec_add_task(**kw):
    return tools.add_task(**kw)

def _exec_list_tasks(**kw):
    return json.dumps(tools.list_tasks(**kw), ensure_ascii=False)

def _exec_complete_task(**kw):
    return tools.complete_task(**kw)

def _exec_delete_task(**kw):
    return tools.delete_task(**kw)

def _exec_add_expense(**kw):
    return tools.add_expense(**kw)

def _exec_list_expenses(**kw):
    return json.dumps(tools.list_expenses(**kw), ensure_ascii=False)

def _exec_expense_summary(**kw):
    return json.dumps(tools.expense_summary(**kw), ensure_ascii=False)

def _exec_delete_expense(**kw):
    return tools.delete_expense(**kw)

def _exec_export_expenses(**kw):
    return tools.export_expenses_to_drive(drive, **kw)

def _exec_make_phone_call(**kw):
    return json.dumps(tools.make_phone_call(**kw), ensure_ascii=False)

def _exec_get_call_status(**kw):
    return json.dumps(tools.get_call_status(**kw), ensure_ascii=False)

def _exec_list_recent_calls(**kw):
    return json.dumps(tools.list_recent_calls(**kw), ensure_ascii=False)

def _exec_reserve_opentable(**kw):
    return json.dumps(tools.reserve_opentable(**kw), ensure_ascii=False)

def _exec_reserve_thefork(**kw):
    return json.dumps(tools.reserve_thefork(**kw), ensure_ascii=False)

def _exec_find_phone_number(**kw):
    return json.dumps(tools.find_phone_number(**kw), ensure_ascii=False)

def _exec_create_apple_note(**kw):
    return create_apple_note(**kw)

def _exec_list_apple_notes(**kw):
    return json.dumps(list_apple_notes(**kw), ensure_ascii=False)

def _exec_search_apple_notes(**kw):
    return json.dumps(search_apple_notes(**kw), ensure_ascii=False)

def _exec_save_memory(**kw):
    return tools.save_memory(**kw)

def _exec_get_memory(**kw):
    return json.dumps(tools.get_memory(), ensure_ascii=False)

def _exec_delete_memory(**kw):
    return tools.delete_memory(**kw)


# -- Fonctions qui nécessitent user_id (injecté par execute_tool) -------------

def _exec_set_reminder(user_id, **kw):
    return tools.set_reminder(user_id, **kw)

def _exec_list_reminders(user_id, **kw):
    return json.dumps(tools.list_reminders(user_id), ensure_ascii=False)

def _exec_cancel_reminder(**kw):
    return tools.cancel_reminder(**kw)

def _exec_track_followup(user_id, **kw):
    return tools.track_followup(user_id, **kw)

def _exec_list_followups(user_id, **kw):
    return json.dumps(tools.list_followups(user_id), ensure_ascii=False)

def _exec_cancel_followup(**kw):
    return tools.cancel_followup(**kw)

def _exec_add_automation(user_id, **kw):
    return tools.add_automation(user_id, **kw)

def _exec_list_automations(user_id, **kw):
    return json.dumps(tools.list_automations(user_id), ensure_ascii=False)

def _exec_delete_automation(**kw):
    return tools.delete_automation(**kw)


# -- Surveillance web --
def _exec_add_web_monitor(user_id, **kw):
    return tools.add_web_monitor(user_id, **kw)

def _exec_list_web_monitors(user_id, **kw):
    return json.dumps(tools.list_web_monitors(user_id), ensure_ascii=False)

def _exec_delete_web_monitor(**kw):
    return tools.delete_web_monitor(**kw)

def _exec_check_web_page(**kw):
    return json.dumps(tools.check_web_page(**kw), ensure_ascii=False)

# -- Résumé de liens --
def _exec_summarize_url(**kw):
    return json.dumps(tools.summarize_url(**kw), ensure_ascii=False)

# -- SMS / WhatsApp --
def _exec_send_sms(**kw):
    return json.dumps(tools.send_sms(**kw), ensure_ascii=False)

def _exec_send_whatsapp(**kw):
    return json.dumps(tools.send_whatsapp(**kw), ensure_ascii=False)

# -- GitHub --
def _exec_github_repo_status(**kw):
    return json.dumps(tools.github_repo_status(**kw), ensure_ascii=False)

def _exec_github_notifications(**kw):
    return json.dumps(tools.github_notifications(), ensure_ascii=False)

def _exec_add_github_repo(user_id, **kw):
    return tools.add_github_repo(user_id, **kw)

def _exec_list_github_repos(user_id, **kw):
    return json.dumps(tools.list_github_repos(user_id), ensure_ascii=False)

def _exec_delete_github_repo(**kw):
    return tools.delete_github_repo(**kw)

# -- Budget --
def _exec_set_budget(**kw):
    return tools.set_budget(**kw)

def _exec_get_budgets(**kw):
    return json.dumps(tools.get_budgets(), ensure_ascii=False)

def _exec_delete_budget(**kw):
    return tools.delete_budget(**kw)

def _exec_check_budget_alerts(**kw):
    return json.dumps(tools.check_budget_alerts(**kw), ensure_ascii=False)

# -- Génération de documents --
def _exec_generate_document(**kw):
    return tools.create_drive_doc(drive, **kw)

# -- Maps & trajets --
def _exec_geocode_address(**kw):
    return json.dumps(tools.geocode_address(**kw), ensure_ascii=False)

def _exec_travel_time(**kw):
    return json.dumps(tools.travel_time(**kw), ensure_ascii=False)

def _exec_get_directions(**kw):
    return json.dumps(tools.get_directions(**kw), ensure_ascii=False)

def _exec_when_to_leave(**kw):
    return json.dumps(tools.when_to_leave(**kw), ensure_ascii=False)

# -- RAG mémoire sémantique --
def _exec_search_memory(**kw):
    return json.dumps(tools.search_memory(**kw), ensure_ascii=False)

def _exec_rag_stats(**kw):
    return json.dumps(tools.rag_stats(), ensure_ascii=False)

def _exec_index_recent_content(user_id, **kw):
    return json.dumps(tools.index_recent_content(user_id), ensure_ascii=False)


# Tools qui nécessitent user_id comme premier argument
_USER_ID_TOOLS = {
    "set_reminder", "list_reminders",
    "track_followup", "list_followups",
    "add_automation", "list_automations",
    "add_web_monitor", "list_web_monitors",
    "add_github_repo", "list_github_repos",
    "index_recent_content",
}


# =============================================================================
#  TOOL_DEFS : source unique de vérité pour chaque outil
#  Chaque entrée = (schema_dict, executor_function)
# =============================================================================

TOOL_DEFS: list[tuple[dict, callable]] = [
    # ── EMAIL ─────────────────────────────────────────────────────────────
    (
        {
            "name": "list_emails",
            "description": "Lister les emails. query accepte les filtres Gmail (ex: 'is:unread', 'from:boss@example.com', 'subject:réunion').",
            "input_schema": {"type": "object", "properties": {
                "max_results": {"type": "integer", "default": 10},
                "query": {"type": "string", "default": "is:unread"},
            }},
        },
        _exec_list_emails,
    ),
    (
        {
            "name": "read_email",
            "description": "Lire le contenu complet d'un email par son ID. Retourne aussi la liste des pièces jointes s'il y en a.",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
            }, "required": ["email_id"]},
        },
        _exec_read_email,
    ),
    (
        {
            "name": "get_attachment",
            "description": "Télécharger et lire le contenu d'une pièce jointe email (texte uniquement). Utilise l'attachment_id retourné par read_email.",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
                "attachment_id": {"type": "string"},
            }, "required": ["email_id", "attachment_id"]},
        },
        _exec_get_attachment,
    ),
    (
        {
            "name": "send_email",
            "description": "Envoyer un email. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            }, "required": ["to", "subject", "body"]},
        },
        _exec_send_email,
    ),
    (
        {
            "name": "reply_email",
            "description": "Répondre à un email. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
                "body": {"type": "string"},
            }, "required": ["email_id", "body"]},
        },
        _exec_reply_email,
    ),
    (
        {
            "name": "create_draft",
            "description": "Créer un brouillon d'email sans l'envoyer.",
            "input_schema": {"type": "object", "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            }, "required": ["to", "subject", "body"]},
        },
        _exec_create_draft,
    ),
    (
        {
            "name": "archive_email",
            "description": "Archiver un email (retirer de la boîte de réception).",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
            }, "required": ["email_id"]},
        },
        _exec_archive_email,
    ),
    (
        {
            "name": "trash_email",
            "description": "Mettre un email à la corbeille. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
            }, "required": ["email_id"]},
        },
        _exec_trash_email,
    ),
    (
        {
            "name": "bulk_trash",
            "description": "Mettre à la corbeille TOUS les emails correspondant à une query Gmail (suppression en masse). 🔴 Confirmation obligatoire — indiquer le nombre approximatif d'emails concernés.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Query Gmail, ex: 'category:promotions', 'from:newsletter@example.com', 'older_than:1y subject:newsletter'"},
            }, "required": ["query"]},
        },
        _exec_bulk_trash,
    ),
    (
        {
            "name": "mark_email",
            "description": "Marquer un email comme lu ou non lu.",
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string"},
                "read": {"type": "boolean", "description": "true = lu, false = non lu"},
            }, "required": ["email_id", "read"]},
        },
        _exec_mark_email,
    ),
    (
        {
            "name": "mark_all_read",
            "description": "Marquer TOUS les emails non lus comme lus d'un coup (batch). Accepte une query Gmail optionnelle pour filtrer (ex: 'is:unread older_than:30d', 'is:unread from:newsletter@'). Par défaut marque TOUS les non lus. Demander confirmation avant.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string", "default": "is:unread", "description": "Query Gmail, ex: 'is:unread', 'is:unread older_than:7d', 'is:unread category:promotions'"},
            }},
        },
        _exec_mark_all_read,
    ),
    (
        {
            "name": "set_vacation_reply",
            "description": "Activer une réponse automatique d'absence. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "message": {"type": "string", "description": "Texte de la réponse automatique"},
                "subject": {"type": "string", "default": "Absent(e) du bureau"},
                "start_date": {"type": "string", "description": "ISO 8601 optionnel"},
                "end_date": {"type": "string", "description": "ISO 8601 optionnel"},
            }, "required": ["message"]},
        },
        _exec_set_vacation_reply,
    ),
    (
        {
            "name": "disable_vacation_reply",
            "description": "Désactiver la réponse automatique d'absence.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_disable_vacation_reply,
    ),
    (
        {
            "name": "send_from_template",
            "description": "Envoyer un email depuis un template sauvegardé. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "template_id": {"type": "integer"},
                "to": {"type": "string"},
                "extra": {"type": "string", "description": "Texte supplémentaire à ajouter en fin de corps"},
            }, "required": ["template_id", "to"]},
        },
        _exec_send_from_template,
    ),
    # ── TEMPLATES EMAIL ───────────────────────────────────────────────────
    (
        {
            "name": "save_email_template",
            "description": "Sauvegarder un modèle d'email réutilisable.",
            "input_schema": {"type": "object", "properties": {
                "name": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            }, "required": ["name", "subject", "body"]},
        },
        _exec_save_email_template,
    ),
    (
        {
            "name": "list_email_templates",
            "description": "Lister les modèles d'emails sauvegardés.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_email_templates,
    ),
    (
        {
            "name": "delete_email_template",
            "description": "Supprimer un modèle d'email.",
            "input_schema": {"type": "object", "properties": {
                "template_id": {"type": "integer"},
            }, "required": ["template_id"]},
        },
        _exec_delete_email_template,
    ),
    # ── ALERTES EMAIL ─────────────────────────────────────────────────────
    (
        {
            "name": "add_email_alert",
            "description": "Créer une alerte : être notifié par Telegram quand un email d'un expéditeur ou contenant un mot-clé arrive.",
            "input_schema": {"type": "object", "properties": {
                "sender": {"type": "string", "description": "Adresse email à surveiller (optionnel)"},
                "keyword": {"type": "string", "description": "Mot-clé à chercher dans le sujet/snippet (optionnel)"},
            }},
        },
        _exec_add_email_alert,
    ),
    (
        {
            "name": "list_email_alerts",
            "description": "Lister les alertes email actives.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_email_alerts,
    ),
    (
        {
            "name": "remove_email_alert",
            "description": "Supprimer une alerte email.",
            "input_schema": {"type": "object", "properties": {
                "alert_id": {"type": "integer"},
            }, "required": ["alert_id"]},
        },
        _exec_remove_email_alert,
    ),
    # ── CALENDRIER ────────────────────────────────────────────────────────
    (
        {
            "name": "list_calendars",
            "description": "Lister tous les calendriers disponibles (principal + partagés).",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_calendars,
    ),
    (
        {
            "name": "list_events",
            "description": "Lister les prochains événements d'un calendrier.",
            "input_schema": {"type": "object", "properties": {
                "max_results": {"type": "integer", "default": 10},
                "time_min": {"type": "string", "description": "Date ISO 8601 de début (optionnel)"},
                "calendar_id": {"type": "string", "default": "primary", "description": "ID du calendrier (par défaut: primary). Utilise list_calendars pour voir les autres."},
            }},
        },
        _exec_list_events,
    ),
    (
        {
            "name": "create_event",
            "description": "Créer un événement calendrier. 🟡 Confirmation légère.",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601, ex: 2026-04-15T10:00:00"},
                "end": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            }, "required": ["title", "start", "end"]},
        },
        _exec_create_event,
    ),
    (
        {
            "name": "update_event",
            "description": "Modifier un événement existant. 🟡 Confirmation légère.",
            "input_schema": {"type": "object", "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            }, "required": ["event_id"]},
        },
        _exec_update_event,
    ),
    (
        {
            "name": "delete_event",
            "description": "Supprimer un événement calendrier. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            }, "required": ["event_id"]},
        },
        _exec_delete_event,
    ),
    # ── CONTACTS ──────────────────────────────────────────────────────────
    (
        {
            "name": "search_contacts",
            "description": "Chercher un contact dans Google Contacts (nom, email, téléphone).",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        },
        _exec_search_contacts,
    ),
    # ── GOOGLE DRIVE ──────────────────────────────────────────────────────
    (
        {
            "name": "search_drive",
            "description": "Rechercher des fichiers dans Google Drive.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            }, "required": ["query"]},
        },
        _exec_search_drive,
    ),
    (
        {
            "name": "read_drive_file",
            "description": "Lire le contenu d'un fichier Google Drive (Docs, texte).",
            "input_schema": {"type": "object", "properties": {
                "file_id": {"type": "string"},
            }, "required": ["file_id"]},
        },
        _exec_read_drive_file,
    ),
    (
        {
            "name": "create_drive_doc",
            "description": "Créer un nouveau Google Doc. 🟡 Confirmation légère.",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string", "description": "Titre du document"},
                "content": {"type": "string", "description": "Contenu texte du document"},
                "folder_id": {"type": "string", "description": "ID du dossier Drive (optionnel)"},
            }, "required": ["title"]},
        },
        _exec_create_drive_doc,
    ),
    (
        {
            "name": "update_drive_doc",
            "description": "Mettre à jour le contenu d'un Google Doc existant. 🟡 Confirmation légère.",
            "input_schema": {"type": "object", "properties": {
                "file_id": {"type": "string"},
                "content": {"type": "string", "description": "Nouveau contenu du document"},
            }, "required": ["file_id", "content"]},
        },
        _exec_update_drive_doc,
    ),
    # ── RECHERCHE / MÉTÉO / ACTUALITÉS ────────────────────────────────────
    (
        {
            "name": "search_web",
            "description": "Faire une recherche sur internet pour répondre à une question factuelle ou trouver des informations récentes.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            }, "required": ["query"]},
        },
        _exec_search_web,
    ),
    (
        {
            "name": "get_weather",
            "description": "Obtenir la météo actuelle et les prévisions du jour pour une ville.",
            "input_schema": {"type": "object", "properties": {
                "city": {"type": "string", "default": "Paris"},
            }},
        },
        _exec_get_weather,
    ),
    (
        {
            "name": "get_news",
            "description": "Obtenir les dernières actualités. Topics disponibles : france, international, tech, economie, sport, politique.",
            "input_schema": {"type": "object", "properties": {
                "topic": {"type": "string", "default": "france"},
                "max_results": {"type": "integer", "default": 5},
            }},
        },
        _exec_get_news,
    ),
    # ── NOTES ─────────────────────────────────────────────────────────────
    (
        {
            "name": "add_note",
            "description": "Enregistrer une note ou un mémo.",
            "input_schema": {"type": "object", "properties": {
                "content": {"type": "string"},
            }, "required": ["content"]},
        },
        _exec_add_note,
    ),
    (
        {
            "name": "list_notes",
            "description": "Lister toutes les notes.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_notes,
    ),
    (
        {
            "name": "delete_note",
            "description": "Supprimer une note.",
            "input_schema": {"type": "object", "properties": {
                "note_id": {"type": "integer"},
            }, "required": ["note_id"]},
        },
        _exec_delete_note,
    ),
    # ── TÂCHES ────────────────────────────────────────────────────────────
    (
        {
            "name": "add_task",
            "description": "Ajouter une tâche à la liste.",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string"},
                "due_date": {"type": "string", "description": "Ex: 2026-04-20"},
            }, "required": ["title"]},
        },
        _exec_add_task,
    ),
    (
        {
            "name": "list_tasks",
            "description": "Lister les tâches.",
            "input_schema": {"type": "object", "properties": {
                "include_done": {"type": "boolean", "default": False},
            }},
        },
        _exec_list_tasks,
    ),
    (
        {
            "name": "complete_task",
            "description": "Marquer une tâche comme terminée.",
            "input_schema": {"type": "object", "properties": {
                "task_id": {"type": "integer"},
            }, "required": ["task_id"]},
        },
        _exec_complete_task,
    ),
    (
        {
            "name": "delete_task",
            "description": "Supprimer une tâche.",
            "input_schema": {"type": "object", "properties": {
                "task_id": {"type": "integer"},
            }, "required": ["task_id"]},
        },
        _exec_delete_task,
    ),
    # ── DÉPENSES ──────────────────────────────────────────────────────────
    (
        {
            "name": "add_expense",
            "description": "Enregistrer une dépense.",
            "input_schema": {"type": "object", "properties": {
                "amount": {"type": "number", "description": "Montant en euros"},
                "category": {"type": "string", "description": "Ex: transport, repas, abonnement"},
                "description": {"type": "string"},
            }, "required": ["amount", "category"]},
        },
        _exec_add_expense,
    ),
    (
        {
            "name": "list_expenses",
            "description": "Lister les dépenses, optionnellement filtrées par mois (format: 2026-04).",
            "input_schema": {"type": "object", "properties": {
                "month": {"type": "string"},
            }},
        },
        _exec_list_expenses,
    ),
    (
        {
            "name": "expense_summary",
            "description": "Obtenir un résumé des dépenses par catégorie.",
            "input_schema": {"type": "object", "properties": {
                "month": {"type": "string", "description": "Ex: 2026-04 (optionnel, tous les mois si absent)"},
            }},
        },
        _exec_expense_summary,
    ),
    (
        {
            "name": "delete_expense",
            "description": "Supprimer une dépense.",
            "input_schema": {"type": "object", "properties": {
                "expense_id": {"type": "integer"},
            }, "required": ["expense_id"]},
        },
        _exec_delete_expense,
    ),
    (
        {
            "name": "export_expenses_to_drive",
            "description": "Exporter les dépenses dans un fichier Excel (.xlsx) et l'uploader sur Google Drive. Retourne le lien du fichier.",
            "input_schema": {"type": "object", "properties": {
                "month": {"type": "string", "description": "Mois au format 2026-04 (optionnel, toutes les dépenses si absent)"},
            }},
        },
        _exec_export_expenses,
    ),
    # ── APPLE NOTES ───────────────────────────────────────────────────────
    (
        {
            "name": "create_apple_note",
            "description": "Créer une note dans l'application Apple Notes (iCloud).",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "folder": {"type": "string", "default": "Notes", "description": "Dossier Apple Notes"},
            }, "required": ["title", "body"]},
        },
        _exec_create_apple_note,
    ),
    (
        {
            "name": "list_apple_notes",
            "description": "Lister les notes dans Apple Notes.",
            "input_schema": {"type": "object", "properties": {
                "folder": {"type": "string", "default": "Notes"},
                "max_results": {"type": "integer", "default": 10},
            }},
        },
        _exec_list_apple_notes,
    ),
    (
        {
            "name": "search_apple_notes",
            "description": "Rechercher des notes dans Apple Notes par mot-clé.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        },
        _exec_search_apple_notes,
    ),
    # ── APPELS TÉLÉPHONIQUES ──────────────────────────────────────────────
    (
        {
            "name": "make_phone_call",
            "description": "Passer un appel téléphonique IA via Bland.ai pour prendre un RDV, faire une réservation ou toute autre démarche. 🔴 Confirmation obligatoire. Décris la tâche en français naturel.",
            "input_schema": {"type": "object", "properties": {
                "phone_number": {"type": "string", "description": "Numéro au format international, ex: +33612345678"},
                "task": {"type": "string", "description": "Instructions pour l'IA : qui appeler, pourquoi, quoi demander (nom, date, heure, nb personnes...)"},
                "max_duration": {"type": "integer", "default": 5, "description": "Durée max en minutes"},
            }, "required": ["phone_number", "task"]},
        },
        _exec_make_phone_call,
    ),
    (
        {
            "name": "get_call_status",
            "description": "Obtenir le statut et la transcription d'un appel téléphonique passé.",
            "input_schema": {"type": "object", "properties": {
                "call_id": {"type": "string"},
            }, "required": ["call_id"]},
        },
        _exec_get_call_status,
    ),
    (
        {
            "name": "list_recent_calls",
            "description": "Lister les derniers appels téléphoniques passés via l'assistant.",
            "input_schema": {"type": "object", "properties": {
                "limit": {"type": "integer", "default": 5},
            }},
        },
        _exec_list_recent_calls,
    ),
    # ── RÉSERVATIONS EN LIGNE ─────────────────────────────────────────────
    (
        {
            "name": "reserve_opentable",
            "description": "Chercher un restaurant sur OpenTable et obtenir le lien de réservation directe.",
            "input_schema": {"type": "object", "properties": {
                "restaurant": {"type": "string", "description": "Nom du restaurant"},
                "city": {"type": "string"},
                "date": {"type": "string", "description": "Format YYYY-MM-DD"},
                "time": {"type": "string", "description": "Format HH:MM"},
                "guests": {"type": "integer", "default": 2},
            }, "required": ["restaurant", "city", "date", "time"]},
        },
        _exec_reserve_opentable,
    ),
    (
        {
            "name": "reserve_thefork",
            "description": "Chercher un restaurant sur TheFork et obtenir le lien de réservation.",
            "input_schema": {"type": "object", "properties": {
                "restaurant": {"type": "string"},
                "city": {"type": "string"},
                "date": {"type": "string", "description": "Format YYYY-MM-DD"},
                "time": {"type": "string", "description": "Format HH:MM"},
                "guests": {"type": "integer", "default": 2},
            }, "required": ["restaurant", "city", "date", "time"]},
        },
        _exec_reserve_thefork,
    ),
    (
        {
            "name": "find_phone_number",
            "description": "Trouver le numéro de téléphone d'un établissement (restaurant, médecin, salon...) pour pouvoir l'appeler.",
            "input_schema": {"type": "object", "properties": {
                "business_name": {"type": "string"},
                "city": {"type": "string"},
            }, "required": ["business_name", "city"]},
        },
        _exec_find_phone_number,
    ),
    # ── MÉMOIRE ───────────────────────────────────────────────────────────
    (
        {
            "name": "save_memory",
            "description": "Mémoriser une information importante sur l'utilisateur (prénom, préférences, habitudes, infos récurrentes...). Utilise cette fonction proactivement dès que tu apprends quelque chose d'utile à retenir.",
            "input_schema": {"type": "object", "properties": {
                "key": {"type": "string", "description": "Nom court de l'info (ex: 'prénom', 'ville', 'médecin', 'voiture')"},
                "value": {"type": "string", "description": "Valeur à mémoriser"},
            }, "required": ["key", "value"]},
        },
        _exec_save_memory,
    ),
    (
        {
            "name": "get_memory",
            "description": "Consulter tout ce qui a été mémorisé sur l'utilisateur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_get_memory,
    ),
    (
        {
            "name": "delete_memory",
            "description": "Effacer un souvenir spécifique.",
            "input_schema": {"type": "object", "properties": {
                "key": {"type": "string"},
            }, "required": ["key"]},
        },
        _exec_delete_memory,
    ),
    # ── RAPPELS ───────────────────────────────────────────────────────────
    (
        {
            "name": "set_reminder",
            "description": "Programmer un rappel Telegram à une date/heure précise.",
            "input_schema": {"type": "object", "properties": {
                "message": {"type": "string", "description": "Texte du rappel"},
                "remind_at": {"type": "string", "description": "ISO 8601, ex: 2026-04-13T09:00:00"},
            }, "required": ["message", "remind_at"]},
        },
        _exec_set_reminder,
    ),
    (
        {
            "name": "list_reminders",
            "description": "Lister les rappels programmés.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_reminders,
    ),
    (
        {
            "name": "cancel_reminder",
            "description": "Annuler un rappel.",
            "input_schema": {"type": "object", "properties": {
                "reminder_id": {"type": "integer"},
            }, "required": ["reminder_id"]},
        },
        _exec_cancel_reminder,
    ),
    # ── SUIVI DE RELANCE EMAIL ────────────────────────────────────────────
    (
        {
            "name": "track_followup",
            "description": (
                "Activer le suivi d'un email envoyé. Le bot vérifiera automatiquement "
                "si une réponse a été reçue et relancera l'utilisateur si pas de réponse "
                "après N jours. Utilise cet outil APRÈS chaque envoi d'email quand une "
                "réponse est attendue."
            ),
            "input_schema": {"type": "object", "properties": {
                "email_id": {"type": "string", "description": "ID de l'email envoyé"},
                "thread_id": {"type": "string", "description": "ID du thread Gmail"},
                "to": {"type": "string", "description": "Destinataire"},
                "subject": {"type": "string", "description": "Sujet de l'email"},
                "followup_days": {"type": "integer", "default": 3, "description": "Jours avant relance"},
            }, "required": ["email_id", "thread_id", "to", "subject"]},
        },
        _exec_track_followup,
    ),
    (
        {
            "name": "list_followups",
            "description": "Lister les emails en attente de réponse (suivi de relance actif).",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_followups,
    ),
    (
        {
            "name": "cancel_followup",
            "description": "Annuler le suivi d'un email.",
            "input_schema": {"type": "object", "properties": {
                "followup_id": {"type": "integer"},
            }, "required": ["followup_id"]},
        },
        _exec_cancel_followup,
    ),
    # ── AUTOMATIONS ───────────────────────────────────────────────────────
    (
        {
            "name": "add_automation",
            "description": (
                "Créer une automation planifiée qui s'exécute automatiquement. "
                "schedule format : 'daily:HH:MM' (ex: 'daily:08:00') "
                "ou 'weekly:DAY:HH:MM' (ex: 'weekly:monday:09:00'). "
                "DAY en anglais minuscule : monday, tuesday, wednesday, thursday, friday, saturday, sunday. "
                "instruction : texte complet à exécuter comme si l'utilisateur l'envoyait. "
                "condition (optionnel) : condition pour exécuter. Formats : "
                "'weather:KEYWORD:CITY' (ex: 'weather:pluie:Paris'), "
                "'tasks:overdue' (si tâches en retard), "
                "'emails:unread:>N' (si plus de N emails non lus). "
                "Sans condition, l'automation s'exécute toujours."
            ),
            "input_schema": {"type": "object", "properties": {
                "description": {"type": "string", "description": "Résumé court de l'automation"},
                "schedule": {"type": "string", "description": "Ex: 'daily:08:00' ou 'weekly:friday:18:00'"},
                "instruction": {"type": "string", "description": "Instruction complète à exécuter automatiquement"},
                "condition": {"type": "string", "description": "Condition optionnelle. Ex: 'weather:pluie:Paris', 'tasks:overdue', 'emails:unread:>5'"},
            }, "required": ["description", "schedule", "instruction"]},
        },
        _exec_add_automation,
    ),
    (
        {
            "name": "list_automations",
            "description": "Lister les automations planifiées.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_automations,
    ),
    (
        {
            "name": "delete_automation",
            "description": "Supprimer une automation planifiée.",
            "input_schema": {"type": "object", "properties": {
                "auto_id": {"type": "integer"},
            }, "required": ["auto_id"]},
        },
        _exec_delete_automation,
    ),
    # ── SURVEILLANCE WEB / PRIX ───────────────────────────────────────────
    (
        {
            "name": "add_web_monitor",
            "description": "Surveiller une page web. Notification si le contenu change (prix, disponibilité, annonce...). Intervalle en minutes.",
            "input_schema": {"type": "object", "properties": {
                "url": {"type": "string", "description": "URL de la page à surveiller"},
                "description": {"type": "string", "description": "Ce qu'on surveille (ex: 'prix du vol Paris-NYC')"},
                "css_selector": {"type": "string", "description": "Sélecteur CSS optionnel pour cibler une partie de la page"},
                "interval_minutes": {"type": "integer", "default": 60, "description": "Intervalle de vérification en minutes"},
            }, "required": ["url", "description"]},
        },
        _exec_add_web_monitor,
    ),
    (
        {
            "name": "list_web_monitors",
            "description": "Lister les pages web surveillées.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_web_monitors,
    ),
    (
        {
            "name": "delete_web_monitor",
            "description": "Arrêter la surveillance d'une page web.",
            "input_schema": {"type": "object", "properties": {
                "monitor_id": {"type": "integer"},
            }, "required": ["monitor_id"]},
        },
        _exec_delete_web_monitor,
    ),
    (
        {
            "name": "check_web_page",
            "description": "Vérifier le contenu actuel d'une page web (one-shot, sans surveillance continue).",
            "input_schema": {"type": "object", "properties": {
                "url": {"type": "string"},
                "css_selector": {"type": "string", "description": "Sélecteur CSS optionnel"},
            }, "required": ["url"]},
        },
        _exec_check_web_page,
    ),
    # ── RÉSUMÉ DE LIENS / ARTICLES ────────────────────────────────────────
    (
        {
            "name": "summarize_url",
            "description": "Extraire et résumer le contenu d'un lien web / article. Envoie un lien → le bot scrape et analyse le contenu.",
            "input_schema": {"type": "object", "properties": {
                "url": {"type": "string", "description": "URL de l'article ou de la page"},
            }, "required": ["url"]},
        },
        _exec_summarize_url,
    ),
    # ── SMS / WHATSAPP ────────────────────────────────────────────────────
    (
        {
            "name": "send_sms",
            "description": "Envoyer un SMS via Twilio. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "to": {"type": "string", "description": "Numéro au format international, ex: +33612345678"},
                "body": {"type": "string", "description": "Contenu du SMS"},
            }, "required": ["to", "body"]},
        },
        _exec_send_sms,
    ),
    (
        {
            "name": "send_whatsapp",
            "description": "Envoyer un message WhatsApp via Twilio. 🔴 Confirmation obligatoire.",
            "input_schema": {"type": "object", "properties": {
                "to": {"type": "string", "description": "Numéro au format international"},
                "body": {"type": "string", "description": "Contenu du message"},
            }, "required": ["to", "body"]},
        },
        _exec_send_whatsapp,
    ),
    # ── GITHUB ────────────────────────────────────────────────────────────
    (
        {
            "name": "github_repo_status",
            "description": "Voir le statut d'un repo GitHub : PRs ouvertes, issues, dernière CI.",
            "input_schema": {"type": "object", "properties": {
                "owner": {"type": "string", "description": "Propriétaire du repo (ex: 'anthropics')"},
                "repo": {"type": "string", "description": "Nom du repo (ex: 'claude-code')"},
            }, "required": ["owner", "repo"]},
        },
        _exec_github_repo_status,
    ),
    (
        {
            "name": "github_notifications",
            "description": "Lister les notifications GitHub non lues.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_github_notifications,
    ),
    (
        {
            "name": "add_github_repo",
            "description": "Ajouter un repo GitHub à la surveillance continue. Notification si nouvelles PRs, issues ou CI cassé.",
            "input_schema": {"type": "object", "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            }, "required": ["owner", "repo"]},
        },
        _exec_add_github_repo,
    ),
    (
        {
            "name": "list_github_repos",
            "description": "Lister les repos GitHub surveillés.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_list_github_repos,
    ),
    (
        {
            "name": "delete_github_repo",
            "description": "Retirer un repo de la surveillance GitHub.",
            "input_schema": {"type": "object", "properties": {
                "repo_id": {"type": "integer"},
            }, "required": ["repo_id"]},
        },
        _exec_delete_github_repo,
    ),
    # ── BUDGET ────────────────────────────────────────────────────────────
    (
        {
            "name": "set_budget",
            "description": "Définir un budget mensuel pour une catégorie de dépenses. Alerte automatique à 80% et 100%.",
            "input_schema": {"type": "object", "properties": {
                "category": {"type": "string", "description": "Catégorie de dépense (ex: 'transport', 'repas')"},
                "amount": {"type": "number", "description": "Montant du budget en euros"},
                "month": {"type": "string", "description": "Mois spécifique (ex: '2026-04') ou vide pour récurrent"},
            }, "required": ["category", "amount"]},
        },
        _exec_set_budget,
    ),
    (
        {
            "name": "get_budgets",
            "description": "Voir tous les budgets définis.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_get_budgets,
    ),
    (
        {
            "name": "delete_budget",
            "description": "Supprimer un budget.",
            "input_schema": {"type": "object", "properties": {
                "category": {"type": "string"},
                "month": {"type": "string"},
            }, "required": ["category"]},
        },
        _exec_delete_budget,
    ),
    (
        {
            "name": "check_budget_alerts",
            "description": "Vérifier si des budgets sont proches d'être dépassés (>80%).",
            "input_schema": {"type": "object", "properties": {
                "month": {"type": "string", "description": "Mois (ex: '2026-04'), par défaut mois courant"},
            }},
        },
        _exec_check_budget_alerts,
    ),
    # ── GÉNÉRATION DE DOCUMENTS ───────────────────────────────────────────
    (
        {
            "name": "generate_document",
            "description": "Générer un document (lettre, devis, contrat, compte-rendu...) et le sauvegarder sur Google Drive. Rédige le contenu complet puis crée le Google Doc. 🟡 Confirmation légère.",
            "input_schema": {"type": "object", "properties": {
                "title": {"type": "string", "description": "Titre du document"},
                "content": {"type": "string", "description": "Contenu complet du document"},
                "folder_id": {"type": "string", "description": "ID du dossier Drive (optionnel)"},
            }, "required": ["title", "content"]},
        },
        _exec_generate_document,
    ),
    # ── MAPS & TRAJETS (OpenStreetMap, gratuit) ───────────────────────────
    (
        {
            "name": "geocode_address",
            "description": "Convertir une adresse en coordonnées GPS (latitude/longitude). Utile pour valider une adresse ou obtenir sa localisation précise.",
            "input_schema": {"type": "object", "properties": {
                "address": {"type": "string", "description": "Adresse à géolocaliser (ex: '15 rue de Rivoli Paris')"},
            }, "required": ["address"]},
        },
        _exec_geocode_address,
    ),
    (
        {
            "name": "travel_time",
            "description": "Calculer le temps de trajet et la distance entre deux adresses. Modes : driving (voiture), walking (à pied), cycling (vélo).",
            "input_schema": {"type": "object", "properties": {
                "origin": {"type": "string", "description": "Adresse de départ"},
                "destination": {"type": "string", "description": "Adresse d'arrivée"},
                "mode": {"type": "string", "enum": ["driving", "walking", "cycling"], "default": "driving"},
            }, "required": ["origin", "destination"]},
        },
        _exec_travel_time,
    ),
    (
        {
            "name": "get_directions",
            "description": "Obtenir un itinéraire détaillé étape par étape entre deux adresses, avec un lien vers la carte OpenStreetMap.",
            "input_schema": {"type": "object", "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "mode": {"type": "string", "enum": ["driving", "walking", "cycling"], "default": "driving"},
            }, "required": ["origin", "destination"]},
        },
        _exec_get_directions,
    ),
    (
        {
            "name": "when_to_leave",
            "description": "Calculer l'heure de départ optimale pour arriver à l'heure à un RDV. Prend en compte le temps de trajet + un buffer de sécurité. Utilise l'adresse mémorisée de l'utilisateur comme origine par défaut si elle existe (consulte get_memory).",
            "input_schema": {"type": "object", "properties": {
                "destination": {"type": "string", "description": "Adresse d'arrivée"},
                "arrival_time_iso": {"type": "string", "description": "Heure d'arrivée voulue (ISO 8601)"},
                "origin": {"type": "string", "description": "Adresse de départ (obligatoire)"},
                "mode": {"type": "string", "enum": ["driving", "walking", "cycling"], "default": "driving"},
                "buffer_minutes": {"type": "integer", "default": 10, "description": "Marge de sécurité en minutes"},
            }, "required": ["destination", "arrival_time_iso", "origin"]},
        },
        _exec_when_to_leave,
    ),
    # ── RAG MÉMOIRE SÉMANTIQUE ────────────────────────────────────────────
    (
        {
            "name": "search_memory",
            "description": (
                "Recherche sémantique dans TOUT l'historique (conversations passées, notes, mémoire). "
                "Utilise cet outil QUAND l'utilisateur fait référence au passé : "
                "'qu'est-ce qu'on a dit sur...', 'quand j'ai parlé de...', 'rappelle-toi ce que...'. "
                "Retourne les passages les plus pertinents avec leur score de similarité."
            ),
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Question ou sujet à chercher en langage naturel"},
                "top_k": {"type": "integer", "default": 5, "description": "Nombre de résultats"},
                "source_filter": {"type": "string", "description": "Filtrer par source (ex: 'note', 'memory_kv', 'conversation_user')"},
            }, "required": ["query"]},
        },
        _exec_search_memory,
    ),
    (
        {
            "name": "rag_stats",
            "description": "Voir les statistiques de la mémoire sémantique (nombre de chunks indexés).",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_rag_stats,
    ),
    (
        {
            "name": "index_recent_content",
            "description": "Forcer la réindexation des conversations, notes et mémoire dans le RAG. Normalement fait automatiquement en background.",
            "input_schema": {"type": "object", "properties": {}},
        },
        _exec_index_recent_content,
    ),
]


# -- Construire les structures utilisées par le reste du code -----------------

# Filtrer les outils Apple Notes si désactivés (défaut) ou si pas sur macOS
_APPLE_NOTES_TOOLS = {"create_apple_note", "list_apple_notes", "search_apple_notes"}
if not _APPLE_NOTES_ENABLED:
    TOOL_DEFS = [td for td in TOOL_DEFS if td[0]["name"] not in _APPLE_NOTES_TOOLS]

TOOLS = [schema for schema, _ in TOOL_DEFS]

_DISPATCH: dict[str, callable] = {schema["name"]: executor for schema, executor in TOOL_DEFS}


def execute_tool(name: str, input_data: dict, user_id: int = None) -> str:
    executor = _DISPATCH.get(name)
    if not executor:
        return f"Outil inconnu : {name}"
    try:
        if name in _USER_ID_TOOLS:
            if user_id is None:
                return f"Impossible d'exécuter {name} : user_id manquant."
            return executor(user_id, **input_data)
        return executor(**input_data)
    except Exception as e:
        return f"Erreur lors de l'exécution de {name} : {str(e)}"
