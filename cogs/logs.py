import os
import asyncio
import discord
from discord.ext import commands

WELCOME_IMAGE_PATH = os.path.join("assets", "welcome_banner.png")
GOODBYE_IMAGE_PATH = os.path.join("assets", "goodbye_banner.png")

SERVER_LOG_CHANNEL_ID = 1522650423604019351


class LogsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_server_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = guild.get_channel(SERVER_LOG_CHANNEL_ID)
        if channel is None:
            print(f"Erreur : salon de logs {SERVER_LOG_CHANNEL_ID} introuvable.")
            return
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print("Erreur : je n'ai pas la permission d'envoyer un message dans le salon de logs généraux.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log_embed = discord.Embed(
            description=f"📥 **Arrivée** — {member.mention} (`{member.id}`)\nCompte créé le {member.created_at.strftime('%d/%m/%Y')}",
            color=discord.Color.blurple()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_server_log(member.guild, log_embed)

        channel_id = os.getenv("WELCOME_CHANNEL_ID")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if channel is None:
            return

        file = discord.File(WELCOME_IMAGE_PATH, filename="welcome_banner.png")
        embed = discord.Embed(color=discord.Color.green())
        embed.set_image(url="attachment://welcome_banner.png")


    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Envoie un message d'au revoir (avec image) quand un membre quitte le serveur."""
        log_embed = discord.Embed(
            description=f"📤 **Départ** — {member.mention} (`{member.id}`)",
            color=discord.Color.dark_grey()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_server_log(member.guild, log_embed)

        channel_id = os.getenv("GOODBYE_CHANNEL_ID") or os.getenv("WELCOME_CHANNEL_ID")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if channel is None:
            return

        file = discord.File(GOODBYE_IMAGE_PATH, filename="goodbye_banner.png")
        embed = discord.Embed(color=discord.Color.red())
        embed.set_image(url="attachment://goodbye_banner.png")

        try:
            await channel.send(content=f"😢 **{member.display_name}** a quitté le serveur.", embed=embed, file=file)
        except discord.Forbidden:
            print("Erreur : je n'ai pas la permission d'envoyer le message d'au revoir dans ce salon.")
        except FileNotFoundError:
            print(f"Erreur : image introuvable à {GOODBYE_IMAGE_PATH}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        contenu = message.content if message.content else "*(pas de texte — image, embed ou fichier)*"
        if len(contenu) > 1000:
            contenu = contenu[:1000] + "…"
        embed = discord.Embed(
            description=f"🗑️ **Message supprimé** dans {message.channel.mention}\nAuteur : {message.author.mention}\n\n{contenu}",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"ID auteur : {message.author.id}")
        await self.send_server_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.guild is None or before.content == after.content:
            return
        avant = before.content if before.content else "*(vide)*"
        apres = after.content if after.content else "*(vide)*"
        if len(avant) > 500:
            avant = avant[:500] + "…"
        if len(apres) > 500:
            apres = apres[:500] + "…"
        embed = discord.Embed(
            description=(
                f"✏️ **Message modifié** dans {before.channel.mention} "
                f"([aller au message]({after.jump_url}))\nAuteur : {before.author.mention}\n\n"
                f"**Avant :** {avant}\n**Après :** {apres}"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"ID auteur : {before.author.id}")
        await self.send_server_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        bump_bot_id = int(os.getenv("USER_BUMP_ID", "0"))
        bump_channel_id = int(os.getenv("CHANNEL_BUMP_ID", "0"))

        if message.author.id != bump_bot_id:
            return
        if message.channel.id != bump_channel_id:
            return
        if not message.embeds:
            return

        description = message.embeds[0].description or ""
        if "bump done" not in description.lower():
            return

        print(f"[BUMP] Bump détecté dans #{message.channel.name}. Rappel dans 2 heures.")
        await asyncio.sleep(7200)

        channel = message.guild.get_channel(bump_channel_id)
        if channel is None:
            print(f"[BUMP] Erreur : salon de bump {bump_channel_id} introuvable.")
            return

        rappel_embed = discord.Embed(
            title="⏰ C'est l'heure du bump !",
            description="2 heures se sont écoulées depuis le dernier bump.\nTape `/bump` pour rebooster le serveur sur **Disboard** ! 🚀",
            color=discord.Color.green()
        )
        try:
            await channel.send(content="@everyone", embed=rappel_embed)
            print("[BUMP] Rappel de bump envoyé avec succès.")
        except discord.Forbidden:
            print("[BUMP] Erreur : je n'ai pas la permission d'envoyer dans le salon de bump.")


async def setup(bot: commands.Bot):
    await bot.add_cog(LogsCog(bot))
