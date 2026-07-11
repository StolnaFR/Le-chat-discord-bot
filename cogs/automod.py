import re
import time
import discord
from discord.ext import commands
from collections import defaultdict

MOTS_INTERDITS = [
    "connard", "connasse", "salope", "pute", "putain", "enculé", "enculer",
    "fdp", "fils de pute", "pd", "batard", "bâtard", "ta gueule", "ferme ta gueule",
    "niquer", "nique ta mère", "ntm", "nique", "merde", "cul", "bite",
    "couille", "couilles", "con", "conne", "abruti", "idiot", "imbécile",
    "débile", "attardé", "bouffon", "gros con", "va te faire"
]

REGEX_MOTS_INTERDITS = re.compile(
    r"\b(" + "|".join(re.escape(mot) for mot in MOTS_INTERDITS) + r")\b",
    re.IGNORECASE
)

REGEX_INVITE_DISCORD = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[\w-]+",
    re.IGNORECASE
)

SPAM_SEUIL_MESSAGES = 5
SPAM_FENETRE_SECONDES = 5


class AutomodCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dictionnaire pour tracker le spam : {user_id: [timestamp, timestamp, ...]}
        self._spam_tracker: dict[int, list[float]] = defaultdict(list)

    async def sanctionner(self, message: discord.Message, raison: str):
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # On ignore les bots et les messages hors serveur
        if message.author.bot or message.guild is None:
            return

        # Les administrateurs sont exemptés de l'auto-modération
        if message.author.guild_permissions.administrator:
            return

        contenu = message.content.lower()

        if REGEX_MOTS_INTERDITS.search(contenu):
            await self.sanctionner(message, "Langage inapproprié interdit sur ce serveur.")
            return

        if REGEX_INVITE_DISCORD.search(message.content):
            await self.sanctionner(message, "Les publicités et invitations Discord sont interdites ici.")
            return

        await self._verifier_spam(message)

    async def _verifier_spam(self, message: discord.Message):
        user_id = message.author.id
        maintenant = time.time()

        self._spam_tracker[user_id].append(maintenant)

        self._spam_tracker[user_id] = [
            t for t in self._spam_tracker[user_id]
            if maintenant - t <= SPAM_FENETRE_SECONDES
        ]

        if len(self._spam_tracker[user_id]) >= SPAM_SEUIL_MESSAGES:
            # On vide le tracker pour éviter de sanctionner 10 fois de suite
            self._spam_tracker[user_id] = []
            await self.sanctionner(message, f"Spam détecté — pas plus de {SPAM_SEUIL_MESSAGES} messages en {SPAM_FENETRE_SECONDES}s.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutomodCog(bot))