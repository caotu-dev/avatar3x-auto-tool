"""Conservative catalog matching for game labels, never for money or quantities."""
import re
import unicodedata


def label_key(text):
    text=unicodedata.normalize('NFD',text.lower().replace('đ','d'))
    text=''.join(c for c in text if unicodedata.category(c)!='Mn')
    text=re.sub(r'^ce\b','ca',text)
    return ' '.join(text.translate(str.maketrans({'0':'o','6':'o','1':'l','v':'u'})).split())


def catalog_label(text, catalog):
    """Only accept a unique known label after observed glyph substitutions."""
    key=label_key(text)
    matches=[value for name,value in catalog.items() if label_key(name)==key]
    return matches[0] if len(matches)==1 else None
