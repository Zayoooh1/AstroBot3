import discord
from discord.ext import commands
from discord import app_commands
import database
import time
from utils import time_parser

class PollsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create_poll", description="Tworzy ankietę z opcjami.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        pytanie="Pytanie ankiety.",
        opcje="Opcje odpowiedzi, oddzielone średnikiem ';'.",
        czas_trwania="Czas trwania ankiety (np. 1d, 1h, 10m) (opcjonalnie)."
    )
    async def create_poll(self, interaction: discord.Interaction, pytanie: str, opcje: str, czas_trwania: str = None):
        options_list = [opt.strip() for opt in opcje.split(';') if opt.strip()]
        if len(options_list) < 2 or len(options_list) > 10:
            return await interaction.response.send_message("Ankieta musi mieć od 2 do 10 opcji.", ephemeral=True)

        ends_at = None
        if czas_trwania:
            duration_seconds = time_parser.parse_duration(czas_trwania)
            if duration_seconds:
                ends_at = int(time.time()) + duration_seconds
            else:
                return await interaction.response.send_message("Nieprawidłowy format czasu trwania.", ephemeral=True)

        # Krok 1: Stwórz ankietę w bazie, aby uzyskać jej ID
        try:
            poll_id = database.create_poll(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                question=pytanie,
                created_by_id=interaction.user.id,
                ends_at=ends_at
            )
        except Exception as e:
            return await interaction.response.send_message(f"Błąd bazy danych przy tworzeniu ankiety: {e}", ephemeral=True)

        # Przygotowanie embeda
        embed = discord.Embed(
            title=f"📊 Ankieta: {pytanie}",
            description="Zagłosuj używając odpowiednich reakcji!",
            color=discord.Color.blue()
        )
        regional_indicators = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯']
        
        poll_text = ""
        for i, option in enumerate(options_list):
            poll_text += f"{regional_indicators[i]} - {option}\n"
            
        embed.add_field(name="Opcje:", value=poll_text, inline=False)
        if ends_at:
            embed.set_footer(text=f"Ankieta kończy się: <t:{ends_at}:R>")

        # Krok 2: Wyślij wiadomość na kanał
        try:
            # Użyj followup, ponieważ interakcja musi zostać potwierdzona
            await interaction.response.send_message("Tworzenie ankiety...", ephemeral=True)
            poll_message = await interaction.channel.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Nie udało się wysłać wiadomości ankiety: {e}", ephemeral=True)
            return

        # Krok 3: Zaktualizuj bazę o ID wiadomości i dodaj reakcje
        try:
            database.set_poll_message_id(poll_id, poll_message.id)
            
            for i, option in enumerate(options_list):
                emoji = regional_indicators[i]
                await poll_message.add_reaction(emoji)
                database.add_poll_option(poll_id, option, emoji)
            
            await interaction.edit_original_response(content="Ankieta została pomyślnie utworzona.")
        except Exception as e:
            await interaction.followup.send(f"Wystąpił błąd podczas finalizowania ankiety: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PollsCog(bot))
