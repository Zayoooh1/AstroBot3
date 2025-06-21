import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import database
import leveling
import random
import time
import json
import asyncio
import collections
import re
from datetime import datetime, timedelta, time as dt_time, UTC
from scrapers import xkom_scraper

# --- Inicjalizacja ---
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Konfiguracja intentów bota
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Słowniki do zarządzania stanem
active_quizzes = {}
last_report_sent_date = {}
last_xp_gain_timestamp = {}
user_recent_messages = collections.defaultdict(lambda: collections.deque(maxlen=3))

# --- Funkcje Pomocnicze (Placeholdery) ---
# Te funkcje powinny zostać rozwinięte lub przeniesione do odpowiednich cogów.
async def send_quiz_question_dm(user: discord.User):
    pass
async def process_quiz_results(user: discord.User):
    pass
async def log_moderation_action(*args, **kwargs):
    # Ta logika powinna zostać przeniesiona do coga moderacyjnego
    # i wywoływana z odpowiednich komend i eventów.
    print(f"Logowanie akcji: {args}, {kwargs}")
    pass
async def _handle_giveaway_end_logic(*args, **kwargs):
    pass

# --- Główny Event `on_ready` ---
@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user}')
    try:
        database.init_db()
        print("Baza danych zainicjalizowana.")
        
        # Ładowanie wszystkich cogów z folderu /cogs
        cogs_path = './AstroBot/cogs'
        if not os.path.isdir(cogs_path):
            cogs_path = './cogs'

        for filename in os.listdir(cogs_path):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    print(f"Załadowano cog: {filename}")
                except Exception as e:
                    print(f"Nie udało się załadować coga {filename}: {e}")
        
        # Synchronizacja komend
        synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend(y) globalnie.")

    except Exception as e:
        print(f"Wystąpił błąd podczas inicjalizacji lub synchronizacji komend: {e}")

    # Uruchamianie zadań w tle
    task_map = {
        "check_expired_roles": check_expired_roles,
        "check_expired_punishments_task": check_expired_punishments_task,
        "check_ended_giveaways_task": check_ended_giveaways_task,
        "scan_products_task": scan_products_task,
        "daily_product_report_task": daily_product_report_task
    }
    for task_name_str, task_obj in task_map.items():
        if task_obj and hasattr(task_obj, 'start') and not task_obj.is_running():
            try:
                task_obj.start()
                print(f"Uruchomiono zadanie '{task_name_str}'.")
            except RuntimeError as e:
                 print(f"Błąd podczas uruchamiania zadania '{task_name_str}': {e}")

# --- Główny Event `on_message` ---
@bot.event
async def on_message(message: discord.Message):
    if isinstance(message.channel, discord.DMChannel) and message.author.id in active_quizzes and not message.author.bot:
        user_id_quiz = message.author.id
        quiz_state = active_quizzes[user_id_quiz]
        if quiz_state["current_q_index"] < len(quiz_state["questions"]):
            quiz_state["answers"].append(message.content)
            quiz_state["current_q_index"] += 1
            await send_quiz_question_dm(message.author)
        return

    if message.author.bot or not message.guild:
        return

    message_deleted_by_moderation = False
    server_config = database.get_server_config(message.guild.id)

    if server_config:
        # Logika Automoderacji
        if server_config.get("filter_profanity_enabled", True):
            banned_words_list = database.get_banned_words(message.guild.id)
            if any(re.search(r"(?i)\b" + re.escape(banned_word) + r"\b", message.content) for banned_word in banned_words_list):
                try:
                    await message.delete()
                    await log_moderation_action(message.guild, message.author, message.content, "Wykryto zakazane słowo.", message.channel, server_config.get("moderation_log_channel_id"))
                    message_deleted_by_moderation = True
                    await message.author.send(f"Twoja wiadomość na **{message.guild.name}** została usunięta (niedozwolone słownictwo).", delete_after=10)
                except Exception as e: print(f"Błąd auto-moderacji (profanity): {e}")

    if message_deleted_by_moderation:
        return

    if server_config:
        prefix = server_config.get("custom_command_prefix", "!")
        if message.content.startswith(prefix):
            pass
            
    # Logika nadawania XP
    guild_id = message.guild.id
    user_id = message.author.id
    current_time = time.time()
    user_cooldown_key = (guild_id, user_id)
    last_gain = last_xp_gain_timestamp.get(user_cooldown_key, 0)

    if current_time - last_gain > leveling.XP_COOLDOWN_SECONDS:
        xp_to_add = random.randint(leveling.XP_PER_MESSAGE_MIN, leveling.XP_PER_MESSAGE_MAX)
        new_total_xp = database.add_xp(guild_id, user_id, xp_to_add)
        last_xp_gain_timestamp[user_cooldown_key] = current_time

        user_stats_xp = database.get_user_stats(guild_id, user_id)
        current_level_db_xp = user_stats_xp['level']
        calculated_level_xp = leveling.get_level_from_xp(new_total_xp)

        if calculated_level_xp > current_level_db_xp:
            database.set_user_level(guild_id, user_id, calculated_level_xp)
            
    await bot.process_commands(message)


