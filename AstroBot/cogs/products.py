import discord
from discord.ext import commands
from discord import app_commands
import database
import re

class ProductsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="watch_product", description="Dodaje produkt do listy śledzenia.")
    @app_commands.describe(url_produktu="Pełny link URL do strony produktu (obecnie tylko X-Kom).")
    async def watch_product_command(self, interaction: discord.Interaction, url_produktu: str):
        if not interaction.guild_id:
            await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
            return

        shop_name = "xkom" if "x-kom.pl" in url_produktu.lower() else None
        if not shop_name:
            await interaction.response.send_message("Nie rozpoznano wspieranego sklepu. Obecnie tylko X-Kom.", ephemeral=True)
            return

        if database.get_watched_product_by_url(url_produktu):
            await interaction.response.send_message("Ten produkt jest już śledzony.", ephemeral=True)
            return

        product_id = database.add_watched_product(
            user_id=interaction.user.id,
            url=url_produktu,
            shop_name=shop_name,
            guild_id=interaction.guild_id
        )

        if product_id:
            await interaction.response.send_message(f"Produkt dodany do listy śledzenia (ID: {product_id}).", ephemeral=True)
        else:
            await interaction.response.send_message("Nie udało się dodać produktu.", ephemeral=True)

    @app_commands.command(name="unwatch_product", description="Przestaje śledzić produkt.")
    @app_commands.describe(id_produktu="ID produktu z Twojej listy (sprawdź /my_watchlist).")
    async def unwatch_product_command(self, interaction: discord.Interaction, id_produktu: int):
        if not interaction.guild_id:
            return await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
        
        if database.deactivate_watched_product(id_produktu):
            await interaction.response.send_message(f"Produkt o ID {id_produktu} usunięty ze śledzenia.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Nie znaleziono produktu o ID {id_produktu}.", ephemeral=True)

    @app_commands.command(name="my_watchlist", description="Wyświetla Twoją listę śledzonych produktów.")
    async def my_watchlist_command(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild:
            return await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)

        user_products = database.get_user_watched_products(user_id=interaction.user.id, guild_id=interaction.guild_id)
        if not user_products:
            return await interaction.response.send_message("Nie śledzisz żadnych produktów.", ephemeral=True)

        embed = discord.Embed(title=f"Twoja lista śledzenia na {interaction.guild.name}", color=discord.Color.dark_blue())
        description = []
        for p in user_products:
            name = p.get('product_name') or "Brak nazwy"
            price = f"{p['last_known_price_cents'] / 100:.2f} zł" if p['last_known_price_cents'] is not None else "Brak danych"
            avail = p.get('last_known_availability_str') or "Brak danych"
            description.append(f"**ID: {p['id']} | [{name}]({p['product_url']})**\n> Cena: {price} | Dostępność: {avail}")
        
        embed.description = "\n\n".join(description)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="set_product_report_channel", description="Ustawia kanał dla codziennych raportów produktowych.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(kanal="Kanał tekstowy, na który będą wysyłane raporty.")
    async def set_product_report_channel_command(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        if not interaction.guild_id: return
        try:
            database.update_server_config(guild_id=interaction.guild_id, product_report_channel_id=kanal.id)
            await interaction.response.send_message(f"Kanał raportów ustawiono na {kanal.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)

    @app_commands.command(name="set_product_report_time", description="Ustawia godzinę (UTC) wysyłania raportów.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(godzina_utc="Godzina w formacie HH:MM (np. 23:00) czasu UTC.")
    async def set_product_report_time_command(self, interaction: discord.Interaction, godzina_utc: str):
        if not interaction.guild_id: return
        if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", godzina_utc):
            return await interaction.response.send_message("Nieprawidłowy format godziny. Użyj HH:MM.", ephemeral=True)
        try:
            database.update_server_config(guild_id=interaction.guild_id, product_report_time_utc=godzina_utc)
            await interaction.response.send_message(f"Godzinę raportów ustawiono na {godzina_utc} UTC.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProductsCog(bot))
