import sqlite3
import time
import json

DB_NAME = 'bot_config.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabela konfiguracji serwera
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS server_configs (
        guild_id INTEGER PRIMARY KEY,
        welcome_message_content TEXT,
        reaction_role_id INTEGER,
        reaction_message_id INTEGER,
        unverified_role_id INTEGER,
        verified_role_id INTEGER,
        moderation_log_channel_id INTEGER,
        filter_profanity_enabled BOOLEAN DEFAULT TRUE,
        filter_spam_enabled BOOLEAN DEFAULT TRUE,
        filter_invites_enabled BOOLEAN DEFAULT TRUE,
        muted_role_id INTEGER,
        moderator_actions_log_channel_id INTEGER,
        custom_command_prefix TEXT DEFAULT '!',
        ticket_category_id INTEGER,
        ticket_log_channel_id INTEGER,
        ticket_support_role_ids_json TEXT DEFAULT '[]',
        feedback_channel_id INTEGER,
        product_report_channel_id INTEGER,
        product_report_time_utc TEXT
    )
    """)

    # Tabela ról czasowych
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timed_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        expiration_timestamp INTEGER NOT NULL
    )
    """)

    # Tabela aktywności użytkowników (XP, poziomy)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message_count INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """)

    # Tabela kar
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS punishments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        moderator_id INTEGER NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('mute', 'ban', 'kick', 'warn')),
        reason TEXT,
        expires_at INTEGER,
        active BOOLEAN DEFAULT TRUE,
        created_at INTEGER NOT NULL
    )
    """)

    # Zaktualizowana tabela śledzonych produktów
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id_who_added INTEGER NOT NULL,
        product_url TEXT NOT NULL UNIQUE,
        shop_name TEXT NOT NULL,
        product_name TEXT,
        last_known_price_cents INTEGER,
        last_known_availability_str TEXT,
        last_scanned_at INTEGER,
        is_active BOOLEAN DEFAULT TRUE,
        notification_channel_id INTEGER 
    )
    """)

    # Tabela historii cen
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        watched_product_id INTEGER NOT NULL,
        scan_date INTEGER NOT NULL,
        price_cents INTEGER,
        availability_str TEXT,
        FOREIGN KEY(watched_product_id) REFERENCES watched_products(id) ON DELETE CASCADE
    )
    """)
    
    # Inne tabele...
    cursor.execute("CREATE TABLE IF NOT EXISTS giveaways (id INTEGER PRIMARY KEY, guild_id INTEGER, channel_id INTEGER, message_id INTEGER, prize TEXT, winner_count INTEGER, created_by_id INTEGER, created_at INTEGER, ends_at INTEGER, is_active BOOLEAN, required_role_id INTEGER, min_level INTEGER, winners_json TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS polls (id INTEGER PRIMARY KEY, guild_id INTEGER, channel_id INTEGER, message_id INTEGER, question TEXT, created_by_id INTEGER, created_at INTEGER, ends_at INTEGER, is_active BOOLEAN, results_message_id INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS poll_options (id INTEGER PRIMARY KEY, poll_id INTEGER, option_text TEXT, reaction_emoji TEXT, FOREIGN KEY(poll_id) REFERENCES polls(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS custom_commands (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, command_name TEXT NOT NULL, response_type TEXT, response_content TEXT, created_by_id INTEGER, created_at INTEGER, UNIQUE(guild_id, command_name))")
    cursor.execute("CREATE TABLE IF NOT EXISTS quiz_questions (id INTEGER PRIMARY KEY, guild_id INTEGER, question TEXT, answer TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS banned_words (id INTEGER PRIMARY KEY, guild_id INTEGER, word TEXT, UNIQUE(guild_id, word))")
    cursor.execute("CREATE TABLE IF NOT EXISTS level_rewards (id INTEGER PRIMARY KEY, guild_id INTEGER, level INTEGER, role_id_to_grant INTEGER, custom_message_on_level_up TEXT, UNIQUE(guild_id, level))")
    
    conn.commit()
    conn.close()

# --- Funkcje Konfiguracji Serwera ---
def update_server_config(guild_id: int, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO server_configs (guild_id) VALUES (?)", (guild_id,))

    updates = []
    params = []
    for key, value in kwargs.items():
        if value is not None:
            updates.append(f"{key} = ?")
            params.append(value)
    
    if updates:
        sql = f"UPDATE server_configs SET {', '.join(updates)} WHERE guild_id = ?"
        params.append(guild_id)
        cursor.execute(sql, tuple(params))
    
    conn.commit()
    conn.close()

def get_server_config(guild_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}
    
# --- Funkcje dla Ról Czasowych ---
def add_timed_role(guild_id: int, user_id: int, role_id: int, expiration_timestamp: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO timed_roles (guild_id, user_id, role_id, expiration_timestamp) VALUES (?, ?, ?, ?)",
                   (guild_id, user_id, role_id, expiration_timestamp))
    conn.commit()
    conn.close()

def get_expired_roles(current_timestamp: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM timed_roles WHERE expiration_timestamp <= ?", (current_timestamp,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def remove_timed_role(timed_role_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM timed_roles WHERE id = ?", (timed_role_id,))
    conn.commit()
    conn.close()

# --- Funkcje dla Systemu Kar ---
def add_punishment(guild_id, user_id, moderator_id, punishment_type, reason, expires_at=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO punishments (guild_id, user_id, moderator_id, type, reason, expires_at, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                   (guild_id, user_id, moderator_id, punishment_type, reason, expires_at, int(time.time())))
    conn.commit()
    conn.close()

def get_user_punishments(guild_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM punishments WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC", (guild_id, user_id))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_expired_active_punishments(current_timestamp: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM punishments WHERE active = 1 AND expires_at IS NOT NULL AND expires_at <= ?", (current_timestamp,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def deactivate_punishment(punishment_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE punishments SET active = 0 WHERE id = ?", (punishment_id,))
    conn.commit()
    conn.close()

# --- Funkcje dla Product Watchlist ---
def add_watched_product(user_id: int, url: str, shop_name: str, guild_id: int | None = None, notification_channel_id: int | None = None) -> int | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO watched_products 
            (guild_id, user_id_who_added, product_url, shop_name, is_active, notification_channel_id) 
            VALUES (?, ?, ?, ?, TRUE, ?)
        """, (guild_id, user_id, url, shop_name, notification_channel_id))
        product_id = cursor.lastrowid
        conn.commit()
        return product_id
    except sqlite3.IntegrityError:
        conn.rollback()
        return None
    finally:
        conn.close()

