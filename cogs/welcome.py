import os
import discord
from discord.ext import commands

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
GOODBYE_CHANNEL_ID = int(os.getenv("GOODBYE_CHANNEL_ID", "0"))

# Chemin absolu vers la racine du projet (Prod/), quel que soit le dossier
# depuis lequel le bot est lancé.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WELCOME_BANNER_PATH = os.path.join(BASE_DIR, "assets", "welcome_banner.png")
GOODBYE_BANNER_PATH = os.path.join(BASE_DIR, "assets", "goodbye_banner.png")

EMBED_COLOR = discord.Color.from_rgb(88, 216, 130)  # liseré vert, comme sur le screenshot


class Welcome(commands.Cog):
    """Envoie un message + une bannière image à l'arrivée et au départ des membres."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------------------------------------------
    # Arrivée d'un membre
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not WELCOME_CHANNEL_ID:
            print("[PROD] ⚠️ WELCOME_CHANNEL_ID non configuré. Message de bienvenue ignoré.")
            return

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            print(f"[PROD] ❌ Salon de bienvenue introuvable (ID: {WELCOME_CHANNEL_ID})")
            return

        if not isinstance(channel, discord.TextChannel):
            print(f"[PROD] ❌ Le salon {WELCOME_CHANNEL_ID} n'est pas un salon texte.")
            return

        if not os.path.exists(WELCOME_BANNER_PATH):
            print(f"[PROD] ❌ Image de bienvenue introuvable : {WELCOME_BANNER_PATH}")
            file = None
            embed = None
        else:
            filename = os.path.basename(WELCOME_BANNER_PATH)
            file = discord.File(WELCOME_BANNER_PATH, filename=filename)
            embed = discord.Embed(color=EMBED_COLOR)
            embed.set_image(url=f"attachment://{filename}")

        content = f"👋 Bienvenue {member.mention} !"

        try:
            if embed:
                await channel.send(content=content, embed=embed, file=file)
            else:
                await channel.send(content=content)
            print(f"[PROD] ✅ Message de bienvenue envoyé pour {member} (#{channel.name})")
        except discord.Forbidden:
            print(f"[PROD] ❌ Permissions manquantes pour envoyer le message de bienvenue dans #{channel.name}")
        except discord.HTTPException as e:
            print(f"[PROD] ❌ Erreur HTTP lors de l'envoi du message de bienvenue : {e}")

    # -----------------------------------------------------------------
    # Départ d'un membre
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not GOODBYE_CHANNEL_ID:
            print("[PROD] ⚠️ GOODBYE_CHANNEL_ID non configuré. Message d'au revoir ignoré.")
            return

        channel = member.guild.get_channel(GOODBYE_CHANNEL_ID)
        if channel is None:
            print(f"[PROD] ❌ Salon d'au revoir introuvable (ID: {GOODBYE_CHANNEL_ID})")
            return

        if not isinstance(channel, discord.TextChannel):
            print(f"[PROD] ❌ Le salon {GOODBYE_CHANNEL_ID} n'est pas un salon texte.")
            return

        if not os.path.exists(GOODBYE_BANNER_PATH):
            print(f"[PROD] ❌ Image d'au revoir introuvable : {GOODBYE_BANNER_PATH}")
            file = None
            embed = None
        else:
            filename = os.path.basename(GOODBYE_BANNER_PATH)
            file = discord.File(GOODBYE_BANNER_PATH, filename=filename)
            embed = discord.Embed(color=EMBED_COLOR)
            embed.set_image(url=f"attachment://{filename}")

        content = f"👋 **{member}** vient de quitter le serveur..."

        try:
            if embed:
                await channel.send(content=content, embed=embed, file=file)
            else:
                await channel.send(content=content)
            print(f"[PROD] ✅ Message d'au revoir envoyé pour {member} (#{channel.name})")
        except discord.Forbidden:
            print(f"[PROD] ❌ Permissions manquantes pour envoyer le message d'au revoir dans #{channel.name}")
        except discord.HTTPException as e:
            print(f"[PROD] ❌ Erreur HTTP lors de l'envoi du message d'au revoir : {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
