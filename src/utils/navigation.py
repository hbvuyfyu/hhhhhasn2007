"""Navigation stack helpers for persistent back button."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def nav_push(context, callback_data: str) -> None:
    """Push current screen onto navigation stack."""
    stack = context.user_data.get("nav_stack", [])
    stack.append(callback_data)
    context.user_data["nav_stack"] = stack


def nav_pop(context) -> str | None:
    """Pop previous screen from navigation stack. Returns None if empty."""
    stack = context.user_data.get("nav_stack", [])
    if stack:
        return stack.pop()
    return None


def nav_clear(context) -> None:
    """Clear navigation stack (e.g. when going to main menu)."""
    context.user_data["nav_stack"] = []


def nav_back_button(context, fallback: str = "main_menu") -> InlineKeyboardButton:
    """Create a back button that navigates to the previous screen."""
    prev = nav_peek(context)
    target = prev if prev else fallback
    return InlineKeyboardButton("🔙 رجوع", callback_data=target)


def nav_peek(context) -> str | None:
    """Peek at the previous screen without popping."""
    stack = context.user_data.get("nav_stack", [])
    if stack:
        return stack[-1]
    return None


def nav_add_back_row(context, kb: list, fallback: str = "main_menu") -> None:
    """Add back button row to keyboard, alongside main menu button."""
    prev = nav_peek(context)
    row = []
    if prev:
        row.append(InlineKeyboardButton("🔙 رجوع", callback_data=prev))
    row.append(InlineKeyboardButton("🏠 القائمة", callback_data="main_menu"))
    kb.append(row)