def get_watched_product_by_url(url: str) -> dict | None:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watched_products WHERE product_url = ?", (url,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_watched_product_data(product_id: int, name: str | None, price_cents: int | None, availability_str: str | None, scanned_at: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE watched_products
        SET product_name = ?, last_known_price_cents = ?, last_known_availability_str = ?, last_scanned_at = ?
        WHERE id = ?
    """, (name, price_cents, availability_str, scanned_at, product_id))
    conn.commit()
    conn.close()

def add_price_history_entry(watched_product_id: int, scan_date: int, price_cents: int | None, availability_str: str | None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO price_history (watched_product_id, scan_date, price_cents, availability_str)
        VALUES (?, ?, ?, ?)
    """, (watched_product_id, scan_date, price_cents, availability_str))
    conn.commit()
    conn.close()
    
def get_all_active_watched_products() -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watched_products WHERE is_active = TRUE")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def deactivate_watched_product(product_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE watched_products SET is_active = FALSE WHERE id = ?", (product_id,))
    updated_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return updated_rows > 0

def get_user_watched_products(user_id: int, guild_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watched_products WHERE user_id_who_added = ? AND guild_id = ? AND is_active = TRUE ORDER BY product_name ASC", (user_id, guild_id))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_guilds_with_product_report_config() -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id, product_report_channel_id, product_report_time_utc FROM server_configs WHERE product_report_channel_id IS NOT NULL AND product_report_time_utc IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
    
# --- Funkcje dla Ankiet ---
def create_poll(guild_id: int, channel_id: int, question: str, created_by_id: int, ends_at: int | None) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO polls (guild_id, channel_id, question, created_by_id, created_at, ends_at, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                   (guild_id, channel_id, question, created_by_id, int(time.time()), ends_at))
    poll_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return poll_id

def set_poll_message_id(poll_id: int, message_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE polls SET message_id = ? WHERE id = ?", (message_id, poll_id))
    conn.commit()
    conn.close()

def add_poll_option(poll_id: int, option_text: str, reaction_emoji: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO poll_options (poll_id, option_text, reaction_emoji) VALUES (?, ?, ?)",
                   (poll_id, option_text, reaction_emoji))
    conn.commit()
    conn.close()

# --- Funkcje dla Losowań ---
def create_giveaway(guild_id, channel_id, prize, winner_count, created_by_id, ends_at, required_role_id, min_level):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO giveaways (guild_id, channel_id, prize, winner_count, created_by_id, created_at, ends_at, required_role_id, min_level, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                   (guild_id, channel_id, prize, winner_count, created_by_id, int(time.time()), ends_at, required_role_id, min_level))
    gid = cursor.lastrowid
    conn.commit()
    conn.close()
    return gid

def set_giveaway_message_id(giveaway_id, message_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id))
    conn.commit()
    conn.close()
    
def get_active_giveaways_to_end(current_timestamp: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM giveaways WHERE is_active = 1 AND ends_at <= ?", (current_timestamp,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def end_giveaway(giveaway_id: int, winners_ids: list[int]):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    winners_json = json.dumps(winners_ids)
    cursor.execute("UPDATE giveaways SET is_active = 0, winners_json = ? WHERE id = ?", (winners_json, giveaway_id))
    conn.commit()
    conn.close()

# --- Funkcje dla Systemu Poziomów ---
def ensure_user_activity_entry(guild_id: int, user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO user_activity (guild_id, user_id, message_count, xp, level) VALUES (?, ?, 0, 0, 0)", (guild_id, user_id))
    conn.commit()
    conn.close()

def add_xp(guild_id: int, user_id: int, xp_to_add: int) -> int:
    ensure_user_activity_entry(guild_id, user_id)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_activity SET xp = xp + ? WHERE guild_id = ? AND user_id = ?", (xp_to_add, guild_id, user_id))
    conn.commit()
    cursor.execute("SELECT xp FROM user_activity WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    new_xp = cursor.fetchone()[0]
    conn.close()
    return new_xp

def get_user_stats(guild_id: int, user_id: int) -> dict:
    ensure_user_activity_entry(guild_id, user_id)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_activity WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {"message_count": 0, "xp": 0, "level": 0}

def set_user_level(guild_id: int, user_id: int, new_level: int):
    ensure_user_activity_entry(guild_id, user_id)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_activity SET level = ? WHERE guild_id = ? AND user_id = ?", (new_level, guild_id, user_id))
    conn.commit()
    conn.close()
    
def get_server_leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_activity WHERE guild_id = ? ORDER BY xp DESC LIMIT ?", (guild_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
    
def get_user_rank_in_server(guild_id: int, user_id: int) -> tuple[int, int] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Find user's xp first
    cursor.execute("SELECT xp FROM user_activity WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    user_xp_row = cursor.fetchone()
    if not user_xp_row:
        conn.close()
        return None
    user_xp = user_xp_row[0]
    
    # Count users with more xp
    cursor.execute("SELECT COUNT(*) FROM user_activity WHERE guild_id = ? AND xp > ?", (guild_id, user_xp))
    rank = cursor.fetchone()[0] + 1
    
    # Count total ranked users
    cursor.execute("SELECT COUNT(*) FROM user_activity WHERE guild_id = ?", (guild_id,))
    total = cursor.fetchone()[0]
    
    conn.close()
    return rank, total

# --- Inne Funkcje ---
def add_custom_command(guild_id: int, name: str, response_type: str, content: str, creator_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO custom_commands (guild_id, command_name, response_type, response_content, created_by_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (guild_id, name, response_type, content, creator_id, int(time.time())))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def remove_custom_command(guild_id: int, name: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_commands WHERE guild_id = ? AND command_name = ?", (guild_id, name))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

def get_banned_words(guild_id: int) -> list[str]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM banned_words WHERE guild_id = ?", (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]
    
def get_rewards_for_level(guild_id: int, level: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM level_rewards WHERE guild_id = ? AND level = ?", (guild_id, level))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
