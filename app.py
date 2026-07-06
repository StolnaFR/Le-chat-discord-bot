import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()  # Charge les variables depuis le fichier .env

# ---------------------------------------------------------------------------
# Environnement : PROD (bot de production — serveur officiel)
# ---------------------------------------------------------------------------
ENV = "prod"

IMAGE_DIR = "role_menu_images"  
os.makedirs(IMAGE_DIR, exist_ok=True)


ALLOWED_COMMAND_ROLE_IDS = {1515042783595991110, 1515050132607992039}

USER_ID = int(os.getenv("USER_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True 


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
        "cogs.automod",    # Tickets : ouverture/fermeture de tickets support
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

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[PROD] Erreur lors de la connexion : {e}")
