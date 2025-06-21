import discord
from discord.ext import commands
from discord import app_commands
import database
import time
from utils import time_parser
from datetime import datetime

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Wyrzuca użytkownika z serwera.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(uzytkownik="Osoba do wyrzucenia.", powod="Powód wyrzucenia (opcjonalny).")
    async def kick_command(self, interaction: discord.Interaction, uzytkownik: discord.Member, powod: str = "Brak powodu"):
        if uzytkownik.id == interaction.user.id:
            return await interaction.response.send_message("Nie możesz wyrzucić samego siebie!", ephemeral=True)
        if uzytkownik.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
            return await interaction.response.send_message("Nie możesz wyrzucić kogoś z taką samą lub wyższą rolą!", ephemeral=True)

        try:
            await uzytkownik.kick(reason=powod)
            database.add_punishment(
                guild_id=interaction.guild.id,
                user_id=uzytkownik.id,
                moderator_id=interaction.user.id,
                punishment_type='kick',
                reason=powod
            )
            await interaction.response.send_message(f"Pomyślnie wyrzucono {uzytkownik.mention}. Powód: {powod}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)

    @kick_command.error
    async def kick_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Nie masz uprawnień do wyrzucania członków.", ephemeral=True)

    @app_commands.command(name="ban", description="Banuje użytkownika na serwerze.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(uzytkownik="Osoba do zbanowania.", czas_trwania="Czas trwania bana (np. 7d, 2h, 30m).", powod="Powód bana (opcjonalny).")
    async def ban_command(self, interaction: discord.Interaction, uzytkownik: discord.Member, czas_trwania: str = None, powod: str = "Brak powodu"):
        if uzytkownik.id == interaction.user.id:
            return await interaction.response.send_message("Nie możesz zbanować samego siebie!", ephemeral=True)
        if uzytkownik.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
            return await interaction.response.send_message("Nie możesz zbanować kogoś z taką samą lub wyższą rolą!", ephemeral=True)
            
        expires_at = None
        if czas_trwania:
            duration_in_seconds = time_parser.parse_duration(czas_trwania)
            if duration_in_seconds:
                expires_at = int(time.time()) + duration_in_seconds
            else:
                return await interaction.response.send_message("Nieprawidłowy format czasu trwania.", ephemeral=True)

        try:
            await uzytkownik.ban(reason=powod)
            database.add_punishment(
                guild_id=interaction.guild.id,
                user_id=uzytkownik.id,
                moderator_id=interaction.user.id,
                punishment_type='ban',
                reason=powod,
                expires_at=expires_at
            )
            duration_text = f" na czas {czas_trwania}" if czas_trwania else ""
            await interaction.response.send_message(f"Pomyślnie zbanowano {uzytkownik.mention}{duration_text}. Powód: {powod}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)
            
    @ban_command.error
    async def ban_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Nie masz uprawnień do banowania członków.", ephemeral=True)

    @app_commands.command(name="history", description="Wyświetla historię kar użytkownika.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def history_command(self, interaction: discord.Interaction, uzytkownik: discord.Member):
        cases = database.get_user_punishments(interaction.guild.id, uzytkownik.id)
        if not cases:
            return await interaction.response.send_message(f"Użytkownik {uzytkownik.mention} nie ma żadnej historii kar.", ephemeral=True)

        embed = discord.Embed(title=f"Historia kar dla {uzytkownik.name}", color=discord.Color.orange())
        
        for case in cases:
            moderator = interaction.guild.get_member(case['moderator_id'])
            mod_name = moderator.name if moderator else "Nieznany Moderator"
            timestamp = datetime.fromtimestamp(case['created_at']).strftime('%Y-%m-%d %H:%M:%S')
            reason = case['reason'] or "Brak"
            status = "Aktywna" if case['active'] else "Nieaktywna"
            
            embed.add_field(
                name=f"Kara #{case['id']} - {case['type'].capitalize()} ({status})",
                value=f"> **Moderator:** {mod_name}\n"
                      f"> **Powód:** {reason}\n"
                      f"> **Data:** {timestamp}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
