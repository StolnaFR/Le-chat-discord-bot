import os
import discord
from discord import app_commands
from discord.ext import commands


MODO_ROLE_ID = int(os.getenv("MODO_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
EXTRA_STAFF_ROLE_ID = 1515042783595991110
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "🎫 Tickets")
TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID", "0"))

TICKET_PANEL_CHANNEL_ID = int(os.getenv("TICKET_PANEL_CHANNEL_ID", "1523690178638643280"))

PANEL_BUTTON_CUSTOM_ID = "tiket:open_ticket"
CLOSE_BUTTON_CUSTOM_ID = "tiket:close_ticket"


def is_staff(member: discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    if member.guild and member == member.guild.owner:
        return True
    if member.id == OWNER_ID:
        return True
    if any(role.id in (MODO_ROLE_ID, EXTRA_STAFF_ROLE_ID) for role in member.roles):
        return True
    return False

class TicketPanelView(discord.ui.View):
    def __init__(self, cog: "TicketCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Ouvrir un ticket",
        emoji="📩",
        style=discord.ButtonStyle.blurple,
        custom_id=PANEL_BUTTON_CUSTOM_ID,
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction)


class TicketCloseView(discord.ui.View):
    def __init__(self, cog: "TicketCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Fermer le ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id=CLOSE_BUTTON_CUSTOM_ID,
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.close_ticket(interaction)

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: dict[int, float] = {} 

    async def cog_load(self):
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketCloseView(self))

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        message = "❌ Une erreur inattendue est survenue lors de l'exécution de la commande."
        print(f"Erreur non gérée dans TicketCog : {error!r}")
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        if not TICKET_PANEL_CHANNEL_ID:
            return

        channel = self.bot.get_channel(TICKET_PANEL_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(TICKET_PANEL_CHANNEL_ID)
            except discord.HTTPException:
                print(f"[TICKET] Impossible de trouver le salon {TICKET_PANEL_CHANNEL_ID}.")
                return

        if await self.panel_already_sent(channel):
            return

        embed = discord.Embed(
            title="🎫 Support",
            description="Clique sur le bouton ci-dessous pour ouvrir un ticket.",
            color=discord.Color.blurple(),
        )
        try:
            await channel.send(embed=embed, view=TicketPanelView(self))
            print(f"[TICKET] Panneau de tickets envoyé dans #{channel.name}.")
        except discord.HTTPException as e:
            print(f"[TICKET] Erreur lors de l'envoi du panneau : {e}")

    async def panel_already_sent(self, channel: discord.abc.Messageable) -> bool:
        try:
            async for msg in channel.history(limit=50):
                if msg.author.id != self.bot.user.id:
                    continue
                for row in msg.components:
                    for child in getattr(row, "children", []):
                        if getattr(child, "custom_id", None) == PANEL_BUTTON_CUSTOM_ID:
                            return True
        except discord.HTTPException:
            pass
        return False

    async def get_or_create_category(self, guild: discord.Guild) -> discord.CategoryChannel:
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)
        return category

    def find_existing_ticket(self, guild: discord.Guild, user: discord.Member):
        marker = f"ID:{user.id}"
        for channel in guild.text_channels:
            if not channel.topic:
                continue
            if any(part == marker for part in channel.topic.split()):
                return channel
        return None

    async def log_event(self, guild: discord.Guild, message: str):
        if not TICKET_LOG_CHANNEL_ID:
            return
        channel = guild.get_channel(TICKET_LOG_CHANNEL_ID)
        if channel:
            try:
                await channel.send(message)
            except discord.HTTPException:
                pass

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Cette action doit être faite depuis un serveur.", ephemeral=True)
            return

        existing = self.find_existing_ticket(guild, member)
        if existing:
            await interaction.response.send_message(
                f"Tu as déjà un ticket ouvert : {existing.mention}", ephemeral=True
            )
            return

        import time
        now = time.monotonic()
        last = self._cooldowns.get(member.id)
        if last is not None and now - last < 30:
            await interaction.response.send_message(
                "⏳ Merci de patienter avant d'ouvrir un nouveau ticket.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        category = await self.get_or_create_category(guild)

        if len(category.channels) >= 50:
            await interaction.followup.send(
                "❌ Le nombre maximum de tickets simultanés a été atteint. Contacte le staff directement.",
                ephemeral=True,
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, attach_files=True
            ),
        }

        modo_role = guild.get_role(MODO_ROLE_ID)
        if modo_role:
            overwrites[modo_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            )

        extra_role = guild.get_role(EXTRA_STAFF_ROLE_ID)
        if extra_role:
            overwrites[extra_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            )

        owner_member = guild.get_member(OWNER_ID)
        if owner_member:
            overwrites[owner_member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            )

        safe_name = "".join(c for c in member.name.lower() if c.isalnum() or c in ("-", "_")) or "utilisateur"
        channel_name = f"ticket-{safe_name}"[:100]

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket de {member} — ID:{member.id}",
                reason=f"Ouverture de ticket par {member} ({member.id})",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission de créer un salon de ticket. Contacte un administrateur.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Une erreur est survenue lors de la création du ticket. Réessaie plus tard.",
                ephemeral=True,
            )
            return

        self._cooldowns[member.id] = now

        embed = discord.Embed(
            title="🎫 Nouveau ticket",
            description=(
                f"Bonjour {member.mention} 👋\n\n"
                "Merci d'expliquer ta demande ci-dessous, un membre du staff te répondra "
                "dès que possible.\n\n"
                "Un membre du staff peut fermer ce ticket avec le bouton ci-dessous."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Ticket ouvert par {member}", icon_url=member.display_avatar.url)

        mentions = member.mention
        if modo_role:
            mentions += f" {modo_role.mention}"
        if extra_role:
            mentions += f" {extra_role.mention}"

        await ticket_channel.send(content=mentions, embed=embed, view=TicketCloseView(self))

        await interaction.followup.send(f"✅ Ton ticket a été créé : {ticket_channel.mention}", ephemeral=True)
        await self.log_event(guild, f"📩 Ticket ouvert par {member.mention} → {ticket_channel.mention}")

    async def close_ticket(self, interaction: discord.Interaction):
        member = interaction.user
        channel = interaction.channel
        guild = interaction.guild

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Action impossible ici.", ephemeral=True)
            return

        if not is_staff(member):
            await interaction.response.send_message(
                "Seul le staff (rôle MODO ou propriétaire) peut fermer un ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Ticket fermé par {member.mention}. Ce salon sera supprimé dans 5 secondes..."
        )
        await self.log_event(guild, f"Ticket **{channel.name}** fermé par {member.mention}")

        import asyncio
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket fermé par {member} ({member.id})")
        except discord.HTTPException:
            pass

    @app_commands.command(name="ticket-panel", description="Envoie le panneau permettant d'ouvrir un ticket.")
    @app_commands.describe(
        salon="Salon où envoyer le panneau (par défaut : le salon actuel)",
        titre="Titre du panneau (optionnel)",
        description="Description du panneau (optionnel)",
    )
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel = None,
        titre: str = "🎫 Support",
        description: str = "Clique sur le bouton ci-dessous pour ouvrir un ticket.",
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seul le staff peut envoyer le panneau de tickets.", ephemeral=True
            )
            return

        target_channel = salon or interaction.channel
        embed = discord.Embed(title=titre, description=description, color=discord.Color.blurple())
        try:
            await target_channel.send(embed=embed, view=TicketPanelView(self))
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Je n'ai pas la permission d'envoyer de message dans {target_channel.mention}.", ephemeral=True
            )
            return
        await interaction.response.send_message(f"✅ Panneau de tickets envoyé dans {target_channel.mention}.", ephemeral=True)

    @app_commands.command(name="close-ticket", description="Ferme le ticket actuel (staff uniquement).")
    async def close_ticket_command(self, interaction: discord.Interaction):
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Action impossible ici.", ephemeral=True)
            return

        if not is_staff(member):
            await interaction.response.send_message(
                "Seul le staff (rôle MODO ou propriétaire) peut fermer un ticket.", ephemeral=True
            )
            return

        channel = interaction.channel
        topic = getattr(channel, "topic", None)
        if not topic or "ID:" not in topic:
            await interaction.response.send_message("Ce salon n'est pas un ticket.", ephemeral=True)
            return

        await self.close_ticket(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))