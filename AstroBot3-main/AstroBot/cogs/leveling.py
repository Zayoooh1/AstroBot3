import discord
from discord.ext import commands
from discord import app_commands
import database
import leveling

class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rank", description="Wyświetla Twój aktualny poziom, XP i rangę na serwerze.")
    @app_commands.describe(uzytkownik="Sprawdź rangę innego użytkownika (opcjonalnie).")
    async def rank_command(self, interaction: discord.Interaction, uzytkownik: discord.Member = None):
        if not interaction.guild:
            await interaction.response.send_message("Tej komendy można używać tylko na serwerze.", ephemeral=True)
            return

        target_user = uzytkownik or interaction.user
        
        stats = database.get_user_stats(interaction.guild.id, target_user.id)
        current_xp = stats['xp']
        current_level = stats['level']

        xp_needed, next_level_gate = leveling.xp_to_next_level(current_xp, current_level)
        
        rank_info = database.get_user_rank_in_server(interaction.guild.id, target_user.id)
        rank_str = f"#{rank_info[0]}/{rank_info[1]}" if rank_info else "Brak w rankingu"

        embed = discord.Embed(
            title=f"Ranga dla {target_user.display_name}",
            color=target_user.color
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(name="Poziom", value=f"**{current_level}**", inline=True)
        embed.add_field(name="Ranga", value=f"**{rank_str}**", inline=True)
        embed.add_field(name="Doświadczenie (XP)", value=f"**{current_xp} / {next_level_gate}**", inline=False)
        
        current_level_xp_start = leveling.total_xp_for_level(current_level)
        xp_in_current_level = current_xp - current_level_xp_start
        xp_for_this_level_up = next_level_gate - current_level_xp_start
        
        progress_percentage = (xp_in_current_level / xp_for_this_level_up) * 100 if xp_for_this_level_up > 0 else 100.0
        progress_bar = "█" * int(progress_percentage / 10) + "░" * (10 - int(progress_percentage / 10))
        
        embed.add_field(
            name=f"Postęp do poziomu {current_level + 1}",
            value=f"`{progress_bar}` ({progress_percentage:.2f}%)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Wyświetla top 10 użytkowników z najwyższym poziomem na serwerze.")
    async def leaderboard_command(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Tej komendy można używać tylko na serwerze.", ephemeral=True)
            return

        leaderboard_data = database.get_server_leaderboard(interaction.guild.id, limit=10)

        if not leaderboard_data:
            await interaction.response.send_message("Na tym serwerze nikt jeszcze nie zdobył żadnych punktów XP.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🏆 Ranking Serwera - {interaction.guild.name}",
            description="Top 10 użytkowników z największą ilością punktów doświadczenia.",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for i, entry in enumerate(leaderboard_data):
            user = interaction.guild.get_member(entry['user_id'])
            user_name = user.display_name if user else f"Użytkownik (ID: {entry['user_id']})"
            leaderboard_text += f"**{i+1}. {user_name}**\n> Poziom: `{entry['level']}` | XP: `{entry['xp']}`\n"

        embed.add_field(name="Najlepsi użytkownicy:", value=leaderboard_text, inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
