import asyncio
import base64
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage
from config import client, conversations, is_allowed, logger, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, BOT_NAME, USER_NAME
from prompt import SYSTEM_PROMPT
from tools_registry import TOOLS, execute_tool, _to_json

# Regex pour détecter les préfixes "Human:" / "Assistant:" que le modèle
# peut générer à tort en mode text-completion legacy. Empêche tout
# feedback loop qui corromprait l'historique.
_RE_HUMAN_PREFIX = re.compile(r'^\s*(Human|Assistant)\s*:\s*', re.IGNORECASE)
_RE_HUMAN_INLINE = re.compile(r'\n\s*(Human|Assistant)\s*:\s*')


def _sanitize_assistant_content(content):
    """Retire les préfixes Human:/Assistant: que le LLM ne devrait pas produire."""
    if not isinstance(content, list):
        return content
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            text = block.get('text', '')
            text = _RE_HUMAN_PREFIX.sub('', text)
            text = _RE_HUMAN_INLINE.sub('\n', text)
            block['text'] = text
    return content

# Verrous asyncio pour éviter les race conditions quand plusieurs messages
# arrivent simultanément pour un même utilisateur.
_user_locks: dict[int, asyncio.Lock] = {}


def _get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


def _build_system_blocks() -> list:
    """
    Construit le system prompt en 2 blocs pour profiter du prompt caching
    Le gros bloc statique (règles, capacités, workflows) est mis en cache,
    seul le petit bloc dynamique (date + mémoire) change.
    Économie de coût : ~10x sur les tokens système.
    """
    memory_text = storage.format_memory_for_prompt()
    fallback = "Rien de mémorisé pour l'instant."
    dynamic = (
        f"Date et heure actuelles : {datetime.now().strftime('%A %d %B %Y à %H:%M')}\n"
        f"Ce que tu sais sur l'utilisateur :\n"
        f"{memory_text if memory_text else fallback}"
    )
    # On enlève les placeholders {datetime} et {memory} du prompt statique
    # et on mord un tag de séparation pour que le statique soit réellement stable.
    static = SYSTEM_PROMPT.replace(
        "Date et heure actuelles : {datetime}", ""
    ).replace(
        "Ce que tu sais sur l'utilisateur :\n{memory}", ""
    ).replace(
        "{bot_name}", BOT_NAME
    ).replace(
        "{user_name}", USER_NAME
    )
    return [
        {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic},
    ]


# Patterns qui indiquent que le LLM n'a rien de vraiment utile à dire.
# Quand on tourne en contexte "job background" (scan, brief conditionnel),
# on ne spam pas l'utilisateur avec ça.
_RE_NOTHING_TO_REPORT = re.compile(
    r"^\s*("
    r"silent"
    r"|none"
    r"|rien[\s\w'àéèê]*signaler"
    r"|rien[\s\w'àéèê]*important"
    r"|rien[\s\w'àéèê]*nouveau"
    r"|rien[\s\w'àéèê]*particulier"
    r"|rien[\s\w'àéèê]*\.?$"
    r"|ras[\s\.]*$"
    r"|aucune?[\s\w'àéèê]*action"
    r"|aucune?[\s\w'àéèê]*alerte"
    r"|aucune?[\s\w'àéèê]*notification"
    r"|aucune?[\s\w'àéèê]*email[\s\w'àéèê]*important"
    r"|tout[\s\w'àéèê]*en ordre"
    r"|tout[\s\w'àéèê]*calme"
    r")[\s\.\!\,]*$",
    re.IGNORECASE,
)


def _is_silent_response(text: str) -> bool:
    """Détecte si la réponse du LLM est 'rien à signaler' sous une forme ou une autre."""
    if not text or len(text.strip()) < 4:
        return True
    stripped = text.strip()
    # Réponse très courte et sans contenu informatif
    if len(stripped) < 80 and _RE_NOTHING_TO_REPORT.match(stripped):
        return True
    return False


async def _run_claude(user_id: int, bot, chat_id: int, silent_if_nothing: bool = False):
    """
    silent_if_nothing=True : si le LLM répond 'rien à signaler' (ou équivalent),
    on n'envoie RIEN à l'utilisateur. Utile pour les jobs background.
    """
    lock = _get_user_lock(user_id)
    async with lock:
        try:
            await _run_claude_inner(user_id, bot, chat_id, silent_if_nothing)
        except Exception as e:
            logger.error(f"Erreur _run_claude user={user_id}: {e}", exc_info=True)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Oups, j'ai rencontré une erreur : `{str(e)[:200]}`\nRéessaie ou utilise /clear si ça persiste.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


