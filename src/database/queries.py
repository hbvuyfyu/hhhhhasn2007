from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging

from .connection import execute, get_db
import psycopg2.extras

logger = logging.getLogger(__name__)


# ==================== Users ====================

def upsert_user(user_id: int, username: str, name: str) -> None:
    execute(
        """
        INSERT INTO users (user_id, username, name, created_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, username, name, datetime.now().isoformat()),
    )


def is_allowed(user_id: int) -> bool:
    row = execute(
        "SELECT allowed FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )
    return bool(row and row["allowed"])


def is_banned(user_id: int) -> Optional[bool]:
    row = execute(
        "SELECT banned FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )
    return bool(row and row["banned"]) if row else None


def is_admin(user_id: int) -> bool:
    from src.config import ADMIN_IDS
    return user_id in ADMIN_IDS


def increment_requests(user_id: int) -> None:
    execute(
        """
        UPDATE users
        SET total_requests = total_requests + 1,
            last_use = %s
        WHERE user_id = %s
        """,
        (datetime.now().isoformat(), user_id),
    )


def add_allowed_user(user_id: int, username: str, name: str, admin_id: int) -> None:
    execute(
        """
        INSERT INTO allowed_users (user_id, username, name, added_by, added_date)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, username, name, admin_id, datetime.now().isoformat()),
    )
    execute(
        "UPDATE users SET allowed = 1 WHERE user_id = %s",
        (user_id,),
    )


def remove_allowed_user(user_id: int) -> None:
    execute("DELETE FROM allowed_users WHERE user_id = %s", (user_id,))
    execute("UPDATE users SET allowed = 0 WHERE user_id = %s", (user_id,))


def ban_user(user_id: int) -> None:
    execute("UPDATE users SET banned = 1 WHERE user_id = %s", (user_id,))


def unban_user(user_id: int) -> None:
    execute("UPDATE users SET banned = 0 WHERE user_id = %s", (user_id,))


def get_all_users() -> List[Dict]:
    return execute(
        "SELECT user_id, username, name, last_use, banned, allowed FROM users ORDER BY created_at DESC",
        fetch="all",
    ) or []


def get_allowed_users() -> List[Dict]:
    return execute(
        "SELECT user_id, username, name, added_date FROM allowed_users ORDER BY added_date DESC",
        fetch="all",
    ) or []


def get_banned_users() -> List[Dict]:
    return execute(
        "SELECT user_id, username, name FROM users WHERE banned = 1",
        fetch="all",
    ) or []


