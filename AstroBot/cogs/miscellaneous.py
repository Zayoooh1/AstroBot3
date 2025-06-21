import discord
from discord.ext import commands
from discord import app_commands
import database

class MiscellaneousCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set_feedback_channel", description="Ustawia kanał do anonimowych opinii.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_feedback_channel(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        database.update_server_config(guild_id=interaction.guild.id, feedback_channel_id=kanal.id)
        await interaction.response.send_message(f"Kanał dla opinii został ustawiony na {kanal.mention}.", ephemeral=True)

    @app_commands.command(name="feedback", description="Wysyła anonimową opinię do administracji.")
    @app_commands.describe(wiadomosc="Twoja opinia lub sugestia.")
    async def feedback(self, interaction: discord.Interaction, wiadomosc: str):
        config = database.get_server_config(interaction.guild.id)
        if not config or not config.get("feedback_channel_id"):
            return await interaction.response.send_message("Na tym serwerze nie skonfigurowano kanału do opinii.", ephemeral=True)
            
        feedback_channel_id = config["feedback_channel_id"]
        channel = self.bot.get_channel(feedback_channel_id)
        
        if not channel:
            return await interaction.response.send_message("Kanał do opinii nie został znaleziony.", ephemeral=True)
            
        embed = discord.Embed(
            title="📬 Nowa Anonimowa Opinia",
            description=wiadomosc,
            color=discord.Color.light_grey()
        )
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message("Twoja opinia została pomyślnie wysłana. Dziękujemy!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Nie mogłem wysłać Twojej opinii. Sprawdź moje uprawnienia na kanale docelowym.", ephemeral=True)
            
async def setup(bot: commands.Bot):
    await bot.add_cog(MiscellaneousCog(bot))
