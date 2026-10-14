import re


def clean_text(text: str) -> str:
    """Identical to the preprocessing used at training time (data_processing.py)."""
    text = re.sub(r"http\S+|www\S+|https\S+", '', text)
    text = re.sub(r'[^A-Za-z ]+', '', text)
    return text.lower()


def display_text(text: str) -> str:
    """Human-friendly version for the dashboard (strip the HTML line breaks)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