def get_user_by_id(user_id: int) -> Optional[Dict]:
    return execute(
        "SELECT user_id, username, name FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )


def get_user_by_identifier(identifier: str) -> Optional[Dict]:
    try:
        uid = int(identifier)
        return execute(
            "SELECT user_id FROM users WHERE user_id = %s",
            (uid,),
            fetch="one",
        )
    except ValueError:
        uname = identifier.lstrip("@")
        return execute(
            "SELECT user_id FROM users WHERE username = %s",
            (uname,),
            fetch="one",
        )


def get_stats() -> Dict[str, int]:
    total    = execute("SELECT COUNT(*) AS cnt FROM users", fetch="one") or {"cnt": 0}
    allowed  = execute("SELECT COUNT(*) AS cnt FROM users WHERE allowed = 1", fetch="one") or {"cnt": 0}
    banned   = execute("SELECT COUNT(*) AS cnt FROM users WHERE banned = 1", fetch="one") or {"cnt": 0}
    requests = execute("SELECT COALESCE(SUM(total_requests), 0) AS cnt FROM users", fetch="one") or {"cnt": 0}
    farms    = execute("SELECT COUNT(*) AS cnt FROM farm_tasks WHERE status = 'running'", fetch="one") or {"cnt": 0}
    active_subs = execute("SELECT COUNT(*) AS cnt FROM subscriptions WHERE status = 'active' AND end_date > NOW()", fetch="one") or {"cnt": 0}
    pending_reqs = execute("SELECT COUNT(*) AS cnt FROM payment_requests WHERE status = 'pending'", fetch="one") or {"cnt": 0}
    return {
        "total":       total["cnt"],
        "allowed":     allowed["cnt"],
        "banned":      banned["cnt"],
        "requests":    requests["cnt"],
        "farms":       farms["cnt"],
        "active_subs": active_subs["cnt"],
        "pending_reqs": pending_reqs["cnt"],
    }


# ==================== Platform ====================

def get_user_platform(user_id: int) -> str:
    row = execute(
        "SELECT platform FROM user_platform WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )
    return row["platform"] if row else "android"


def set_user_platform(user_id: int, platform: str) -> None:
    execute(
        """
        INSERT INTO user_platform (user_id, platform)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET platform = EXCLUDED.platform
        """,
        (user_id, platform),
    )


def ensure_user_platform(user_id: int) -> None:
    execute(
        """
        INSERT INTO user_platform (user_id, platform)
        VALUES (%s, 'android')
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,),
    )


# ==================== Proxy ====================

def get_proxy_for_user(user_id: int) -> Optional[Dict]:
    return execute(
        "SELECT proxy_type, host, port, username, password FROM proxies WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )


def save_proxy(user_id: int, proxy_type: str, host: str, port: int, username: str = "", password: str = "") -> None:
    execute(
        """
        INSERT INTO proxies (user_id, proxy_type, host, port, username, password)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET proxy_type = EXCLUDED.proxy_type,
                host = EXCLUDED.host,
                port = EXCLUDED.port,
                username = EXCLUDED.username,
                password = EXCLUDED.password
        """,
        (user_id, proxy_type, host, port, username, password),
    )


def delete_proxy(user_id: int) -> None:
    execute("DELETE FROM proxies WHERE user_id = %s", (user_id,))


# ==================== AppsFlyer Games ====================

def get_all_games_af() -> List[Dict]:
    return execute(
        "SELECT id, name, display_name, package, dev_key, emoji FROM games_af ORDER BY display_name",
        fetch="all",
    ) or []


def get_game_af_by_id(game_id: int) -> Optional[Dict]:
    return execute(
        "SELECT id, name, display_name, package, dev_key, emoji FROM games_af WHERE id = %s",
        (game_id,),
        fetch="one",
    )


def get_af_events(game_id: int) -> List[Dict]:
    return execute(
        "SELECT id, event_name, display_name, event_type, revenue, level_value FROM events_af WHERE game_id = %s ORDER BY display_name",
        (game_id,),
        fetch="all",
    ) or []


def add_game_af(name: str, display_name: str, package: str, dev_key: str, emoji: str) -> None:
    execute(
        "INSERT INTO games_af (name, display_name, package, dev_key, emoji) VALUES (%s, %s, %s, %s, %s)",
        (name, display_name, package, dev_key, emoji),
    )


def add_event_af(game_id: int, event_name: str, display_name: str, event_type: str = "level", revenue: float = None, level_value: int = None) -> None:
    execute(
        "INSERT INTO events_af (game_id, event_name, display_name, event_type, revenue, level_value) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (game_id, event_name, display_name, event_type, revenue, level_value),
    )


def delete_event_af(event_id: int) -> None:
    execute("DELETE FROM events_af WHERE id = %s", (event_id,))


def delete_game_af(game_id: int) -> None:
    execute("DELETE FROM events_af WHERE game_id = %s", (game_id,))
    execute("DELETE FROM games_af WHERE id = %s", (game_id,))


# ==================== Adjust Games ====================

def get_all_games_adj() -> List[Dict]:
    return execute(
        "SELECT id, name, display_name, app_token, emoji FROM games_adj ORDER BY display_name",
        fetch="all",
    ) or []


def get_game_adj_by_id(game_id: int) -> Optional[Dict]:
    return execute(
        "SELECT id, name, display_name, app_token, emoji FROM games_adj WHERE id = %s",
        (game_id,),
        fetch="one",
    )


def get_adj_events(game_id: int) -> List[Dict]:
    return execute(
        "SELECT id, event_name, event_token, display_name, level_value FROM events_adj WHERE game_id = %s ORDER BY display_name",
        (game_id,),
        fetch="all",
    ) or []


def add_game_adj(name: str, display_name: str, app_token: str, emoji: str) -> None:
    execute(
        "INSERT INTO games_adj (name, display_name, app_token, emoji) VALUES (%s, %s, %s, %s)",
        (name, display_name, app_token, emoji),
    )


def add_event_adj(game_id: int, event_name: str, event_token: str, display_name: str, level_value: int = None) -> None:
    execute(
        "INSERT INTO events_adj (game_id, event_name, event_token, display_name, level_value) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (game_id, event_name, event_token, display_name, level_value),
    )


def delete_event_adj(event_id: int) -> None:
    execute("DELETE FROM events_adj WHERE id = %s", (event_id,))


def delete_game_adj(game_id: int) -> None:
    execute("DELETE FROM events_adj WHERE game_id = %s", (game_id,))
    execute("DELETE FROM games_adj WHERE id = %s", (game_id,))


# ==================== Singular Games ====================

def get_all_games_singular() -> List[Dict]:
    return execute(
        "SELECT id, name, display_name, package, app_key, emoji FROM games_singular ORDER BY display_name",
        fetch="all",
    ) or []


def get_game_singular_by_id(game_id: int) -> Optional[Dict]:
    return execute(
        "SELECT id, name, display_name, package, app_key, emoji FROM games_singular WHERE id = %s",
        (game_id,),
        fetch="one",
    )


def get_singular_events(game_id: int) -> List[Dict]:
    return execute(
        "SELECT id, event_name, display_name, event_type, level_value FROM events_singular WHERE game_id = %s ORDER BY display_name",
        (game_id,),
        fetch="all",
    ) or []


def add_game_singular(name: str, display_name: str, package: str, app_key: str, emoji: str) -> None:
    execute(
        "INSERT INTO games_singular (name, display_name, package, app_key, emoji) VALUES (%s, %s, %s, %s, %s)",
        (name, display_name, package, app_key, emoji),
    )


def add_event_singular(game_id: int, event_name: str, display_name: str, event_type: str = "level", level_value: int = None) -> None:
    execute(
        "INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (game_id, event_name, display_name, event_type, level_value),
    )


def delete_event_singular(event_id: int) -> None:
    execute("DELETE FROM events_singular WHERE id = %s", (event_id,))


def delete_game_singular(game_id: int) -> None:
    execute("DELETE FROM events_singular WHERE game_id = %s", (game_id,))
    execute("DELETE FROM games_singular WHERE id = %s", (game_id,))


# ==================== Farm Tasks ====================

def create_farm_task(
    user_id: int, task_name: str, platform: str, game_id: int, game_name: str,
    start_level: int, end_level: int, total_days: int, mode: str,
    aifa: str = "", gaid: str = "", af_uid: str = "", gps_adid: str = "",
    idfa: str = "", idfv: str = "", singular_uid: str = "",
) -> Optional[int]:
    row = execute(
        """
        INSERT INTO farm_tasks
            (user_id, task_name, platform, game_id, game_name, start_level, end_level,
             total_days, mode, current_day, current_level, status, created_date,
             aifa, gaid, af_uid, gps_adid, idfa, idfv, singular_uid)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,'running',%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            user_id, task_name, platform, game_id, game_name,
            start_level, end_level, total_days, mode, start_level,
            datetime.now().isoformat(),
            aifa, gaid, af_uid, gps_adid, idfa, idfv, singular_uid,
        ),
        fetch="one",
    )
    return row["id"] if row else None


def get_active_farm_tasks(user_id: int) -> List[Dict]:
    return execute(
        """
        SELECT id, task_name, platform, game_name, start_level, end_level,
               current_level, status, mode, current_day, total_days,
               aifa, gaid, af_uid, gps_adid, idfa, idfv, singular_uid, game_id
        FROM farm_tasks
        WHERE user_id = %s AND status = 'running'
        ORDER BY created_date DESC
        """,
        (user_id,),
        fetch="all",
    ) or []


def get_all_running_farm_tasks() -> List[Dict]:
    return execute(
        """
        SELECT id, user_id, task_name, platform, game_id, game_name,
               start_level, end_level, current_level, current_day, total_days,
               mode, aifa, gaid, af_uid, gps_adid, idfa, idfv, singular_uid
        FROM farm_tasks
        WHERE status = 'running'
        """,
        fetch="all",
    ) or []


def stop_farm_task(task_id: int, user_id: int) -> None:
    execute(
        "UPDATE farm_tasks SET status = 'stopped' WHERE id = %s AND user_id = %s",
        (task_id, user_id),
    )


def update_farm_task_level(task_id: int, current_level: int, current_day: int) -> None:
    execute(
        "UPDATE farm_tasks SET current_level = %s, current_day = %s WHERE id = %s",
        (current_level, current_day, task_id),
    )


def complete_farm_task(task_id: int) -> None:
    execute(
        "UPDATE farm_tasks SET status = 'completed' WHERE id = %s",
        (task_id,),
    )


def get_farm_task_by_id(task_id: int) -> Optional[Dict]:
    return execute(
        "SELECT * FROM farm_tasks WHERE id = %s",
        (task_id,),
        fetch="one",
    )


def get_stoppable_tasks(user_id: int) -> List[Dict]:
    return execute(
        "SELECT id, task_name FROM farm_tasks WHERE user_id = %s AND status = 'running'",
        (user_id,),
        fetch="all",
    ) or []


# ==================== Subscriptions ====================

def get_active_subscription(user_id: int) -> Optional[Dict]:
    row = execute(
        """
        SELECT id, plan_name, daily_limit, daily_used, last_reset_date, end_date
        FROM subscriptions
        WHERE user_id = %s AND status = 'active' AND end_date > NOW()
        ORDER BY end_date DESC
        LIMIT 1
        """,
        (user_id,),
        fetch="one",
    )
    if not row:
        return None
    today = date.today()
    last_reset = row.get("last_reset_date")
    if isinstance(last_reset, str):
        try:
            from datetime import date as _date
            last_reset = _date.fromisoformat(last_reset)
        except Exception:
            last_reset = None
    if last_reset != today:
        execute(
            "UPDATE subscriptions SET daily_used = 0, last_reset_date = %s WHERE user_id = %s AND status = 'active' AND end_date > NOW()",
            (today, user_id),
        )
        row = dict(row)
        row["daily_used"] = 0
        row["last_reset_date"] = today
    return row


def increment_subscription_usage(user_id: int) -> None:
    execute(
        """
        UPDATE subscriptions
        SET daily_used = daily_used + 1
        WHERE user_id = %s AND status = 'active' AND end_date > NOW()
        """,
        (user_id,),
    )


def create_subscription(user_id: int, plan_id: int, plan_name: str,
                        duration_days: int, daily_limit: int) -> None:
    execute(
        "UPDATE subscriptions SET status = 'expired' WHERE user_id = %s AND status = 'active'",
        (user_id,),
    )
    end_date = datetime.now() + timedelta(days=duration_days)
    execute(
        """
        INSERT INTO subscriptions (user_id, plan_id, plan_name, daily_limit, start_date, end_date)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        """,
        (user_id, plan_id, plan_name, daily_limit, end_date),
    )
    execute("UPDATE users SET allowed = 1 WHERE user_id = %s", (user_id,))


# ==================== Subscription Plans ====================

def get_active_plans() -> List[Dict]:
    return execute(
        "SELECT id, name, duration_days, price, daily_limit FROM subscription_plans WHERE is_active = TRUE ORDER BY price",
        fetch="all",
    ) or []


def get_all_plans() -> List[Dict]:
    return execute(
        "SELECT id, name, duration_days, price, daily_limit, is_active FROM subscription_plans ORDER BY price",
        fetch="all",
    ) or []


def get_plan_by_id(plan_id: int) -> Optional[Dict]:
    return execute(
        "SELECT id, name, duration_days, price, daily_limit, is_active FROM subscription_plans WHERE id = %s",
        (plan_id,),
        fetch="one",
    )


def add_plan(name: str, duration_days: int, price: float, daily_limit: int) -> None:
    execute(
        "INSERT INTO subscription_plans (name, duration_days, price, daily_limit) VALUES (%s, %s, %s, %s)",
        (name, duration_days, price, daily_limit),
    )


def toggle_plan(plan_id: int, is_active: bool) -> None:
    execute("UPDATE subscription_plans SET is_active = %s WHERE id = %s", (is_active, plan_id))


def delete_plan(plan_id: int) -> None:
    execute("DELETE FROM subscription_plans WHERE id = %s", (plan_id,))


def update_plan(plan_id: int, name: str, duration_days: int, price: float, daily_limit: int) -> None:
    execute(
        "UPDATE subscription_plans SET name=%s, duration_days=%s, price=%s, daily_limit=%s WHERE id=%s",
        (name, duration_days, price, daily_limit, plan_id),
    )


# ==================== Payment Settings ====================

def get_payment_setting(method: str) -> Optional[Dict]:
    return execute(
        "SELECT * FROM payment_settings WHERE method = %s",
        (method,),
        fetch="one",
    )


def get_all_payment_settings() -> List[Dict]:
    return execute(
        "SELECT * FROM payment_settings ORDER BY method",
        fetch="all",
    ) or []


def get_active_payment_settings() -> List[Dict]:
    return execute(
        "SELECT * FROM payment_settings WHERE is_active = TRUE ORDER BY method",
        fetch="all",
    ) or []


def update_payment_setting_field(method: str, field: str, value: str) -> None:
    allowed = {"address", "instructions", "binance_api_key", "binance_api_secret", "is_active", "display_name"}
    if field not in allowed:
        return
    execute(
        f"UPDATE payment_settings SET {field} = %s, updated_at = NOW() WHERE method = %s",
        (value, method),
    )


def set_payment_setting(method: str, address: str, instructions: str,
                        binance_api_key: str = "", binance_api_secret: str = "",
                        display_name: str = "", is_active: bool = True) -> None:
    execute(
        """
        INSERT INTO payment_settings (method, address, instructions, binance_api_key, binance_api_secret, display_name, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (method) DO UPDATE SET
            address = EXCLUDED.address,
            instructions = EXCLUDED.instructions,
            binance_api_key = EXCLUDED.binance_api_key,
            binance_api_secret = EXCLUDED.binance_api_secret,
            display_name = EXCLUDED.display_name,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
        """,
        (method, address, instructions, binance_api_key, binance_api_secret, display_name, is_active),
    )


# ==================== Payment Requests ====================

def create_payment_request(
    user_id: int, user_name: str, user_username: str,
    plan_id: int, plan_name: str, method: str, amount: float,
    transaction_id: str = "", proof_file_id: str = "",
) -> int:
    row = execute(
        """
        INSERT INTO payment_requests
            (user_id, user_name, user_username, plan_id, plan_name, method, amount, transaction_id, proof_file_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, user_name, user_username, plan_id, plan_name, method, amount, transaction_id, proof_file_id),
        fetch="one",
    )
    return row["id"] if row else 0


def process_payment_request_auto(
    user_id: int, user_name: str, user_username: str,
    plan_id: int, plan_name: str, method: str, amount: float, transaction_id: str,
) -> None:
    execute(
        """
        INSERT INTO payment_requests
            (user_id, user_name, user_username, plan_id, plan_name, method, amount, transaction_id, status, processed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'approved', NOW())
        """,
        (user_id, user_name, user_username, plan_id, plan_name, method, amount, transaction_id),
    )


def get_payment_request(request_id: int) -> Optional[Dict]:
    return execute(
        "SELECT * FROM payment_requests WHERE id = %s",
        (request_id,),
        fetch="one",
    )


def process_payment_request(request_id: int, status: str, admin_id: int) -> None:
    execute(
        "UPDATE payment_requests SET status = %s, admin_id = %s, processed_at = NOW() WHERE id = %s",
        (status, admin_id, request_id),
    )


def get_pending_requests() -> List[Dict]:
    return execute(
        "SELECT * FROM payment_requests WHERE status = 'pending' ORDER BY created_at DESC",
        fetch="all",
    ) or []


def get_user_subscriptions(user_id: int) -> List[Dict]:
    return execute(
        "SELECT * FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
        fetch="all",
    ) or []


def get_all_payment_requests() -> List[Dict]:
    return execute(
        "SELECT * FROM payment_requests ORDER BY created_at DESC LIMIT 100",
        fetch="all",
    ) or []
