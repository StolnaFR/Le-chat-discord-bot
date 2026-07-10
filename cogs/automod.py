import re
import time
import discord
from discord.ext import commands
from collections import defaultdict


# ---------------------------------------------------------------------------
# Auto-modération — anti-insultes, anti-pub Discord, anti-spam
# ---------------------------------------------------------------------------

# --- Liste des mots interdits (complète à ta guise) ---
MOTS_INTERDITS = [
    "connard", "connasse", "salope", "pute", "putain", "enculé", "enculer",
    "fdp", "fils de pute", "pd", "batard", "bâtard", "ta gueule", "ferme ta gueule",
    "niquer", "nique ta mère", "ntm", "nique", "merde", "cul", "bite",
    "couille", "couilles", "con", "conne", "abruti", "idiot", "imbécile",
    "débile", "attardé", "bouffon", "gros con", "va te faire"
]

# --- Regex pour détecter les invitations Discord ---
# Détecte : discord.gg/xxx  |  discord.com/invite/xxx  |  discordapp.com/invite/xxx
REGEX_INVITE_DISCORD = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[\w-]+",
    re.IGNORECASE
)

# --- Config anti-spam ---
SPAM_SEUIL_MESSAGES = 5   # nombre de messages
SPAM_FENETRE_SECONDES = 5  # sur cette durée (en secondes)


class AutomodCog(commands.Cog):
    """Auto-modération : anti-insultes, anti-pub Discord, anti-spam."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dictionnaire pour tracker le spam : {user_id: [timestamp, timestamp, ...]}
        self._spam_tracker: dict[int, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Utilitaire — supprimer le message + avertir l'utilisateur
    # ------------------------------------------------------------------

    async def sanctionner(self, message: discord.Message, raison: str):
        """Supprime le message et envoie un avertissement visible dans le salon."""
        try:
            await message.delete()
        except discord.Forbidden:
            print(f"[AUTOMOD] Impossible de supprimer le message de {message.author} : permission manquante.")
            return

        try:
            avertissement = await message.channel.send(
                f"⚠️ {message.author.mention} — **{raison}**",
                delete_after=8  # le message d'avertissement disparaît après 8 secondes
            )
        except discord.Forbidden:
            print(f"[AUTOMOD] Impossible d'envoyer l'avertissement dans #{message.channel.name}.")

    # ------------------------------------------------------------------
    # Événement principal — chaque message passe par ici
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # On ignore les bots et les messages hors serveur
        if message.author.bot or message.guild is None:
            return

        # Les administrateurs sont exemptés de l'auto-modération
        if message.author.guild_permissions.administrator:
            return

        contenu = message.content.lower()

        # --- Vérification 1 : anti-insultes ---
        for mot in MOTS_INTERDITS:
            if mot in contenu:
                await self.sanctionner(message, "Langage inapproprié interdit sur ce serveur.")
                return  # On arrête ici, pas besoin de vérifier le reste

        # --- Vérification 2 : anti-pub Discord ---
        if REGEX_INVITE_DISCORD.search(message.content):
            await self.sanctionner(message, "Les publicités et invitations Discord sont interdites ici.")
            return

        # --- Vérification 3 : anti-spam ---
        await self._verifier_spam(message)

    # ------------------------------------------------------------------
    # Anti-spam — détection de messages trop rapides
    # ------------------------------------------------------------------

    async def _verifier_spam(self, message: discord.Message):
        """
        Détecte si un utilisateur envoie trop de messages trop vite.
        On garde une liste des timestamps (horodatages) de ses messages récents.
        Si le nombre de messages dans la fenêtre de temps dépasse le seuil → spam.
        """
        user_id = message.author.id
        maintenant = time.time()

        # On ajoute le timestamp du message actuel
        self._spam_tracker[user_id].append(maintenant)

        # On ne garde que les timestamps dans la fenêtre de temps
        self._spam_tracker[user_id] = [
            t for t in self._spam_tracker[user_id]
            if maintenant - t <= SPAM_FENETRE_SECONDES
        ]

        # Si le nombre de messages dépasse le seuil → spam détecté
        if len(self._spam_tracker[user_id]) >= SPAM_SEUIL_MESSAGES:
            # On vide le tracker pour éviter de sanctionner 10 fois de suite
            self._spam_tracker[user_id] = []
            await self.sanctionner(message, f"Spam détecté — pas plus de {SPAM_SEUIL_MESSAGES} messages en {SPAM_FENETRE_SECONDES}s.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutomodCog(bot))