# --- Zadania w Tle (Tasks) ---
@tasks.loop(hours=4)
async def scan_products_task():
    await bot.wait_until_ready()
    print("[PRODUCT_SCAN_TASK] Rozpoczynam skanowanie produktów...")
    active_products = database.get_all_active_watched_products()
    if not active_products:
        print("[PRODUCT_SCAN_TASK] Brak aktywnych produktów do skanowania.")
        return

    for product in active_products:
        print(f"[PRODUCT_SCAN_TASK] Skanuję: {product['product_url']} (ID: {product['id']})")
        scraped_data = None
        if product['shop_name'] == 'xkom':
            await asyncio.sleep(random.randint(5, 15))
            scraped_data = xkom_scraper.scrape_xkom_product(product['product_url'])

        current_scan_time = int(time.time())
        if scraped_data:
            name = scraped_data.get("name")
            price_cents = scraped_data.get("price_in_cents")
            availability_str = scraped_data.get("availability_str")

            database.update_watched_product_data(
                product_id=product['id'],
                name=name if name else product.get('product_name'),
                price_cents=price_cents,
                availability_str=availability_str,
                scanned_at=current_scan_time
            )
            database.add_price_history_entry(
                watched_product_id=product['id'],
                scan_date=current_scan_time,
                price_cents=price_cents,
                availability_str=availability_str
            )
            price_display = f"{price_cents / 100:.2f} zł" if price_cents is not None else "N/A"
            print(f"[PRODUCT_SCAN_TASK] Zaktualizowano ID {product['id']}: Cena: {price_display}, Dostępność: {availability_str}")
        else:
            print(f"[PRODUCT_SCAN_TASK] Nie udało się zeskanować ID {product['id']}. Zapisuję czas skanowania.")
            database.update_watched_product_data(product_id=product['id'], name=None, price_cents=None, availability_str=None, scanned_at=current_scan_time)
            database.add_price_history_entry(watched_product_id=product['id'], scan_date=current_scan_time, price_cents=None, availability_str="Błąd skanowania")
    print("[PRODUCT_SCAN_TASK] Zakończono skanowanie produktów.")

@tasks.loop(minutes=15)
async def daily_product_report_task():
    await bot.wait_until_ready()
    now_utc = datetime.now(UTC)
    guild_configs = database.get_all_guilds_with_product_report_config()

    for config in guild_configs:
        guild_id = config["guild_id"]
        report_channel_id = config.get("report_channel_id")
        report_time_str = config.get("report_time_utc")

        if not report_channel_id or not report_time_str:
            continue

        today_date_str = now_utc.strftime("%Y-%m-%d")
        if last_report_sent_date.get(guild_id) == today_date_str:
            continue

        try:
            report_hour, report_minute = map(int, report_time_str.split(':'))
            if now_utc.hour == report_hour and now_utc.minute >= report_minute:
                guild = bot.get_guild(guild_id)
                if not guild: continue
                report_channel = guild.get_channel(report_channel_id)
                if not report_channel or not isinstance(report_channel, discord.TextChannel):
                    print(f"[REPORT_TASK] Nie znaleziono kanału raportów (ID: {report_channel_id}) na {guild.name}")
                    continue
                print(f"[REPORT_TASK] Generowanie raportu dla {guild.name} (ID: {guild_id})")

                product_changes = database.get_product_changes_for_report(guild_id, hours_ago=24)
                top_drops = database.get_top_price_drops(guild_id, hours_ago=24, limit=5)

                embed = discord.Embed(title=f"📊 Dzienny Raport Produktowy - {now_utc.strftime('%Y-%m-%d')}", color=discord.Color.blue(), timestamp=now_utc)
                embed.set_footer(text=f"Serwer: {guild.name}")
                # ... (reszta logiki budowania embeda) ...

                await report_channel.send(embed=embed)
                last_report_sent_date[guild_id] = today_date_str
                print(f"[REPORT_TASK] Wysyłano raport dla {guild.name}")
        except Exception as e:
            print(f"Błąd przetwarzania konfiguracji raportu dla gildii {guild_id}: {e}")

