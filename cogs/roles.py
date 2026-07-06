import os
import json
import discord
from discord import app_commands
from discord.ext import commands


# ---------------------------------------------------------------------------
# Rôles — reaction roles & menus déroulants de rôles
# ---------------------------------------------------------------------------

IMAGE_DIR = "role_menu_images"


# ------------------------------------------------------------------
# Helpers JSON
# ------------------------------------------------------------------

def get_reaction_roles():
    try:
        with open('reaction_roles.json', 'r') as f:
            return json.load(f).get("roles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_reaction_roles(roles):
    with open('reaction_roles.json', 'w') as f:
        json.dump({"roles": roles}, f, indent=2)


def get_menus():
    try:
        with open('role_menus.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_menus(menus):
    with open('role_menus.json', 'w') as f:
        json.dump(menus, f, indent=2)


# ------------------------------------------------------------------
# Vue — menu déroulant de rôles
# ------------------------------------------------------------------

class RoleMenuView(discord.ui.View):
    """Menu déroulant persistant permettant à un membre de s'auto-assigner des rôles."""

    def __init__(self, menu_name: str, options_data: list):
        super().__init__(timeout=None)
        self.menu_name = menu_name

        select_options = [
            discord.SelectOption(
                label=opt["label"],
                value=opt["role_id"],
                emoji=opt.get("emoji") or None
            )
            for opt in options_data
        ]

        select = discord.ui.Select(
            placeholder="Choisis tes rôles",
            min_values=0,
            max_values=len(select_options) if select_options else 1,
            options=select_options,
            custom_id=f"rolemenu:{menu_name}"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        menus = get_menus()
        menu = menus.get(self.menu_name)
        if not menu:
            await interaction.response.send_message("Ce menu n'existe plus.", ephemeral=True)
            return

        selected_ids = set(interaction.data.get("values", []))
        all_role_ids = {opt["role_id"] for opt in menu["options"]}
        member = interaction.user

        to_add, to_remove = [], []
        for role_id in all_role_ids:
            role = interaction.guild.get_role(int(role_id))
            if not role:
                continue
            has_role = role in member.roles
            wants_role = role_id in selected_ids
            if wants_role and not has_role:
                to_add.append(role)
            elif not wants_role and has_role:
                to_remove.append(role)

        try:
            if to_add:
                await member.add_roles(*to_add, reason="Menu de rôles")
            if to_remove:
                await member.remove_roles(*to_remove, reason="Menu de rôles")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Je n'ai pas la permission de gérer un ou plusieurs de ces rôles.", ephemeral=True
            )
            return

        await interaction.response.send_message("✅ Tes rôles ont été mis à jour.", ephemeral=True)


# ------------------------------------------------------------------
# Cog principal
# ------------------------------------------------------------------

class RolesCog(commands.Cog):
    """Gère les reaction roles et les menus déroulants de rôles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Groupes de commandes slash
        self.rolemenu_group = app_commands.Group(
            name="rolemenu",
            description="Créer un menu déroulant de rôles auto-assignables"
        )
        self.reactionrole_group = app_commands.Group(
            name="reactionrole",
            description="Gérer les associations réaction/rôle"
        )

        # Enregistrement des commandes dans les groupes
        self._register_rolemenu_commands()
        self._register_reactionrole_commands()

        bot.tree.add_command(self.rolemenu_group)
        bot.tree.add_command(self.reactionrole_group)

    # ------------------------------------------------------------------
    # Reaction roles — événements
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        reaction_roles = get_reaction_roles()
        for rr in reaction_roles:
            if str(payload.message_id) == rr["message_id"]:
                if payload.emoji.name == rr["emoji"] or str(payload.emoji) == rr["emoji"]:
                    guild = self.bot.get_guild(payload.guild_id)
                    role = guild.get_role(int(rr["role_id"]))
                    member = guild.get_member(payload.user_id)
                    if role and member:
                        try:
                            await member.add_roles(role)
                        except discord.Forbidden:
                            print("Erreur : Je n'ai pas les permissions de donner le rôle.")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        reaction_roles = get_reaction_roles()
        for rr in reaction_roles:
            if str(payload.message_id) == rr["message_id"]:
                if payload.emoji.name == rr["emoji"] or str(payload.emoji) == rr["emoji"]:
                    guild = self.bot.get_guild(payload.guild_id)
                    role = guild.get_role(int(rr["role_id"]))
                    member = guild.get_member(payload.user_id)
                    if role and member:
                        try:
                            await member.remove_roles(role)
                        except discord.Forbidden:
                            print("Erreur : Je n'ai pas les permissions d'enlever le rôle.")

    # ------------------------------------------------------------------
    # Enregistrement des sous-commandes /rolemenu
    # ------------------------------------------------------------------

    def _register_rolemenu_commands(self):

        @self.rolemenu_group.command(name="create", description="Crée un nouveau menu de rôles (vide, à remplir avec add_option)")
        @app_commands.describe(
            name="Identifiant court du menu (ex: couleurs)",
            titre="Titre affiché en haut du menu",
            description="Texte affiché sous le titre (optionnel)",
            image_url="URL d'une image à afficher (optionnel, ignoré si tu fournis 'image')",
            image="Fichier image/gif à uploader depuis ton ordinateur (optionnel, prioritaire sur image_url)"
        )
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_create(interaction: discord.Interaction, name: str, titre: str, description: str = "", image_url: str = None, image: discord.Attachment = None):
            menus = get_menus()
            if name in menus:
                await interaction.response.send_message("Un menu avec ce nom existe déjà. Choisis un autre nom.", ephemeral=True)
                return

            menu_data = {"title": titre, "description": description, "image_url": image_url, "image_path": None, "options": []}

            if image is not None:
                if not (image.content_type and image.content_type.startswith("image/")):
                    await interaction.response.send_message("Le fichier fourni n'est pas une image valide (jpg/png/gif...).", ephemeral=True)
                    return
                ext = os.path.splitext(image.filename)[1] or ".gif"
                filepath = os.path.join(IMAGE_DIR, f"{name}{ext}")
                await image.save(filepath)
                menu_data["image_path"] = filepath
                menu_data["image_url"] = None

            menus[name] = menu_data
            save_menus(menus)
            await interaction.response.send_message(
                f"✅ Menu `{name}` créé. Ajoute des rôles avec `/rolemenu add_option`, puis envoie-le avec `/rolemenu send`.",
                ephemeral=True
            )

        @self.rolemenu_group.command(name="add_option", description="Ajoute un rôle sélectionnable à un menu")
        @app_commands.describe(
            name="Identifiant du menu",
            role="Le rôle à ajouter",
            label="Texte affiché dans le menu (ex: Rouge)",
            emoji="Emoji affiché à côté (optionnel)"
        )
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_add_option(interaction: discord.Interaction, name: str, role: discord.Role, label: str, emoji: str = None):
            menus = get_menus()
            menu = menus.get(name)
            if not menu:
                await interaction.response.send_message("Menu introuvable. Crée-le d'abord avec `/rolemenu create`.", ephemeral=True)
                return
            if len(menu["options"]) >= 25:
                await interaction.response.send_message("Un menu déroulant Discord est limité à 25 rôles.", ephemeral=True)
                return
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "Je ne peux pas gérer ce rôle : il est placé au-dessus (ou au même niveau) que mon rôle.", ephemeral=True
                )
                return

            menu["options"].append({"role_id": str(role.id), "label": label, "emoji": emoji})
            save_menus(menus)
            await interaction.response.send_message(f"✅ {role.mention} ajouté au menu `{name}` sous le label « {label} ».", ephemeral=True)

        @self.rolemenu_group.command(name="set_image", description="Change l'image/gif d'un menu existant (fichier uploadé ou URL)")
        @app_commands.describe(
            name="Identifiant du menu",
            image_url="URL d'une image à afficher (optionnel, ignoré si tu fournis 'image')",
            image="Fichier image/gif à uploader depuis ton ordinateur (optionnel, prioritaire sur image_url)"
        )
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_set_image(interaction: discord.Interaction, name: str, image_url: str = None, image: discord.Attachment = None):
            menus = get_menus()
            menu = menus.get(name)
            if not menu:
                await interaction.response.send_message("Menu introuvable.", ephemeral=True)
                return

            if image is None and image_url is None:
                await interaction.response.send_message("Fournis soit un fichier (`image`), soit une URL (`image_url`).", ephemeral=True)
                return

            old_path = menu.get("image_path")
            if old_path and os.path.exists(old_path):
                os.remove(old_path)

            if image is not None:
                if not (image.content_type and image.content_type.startswith("image/")):
                    await interaction.response.send_message("Le fichier fourni n'est pas une image valide (jpg/png/gif...).", ephemeral=True)
                    return
                ext = os.path.splitext(image.filename)[1] or ".gif"
                filepath = os.path.join(IMAGE_DIR, f"{name}{ext}")
                await image.save(filepath)
                menu["image_path"] = filepath
                menu["image_url"] = None
            else:
                menu["image_path"] = None
                menu["image_url"] = image_url

            save_menus(menus)
            await interaction.response.send_message(
                f"✅ Image du menu `{name}` mise à jour. Renvoie-le avec `/rolemenu send` pour voir le changement "
                f"(le message déjà envoyé ne se met pas à jour tout seul).",
                ephemeral=True
            )

        @self.rolemenu_group.command(name="send", description="Envoie (ou renvoie) le menu de rôles dans un salon")
        @app_commands.describe(name="Identifiant du menu", salon="Salon où envoyer le menu (par défaut : ce salon)")
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_send(interaction: discord.Interaction, name: str, salon: discord.TextChannel = None):
            menus = get_menus()
            menu = menus.get(name)
            if not menu:
                await interaction.response.send_message("Menu introuvable.", ephemeral=True)
                return
            if not menu["options"]:
                await interaction.response.send_message("Ajoute au moins un rôle avec `/rolemenu add_option` avant d'envoyer.", ephemeral=True)
                return

            channel = salon or interaction.channel
            embed = discord.Embed(
                title=menu["title"],
                description=menu.get("description") or None,
                color=discord.Color.blurple()
            )

            file = None
            image_path = menu.get("image_path")
            if image_path and os.path.exists(image_path):
                filename = os.path.basename(image_path)
                file = discord.File(image_path, filename=filename)
                embed.set_image(url=f"attachment://{filename}")
            elif menu.get("image_url"):
                embed.set_image(url=menu["image_url"])

            view = RoleMenuView(name, menu["options"])
            if file:
                await channel.send(embed=embed, view=view, file=file)
            else:
                await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Menu `{name}` envoyé dans {channel.mention}.", ephemeral=True)

        @self.rolemenu_group.command(name="list", description="Liste les menus de rôles configurés")
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_list(interaction: discord.Interaction):
            menus = get_menus()
            if not menus:
                await interaction.response.send_message("Aucun menu de rôles configuré.", ephemeral=True)
                return

            lines = []
            for name, menu in menus.items():
                lines.append(f"• `{name}` — « {menu['title']} » ({len(menu['options'])} rôle(s))")
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        @self.rolemenu_group.command(name="delete", description="Supprime définitivement un menu de rôles")
        @app_commands.describe(name="Identifiant du menu à supprimer")
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolemenu_delete(interaction: discord.Interaction, name: str):
            menus = get_menus()
            if name not in menus:
                await interaction.response.send_message("Menu introuvable.", ephemeral=True)
                return

            image_path = menus[name].get("image_path")
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

            del menus[name]
            save_menus(menus)
            await interaction.response.send_message(
                f"🗑️ Menu `{name}` supprimé. Si tu l'avais déjà envoyé dans un salon, "
                f"le message reste affiché mais ne fonctionnera plus : supprime-le manuellement si besoin.",
                ephemeral=True
            )

    # ------------------------------------------------------------------
    # Enregistrement des sous-commandes /reactionrole
    # ------------------------------------------------------------------

    def _register_reactionrole_commands(self):

        @self.reactionrole_group.command(name="add", description="Associe une réaction sur un message à un rôle")
        @app_commands.describe(
            message_id="L'ID du message sur lequel réagir (clic droit sur le message > Copier l'ID)",
            emoji="L'emoji à utiliser pour la réaction",
            role="Le rôle à donner/retirer quand on réagit"
        )
        @app_commands.checks.has_permissions(manage_roles=True)
        async def reactionrole_add(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "Je ne peux pas gérer ce rôle : il est placé au-dessus (ou au même niveau) que mon propre rôle. "
                    "Monte mon rôle plus haut dans la liste des rôles du serveur.",
                    ephemeral=True
                )
                return

            message = None
            for channel in interaction.guild.text_channels:
                try:
                    message = await channel.fetch_message(int(message_id))
                    break
                except (discord.NotFound, discord.Forbidden, ValueError):
                    continue

            if message is None:
                await interaction.response.send_message(
                    "Message introuvable. Vérifie l'ID (clic droit sur le message > Copier l'ID) "
                    "et que j'ai accès au salon.",
                    ephemeral=True
                )
                return

            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                await interaction.response.send_message("Emoji invalide ou je ne peux pas l'utiliser.", ephemeral=True)
                return

            roles = get_reaction_roles()
            roles.append({
                "message_id": str(message_id),
                "emoji": emoji,
                "role_id": str(role.id)
            })
            save_reaction_roles(roles)

            await interaction.response.send_message(
                f"✅ Configuré : réagir avec {emoji} sur [ce message]({message.jump_url}) donnera le rôle {role.mention}.",
                ephemeral=True
            )

        @self.reactionrole_group.command(name="remove", description="Retire une association réaction/rôle")
        @app_commands.describe(message_id="L'ID du message concerné", emoji="L'emoji concerné")
        @app_commands.checks.has_permissions(manage_roles=True)
        async def reactionrole_remove(interaction: discord.Interaction, message_id: str, emoji: str):
            roles = get_reaction_roles()
            new_roles = [
                rr for rr in roles
                if not (rr["message_id"] == str(message_id) and (rr["emoji"] == emoji))
            ]
            if len(new_roles) == len(roles):
                await interaction.response.send_message("Aucune configuration trouvée pour ce message/emoji.", ephemeral=True)
                return
            save_reaction_roles(new_roles)
            await interaction.response.send_message("✅ Configuration supprimée.", ephemeral=True)

        @self.reactionrole_group.command(name="list", description="Liste toutes les associations réaction/rôle configurées")
        @app_commands.checks.has_permissions(manage_roles=True)
        async def reactionrole_list(interaction: discord.Interaction):
            roles = get_reaction_roles()
            if not roles:
                await interaction.response.send_message("Aucune reaction role configurée.", ephemeral=True)
                return

            lines = []
            for rr in roles:
                role = interaction.guild.get_role(int(rr["role_id"]))
                role_txt = role.mention if role else f"(rôle supprimé : {rr['role_id']})"
                lines.append(f"• Message `{rr['message_id']}` — {rr['emoji']} → {role_txt}")

            await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
