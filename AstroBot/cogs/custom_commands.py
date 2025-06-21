import discord
from discord.ext import commands
from discord import app_commands
import database
import json

class CustomCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="addcustomcommand", description="Dodaje nową niestandardową komendę.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(nazwa="Nazwa komendy (bez prefixu).", tresc="Treść odpowiedzi (dla embedów: JSON).")
    async def add_custom_command(self, interaction: discord.Interaction, nazwa: str, tresc: str):
        # Sprawdzamy czy to JSON
        try:
            json.loads(tresc)
            response_type = 'embed'
        except json.JSONDecodeError:
            response_type = 'text'

        command_id = database.add_custom_command(
            guild_id=interaction.guild.id,
            name=nazwa.lower(),
            response_type=response_type,
            content=tresc,
            creator_id=interaction.user.id
        )
        if command_id:
            await interaction.response.send_message(f"Komenda `!{nazwa}` została dodana.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Komenda o nazwie `!{nazwa}` już istnieje.", ephemeral=True)
            
    @app_commands.command(name="removecustomcommand", description="Usuwa niestandardową komendę.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_custom_command(self, interaction: discord.Interaction, nazwa: str):
        if database.remove_custom_command(interaction.guild.id, nazwa.lower()):
            await interaction.response.send_message(f"Komenda `!{nazwa}` została usunięta.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Nie znaleziono komendy o nazwie `!{nazwa}`.", ephemeral=True)
            
async def setup(bot: commands.Bot):
    await bot.add_cog(CustomCommandsCog(bot))