@tasks.loop(hours=1)
async def check_expired_roles():
    await bot.wait_until_ready()
    print("[EXPIRED_ROLES_TASK] Sprawdzam wygasłe role...")
    expired_roles = database.get_expired_roles(int(time.time()))
    for entry in expired_roles:
        guild = bot.get_guild(entry['guild_id'])
        if not guild: continue
        member = guild.get_member(entry['user_id'])
        if not member:
            database.remove_timed_role(entry['id'])
            continue
        role = guild.get_role(entry['role_id'])
        if not role:
            database.remove_timed_role(entry['id'])
            continue
        if role in member.roles:
            try:
                await member.remove_roles(role, reason="Wygasła rola czasowa")
            except Exception as e:
                print(f"Błąd usuwania wygasłej roli: {e}")
        database.remove_timed_role(entry['id'])
    print("[EXPIRED_ROLES_TASK] Zakończono sprawdzanie.")

@tasks.loop(minutes=5)
async def check_expired_punishments_task():
    await bot.wait_until_ready()
    print("[EXPIRED_PUNISHMENTS_TASK] Sprawdzam wygasłe kary...")
    expired_punishments = database.get_expired_active_punishments(int(time.time()))
    for punishment in expired_punishments:
        guild = bot.get_guild(punishment['guild_id'])
        if not guild: continue
        try:
            if punishment['type'] == "mute":
                member = guild.get_member(punishment['user_id'])
                if member:
                    server_config = database.get_server_config(guild.id)
                    mute_role_id = server_config.get("muted_role_id")
                    if mute_role_id:
                        mute_role = guild.get_role(mute_role_id)
                        if mute_role and mute_role in member.roles:
                            await member.remove_roles(mute_role, reason="Wygasło wyciszenie")
            elif punishment['type'] == "ban":
                await guild.unban(discord.Object(id=punishment['user_id']), reason="Wygasł tymczasowy ban")
        except Exception as e:
            print(f"Błąd zdejmowania kary: {e}")
        finally:
            database.deactivate_punishment(punishment['id'])
    print("[EXPIRED_PUNISHMENTS_TASK] Zakończono sprawdzanie.")

@tasks.loop(minutes=1)
async def check_ended_giveaways_task():
    await bot.wait_until_ready()
    print("[GIVEAWAY_TASK] Sprawdzam zakończone giveaway'e...")
    ended_giveaways = database.get_active_giveaways_to_end(int(time.time()))
    for giveaway in ended_giveaways:
        guild = bot.get_guild(giveaway['guild_id'])
        if not guild: continue
        channel = guild.get_channel(giveaway['channel_id'])
        if not channel: continue
        try:
            message = await channel.fetch_message(giveaway['message_id'])
            await _handle_giveaway_end_logic(message, giveaway)
        except Exception as e:
            print(f"Błąd kończenia giveaway'a: {e}")
        finally:
            database.end_giveaway(giveaway['id'], [])
    print("[GIVEAWAY_TASK] Zakończono sprawdzanie.")

# --- Uruchomienie Bota ---
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Błąd: Brak tokenu bota. Upewnij się, że plik .env zawiera DISCORD_BOT_TOKEN.")
