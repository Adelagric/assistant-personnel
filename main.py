import atexit
import os
import subprocess
import sys
from datetime import time

import pytz
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

from config import logger
from handlers import (
    handle_start, handle_help, handle_brief,
    handle_tasks, handle_notes, handle_depenses, handle_clear,
    handle_message, handle_voice, handle_document, handle_photo,
    handle_callback,
)
from jobs import (
    send_daily_brief, check_reminders, check_email_alerts,
    check_automations, check_followups, prepare_meetings,
    smart_email_scan, analyze_habits,
    check_web_monitors, post_meeting_followup,
    check_budget_alerts_job, check_github_repos,
    reindex_rag,
)


def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN manquant dans le fichier .env")

    app = Application.builder().token(token).build()

    # -- Commandes --
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("brief", handle_brief))
    app.add_handler(CommandHandler("tasks", handle_tasks))
    app.add_handler(CommandHandler("notes", handle_notes))
    app.add_handler(CommandHandler("depenses", handle_depenses))
    app.add_handler(CommandHandler("clear", handle_clear))

    # -- Messages --
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # -- Jobs planifiés --
    jq = app.job_queue
    if jq:
        paris = pytz.timezone("Europe/Paris")
        # Brief quotidien
        jq.run_daily(send_daily_brief, time=time(8, 0, tzinfo=paris), name="brief_matinal")
        # Checks fréquents (toutes les minutes)
        jq.run_repeating(check_reminders, interval=60, first=10, name="check_reminders")
        jq.run_repeating(check_email_alerts, interval=60, first=30, name="email_alerts")
        jq.run_repeating(check_automations, interval=60, first=15, name="check_automations")
        # Checks modérés (toutes les 5-30 min)
        jq.run_repeating(prepare_meetings, interval=300, first=60, name="prepare_meetings")
        jq.run_repeating(post_meeting_followup, interval=300, first=120, name="post_meeting_followup")
        jq.run_repeating(check_web_monitors, interval=300, first=90, name="check_web_monitors")
        jq.run_repeating(smart_email_scan, interval=1800, first=90, name="smart_email_scan")
        # Checks horaires
        jq.run_repeating(check_followups, interval=3600, first=120, name="check_followups")
        jq.run_repeating(check_github_repos, interval=3600, first=180, name="check_github_repos")
        jq.run_repeating(reindex_rag, interval=3600, first=240, name="reindex_rag")
        # Checks quotidiens
        jq.run_daily(check_budget_alerts_job, time=time(20, 0, tzinfo=paris), name="budget_alerts")
        jq.run_daily(analyze_habits, time=time(20, 0, tzinfo=paris), days=(6,), name="analyze_habits")

    logger.info("✅ Assistant personnel démarré.")
    app.run_polling()


if __name__ == "__main__":
    if sys.platform == "darwin":
        _caffeinate = subprocess.Popen(["caffeinate", "-i"])
        atexit.register(_caffeinate.terminate)
    main()
