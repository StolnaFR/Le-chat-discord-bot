import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Le .env utilise USER_BUMP_ID (et non BUMP_USER_ID)
_bump_user_raw    = os.getenv("USER_BUMP_ID")
_bump_channel_raw = os.getenv("CHANNEL_BUMP_ID")

BUMP_USER_ID    = int(_bump_user_raw)    if _bump_user_raw    else None
CHANNEL_BUMP_ID = int(_bump_channel_raw) if _bump_channel_raw else None

if BUMP_USER_ID is None:
    print("[BUMP] ⚠️ USER_BUMP_ID manquant dans le .env — le rappel de bump est désactivé.")
else:
    print(f"[BUMP] ✅ Bump configuré — User ID: {BUMP_USER_ID}")


class BumpReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._bump_task = None  # Pour éviter les doublons de tâche

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorer les messages du bot lui-même
        if message.author == self.bot.user:
            return

        # Rien à faire si BUMP_USER_ID n'est pas configuré
        if BUMP_USER_ID is None:
            return

        # Déclencher pour TOUS les messages de l'utilisateur de bump
        if message.author.id == BUMP_USER_ID:
            # Utiliser le salon du message de bump (ou le salon configuré si défini)
            channel = message.channel

            print(f"[BUMP] 📨 Message du bot de bump détecté dans #{channel.name}")

            # Annuler la tâche précédente si elle tourne encore
            if self._bump_task and not self._bump_task.done():
                self._bump_task.cancel()
                print("[BUMP] 🔄 Ancienne tâche de rappel annulée.")

            # Lancer la nouvelle tâche de rappel
            self._bump_task = asyncio.create_task(
                self._envoyer_rappel(channel)
            )

    async def _envoyer_rappel(self, channel: discord.TextChannel):
        """Attend 2h puis envoie le rappel de bump."""
        try:
            await channel.send("🎉 Merci pour le bump ! Le serveur a été mis en avant.")
            print(f"[BUMP] ✅ Confirmation envoyée dans #{channel.name}")

            print("[BUMP] ⏳ Attente de 2h avant le rappel...")
            await asyncio.sleep(7200)  # 2 heures

            await channel.send(
                "⏰ **2 heures se sont écoulées !**\n"
                "Tu peux bump le serveur à nouveau avec `/bump` sur Disboard !"
            )
            print(f"[BUMP] ✅ Rappel de bump envoyé dans #{channel.name}")

        except asyncio.CancelledError:
            print("[BUMP] ⚠️ Tâche de rappel annulée (nouveau bump reçu).")
        except discord.HTTPException as e:
            print(f"[BUMP] ❌ Erreur lors de l'envoi du message : {e}")


async def setup(bot):
    await bot.add_cog(BumpReminder(bot))