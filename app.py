import os
import json
import discord
from discord import app_commands
from discord.ext import commands,tasks
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import threading
import logging
from datetime import datetime
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
import requests


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
BACKUP_CHANNEL_ID = 1522650423604019351

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
    return render_template('index.html')

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




@bot.loop(minutes=10)  # Toutes les 10 minutes
async def keepalive():
    try:
        requests.get("https://le-chat-discord-bot.onrender.com/", timeout=5)
        print("[KEEPALIVE] Ping envoyé")
    except Exception as e:
        print(f"[KEEPALIVE] Erreur : {e}")





# ---------------------------------------------------------------------------
# Gestion des nouveux fichiers
# ---------------------------------------------------------------------------

class FileBackupHandler(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_modified = {}

    def process_event(self, event):
        if event.is_directory:
            return

        path = os.path.abspath(event.src_path)
        parent_dir = os.path.dirname(path)
        base_dir_abs = os.path.abspath(BASE_DIR)
        image_dir_abs = os.path.join(base_dir_abs, "role_menu_images")

        is_json = path.endswith(".json") and parent_dir == base_dir_abs
        is_image = path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and parent_dir == image_dir_abs

        if not (is_json or is_image):
            return

        now = datetime.now().timestamp()
        last_time = self.last_modified.get(path, 0)
        if now - last_time < 2.0:
            return
        self.last_modified[path] = now

        if self.bot.loop and self.bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_backup(path),
                self.bot.loop
            )

    def on_modified(self, event):
        self.process_event(event)

    def on_created(self, event):
        self.process_event(event)


async def send_backup(filepath):
    await asyncio.sleep(1)

    if not os.path.exists(filepath):
        return

    await bot.wait_until_ready()

    channel = bot.get_channel(BACKUP_CHANNEL_ID)

    if channel is None:
        print("❌ Salon backup introuvable")
        return

    try:
        filename = os.path.basename(filepath)

        await channel.send(
            content=f"📁 **Nouveau fichier détecté :** `{filename}`",
            file=discord.File(filepath)
        )

        print(f"📤 Backup envoyé : {filename}")

    except Exception as e:
        print(f"❌ Erreur backup : {e}")


def start_file_watcher():
    event_handler = FileBackupHandler(bot)
    bot.observer = Observer()
    bot.observer.schedule(
        event_handler,
        path=BASE_DIR,
        recursive=True
    )
    bot.observer.start()
    print("👀 Surveillance des fichiers activée")






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

    if not getattr(bot, "watcher_started", False):
        start_file_watcher()
        bot.watcher_started = True


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
# Conexion serveur
# ---------------------------------------------------------------------------

@bot.tree.command(name="server-stat", description="Affiche la latence du bot")
async def server_stat(interaction: discord.Interaction):
    ping = round(bot.latency * 1000)
    await interaction.response.send_message(
        f" Latence du serveur : {ping} ms"
    )




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
