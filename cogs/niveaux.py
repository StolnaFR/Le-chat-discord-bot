import os
import json
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from cogs.tickets import is_staff

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
XP_PATH = os.path.join(DATA_DIR, "xp_playeur.json")

os.makedirs(DATA_DIR, exist_ok=True)

XP_MIN = 15
XP_MAX = 25
COOLDOWN = 60

SALONS_EXCLUS = set()

RECOMPENSES_NIVEAU = {}


def xp_requis(niveau: int) -> int:
    return 5 * (niveau ** 2) + 50 * niveau + 100


def barre_progression(xp: int, requis: int, longueur: int = 12) -> str:
    ratio = max(0, min(1, xp / requis)) if requis else 0
    plein = round(ratio * longueur)
    return "█" * plein + "░" * (longueur - plein)


def charger_donnees() -> dict:
    if not os.path.exists(XP_PATH):
        return {}
    try:
        with open(XP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[PROD] ❌ Erreur de lecture de {XP_PATH} : {e}")
        return {}


def sauvegarder_donnees(data: dict) -> None:
    try:
        with open(XP_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[PROD] ❌ Erreur d'écriture de {XP_PATH} : {e}")


def get_profil(data: dict, guild_id: int, user_id: int) -> dict:
    g = data.setdefault(str(guild_id), {})
    u = g.setdefault(str(user_id), {"xp": 0, "niveau": 0, "last_message": 0})
    return u


def est_autorise(interaction: discord.Interaction) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    return is_staff(member)


class Niveaux(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = charger_donnees()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.channel.id in SALONS_EXCLUS:
            return

        profil = get_profil(self.data, message.guild.id, message.author.id)

        maintenant = time.time()
        if maintenant - profil["last_message"] < COOLDOWN:
            return

        profil["last_message"] = maintenant
        gain = random.randint(XP_MIN, XP_MAX)
        profil["xp"] += gain

        leveled_up = False
        while profil["xp"] >= xp_requis(profil["niveau"]):
            profil["xp"] -= xp_requis(profil["niveau"])
            profil["niveau"] += 1
            leveled_up = True

        sauvegarder_donnees(self.data)

        if leveled_up:
            await self._annoncer_level_up(message, profil["niveau"])

    async def _annoncer_level_up(self, message: discord.Message, nouveau_niveau: int):
        embed = discord.Embed(
            description=f"🎉 {message.author.mention} passe **niveau {nouveau_niveau}** !",
            color=discord.Color.gold()
        )
        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException as e:
            print(f"[PROD] ⚠️ Impossible d'annoncer le level up : {e}")

        role_id = RECOMPENSES_NIVEAU.get(nouveau_niveau)
        if role_id:
            role = message.guild.get_role(role_id)
            if role and isinstance(message.author, discord.Member):
                try:
                    await message.author.add_roles(role, reason=f"Récompense niveau {nouveau_niveau}")
                except discord.Forbidden:
                    print(f"[PROD] ❌ Permissions insuffisantes pour attribuer le rôle {role_id}")

    niveau_group = app_commands.Group(name="niveau", description="Système de niveaux")

    @niveau_group.command(name="voir", description="Affiche ton niveau ou celui d'un membre")
    @app_commands.describe(membre="Le membre à consulter (par défaut : toi)")
    async def voir(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        profil = get_profil(self.data, interaction.guild.id, membre.id)
        requis = xp_requis(profil["niveau"])
        barre = barre_progression(profil["xp"], requis)

        embed = discord.Embed(
            title=f"Niveau de {membre.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="Niveau", value=str(profil["niveau"]), inline=True)
        embed.add_field(name="XP", value=f"{profil['xp']} / {requis}", inline=True)
        embed.add_field(name="Progression", value=barre, inline=False)

        await interaction.response.send_message(embed=embed)

    @niveau_group.command(name="classement", description="Affiche le classement des niveaux du serveur")
    async def classement(self, interaction: discord.Interaction):
        g = self.data.get(str(interaction.guild.id), {})
        if not g:
            await interaction.response.send_message("Personne n'a encore gagné d'XP ici.", ephemeral=True)
            return

        classement = sorted(
            g.items(),
            key=lambda item: (item[1]["niveau"], item[1]["xp"]),
            reverse=True
        )[:10]

        lignes = []
        for i, (user_id, profil) in enumerate(classement, start=1):
            membre = interaction.guild.get_member(int(user_id))
            nom = membre.display_name if membre else f"Utilisateur {user_id}"
            lignes.append(f"**{i}.** {nom} — niveau {profil['niveau']} ({profil['xp']} xp)")

        embed = discord.Embed(
            title=f"🏆 Classement — {interaction.guild.name}",
            description="\n".join(lignes),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    @niveau_group.command(name="ajouter", description="[Admin] Ajoute de l'XP à un membre")
    @app_commands.describe(membre="Le membre concerné", quantite="Quantité d'XP à ajouter")
    async def ajouter(self, interaction: discord.Interaction, membre: discord.Member, quantite: int):
        if not est_autorise(interaction):
            await interaction.response.send_message("❌ Tu n'es pas autorisé à utiliser cette commande.", ephemeral=True)
            return

        profil = get_profil(self.data, interaction.guild.id, membre.id)
        profil["xp"] += quantite

        leveled_up = False
        while profil["xp"] >= xp_requis(profil["niveau"]):
            profil["xp"] -= xp_requis(profil["niveau"])
            profil["niveau"] += 1
            leveled_up = True

        sauvegarder_donnees(self.data)

        msg = f"✅ {quantite} XP ajouté(s) à {membre.mention}. Niveau actuel : {profil['niveau']}."
        await interaction.response.send_message(msg, ephemeral=True)

        if leveled_up:
            role_id = RECOMPENSES_NIVEAU.get(profil["niveau"])
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role:
                    try:
                        await membre.add_roles(role, reason="Récompense niveau (ajout manuel)")
                    except discord.Forbidden:
                        pass

    @niveau_group.command(name="definir", description="[Admin] Définit le niveau et l'XP d'un membre")
    @app_commands.describe(membre="Le membre concerné", niveau="Nouveau niveau", xp="XP dans ce niveau")
    async def definir(self, interaction: discord.Interaction, membre: discord.Member, niveau: int, xp: int = 0):
        if not est_autorise(interaction):
            await interaction.response.send_message("❌ Tu n'es pas autorisé à utiliser cette commande.", ephemeral=True)
            return

        profil = get_profil(self.data, interaction.guild.id, membre.id)
        profil["niveau"] = max(0, niveau)
        profil["xp"] = max(0, xp)
        sauvegarder_donnees(self.data)

        await interaction.response.send_message(
            f"✅ {membre.mention} est maintenant niveau {profil['niveau']} ({profil['xp']} xp).",
            ephemeral=True
        )

    @niveau_group.command(name="reset", description="[Admin] Réinitialise le niveau d'un membre")
    @app_commands.describe(membre="Le membre concerné")
    async def reset(self, interaction: discord.Interaction, membre: discord.Member):
        if not est_autorise(interaction):
            await interaction.response.send_message("❌ Tu n'es pas autorisé à utiliser cette commande.", ephemeral=True)
            return

        profil = get_profil(self.data, interaction.guild.id, membre.id)
        profil["xp"] = 0
        profil["niveau"] = 0
        profil["last_message"] = 0
        sauvegarder_donnees(self.data)

        await interaction.response.send_message(f"✅ Niveau de {membre.mention} réinitialisé.", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = Niveaux(bot)
    await bot.add_cog(cog)
    print("[PROD] Cog chargé : cogs.niveaux")