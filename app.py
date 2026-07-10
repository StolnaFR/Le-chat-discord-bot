import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, jsonify
import threading
import logging
from datetime import datetime
from collections import deque

load_dotenv()  # Charge les variables depuis le fichier .env

# ---------------------------------------------------------------------------
# Environnement : PROD (bot de production — serveur officiel)
# ---------------------------------------------------------------------------
ENV = "prod"

IMAGE_DIR = "role_menu_images"  
os.makedirs(IMAGE_DIR, exist_ok=True)

# Chemin absolu du fichier role_menus.json (à la racine du projet)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROLE_MENUS_PATH = os.path.join(BASE_DIR, "role_menus.json")


ALLOWED_COMMAND_ROLE_IDS = {1515042783595991110, 1515050132607992039}

USER_ID = int(os.getenv("USER_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
ROLE_SALON = int(os.getenv("ROLE_SALON", "0"))

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True


# ---------------------------------------------------------------------------
# Système de Logging Personnalisé
# ---------------------------------------------------------------------------

class LogCapture:
    def __init__(self, max_logs=1000):
        self.logs = deque(maxlen=max_logs)
        self.lock = threading.Lock()
    
    def add_log(self, message, log_type="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append({
                "timestamp": timestamp,
                "message": message,
                "type": log_type
            })
    
    def get_logs(self):
        with self.lock:
            return list(self.logs)
    
    def clear_logs(self):
        with self.lock:
            self.logs.clear()

log_capture = LogCapture(max_logs=1000)

# Redirection des logs personnalisés
_original_print = print

def custom_print(*args, **kwargs):
    message = " ".join(str(arg) for arg in args)
    
    # Déterminer le type de log
    if "❌" in message or "Erreur" in message or "ERROR" in message:
        log_type = "error"
    elif "✅" in message or "succès" in message:
        log_type = "success"
    elif "🔍" in message or "🔄" in message or "📋" in message or "📤" in message or "🗑️" in message:
        log_type = "info"
    elif "⚠️" in message or "Warning" in message:
        log_type = "warning"
    else:
        log_type = "info"
    
    log_capture.add_log(message, log_type)
    _original_print(*args, **kwargs)

# Remplacer la fonction print globalement
import builtins
builtins.print = custom_print

# Imprimer les logs d'initialisation
custom_print(f"[PROD] 📁 Chemin du projet: {BASE_DIR}")
custom_print(f"[PROD] 📄 Chemin du fichier JSON: {ROLE_MENUS_PATH}")


# ---------------------------------------------------------------------------
# Configuration Flask (pour Render Web Service)
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Désactiver les logs de Flask pour un output plus propre
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 Le Chat - Dashboard Logs</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                min-height: 100vh;
                padding: 20px;
                color: #e2e8f0;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            .header {
                text-align: center;
                margin-bottom: 40px;
                animation: fadeIn 0.8s ease-out;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            .header-title {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
                margin-bottom: 10px;
            }
            
            .header-title h1 {
                font-size: 2.5em;
                background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .emoji {
                font-size: 2.5em;
                animation: bounce 2s infinite;
            }
            
            @keyframes bounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-10px); }
            }
            
            .status-bar {
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }
            
            .status-item {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 10px 20px;
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 8px;
                backdrop-filter: blur(10px);
            }
            
            .status-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: #10b981;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; box-shadow: 0 0 10px rgba(16, 185, 129, 0.7); }
                50% { opacity: 0.5; }
            }
            
            .logs-section {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 12px;
                padding: 25px;
                backdrop-filter: blur(10px);
                animation: slideUp 0.8s ease-out;
            }
            
            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .logs-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                flex-wrap: wrap;
                gap: 15px;
            }
            
            .logs-header h2 {
                font-size: 1.5em;
                color: #60a5fa;
            }
            
            .controls {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.9em;
                font-weight: 600;
                transition: all 0.3s ease;
                background: rgba(96, 165, 250, 0.2);
                color: #60a5fa;
                border: 1px solid #60a5fa;
            }
            
            .btn:hover {
                background: #60a5fa;
                color: #0f172a;
                transform: translateY(-2px);
            }
            
            .btn.danger {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border-color: #ef4444;
            }
            
            .btn.danger:hover {
                background: #ef4444;
                color: #0f172a;
            }
            
            .search-box {
                padding: 8px 12px;
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(96, 165, 250, 0.3);
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 0.9em;
                min-width: 200px;
            }
            
            .search-box::placeholder {
                color: rgba(226, 232, 240, 0.5);
            }
            
            .logs-container {
                background: rgba(2, 6, 23, 0.6);
                border-radius: 8px;
                padding: 15px;
                max-height: 600px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.95em;
                line-height: 1.6;
            }
            
            .logs-container::-webkit-scrollbar {
                width: 8px;
            }
            
            .logs-container::-webkit-scrollbar-track {
                background: rgba(30, 41, 59, 0.3);
                border-radius: 4px;
            }
            
            .logs-container::-webkit-scrollbar-thumb {
                background: rgba(96, 165, 250, 0.5);
                border-radius: 4px;
            }
            
            .logs-container::-webkit-scrollbar-thumb:hover {
                background: rgba(96, 165, 250, 0.8);
            }
            
            .log-entry {
                padding: 8px 12px;
                margin-bottom: 4px;
                border-radius: 4px;
                border-left: 3px solid transparent;
                transition: all 0.2s ease;
            }
            
            .log-entry:hover {
                background: rgba(96, 165, 250, 0.1);
            }
            
            .log-time {
                color: #94a3b8;
                font-weight: 600;
            }
            
            .log-message {
                color: #cbd5e1;
                word-break: break-word;
            }
            
            .log-entry.info {
                border-left-color: #60a5fa;
            }
            
            .log-entry.success {
                border-left-color: #10b981;
                background: rgba(16, 185, 129, 0.1);
            }
            
            .log-entry.success .log-message {
                color: #6ee7b7;
            }
            
            .log-entry.warning {
                border-left-color: #f59e0b;
                background: rgba(245, 158, 11, 0.1);
            }
            
            .log-entry.warning .log-message {
                color: #fcd34d;
            }
            
            .log-entry.error {
                border-left-color: #ef4444;
                background: rgba(239, 68, 68, 0.1);
            }
            
            .log-entry.error .log-message {
                color: #fca5a5;
            }
            
            .empty-state {
                text-align: center;
                padding: 40px 20px;
                color: #64748b;
            }
            
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #64748b;
                font-size: 0.9em;
            }
            
            .footer a {
                color: #60a5fa;
                text-decoration: none;
            }
            
            .footer a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-title">
                    <span class="emoji">🤖</span>
                    <h1>Le Chat</h1>
                </div>
                <p>Dashboard Logs en temps réel</p>
            </div>
            
            <div class="status-bar">
                <div class="status-item">
                    <span class="status-dot"></span>
                    <span>Bot actif</span>
                </div>
                <div class="status-item">
                    <span style="color: #60a5fa;">⚡</span>
                    <span>Render Web Service</span>
                </div>
                <div class="status-item">
                    <span>📊</span>
                    <span id="log-count">0 logs</span>
                </div>
            </div>
            
            <div class="logs-section">
                <div class="logs-header">
                    <h2>📋 Logs du Bot</h2>
                    <div class="controls">
                        <input type="text" class="search-box" id="search-input" placeholder="Rechercher...">
                        <button class="btn" onclick="scrollToBottom()">↓ Bas</button>
                        <button class="btn danger" onclick="clearLogs()">🗑️ Nettoyer</button>
                    </div>
                </div>
                
                <div class="logs-container" id="logs-container">
                    <div class="empty-state">
                        <p>En attente de logs...</p>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                ✨ Bot Discord • Powered by Discord.py • Déployé sur Render
            </div>
        </div>
        
        <script>
            const logsContainer = document.getElementById('logs-container');
            const searchInput = document.getElementById('search-input');
            let allLogs = [];
            
            async function fetchLogs() {
                try {
                    const response = await fetch('/api/logs');
                    const data = await response.json();
                    allLogs = data.logs;
                    updateLogDisplay();
                    document.getElementById('log-count').textContent = allLogs.length + ' logs';
                } catch (error) {
                    console.error('Erreur lors de la récupération des logs:', error);
                }
            }
            
            function updateLogDisplay() {
                const query = searchInput.value.toLowerCase();
                const filteredLogs = allLogs.filter(log => 
                    log.message.toLowerCase().includes(query)
                );
                
                if (filteredLogs.length === 0) {
                    logsContainer.innerHTML = '<div class="empty-state"><p>Aucun log correspondant</p></div>';
                    return;
                }
                
                logsContainer.innerHTML = filteredLogs.map(log => `
                    <div class="log-entry ${log.type}">
                        <span class="log-time">[${log.timestamp}]</span>
                        <span class="log-message">${escapeHtml(log.message)}</span>
                    </div>
                `).join('');
            }
            
            function escapeHtml(text) {
                const map = {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#039;'
                };
                return text.replace(/[&<>"']/g, m => map[m]);
            }
            
            function scrollToBottom() {
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
            
            function clearLogs() {
                if (confirm('Êtes-vous sûr de vouloir nettoyer les logs ?')) {
                    fetch('/api/logs/clear', { method: 'POST' })
                        .then(() => {
                            allLogs = [];
                            updateLogDisplay();
                            document.getElementById('log-count').textContent = '0 logs';
                        });
                }
            }
            
            // Rafraîchir les logs toutes les 500ms
            fetchLogs();
            setInterval(fetchLogs, 500);
            
            // Rafraîchir l'affichage quand on tape dans la recherche
            searchInput.addEventListener('input', updateLogDisplay);
            
            // Auto-scroll vers le bas quand de nouveaux logs arrivent
            setInterval(() => {
                if (logsContainer.scrollHeight - logsContainer.scrollTop - logsContainer.clientHeight < 100) {
                    scrollToBottom();
                }
            }, 500);
        </script>
    </body>
    </html>
    """
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/logs')
def get_logs():
    return jsonify({"logs": log_capture.get_logs()})

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    log_capture.clear_logs()
    return jsonify({"status": "cleared"})

@app.route('/health')
def health():
    return jsonify({"health": "✅ OK", "status": "running"})

def run_flask():
    """Lance le serveur Flask sur le port 5000"""
    port = int(os.getenv("PORT", 5000))
    print(f"[FLASK] 🌐 Serveur Flask lancé sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

# ---------------------------------------------------------------------------
# CommandTree personnalisé — restriction d'accès globale
# ---------------------------------------------------------------------------

class RestrictedCommandTree(app_commands.CommandTree):
    """CommandTree personnalisé : bloque l'accès à TOUTES les commandes slash sauf pour les membres
    ayant un des rôles autorisés (ou le propriétaire/un administrateur du serveur, pour éviter de se
    bloquer soi-même). Ça ne concerne PAS l'attribution de rôle par réaction, qui reste ouverte à tous."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False

        member = interaction.user
        if not isinstance(member, discord.Member):
            return False

        if member.guild_permissions.administrator or member == interaction.guild.owner:
            return True

        if any(role.id in ALLOWED_COMMAND_ROLE_IDS for role in member.roles):
            return True

        raise app_commands.CheckFailure("Tu n'es pas autorisé à utiliser les commandes de ce bot.")


bot = commands.Bot(command_prefix='!', intents=intents, tree_cls=RestrictedCommandTree)


# ---------------------------------------------------------------------------
# Événements de base
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f'[PROD] Connecté en tant que {bot.user} (ID: {bot.user.id})')
    print('[PROD] Le bot est prêt !')
    print('------')

    guild_id = os.getenv("GUILD_ID")  # optionnel : ID du serveur pour un sync instantané

    try:
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"[PROD] {len(synced)} commande(s) slash synchronisée(s) sur le serveur {guild_id}.")
        else:
            synced = await bot.tree.sync()
            print(f"[PROD] {len(synced)} commande(s) slash synchronisée(s) globalement (peut prendre jusqu'à 1h).")
    except Exception as e:
        print(f"[PROD] Erreur lors de la synchronisation des commandes slash : {e}")

    # ===============================================================
    # Supprimer les anciens menus et renvoyer tous les menus de rôles
    # ===============================================================
    
    print(f"[PROD] ROLE_SALON configuré : {ROLE_SALON}")
    
    if ROLE_SALON and ROLE_SALON != 0:
        try:
            print(f"[PROD] 🔍 Recherche du serveur avec guild_id: {guild_id}")
            
            # Récupérer TOUS les serveurs du bot
            guilds = bot.guilds
            print(f"[PROD] Le bot est sur {len(guilds)} serveur(s)")
            
            guild = None
            if guild_id:
                guild = bot.get_guild(int(guild_id))
                print(f"[PROD] Serveur trouvé avec GUILD_ID: {guild}")
            else:
                # Si pas de GUILD_ID, prendre le premier serveur
                if guilds:
                    guild = guilds[0]
                    print(f"[PROD] Aucun GUILD_ID, utilisation du premier serveur: {guild.name}")
            
            if guild:
                print(f"[PROD] ✅ Serveur détecté: {guild.name} (ID: {guild.id})")
                channel = guild.get_channel(ROLE_SALON)
                
                if channel:
                    print(f"[PROD] ✅ Salon trouvé: #{channel.name} (ID: {channel.id})")
                    
                    if isinstance(channel, discord.TextChannel):
                        print(f"[PROD] 🗑️ Suppression des anciens menus de rôles dans #{channel.name}...")
                        
                        deleted_count = 0
                        # Supprimer les 100 derniers messages du salon
                        async for message in channel.history(limit=100):
                            try:
                                # Supprimer uniquement les messages du bot
                                if message.author == bot.user:
                                    await message.delete()
                                    deleted_count += 1
                            except discord.Forbidden:
                                print(f"[PROD] ❌ Impossible de supprimer un message (permissions)")
                            except discord.HTTPException as e:
                                print(f"[PROD] ⚠️ Erreur HTTP lors de la suppression: {e}")
                        
                        print(f"[PROD] ✅ {deleted_count} ancien(s) message(s) supprimé(s)")
                        print(f"[PROD] 📤 Envoi des menus de rôles...")
                        
                        # Renvoyer tous les menus configurés
                        try:
                            from cogs.roles import RoleMenuView
                            
                            print(f"[PROD] 🔄 Tentative de lecture de {ROLE_MENUS_PATH}...")
                            
                            # Vérifier si le fichier existe
                            if not os.path.exists(ROLE_MENUS_PATH):
                                print(f"[PROD] ❌ Fichier '{ROLE_MENUS_PATH}' NON TROUVÉ")
                                print(f"[PROD] 📂 Crée-le d'abord avec /rolemenu create ...")
                            else:
                                print(f"[PROD] ✅ Fichier trouvé!")
                                
                                # Essayer de lire le fichier directement
                                try:
                                    with open(ROLE_MENUS_PATH, 'r', encoding='utf-8') as f:
                                        menus = json.load(f)
                                    
                                    print(f"[PROD] ✅ JSON lu avec succès")
                                    print(f"[PROD] 📋 {len(menus)} menu(s) détecté(s)")
                                    
                                    if not menus:
                                        print(f"[PROD] ⚠️ Le fichier JSON est vide {{}}")
                                    else:
                                        # Afficher les menus trouvés
                                        for menu_name in menus.keys():
                                            print(f"[PROD]    • Menu trouvé: '{menu_name}'")
                                    
                                    if menus:
                                        for menu_name, menu_data in menus.items():
                                            try:
                                                print(f"[PROD] 📤 Envoi du menu '{menu_name}'...")
                                                
                                                # Vérifier la structure du menu
                                                if "title" not in menu_data:
                                                    print(f"[PROD]    ⚠️ Clé 'title' manquante dans le menu")
                                                if "options" not in menu_data:
                                                    print(f"[PROD]    ⚠️ Clé 'options' manquante dans le menu")
                                                
                                                # Créer l'embed
                                                embed = discord.Embed(
                                                    title=menu_data.get("title", "Menu"),
                                                    description=menu_data.get("description") or None,
                                                    color=discord.Color.blurple()
                                                )
                                                
                                                # Ajouter l'image si elle existe
                                                file = None
                                                image_path = menu_data.get("image_path")
                                                if image_path and os.path.exists(image_path):
                                                    print(f"[PROD]    → Image trouvée: {image_path}")
                                                    filename = os.path.basename(image_path)
                                                    file = discord.File(image_path, filename=filename)
                                                    embed.set_image(url=f"attachment://{filename}")
                                                elif menu_data.get("image_url"):
                                                    print(f"[PROD]    → URL image: {menu_data.get('image_url')}")
                                                    embed.set_image(url=menu_data["image_url"])
                                                
                                                # Envoyer le menu avec la view
                                                options = menu_data.get("options", [])
                                                print(f"[PROD]    → {len(options)} rôle(s) dans ce menu")
                                                
                                                view = RoleMenuView(menu_name, options)
                                                if file:
                                                    await channel.send(embed=embed, view=view, file=file)
                                                else:
                                                    await channel.send(embed=embed, view=view)
                                                
                                                print(f"[PROD] ✅ Menu '{menu_name}' renvoyé avec succès!")
                                            except Exception as e:
                                                print(f"[PROD] ❌ Erreur lors de l'envoi du menu '{menu_name}': {type(e).__name__}: {e}")
                                                import traceback
                                                traceback.print_exc()
                                
                                except json.JSONDecodeError as je:
                                    print(f"[PROD] ❌ ERREUR JSON (fichier corrompu): {je.msg}")
                                    print(f"[PROD]    Ligne {je.lineno}, Colonne {je.colno}")
                                except Exception as e:
                                    print(f"[PROD] ❌ Erreur lors de la récupération des menus: {type(e).__name__}: {e}")
                                    import traceback
                                    traceback.print_exc()
                        except ImportError as ie:
                            print(f"[PROD] ❌ Erreur d'import: {ie}")
                            print(f"[PROD] Vérifie que le fichier cogs/roles.py existe")
                        except Exception as e:
                            print(f"[PROD] ❌ Erreur générale: {type(e).__name__}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"[PROD] ❌ {ROLE_SALON} n'est pas un salon texte")
                else:
                    print(f"[PROD] ❌ Salon ROLE_SALON ({ROLE_SALON}) introuvable dans le serveur {guild.name}")
            else:
                print(f"[PROD] ❌ Serveur introuvable. Vérifie GUILD_ID dans le .env")
        except Exception as e:
            print(f"[PROD] ❌ Erreur générale: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[PROD] ⚠️ ROLE_SALON non configuré ou égal à 0. Passe cette étape.")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Surveille ✨Les Chouchous✨")
    )


@bot.tree.command(name="bonjour", description="Le bot te dit bonjour !")
async def bonjour(interaction: discord.Interaction):
    await interaction.response.send_message(f"Bonjour {interaction.user.mention} !")


# ---------------------------------------------------------------------------
# Gestion des erreurs de commandes slash
# ---------------------------------------------------------------------------

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
    elif isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "❌ Tu n'es pas autorisé à utiliser les commandes de ce bot.", ephemeral=True
        )
    else:
        print(f"Erreur de commande : {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Une erreur est survenue.", ephemeral=True)


# ---------------------------------------------------------------------------
# Chargement des cogs
# ---------------------------------------------------------------------------

async def load_cogs():
    """Charge tous les modules (cogs) depuis le dossier cogs/."""
    cogs = [
        "cogs.logs",        # Logs : membres + messages
        "cogs.moderation",  # Modération : kick, ban, unban, mute, unmute, warn, clear
        "cogs.roles",       # Rôles : reaction roles & menus déroulants
        "cogs.tiket", 
        "cogs.welcome",
        
        ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"[PROD] Cog chargé : {cog}")
        except Exception as e:
            print(f"[PROD] Erreur lors du chargement de {cog} : {e}")


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise SystemExit("[PROD] Erreur : la variable d'environnement DISCORD_TOKEN n'est pas définie (vois le fichier .env).")

    async def main():
        async with bot:
            await load_cogs()
            await bot.start(TOKEN)

    # Lancer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("[PROD] 🚀 Thread Flask lancé en arrière-plan")

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[PROD] Erreur lors de la connexion : {e}")
