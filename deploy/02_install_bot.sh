#!/bin/bash
# ============================================================================
#  Installation du bot dans /home/bot/assistant-personnel
#  À exécuter EN TANT QUE L'UTILISATEUR 'bot' (pas root).
#  Prérequis : le dossier du projet a été transféré dans ~/assistant-personnel
#  Usage :  bash ~/assistant-personnel/deploy/02_install_bot.sh
# ============================================================================
set -euo pipefail

PROJECT_DIR="$HOME/assistant-personnel"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "❌ $PROJECT_DIR introuvable. Transfère le projet d'abord :"
    echo "   depuis ton Mac : rsync -avz --exclude='__pycache__' --exclude='.venv' \\"
    echo "       --exclude='bot.log*' ~/assistant-personnel/ bot@TON_IP:~/assistant-personnel/"
    exit 1
fi

cd "$PROJECT_DIR"

echo "=== 1. Création du venv Python ==="
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "=== 2. Installation des dépendances ==="
pip install --upgrade pip wheel
pip install -r requirements.txt

echo "=== 3. Vérification des fichiers sensibles ==="
for f in .env credentials.json token.pickle; do
    if [[ ! -f "$PROJECT_DIR/$f" ]]; then
        echo "⚠️  $f manquant — le bot ne démarrera pas sans."
    else
        chmod 600 "$PROJECT_DIR/$f"
        echo "   ✓ $f (permissions 600)"
    fi
done

echo "=== 4. Test d'import ==="
python3 -c "
from config import CLAUDE_MODEL
from tools_registry import TOOLS
print(f'   Model: {CLAUDE_MODEL}')
print(f'   Outils: {len(TOOLS)}')
print('   ✓ Imports OK')
"

echo "=== 5. Installation du service systemd ==="
sudo cp "$PROJECT_DIR/deploy/assistant-personnel.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable assistant-personnel

echo "=== 6. Setup backup quotidien ==="
chmod +x "$PROJECT_DIR/deploy/backup.sh"
# cron : backup chaque jour à 3h30 du matin
(crontab -l 2>/dev/null | grep -v 'assistant-personnel/deploy/backup.sh' ; \
 echo "30 3 * * * $PROJECT_DIR/deploy/backup.sh >> $PROJECT_DIR/backup.log 2>&1") | crontab -

echo "=== 7. Setup logrotate ==="
sudo tee /etc/logrotate.d/assistant-personnel > /dev/null <<EOF
$PROJECT_DIR/bot.log $PROJECT_DIR/bot.error.log $PROJECT_DIR/backup.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF

echo ""
echo "✅ Installation terminée."
echo ""
echo "Démarre le bot :"
echo "   sudo systemctl start assistant-personnel"
echo ""
echo "Vérifie le statut :"
echo "   sudo systemctl status assistant-personnel"
echo "   tail -f $PROJECT_DIR/bot.log"
echo ""
