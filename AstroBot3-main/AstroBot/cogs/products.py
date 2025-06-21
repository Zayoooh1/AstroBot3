import discord
from discord.ext import commands
from discord import app_commands
import database
import re
import time
import asyncio
from scrapers import xkom_scraper # Importujemy nasz scraper

class ProductsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="watch_product", description="Dodaje produkt do listy śledzenia i od razu go skanuje.")
    @app_commands.describe(
        url_produktu="Pełny link URL do strony produktu (obecnie tylko X-Kom).",
        kanal="Kanał dla powiadomień o tym produkcie (opcjonalnie, domyślnie globalny)."
    )
    async def watch_product_command(self, interaction: discord.Interaction, url_produktu: str, kanal: discord.TextChannel = None):
        if not interaction.guild_id:
            await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
            return

        shop_name = "xkom" if "x-kom.pl" in url_produktu.lower() else None
        if not shop_name:
            await interaction.response.send_message("Nie rozpoznano wspieranego sklepu. Obecnie tylko X-Kom.", ephemeral=True)
            return

        await interaction.response.send_message("🔎 Dodawanie i skanowanie produktu... To może chwilę potrwać.", ephemeral=True)

        if database.get_watched_product_by_url(url_produktu):
            await interaction.edit_original_response(content="Ten produkt jest już śledzony.")
            return

        # Krok 1: Dodanie produktu do bazy danych z informacją o kanale
        product_id = database.add_watched_product(
            user_id=interaction.user.id,
            url=url_produktu,
            shop_name=shop_name,
            guild_id=interaction.guild_id,
            notification_channel_id=kanal.id if kanal else None # Zapisujemy ID kanału
        )
        if not product_id:
            await interaction.edit_original_response(content="Wystąpił błąd podczas dodawania produktu do bazy danych.")
            return

        # Krok 2: Natychmiastowe skanowanie produktu
        try:
            scraped_data = await self.bot.loop.run_in_executor(None, xkom_scraper.scrape_xkom_product, url_produktu)
        except Exception as e:
            await interaction.edit_original_response(content=f"Produkt dodany (ID: {product_id}), ale nie udało się pobrać wstępnych danych: {e}")
            return
            
        # Krok 3: Aktualizacja bazy danych o zeskanowane informacje
        if scraped_data:
            scan_time = int(time.time())
            database.update_watched_product_data(
                product_id=product_id, name=scraped_data.get("name"),
                price_cents=scraped_data.get("price_in_cents"),
                availability_str=scraped_data.get("availability_str"),
                scanned_at=scan_time
            )
            database.add_price_history_entry(
                watched_product_id=product_id, scan_date=scan_time,
                price_cents=scraped_data.get("price_in_cents"),
                availability_str=scraped_data.get("availability_str")
            )

        # Krok 4: Ustalenie kanału docelowego i wysłanie powiadomienia
        notification_target_channel = kanal
        if not notification_target_channel:
            # Jeśli użytkownik nie podał kanału, użyj globalnego
            config = database.get_server_config(interaction.guild.id)
            report_channel_id = config.get("product_report_channel_id")
            if report_channel_id:
                notification_target_channel = self.bot.get_channel(report_channel_id)

        if notification_target_channel:
            embed = discord.Embed(title="✅ Nowy produkt dodany do śledzenia", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            product_name = scraped_data.get("name", "Nie udało się pobrać nazwy") if scraped_data else "Błąd skanowania"
            embed.add_field(name="Produkt", value=f"[{product_name}]({url_produktu})", inline=False)
            
            if scraped_data:
                price = f"{scraped_data['price_in_cents'] / 100:.2f} zł" if scraped_data.get('price_in_cents') is not None else "Brak danych"
                avail = scraped_data.get('availability_str') or "Brak danych"
                embed.add_field(name="Aktualna cena", value=price, inline=True)
                embed.add_field(name="Dostępność", value=avail, inline=True)
            
            embed.add_field(name="Dodany przez", value=interaction.user.mention, inline=False)
            embed.set_footer(text=f"ID Produktu: {product_id} | Powiadomienia na kanale: #{notification_target_channel.name}")
            
            try:
                await notification_target_channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.edit_original_response(content=f"Produkt dodany (ID: {product_id}), ale nie mogłem wysłać powiadomienia. Sprawdź moje uprawnienia na kanale docelowym.")
                return
        
        await interaction.edit_original_response(content=f"Produkt został pomyślnie dodany i zeskanowany (ID: {product_id}).")


    @app_commands.command(name="unwatch_product", description="Przestaje śledzić produkt.")
    @app_commands.describe(id_produktu="ID produktu z Twojej listy (sprawdź /my_watchlist).")
    async def unwatch_product_command(self, interaction: discord.Interaction, id_produktu: int):
        # ... (bez zmian) ...
        pass
    
    @app_commands.command(name="my_watchlist", description="Wyświetla Twoją listę śledzonych produktów.")
    async def my_watchlist_command(self, interaction: discord.Interaction):
        # ... (bez zmian) ...
        pass

    @app_commands.command(name="set_product_report_channel", description="Ustawia domyślny kanał dla raportów produktowych.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(kanal="Domyślny kanał tekstowy, na który będą wysyłane raporty.")
    async def set_product_report_channel_command(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        # ... (bez zmian) ...
        pass

    @app_commands.command(name="set_product_report_time", description="Ustawia godzinę (UTC) wysyłania raportów.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(godzina_utc="Godzina w formacie HH:MM (np. 23:00) czasu UTC.")
    async def set_product_report_time_command(self, interaction: discord.Interaction, godzina_utc: str):
        # ... (bez zmian) ...
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ProductsCog(bot))
