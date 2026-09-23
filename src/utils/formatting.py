def format_number(val) -> str:
    if val is None or val != val:
        return "N/A"
    try:
        val = float(val)
        if val >= 1_000_000:
            return f"{val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"{val / 1_000:.1f}K"
        return f"{int(val):,}" if val.is_integer() else f"{val:.2f}"
    except (ValueError, TypeError):
        return str(val)

def format_percent(val) -> str:
    if val is None or val != val:
        return "N/A"
    try:
        val = float(val)
        return f"{val:.2f}%"
    except (ValueError, TypeError):
        return str(val)