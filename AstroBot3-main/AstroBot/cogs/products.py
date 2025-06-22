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

        await interaction.response.send_message("🔎 Sprawdzanie i dodawanie produktu...", ephemeral=True)

        # Sprawdzamy, czy produkt istnieje w bazie (nawet nieaktywny)
        existing_product = database.get_watched_product_by_url(url_produktu)

        if existing_product:
            # Jeśli produkt jest już AKTYWNIE śledzony
            if existing_product['is_active']:
                await interaction.edit_original_response(content="Ten produkt jest już aktywnie śledzony.")
                return
            else:
        # Jeśli produkt jest NIEAKTYWNY, reaktywujemy go dla nowego użytkownika
                product_id = existing_product['id']
                database.reactivate_watched_product(
                    product_id=product_id,
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    notification_channel_id=kanal.id if kanal else None
                )
                await interaction.edit_original_response(content=f"Produkt (ID: {product_id}) został ponownie aktywowany na Twojej liście obserwowanych.")
                return

        # Jeśli produkt jest zupełnie nowy, kontynuujemy standardową logikę dodawania
        product_id = database.add_watched_product(
            user_id=interaction.user.id,
            url=url_produktu,
            shop_name=shop_name,
            guild_id=interaction.guild_id,
            notification_channel_id=kanal.id if kanal else None
        )
        if not product_id:
            await interaction.edit_original_response(content="Wystąpił błąd podczas dodawania produktu do bazy danych (prawdopodobnie przez unikalny URL).")
            return

        # Natychmiastowe skanowanie
        try:
            scraped_data = await self.bot.loop.run_in_executor(None, xkom_scraper.scrape_xkom_product, url_produktu)
        except Exception as e:
            await interaction.edit_original_response(content=f"Produkt dodany (ID: {product_id}), ale nie udało się pobrać wstępnych danych: {e}")
            return
            
        # Aktualizacja bazy danych
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

        # Wysyłanie powiadomienia
        notification_target_channel = kanal or (self.bot.get_channel(database.get_server_config(interaction.guild.id).get("product_report_channel_id")) if database.get_server_config(interaction.guild.id) else None)

        if notification_target_channel:
            embed = discord.Embed(title="✅ Nowy produkt dodany do śledzenia", color=discord.Color.green(), timestamp=discord.utils.utcnow())

            if scraped_data:
                product_name = scraped_data.get("name", "Nieznana nazwa")
                price_cents = scraped_data.get("price_in_cents")
                availability_str = scraped_data.get("availability_str", "Brak danych")

                price = f"{price_cents / 100:.2f} zł" if price_cents is not None else "Brak danych"

                embed.add_field(name="Produkt", value=f"[{product_name}]({url_produktu})", inline=False)
                embed.add_field(name="Aktualna cena", value=price, inline=True)
                embed.add_field(name="Dostępność", value=availability_str, inline=True)
            else:
                embed.add_field(name="Produkt", value=f"[Błąd skanowania - Możliwe zablokowanie scrapowania przez X-Kom. Dodaj proxy do scrapers/xkom_scraper.py]({url_produktu})", inline=False)

            embed.add_field(name="Dodany przez", value=interaction.user.mention, inline=False)
            embed.set_footer(text=f"ID Produktu: {product_id} | Powiadomienia na kanale: #{notification_target_channel.name}")
            
            try:
                await notification_target_channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.edit_original_response(content=f"Produkt dodany (ID: {product_id}), ale nie mogłem wysłać powiadomienia. Sprawdź moje uprawnienia.")
                return
        
        await interaction.edit_original_response(content=f"Produkt został pomyślnie dodany i zeskanowany (ID: {product_id}).")


    @app_commands.command(name="unwatch_product", description="Przestaje śledzić produkt.")
    @app_commands.describe(id_produktu="ID produktu z Twojej listy (sprawdź /my_watchlist lub /product_list).")
    async def unwatch_product_command(self, interaction: discord.Interaction, id_produktu: int):
        if not interaction.guild_id:
            return await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
        
        if database.deactivate_watched_product(id_produktu):
            await interaction.response.send_message(f"Produkt o ID {id_produktu} został usunięty z aktywnego śledzenia.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Nie znaleziono produktu o ID {id_produktu} na Twojej liście lub już jest nieaktywny.", ephemeral=True)

    
    @app_commands.command(name="my_watchlist", description="Wyświetla Twoją listę śledzonych produktów na tym serwerze.")
    async def my_watchlist_command(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild:
            await interaction.response.send_message("Ta komenda musi być użyta tylko na serwerze.", ephemeral=True)
            return

        user_products = database.get_user_watched_products(user_id=interaction.user.id, guild_id=interaction.guild_id)

        if not user_products:
            await interaction.response.send_message("Nie śledzisz obecnie żadnych produktów na tym serwerze.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Twoja Lista Śledzonych Produktów na {interaction.guild.name}", color=discord.Color.dark_blue())
        description = ""
        for product in user_products:
            name = product.get('product_name') or "Jeszcze nie zeskanowano nazwy"
            price_cents = product.get('last_known_price_cents')
            price_display = f"{price_cents / 100:.2f} zł" if price_cents is not None else "Brak danych"
            availability = product.get('last_known_availability_str') or "Brak danych"

            description += (f"**ID: {product['id']} | [{name}]({product['product_url']})**\n"
                            f"Sklep: {product['shop_name'].upper()} | Cena: {price_display} | Dostępność: {availability}\n\n")

        if len(description) > 4000: description = description[:3990] + "\n... (lista zbyt długa)"
        embed.description = description if description else "Brak produktów na liście."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="product_list", description="[Admin] Wyświetla wszystkie śledzone produkty na serwerze.")
    @app_commands.checks.has_permissions(administrator=True)
    async def product_list_command(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild:
            return await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)

        all_products = database.get_all_active_watched_products()
        server_products = [p for p in all_products if p['guild_id'] == interaction.guild_id]

        if not server_products:
            return await interaction.response.send_message("Na tym serwerze nie są śledzone żadne produkty.", ephemeral=True)

        embed = discord.Embed(
            title=f"📋 Lista Wszystkich Śledzonych Produktów na {interaction.guild.name}",
            color=discord.Color.blue()
        )
        
        description = ""
        for product in server_products:
            name = product.get('product_name') or "Brak nazwy"
            user = self.bot.get_user(product['user_id_who_added'])
            added_by = user.mention if user else f"ID: {product['user_id_who_added']}"
            
            description += (f"**ID: {product['id']} | [{name}]({product['product_url']})**\n"
                            f"> Dodany przez: {added_by}\n")

        if len(description) > 4000:
            description = description[:3990] + "\n... (lista zbyt długa)"
            
        embed.description = description
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @product_list_command.error
    async def product_list_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Nie masz uprawnień do użycia tej komendy.", ephemeral=True)

    @app_commands.command(name="set_product_report_channel", description="Ustawia domyślny kanał dla raportów produktowych.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(kanal="Domyślny kanał tekstowy, na który będą wysyłane raporty.")
    async def set_product_report_channel_command(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        if not interaction.guild_id:
            await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
            return
        try:
            database.update_server_config(guild_id=interaction.guild_id, product_report_channel_id=kanal.id)
            await interaction.response.send_message(f"Kanał dla codziennych raportów produktowych został ustawiony na {kanal.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)

    @app_commands.command(name="set_product_report_time", description="Ustawia godzinę (UTC) wysyłania raportów.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(godzina_utc="Godzina w formacie HH:MM (np. 23:00) czasu UTC.")
    async def set_product_report_time_command(self, interaction: discord.Interaction, godzina_utc: str):
        if not interaction.guild_id:
            await interaction.response.send_message("Ta komenda musi być użyta na serwerze.", ephemeral=True)
            return

        if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", godzina_utc):
            return await interaction.response.send_message("Nieprawidłowy format godziny. Użyj HH:MM (np. 08:30, 23:59).", ephemeral=True)

        try:
            database.update_server_config(guild_id=interaction.guild_id, product_report_time_utc=godzina_utc)
            await interaction.response.send_message(f"Godzina codziennych raportów produktowych została ustawiona na {godzina_utc} UTC.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Wystąpił błąd: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProductsCog(bot))
