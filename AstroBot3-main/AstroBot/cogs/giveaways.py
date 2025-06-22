import discord
from discord.ext import commands
from discord import app_commands
import database
import time
from utils import time_parser
import random

class GiveawaysCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create_giveaway", description="Tworzy nowe losowanie (giveaway).")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        nagroda="Co jest do wygrania?",
        czas_trwania="Jak długo ma trwać losowanie (np. 1d, 12h, 30m)?",
        zwyciezcy="Ilu będzie zwycięzców?",
        kanal="Na którym kanale ogłosić losowanie?",
        rola_wymagana="Wymagana rola do wzięcia udziału (opcjonalnie).",
        min_poziom="Minimalny poziom XP do wzięcia udziału (opcjonalnie)."
    )
    async def create_giveaway(self, interaction: discord.Interaction, nagroda: str, czas_trwania: str, zwyciezcy: int, kanal: discord.TextChannel, rola_wymagana: discord.Role = None, min_poziom: int = None):
        duration_seconds = time_parser.parse_duration(czas_trwania)
        if not duration_seconds:
            return await interaction.response.send_message("Nieprawidłowy format czasu trwania.", ephemeral=True)
            
        ends_at = int(time.time()) + duration_seconds
        
        # Krok 1: Stwórz wpis w bazie danych, aby uzyskać ID
        try:
            giveaway_id = database.create_giveaway(
                guild_id=interaction.guild.id,
                channel_id=kanal.id,
                prize=nagroda,
                winner_count=zwyciezcy,
                created_by_id=interaction.user.id,
                ends_at=ends_at,
                required_role_id=rola_wymagana.id if rola_wymagana else None,
                min_level=min_poziom
            )
        except Exception as e:
            return await interaction.response.send_message(f"Błąd bazy danych przy tworzeniu losowania: {e}", ephemeral=True)

        # Przygotowanie embeda
        embed = discord.Embed(
            title=f"🎉 **LOSOWANIE: {nagroda}**",
            description=f"Zareaguj 🎉 aby wziąć udział!\n"
                        f"Kończy się: <t:{ends_at}:R>\n"
                        f"Prowadzący: {interaction.user.mention}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Zwycięzcy: {zwyciezcy}")

        # Krok 2: Wyślij wiadomość
        try:
            await interaction.response.send_message(f"Tworzenie losowania na kanale {kanal.mention}...", ephemeral=True)
            giveaway_message = await kanal.send(embed=embed)
        except Exception as e:
            await interaction.edit_original_response(content=f"Nie udało się wysłać wiadomości losowania: {e}")
            return

        # Krok 3: Zaktualizuj bazę o ID wiadomości i dodaj reakcję
        try:
            database.set_giveaway_message_id(giveaway_id, giveaway_message.id)
            await giveaway_message.add_reaction("🎉")
            await interaction.edit_original_response(content="Losowanie zostało pomyślnie utworzone!")
        except Exception as e:
            await interaction.edit_original_response(content=f"Wystąpił błąd podczas finalizowania losowania: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawaysCog(bot))
