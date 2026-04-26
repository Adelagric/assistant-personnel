# 🤖 Assistant Personnel IA sur Telegram

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Adelagric/assistant-personnel/pulls)
[![Last commit](https://img.shields.io/github/last-commit/Adelagric/assistant-personnel)](https://github.com/Adelagric/assistant-personnel/commits/main)

> Un assistant personnel francophone propulsé par un grand modèle de langage, avec ~87 outils intégrés à Gmail, Google Calendar, Drive, Contacts, un RAG sémantique local, des automations conditionnelles, et une architecture modulaire prête pour l'extension.

**Projet personnel open source — MIT License.** Forkez, adaptez, contribuez.

---

## ✨ Qu'est-ce que ça fait ?

Un vrai assistant personnel que vous pilotez depuis Telegram (texte, vocal, image, PDF). Il vous connaît (mémoire persistante), anticipe (brief matinal, prépa réunion), et exécute (envoyer un email, créer un événement, passer un appel téléphonique IA).

**Exemples de conversations réelles :**

```
Toi : « Envoie un mail à Marie pour décaler notre réunion de jeudi à vendredi 14h »
→ Le bot rédige, te montre le brouillon, envoie après confirmation, active
  le suivi de relance automatique si pas de réponse dans 3 jours.

Toi : [photo d'un ticket de caisse]
→ Extrait le montant et la catégorie, crée la dépense, archive le ticket.

Toi : « Qu'est-ce qu'on s'était dit avec Jean à propos du projet X ? »
→ Recherche sémantique dans tout ton historique, retrouve la conversation,
  résume les points clés.

[8h du matin, automatique]
→ Brief : 5 emails non lus importants résumés, tes RDV du jour, la météo,
  2 tâches en retard.
```

---

## 🧰 Les 87 outils intégrés

<details>
<summary><b>📧 Email — 18 outils</b></summary>

Lister, lire (+ pièces jointes), envoyer, répondre, brouillon, archiver, corbeille, suppression en masse, marquer lu/non-lu, réponse automatique d'absence, templates réutilisables, alertes par expéditeur/mot-clé, **suivi de relance** (alerte si pas de réponse après N jours).
</details>

<details>
<summary><b>📅 Calendrier Google — 6 outils</b></summary>

Liste des calendriers, événements (CRUD), multi-calendriers, préparation automatique 30 min avant chaque réunion, compte-rendu post-réunion auto-généré sur Drive.
</details>

<details>
<summary><b>👤 Contacts & 📁 Drive — 6 outils</b></summary>

Recherche dans Google Contacts, recherche et lecture dans Drive, création/mise à jour de Google Docs, **export automatique des dépenses en Excel stylisé sur Drive**.
</details>

<details>
<summary><b>🗺️ Maps & trajets (OpenStreetMap, gratuit) — 4 outils</b></summary>

Géocodage, temps de trajet (voiture/vélo/piéton), itinéraires détaillés, **« à quelle heure je dois partir pour être à X à Y » en tenant compte du buffer de sécurité**.
</details>

<details>
<summary><b>🧠 Mémoire sémantique (RAG local) — 3 outils</b></summary>

ChromaDB + sentence-transformers multilingue, 100% local, zéro API. Indexation automatique des conversations, notes, et mémoire clé-valeur. Recherche par sens (pas par mots-clés).
</details>

<details>
<summary><b>🔍 Web, 🌤️ Météo, 📰 News — 4 outils</b></summary>

Recherche web via DuckDuckGo, scrape et résumé d'articles, météo wttr.in, flux RSS thématiques.
</details>

<details>
<summary><b>📝 Notes, ✅ Tâches, 💶 Dépenses, ⏰ Rappels — 17 outils</b></summary>

Gestion complète + **budgets mensuels par catégorie** avec alertes à 80% et 100%, rappels programmés au format ISO.
</details>

<details>
<summary><b>🤖 Automations conditionnelles — 3 outils</b></summary>

Tâches récurrentes (`daily:08:00`, `weekly:friday:18:00`) avec **conditions** : `weather:pluie:Paris`, `tasks:overdue`, `emails:unread:>5`. L'automation ne s'exécute que si la condition est remplie.
</details>

<details>
<summary><b>☎️ Appels téléphoniques IA — 3 outils (optionnel)</b></summary>

Le bot **passe de vrais appels téléphoniques** pilotés par IA pour prendre un RDV, faire une réservation, vérifier une info. Transcription fournie après l'appel.
</details>

<details>
<summary><b>📱 SMS/WhatsApp, 🐙 GitHub, 🔄 Surveillance web — 10 outils (optionnels)</b></summary>

SMS/WhatsApp via Twilio, statut de repos GitHub (PRs, issues, CI), surveillance de pages web avec détection de changements (prix, dispo, annonces).
</details>

<details>
<summary><b>📸 Vision, 🎤 Voice, 📄 PDF (inputs multimodaux)</b></summary>

Analyse d'images via vision multimodale (reçu → dépense, carte de visite → contact), transcription vocale via Whisper, résumé de PDF uploadé dans Telegram.
</details>

---

## 🏗️ Architecture

```
├── main.py              # Point d'entrée minimal
├── config.py            # Clients API, logging, état global
├── prompt.py            # SYSTEM_PROMPT (paramétré via .env)
├── tools_registry.py    # 87 outils : schémas + dispatch dict (source unique de vérité)
├── handlers.py          # Handlers Telegram + boucle d'exécution agent
├── jobs.py              # 13 jobs background
├── tools.py             # Wrappers Google API
├── storage.py           # Persistance JSON avec FileLock
├── features/            # Modules annexes (RAG, Maps, Twilio, GitHub, etc.)
└── deploy/              # Kit de déploiement VPS (Hetzner + systemd + backup)
```

**Design patterns clés :**

- **Registre d'outils centralisé** : chaque outil est une paire `(schema, executor)` dans `TOOL_DEFS`. Ajouter un outil = une entrée à un endroit (pas 3 comme dans la plupart des projets LLM).
- **Prompt caching** : ~8700 chars de prompt statique mis en cache → ~90% d'économie sur les tokens système.
- **Delta-indexing RAG** : le job de réindexation horaire ne réencode QUE les nouveaux documents (déduplication par hash de contenu).
- **Asyncio.Lock par user** : empêche les race conditions si plusieurs messages arrivent en parallèle.
- **FileLock sur `data.json`** : 13 jobs background écrivent, aucune perte de données.
- **Mode silencieux pour jobs** : sanitization anti-spam — l'agent répond `SILENT` quand il n'a rien à dire, le bot ne notifie pas l'utilisateur.
- **Fallback gracieux** : un try/except global garantit que le bot ne reste jamais muet, même sur timeout réseau.

---

## 🚀 Installation rapide

**Pré-requis :** Python 3.12, un compte Google Cloud, un bot Telegram créé via [@BotFather](https://t.me/BotFather), et une clé API LLM.

```bash
# 1. Clone
git clone https://github.com/TON_USER/assistant-personnel.git
cd assistant-personnel

# 2. Venv + deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Édite .env avec tes clés API

# 4. Google OAuth (première connexion)
# Place ton credentials.json (depuis Google Cloud Console) à la racine
# Active : Gmail API, Calendar API, People API, Drive API
python3 -c "from auth import get_credentials; get_credentials()"
# → ouvre le navigateur pour autoriser l'accès

# 5. Lance le bot
python3 main.py
```

---

## 🖥️ Déploiement VPS

Un kit complet est fourni dans `deploy/` :

- `01_setup_vps.sh` : hardening initial (SSH, UFW, fail2ban, unattended-upgrades, swap)
- `02_install_bot.sh` : installation + venv + systemd + logrotate
- `assistant-personnel.service` : unit systemd avec restart auto et hardening
- `backup.sh` : backup quotidien (data.json + RAG) vers Backblaze B2 avec chiffrement GPG
- `README.md` : guide step-by-step

**Coût estimé :** ~4,50 €/mois (Hetzner CX22 + B2 backups).

---

## 🎯 Ce que ce projet illustre techniquement

- **Agents LLM avec tool use** : 87 outils, chaînages complexes, confirmations multi-niveaux (🟢 autonome / 🟡 confirmation légère / 🔴 confirmation obligatoire).
- **RAG local à coût zéro** : sentence-transformers multilingue + ChromaDB.
- **Intégrations Google Workspace** : Gmail (History API pour le polling efficient), Calendar, Drive, Contacts, People API.
- **Prompt engineering** : 3 niveaux d'autonomie, mode silencieux pour jobs, parsing de dates en langage naturel, multi-langue auto pour les emails.
- **Concurrence asyncio** : locks par utilisateur, jobs background avec retry exponentiel, asyncio.to_thread pour ne pas bloquer l'event loop avec les appels sync des SDK Google.
- **Robustesse production** : FileLock sur les écritures JSON, sanitization défensive, logrotate, systemd, backup chiffré.
- **Prompt caching** : division du coût par 10 sur les tokens système.

---

## ⚠️ Limitations connues & axes d'amélioration

- **Mono-utilisateur de fait** : la whitelist `ALLOWED_USER_IDS` permet plusieurs users, mais les données (notes, tâches, dépenses) sont partagées globalement. Pour un vrai multi-tenant, il faut refactor.
- **Stockage JSON flat** : parfait pour un usage perso, à migrer vers SQLite au-delà de ~10MB.
- **Pas de tests unitaires** : c'est un projet perso, les "tests" ont été le quotidien d'utilisation. Un vrai projet prod aurait pytest.
- **Modèles locaux non supportés out-of-the-box** : pour utiliser un modèle local (Ollama, LM Studio), il faut un adapter OpenAI-compatible — quelques lignes dans `config.py`.

---

## 🔐 Sécurité

- `.env`, `token.pickle`, `credentials.json`, `data.json` sont dans `.gitignore` (ne JAMAIS les commit).
- Les tokens OAuth Google sont renouvelés automatiquement via refresh token.
- Whitelist par user_id Telegram pour empêcher les accès non autorisés.
- `ProtectSystem=strict` et `NoNewPrivileges=true` dans la unit systemd.
- FileLock empêche la corruption de données sur écritures concurrentes.

---

## 📜 Licence

MIT — fais-en ce que tu veux, contribue si tu veux, fork librement.

---

## 🙏 Stack technique

Construit avec :
- **[python-telegram-bot](https://python-telegram-bot.org/)** pour l'interface Telegram
- **[ChromaDB](https://www.trychroma.com/)** + **[sentence-transformers](https://www.sbert.net/)** pour le RAG local
- **[OpenStreetMap](https://www.openstreetmap.org/)** + **[OSRM](http://project-osrm.org/)** pour les maps gratuites
- **[OpenAI Whisper](https://openai.com/research/whisper)** pour la transcription vocale
- **[Bland.ai](https://www.bland.ai/)** pour les appels téléphoniques IA
- **[Google APIs](https://developers.google.com/workspace)** pour Workspace

