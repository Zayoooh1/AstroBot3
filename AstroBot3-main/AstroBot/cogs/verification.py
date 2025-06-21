import discord
from discord.ext import commands
from discord import app_commands
import database

class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set_verification_role", description="Ustawia rolę, którą użytkownik otrzyma po weryfikacji.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_verification_role(self, interaction: discord.Interaction, rola: discord.Role):
        database.update_server_config(guild_id=interaction.guild.id, reaction_role_id=rola.id)
        await interaction.response.send_message(f"Rola weryfikacyjna została ustawiona na {rola.mention}.", ephemeral=True)

    @app_commands.command(name="verify", description="Publikuje wiadomość weryfikacyjną na tym kanale.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verify_command(self, interaction: discord.Interaction, *, tresc: str = "Kliknij reakcję poniżej, aby się zweryfikować i uzyskać dostęp do serwera!"):
        config = database.get_server_config(interaction.guild.id)
        if not config or not config.get('reaction_role_id'):
            return await interaction.response.send_message("Najpierw ustaw rolę weryfikacyjną za pomocą `/set_verification_role`!", ephemeral=True)
            
        embed = discord.Embed(title="✅ Weryfikacja", description=tresc, color=discord.Color.green())
        
        verify_message = await interaction.channel.send(embed=embed)
        await verify_message.add_reaction("✅")
        
        database.update_server_config(guild_id=interaction.guild.id, reaction_message_id=verify_message.id)
        await interaction.response.send_message("Wiadomość weryfikacyjna została opublikowana.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return

        config = database.get_server_config(payload.guild_id)
        if not config or not config.get('reaction_message_id') or payload.message_id != config.get('reaction_message_id'):
            return

        if str(payload.emoji) == "✅":
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(config['reaction_role_id'])
            if role:
                try:
                    await payload.member.add_roles(role, reason="Weryfikacja przez reakcję")
                except discord.Forbidden:
                    print(f"Brak uprawnień do nadania roli weryfikacyjnej na serwerze {guild.name}")
            else:
                print(f"Nie znaleziono roli weryfikacyjnej na serwerze {guild.name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot))
