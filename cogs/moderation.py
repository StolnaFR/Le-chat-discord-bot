import json
import datetime
import discord
from discord import app_commands
from discord.ext import commands

SANCTION_LOG_CHANNEL_ID = 1515968529466265741
WARNS_FILE = "warns.json"


def load_warns() -> dict:
    try:
        with open(WARNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_warns(data: dict):
    with open(WARNS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_warn(guild_id: int, user_id: int, moderator: str, raison: str) -> int:
    data = load_warns()
    guild_key = str(guild_id)
    user_key = str(user_id)

    if guild_key not in data:
        data[guild_key] = {}
    if user_key not in data[guild_key]:
        data[guild_key][user_key] = []

    data[guild_key][user_key].append({
        "raison": raison,
        "par": moderator,
        "date": datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    })

    save_warns(data)
    return len(data[guild_key][user_key])


def get_warns(guild_id: int, user_id: int) -> list:
    data = load_warns()
    return data.get(str(guild_id), {}).get(str(user_id), [])


def clear_warns(guild_id: int, user_id: int):
    data = load_warns()
    guild_key = str(guild_id)
    user_key = str(user_id)
    if guild_key in data and user_key in data[guild_key]:
        del data[guild_key][user_key]
        save_warns(data)

def peut_sanctionner(interaction: discord.Interaction, cible: discord.Member) -> tuple[bool, str]:
    auteur = interaction.user

    if cible.id == interaction.client.user.id:
        return False, "Je ne peux pas m'appliquer une sanction à moi-même."

    if cible.id == auteur.id:
        return False, "Tu ne peux pas te sanctionner toi-même."

    if auteur == interaction.guild.owner:
        return True, ""

    if cible == interaction.guild.owner:
        return False, "Tu ne peux pas sanctionner le propriétaire du serveur."

    if cible.guild_permissions.administrator:
        return False, "Tu ne peux pas sanctionner un administrateur."

    if cible.top_role >= auteur.top_role:
        return False, "Tu ne peux pas sanctionner ce membre (rôle égal ou supérieur au tien)."

    return True, ""


def bot_peut_agir(interaction: discord.Interaction, cible: discord.Member) -> tuple[bool, str]:
    moi = interaction.guild.me
    if cible.top_role >= moi.top_role:
        return False, "Je ne peux pas agir sur ce membre : mon rôle est égal ou inférieur au sien. Remonte mon rôle dans la hiérarchie du serveur."
    return True, ""


class ModerationCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Tu n'as pas la permission nécessaire pour utiliser cette commande."
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = "Je n'ai pas la permission nécessaire pour effectuer cette action."
        else:
            message = "Une erreur inattendue est survenue lors de l'exécution de la commande."
            print(f"Erreur non gérée dans ModerationCog : {error!r}")

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def send_sanction_log(self, guild: discord.Guild, description: str, color: discord.Color = discord.Color.orange()):
        channel = guild.get_channel(SANCTION_LOG_CHANNEL_ID)
        if channel is None:
            print(f"Erreur : salon de logs {SANCTION_LOG_CHANNEL_ID} introuvable.")
            return
        embed = discord.Embed(description=description, color=color)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print("Erreur : je n'ai pas la permission d'envoyer un message dans le salon de logs.")

    @app_commands.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.describe(membre="Le membre à expulser", raison="Raison de l'expulsion")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        autorise, erreur = bot_peut_agir(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        try:
            await membre.kick(reason=raison)
            await interaction.response.send_message(f"{membre.mention} a été expulsé. Raison : {raison}")
            await self.send_sanction_log(
                interaction.guild,
                f"**Kick** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}\nRaison : {raison}",
                discord.Color.orange()
            )
        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission d'expulser ce membre.", ephemeral=True)

    @app_commands.command(name="ban", description="Bannit un membre du serveur")
    @app_commands.describe(membre="Le membre à bannir", raison="Raison du bannissement")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        autorise, erreur = bot_peut_agir(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        try:
            await membre.ban(reason=raison)
            await interaction.response.send_message(f"{membre.mention} a été banni. Raison : {raison}")
            await self.send_sanction_log(
                interaction.guild,
                f"**Ban** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}\nRaison : {raison}",
                discord.Color.red()
            )
        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission de bannir ce membre.", ephemeral=True)

    @app_commands.command(name="unban", description="Débannit un utilisateur via son ID")
    @app_commands.describe(user_id="L'ID Discord de l'utilisateur à débannir")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not user_id.isdigit():
            await interaction.response.send_message("L'ID fourni n'est pas un identifiant Discord valide.", ephemeral=True)
            return
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"{user.mention} a été débanni.")
            await self.send_sanction_log(
                interaction.guild,
                f"**Unban** — {user.mention} (`{user.id}`)\nPar : {interaction.user.mention}",
                discord.Color.green()
            )
        except (discord.NotFound, ValueError):
            await interaction.response.send_message("Utilisateur introuvable ou non banni.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission de débannir.", ephemeral=True)

    @app_commands.command(name="mute", description="Rend muet un membre pendant une durée donnée (timeout)")
    @app_commands.describe(membre="Le membre à muter", minutes="Durée du mute en minutes (max 40320 = 28 jours)", raison="Raison")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, membre: discord.Member, minutes: app_commands.Range[int, 1, 40320], raison: str = "Aucune raison fournie"):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        autorise, erreur = bot_peut_agir(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        try:
            duree = datetime.timedelta(minutes=minutes)
            await membre.timeout(duree, reason=raison)
            await interaction.response.send_message(f"{membre.mention} a été rendu muet pendant {minutes} minute(s). Raison : {raison}")
            await self.send_sanction_log(
                interaction.guild,
                f"**Mute** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}\nDurée : {minutes} minute(s)\nRaison : {raison}",
                discord.Color.orange()
            )
        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission de muter ce membre.", ephemeral=True)

    @app_commands.command(name="unmute", description="Retire le mute (timeout) d'un membre")
    @app_commands.describe(membre="Le membre à démuter")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, membre: discord.Member):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        try:
            await membre.timeout(None)
            await interaction.response.send_message(f"{membre.mention} n'est plus muet.")
            await self.send_sanction_log(
                interaction.guild,
                f"**Unmute** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}",
                discord.Color.green()
            )
        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission de démuter ce membre.", ephemeral=True)

    @app_commands.command(name="warn", description="Avertit un membre (message privé + log + sauvegarde JSON)")
    @app_commands.describe(membre="Le membre à avertir", raison="Raison de l'avertissement")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison fournie"):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        total = add_warn(interaction.guild.id, membre.id, str(interaction.user), raison)
        try:
            await membre.send(f"Tu as reçu un avertissement sur **{interaction.guild.name}**. Raison : {raison}")
        except discord.Forbidden:
            pass
        await interaction.response.send_message(f"{membre.mention} a été averti. Raison : {raison} (**{total} warn(s)** au total)")
        await self.send_sanction_log(
            interaction.guild,
            f"**Warn** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}\nRaison : {raison}\nTotal : **{total} warn(s)**",
            discord.Color.gold()
        )

    @app_commands.command(name="warns", description="Affiche l'historique des warns d'un membre")
    @app_commands.describe(membre="Le membre dont tu veux voir les warns")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns(self, interaction: discord.Interaction, membre: discord.Member):
        liste = get_warns(interaction.guild.id, membre.id)
        if not liste:
            await interaction.response.send_message(f"{membre.mention} n'a aucun warn.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Warns de {membre.display_name}",
            color=discord.Color.gold()
        )
        for i, w in enumerate(liste, start=1):
            embed.add_field(
                name=f"Warn #{i} — {w['date']}",
                value=f"**Raison :** {w['raison']}\n**Par :** {w['par']}",
                inline=False
            )
        embed.set_footer(text=f"Total : {len(liste)} warn(s) — ID : {membre.id}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarns", description="Supprime tous les warns d'un membre")
    @app_commands.describe(membre="Le membre dont tu veux effacer les warns")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clearwarns(self, interaction: discord.Interaction, membre: discord.Member):
        autorise, erreur = peut_sanctionner(interaction, membre)
        if not autorise:
            await interaction.response.send_message(erreur, ephemeral=True)
            return
        liste = get_warns(interaction.guild.id, membre.id)
        if not liste:
            await interaction.response.send_message(f"{membre.mention} n'a aucun warn à effacer.", ephemeral=True)
            return
        clear_warns(interaction.guild.id, membre.id)
        await interaction.response.send_message(f"{len(liste)} warn(s) supprimé(s) pour {membre.mention}.", ephemeral=True)
        await self.send_sanction_log(
            interaction.guild,
            f"**Clearwarns** — {membre.mention} (`{membre.id}`)\nPar : {interaction.user.mention}\n{len(liste)} warn(s) supprimé(s)",
            discord.Color.blue()
        )

    @app_commands.command(name="clear", description="Supprime un nombre de messages dans le salon")
    @app_commands.describe(nombre="Nombre de messages à supprimer (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, nombre: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"{len(deleted)} message(s) supprimé(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))