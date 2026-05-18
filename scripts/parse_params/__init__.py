from .danfoss import parse as parse_danfoss

PARSERS = {
    'Danfoss': parse_danfoss,
}

def parse_for_producator(producator: str, content):
    producator_norm = (producator or '').strip()
    for key, fn in PARSERS.items():
        if key.lower() in producator_norm.lower():
            return key, fn(content)
    return None, None
