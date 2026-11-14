import re


def normalize_phone(raw: str) -> str:
    """Har qanday yozuvni 998XXXXXXXXX ko'rinishiga keltiradi. Noto'g'ri bo'lsa — bo'sh satr."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    return digits if len(digits) == 12 and digits.startswith("998") else ""


def format_sum(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"