async def _run_claude_inner(user_id: int, bot, chat_id: int, silent_if_nothing: bool = False):
    system_blocks = _build_system_blocks()
    while True:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        response = await asyncio.to_thread(
            client.messages.create,
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_blocks,
            tools=TOOLS,
            messages=conversations[user_id],
        )
        assistant_content = _sanitize_assistant_content(_to_json(response.content))
        conversations[user_id].append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            # Sécurité : ne jamais envoyer un message avec préfixe "Human:"
            text = _RE_HUMAN_PREFIX.sub('', text)
            text = _RE_HUMAN_INLINE.sub('\n', text)
            # En mode job background : ne pas spammer l'utilisateur avec
            # des "rien à signaler" / "RAS" / "SILENT".
            if silent_if_nothing and _is_silent_response(text):
                logger.info(f"[job] Réponse silencieuse filtrée (user={user_id}): {text[:80]!r}")
                break
            if text:
                for i in range(0, len(text), 4000):
                    await bot.send_message(chat_id=chat_id, text=text[i:i + 4000])
            break
        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    await bot.send_chat_action(chat_id=chat_id, action="typing")
                    result = await asyncio.to_thread(execute_tool, block.name, block.input, user_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            conversations[user_id].append({"role": "user", "content": tool_results})
        else:
            break

    # Tronquer à 20 messages max, en s'assurant de commencer par un message user texte
    msgs = conversations[user_id]
    if len(msgs) > 20:
        msgs = msgs[-20:]
        for i, m in enumerate(msgs):
            if m["role"] == "user" and isinstance(m["content"], str):
                msgs = msgs[i:]
                break
        conversations[user_id] = msgs
    storage.save_conversation(user_id, conversations[user_id])


# -- Handlers messages --------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    if user_id not in conversations:
        conversations[user_id] = storage.load_conversation(user_id)
    conversations[user_id].append({"role": "user", "content": update.message.text})
    await _run_claude(user_id, context.bot, update.effective_chat.id)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from features.voice import transcribe_voice
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)
    audio_bytes = bytes(await file.download_as_bytearray())
    text = transcribe_voice(audio_bytes, suffix=".ogg")

    await update.message.reply_text(f"🎤 _{text}_", parse_mode="Markdown")

    if user_id not in conversations:
        conversations[user_id] = storage.load_conversation(user_id)
    conversations[user_id].append({"role": "user", "content": text})
    await _run_claude(user_id, context.bot, update.effective_chat.id)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from features.voice import extract_pdf_text
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    doc = update.message.document

    if not doc.mime_type or "pdf" not in doc.mime_type:
        await update.message.reply_text("Je ne sais lire que les fichiers PDF pour l'instant.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    file = await context.bot.get_file(doc.file_id)
    pdf_bytes = bytes(await file.download_as_bytearray())
    text = extract_pdf_text(pdf_bytes)

    if user_id not in conversations:
        conversations[user_id] = storage.load_conversation(user_id)
    conversations[user_id].append({
        "role": "user",
        "content": f"Voici le contenu d'un PDF intitulé '{doc.file_name}'. Résume-le de façon claire et concise :\n\n{text}"
    })
    await _run_claude(user_id, context.bot, update.effective_chat.id)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyse une image envoyée (reçu, carte de visite, screenshot...) via le LLM multimodal."""
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Prendre la meilleure résolution
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = bytes(await file.download_as_bytearray())
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

    caption = update.message.caption or ""
    prompt = caption if caption else (
        "Analyse cette image. Si c'est un reçu/ticket/facture, extrais le montant et la catégorie. "
        "Si c'est une carte de visite, extrais les coordonnées. "
        "Si c'est un screenshot, décris ce que tu vois et propose des actions pertinentes. "
        "Sois concis."
    )

    if user_id not in conversations:
        conversations[user_id] = storage.load_conversation(user_id)
    conversations[user_id].append({
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": prompt},
        ]
    })
    await _run_claude(user_id, context.bot, update.effective_chat.id)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les clics sur les boutons inline (confirmations)."""
    query = update.callback_query
    await query.answer()
    data = query.data  # format: "confirm:xxx" ou "cancel:xxx"

    if data.startswith("confirm:"):
        # L'utilisateur confirme → injecter "oui" dans la conversation
        user_id = query.from_user.id
        if user_id not in conversations:
            conversations[user_id] = storage.load_conversation(user_id)
        conversations[user_id].append({"role": "user", "content": "oui, vas-y"})
        await query.edit_message_reply_markup(reply_markup=None)
        await _run_claude(user_id, context.bot, query.message.chat_id)
    elif data.startswith("cancel:"):
        await query.edit_message_text("❌ Action annulée.")


# -- Commandes ----------------------------------------------------------------

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    conversations[user_id] = []
    storage.register_brief_user(user_id)
    await update.message.reply_text(
        f"👋 Bonjour ! Je suis **{BOT_NAME}**, ton assistant personnel et secrétaire.\n\n"
        "📧 Emails — lire, envoyer, archiver, brouillons, alertes, templates\n"
        "📅 Calendrier — voir, créer, modifier, supprimer\n"
        "👤 Contacts — chercher dans Google Contacts\n"
        "📁 Drive — chercher et lire des fichiers\n"
        "🔍 Recherche web en temps réel\n"
        "🌤️ Météo & 📰 Actualités\n"
        "📝 Notes & ✅ Tâches\n"
        "💶 Suivi des dépenses\n"
        "⏰ Rappels Telegram\n"
        "🎤 Messages vocaux (transcription automatique)\n"
        "📄 Résumé de PDF\n\n"
        "/brief /tasks /notes /depenses /help"
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Accès non autorisé.")
        return
    await update.message.reply_text(
        "🤖 *Assistant Personnel — Aide*\n\n"
        "*Email*\n"
        "• \"Montre mes emails non lus\"\n"
        "• \"Envoie un email à marie@example.com\"\n"
        "• \"Archive l'email #2\" / \"Crée un brouillon\"\n"
        "• \"Active réponse automatique jusqu'au 20 avril\"\n"
        "• \"Alerte si email de boss@example.com\"\n\n"
        "*Calendrier*\n"
        "• \"Mes RDV cette semaine ?\"\n"
        "• \"Crée réunion lundi 14h-15h à Paris\"\n\n"
        "*Contacts & Drive*\n"
        "• \"Cherche le contact Jean Dupont\"\n"
        "• \"Cherche dans mon Drive : rapport 2026\"\n\n"
        "*Recherche / Météo / Actu*\n"
        "• \"Météo à Lyon demain\"\n"
        "• \"Actualités tech\"\n"
        "• \"Cherche sur internet : prix train Paris-Lyon\"\n\n"
        "*Notes & Tâches*\n"
        "• \"Note : WiFi bureau = monreseau123\"\n"
        "• \"Tâche : appeler médecin avant vendredi\"\n\n"
        "*Dépenses*\n"
        "• \"J'ai dépensé 12€ pour un café\"\n"
        "• \"Résumé dépenses avril\"\n\n"
        "*Rappels*\n"
        "• \"Rappelle-moi dans 2h de rappeler Jean\"\n\n"
        "*Commandes*\n"
        "/brief /tasks /notes /depenses /clear /help",
        parse_mode="Markdown"
    )


async def handle_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    if user_id not in conversations:
        conversations[user_id] = storage.load_conversation(user_id)
    conversations[user_id].append({
        "role": "user",
        "content": (
            "Fais-moi un brief complet : emails non lus importants (max 5) avec résumé, "
            "événements du calendrier aujourd'hui et demain, météo à Paris, "
            "et rappelle-moi les tâches urgentes ou en retard si il y en a."
        )
    })
    await _run_claude(user_id, context.bot, update.effective_chat.id)


async def handle_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Accès non autorisé.")
        return
    tasks = storage.list_tasks(include_done=False)
    if not tasks:
        await update.message.reply_text("✅ Aucune tâche en cours !")
        return
    lines = ["📋 *Tâches en cours :*\n"]
    for t in tasks:
        due = f" — _{t['due_date']}_" if t.get("due_date") else ""
        lines.append(f"• #{t['id']} {t['title']}{due}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Accès non autorisé.")
        return
    notes = storage.list_notes()
    if not notes:
        await update.message.reply_text("📝 Aucune note enregistrée.")
        return
    lines = ["📝 *Notes :*\n"]
    for n in notes:
        lines.append(f"• #{n['id']} {n['content']} _({n['created_at']})_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_depenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Accès non autorisé.")
        return
    month = datetime.now().strftime("%Y-%m")
    summary = storage.expense_summary(month)
    if not summary["nb_depenses"]:
        await update.message.reply_text(f"💶 Aucune dépense enregistrée pour {month}.")
        return
    lines = [f"💶 *Dépenses {month} — Total : {summary['total']}€*\n"]
    for cat, total in sorted(summary["par_categorie"].items(), key=lambda x: -x[1]):
        lines.append(f"• {cat} : {total}€")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("Accès non autorisé.")
        return
    conversations[user_id] = []
    storage.save_conversation(user_id, [])
    await update.message.reply_text("🗑️ Historique effacé.")
