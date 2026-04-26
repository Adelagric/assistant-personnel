# Déploiement Qezdebou sur VPS Hetzner

Procédure complète pour déployer le bot sur un VPS Hetzner (ou n'importe quel VPS Debian/Ubuntu).

**Temps total estimé : ~1h15**  **Coût : ~5 €/mois**

---

## 📋 Pré-requis

- Un compte Hetzner Cloud (https://console.hetzner.cloud)
- Une clé SSH publique locale (`cat ~/.ssh/id_ed25519.pub`)
- *(Optionnel)* Un compte Backblaze B2 pour backups distants
- *(Optionnel)* Un compte UptimeRobot pour monitoring externe

---

## Étape 1 — Créer le VPS Hetzner (5 min)

1. Console Hetzner → `Add Server`
2. **Location** : Falkenstein ou Helsinki
3. **Image** : Ubuntu 24.04
4. **Type** : CX22 (4,51 €/mois, 4 GB RAM, 40 GB SSD)
5. **SSH Key** : ajouter ta clé publique
6. **Name** : `qezdebou` (ou ce que tu veux)
7. Clic `Create & Buy now`

Récupère l'IP publique, tu en auras besoin pour la suite.

---

## Étape 2 — Hardening du VPS (10 min)

Depuis ton Mac :

```bash
# Exporte ta clé publique SSH (celle que tu as ajoutée dans Hetzner)
export BOT_SSH_KEY="$(cat ~/.ssh/id_ed25519.pub)"

# Exécute le script de hardening sur le VPS (en root)
ssh -o StrictHostKeyChecking=accept-new root@TON_IP "BOT_SSH_KEY='$BOT_SSH_KEY' bash -s" \
    < ~/assistant-personnel/deploy/01_setup_vps.sh
```

Ce script :
- Met à jour le système
- Crée l'utilisateur `bot` avec ta clé SSH
- Durcit SSH (plus de root, plus de password)
- Active UFW (seulement port 22)
- Active fail2ban + mises à jour auto
- Ajoute 2 GB de swap (utile pour charger le modèle RAG)

⚠️ **Après ce script, root ne peut plus se connecter en SSH. Teste d'abord la nouvelle connexion :**

```bash
ssh bot@TON_IP
# Si ça marche : tu es tranquille.
```

---

## Étape 3 — Transférer le projet (5 min)

Depuis ton Mac :

```bash
rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='bot.log*' \
    --exclude='bot.error.log*' \
    --exclude='backups' \
    ~/assistant-personnel/ bot@TON_IP:~/assistant-personnel/
```

---

## Étape 4 — Installer le bot (15 min)

SSH sur le VPS :

```bash
ssh bot@TON_IP
bash ~/assistant-personnel/deploy/02_install_bot.sh
```

Ce script :
- Crée un venv Python dédié
- Installe les dépendances (torch, ChromaDB, etc. — prend ~10 min)
- Vérifie `.env`, `credentials.json`, `token.pickle`
- Installe le service systemd
- Configure le cron de backup quotidien
- Configure la rotation des logs

---

## Étape 5 — Démarrer le bot

```bash
sudo systemctl start assistant-personnel
sudo systemctl status assistant-personnel
tail -f ~/assistant-personnel/bot.log
```

Tu devrais voir `✅ Assistant personnel démarré.` Envoie un message Telegram pour valider.

⚠️ **ATTENTION : avant de démarrer sur le VPS, arrête le bot sur ton Mac :**
```bash
# Sur ton Mac
launchctl unload ~/Library/LaunchAgents/com.user.assistant-personnel.plist
```
Sinon **deux instances** = conflit Telegram (`terminated by other getUpdates request`).

---

## Étape 6 — Backup distant (optionnel, 10 min)

### Option A — Backblaze B2 (recommandé, ~0,05 €/mois)

1. Crée un compte https://www.backblaze.com/b2
2. Crée un bucket privé `qezdebou-backups`
3. Crée une Application Key avec accès au bucket
4. Ajoute dans `~/assistant-personnel/.env` sur le VPS :

```
B2_ACCOUNT_ID=xxxxx
B2_APPLICATION_KEY=xxxxx
B2_BUCKET=qezdebou-backups
BACKUP_ENCRYPTION_KEY=un_gros_mot_de_passe_bien_complexe
```

5. Test manuel :
```bash
~/assistant-personnel/deploy/backup.sh
```

### Option B — Backup local uniquement
Rien à faire. Les backups s'accumulent dans `~/assistant-personnel/backups/` (7 jours de rétention).

---

## Étape 7 — Monitoring (optionnel, 5 min)

### UptimeRobot (gratuit)

Le bot ne serveur pas d'endpoint HTTP, donc check par **Keyword** sur le log :

Plus simple : installer un petit script qui ping chaque 5 min :

```bash
# Sur le VPS, crée un endpoint healthcheck simple via Hetzner Cloud Console
# OU utilise healthchecks.io :

# 1. Va sur https://healthchecks.io → crée un check "Qezdebou" toutes les 10 min
# 2. Récupère l'URL de ping (ex: https://hc-ping.com/xxxxxxxxxxxx)
# 3. Ajoute un cron :
(crontab -l; echo "*/5 * * * * pgrep -f 'main.py' >/dev/null && curl -fsS https://hc-ping.com/XXX > /dev/null") | crontab -
```

Si le bot plante, tu reçois un mail dans les 15 min.

---

## Maintenance courante

### Voir les logs
```bash
sudo journalctl -u assistant-personnel -f      # logs systemd
tail -f ~/assistant-personnel/bot.log           # logs app
```

### Redémarrer
```bash
sudo systemctl restart assistant-personnel
```

### Mettre à jour le code
Depuis ton Mac :
```bash
rsync -avz --exclude='__pycache__' --exclude='.venv' \
    --exclude='bot.log*' --exclude='data.json' --exclude='rag_db' \
    --exclude='token.pickle' --exclude='.env' \
    ~/assistant-personnel/ bot@TON_IP:~/assistant-personnel/
ssh bot@TON_IP 'sudo systemctl restart assistant-personnel'
```

*(Note : on exclut `data.json`, `rag_db`, `token.pickle`, `.env` pour ne pas écraser les données/secrets du VPS.)*

### Restaurer un backup
```bash
cd ~/assistant-personnel
sudo systemctl stop assistant-personnel
tar -xzf backups/backup_20260501_033000.tar.gz   # ou .tar.gz.gpg avec gpg --decrypt
sudo systemctl start assistant-personnel
```

---

## Désactiver Apple Notes

Déjà fait : sur le VPS (Linux), les outils Apple Notes sont automatiquement ignorés (`sys.platform != "darwin"`).

Variable d'env dans `.env` pour double-sûreté :
```
ENABLE_APPLE_NOTES=false
```

---

## Coût mensuel total

| Poste | Coût |
|-------|------|
| VPS Hetzner CX22 | 4,51 € |
| Backblaze B2 (~1 GB) | 0,005 € |
| UptimeRobot / healthchecks.io | 0 € |
| **Total** | **~4,52 €/mois** |

Plus les coûts API LLM (tokens) qui ne changent pas selon l'hébergement.

---

## Troubleshooting

### Le bot ne démarre pas
```bash
sudo journalctl -u assistant-personnel -n 50 --no-pager
```

### Erreur "address already in use" Telegram
Un autre bot tourne. Vérifie sur ton Mac que le LaunchAgent est bien arrêté.

### ChromaDB/torch plante à l'install
```bash
# 4 GB de RAM peut être juste. Lance-le manuellement 1 fois pour télécharger le modèle :
cd ~/assistant-personnel
source .venv/bin/activate
python3 -c "from features.rag import _get_model; _get_model()"
# La première exécution télécharge ~80 MB et peut prendre 1-2 min
```

### Le VPS swap beaucoup / devient lent
CX22 = 4 GB RAM, c'est serré quand sentence-transformers est chargé. Upgrade vers CX32 (8 GB, 7,90 €/mois) si ça devient gênant.
