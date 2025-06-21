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

        embed = discord.Embed(
            title=f"📊 Ankieta: {pytanie}",
            description="Zagłosuj używając odpowiednich reakcji!",
            color=discord.Color.blue()
        )
        
        regional_indicators = [
            '🇦', '🇧', '🇨', '🇩', '🇪', 
            '🇫', '🇬', '🇭', '🇮', '🇯'
        ]
        
        poll_text = ""
        for i, option in enumerate(options_list):
            poll_text += f"{regional_indicators[i]} - {option}\n"
            
        embed.add_field(name="Opcje:", value=poll_text, inline=False)
        if ends_at:
            embed.set_footer(text=f"Ankieta kończy się: <t:{ends_at}:R>")

        try:
            poll_message = await interaction.channel.send(embed=embed)
            poll_id = database.create_poll(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                message_id=poll_message.id,
                question=pytanie,
                created_by_id=interaction.user.id,
                ends_at=ends_at
            )

            for i, option in enumerate(options_list):
                emoji = regional_indicators[i]
                await poll_message.add_reaction(emoji)
                database.add_poll_option(poll_id, option, emoji)
            
            await interaction.response.send_message("Ankieta została utworzona.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PollsCog(bot))
