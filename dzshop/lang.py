"""Language detection (Darija-Latin / Arabic / French) and Arabizi normalisation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DARIJA, ARABIC, FRENCH, UNKNOWN = "darija", "ar", "fr", "und"

# Arabizi numerals used inside Latin-script words.
ARABIZI = {"3": "ع", "7": "ح", "9": "ق", "5": "خ", "2": "ء", "8": "غ", "6": "ط"}

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LATIN_RE = re.compile(r"[a-zA-ZÀ-ÿ]")
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_TASHKEEL = re.compile(r"[ً-ٰٟـ]")
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# tokens like 2pcs, 20000mah, x2 are quantities/units, never Arabizi.
_UNIT_TOKEN = re.compile(r"^(x\d+|\d+(x|pcs|pc|pieces|piece|dz|da|dzd|ml|mah|gb|kg|g|m|cm|h))$")

# Strong Darija (Latin) markers.
_DARIJA_WORDS = {
    "slm", "salam", "salem", "salamu", "wach", "wesh", "chhal", "chal", "soum", "soumha", "sa3r",
    "ghali", "rkhis", "bghit", "bgheit", "bghina", "nheb", "nebghi", "kayn", "kayna", "makach",
    "mazal", "rani", "khouya", "khoya", "khti", "barsha", "bezzaf", "bzaf", "tawsil", "twsil",
    "wssel", "wsel", "wslet", "wsslet", "wssal", "win", "kifach", "kifah", "3afak", "afak", "3lach", "daba",
    "ghadi", "dyal", "dial", "ta3", "t3", "hna", "ghodwa", "ghedwa", "lyoum", "bach", "wahed",
    "zouj", "iyeh", "ih", "wah", "walou", "nchri", "nechri", "ncommandi", "kmel", "kml", "mrhba",
    "merhba", "sa7a", "saha", "yatik", "rabi", "inchallah", "chno", "chnou", "ach", "wakila",
    "mli7", "mlih", "7ata", "hadi", "hada", "hadak", "dyali", "3ndi", "3andi", "3andkom", "3ndkom",
    "3andek", "3ndek", "fin", "nsayb", "ntsanna", "tsna", "stanna", "bsah", "bs7", "ndir", "ndiro",
    "bghitch", "annuli", "batel", "nji", "njib", "yji", "yjini", "jiboulhom", "dzayer", "wahran", "9ima", "thmen", "tmen",
}
# French markers: strong ones, plus ambiguous loanwords shared with Darija code-switching.
_FRENCH_STRONG = {
    "bonjour", "bonsoir", "je", "j", "voudrais", "veux", "souhaite", "combien", "quel", "quelle",
    "quels", "est", "ce", "vous", "avez", "les", "des", "une", "pour", "mon", "mes", "ça",
    "ca", "comment", "où", "ou", "suivi", "colis", "adresse", "coûte", "coute", "cout", "frais",
    "oui", "non", "pouvez", "cher", "s", "svp", "plait", "merci", "disponible", "disponibles",
    "avez", "prendre", "passer", "commander", "livrer", "livré", "reçu", "recu", "quand", "est-ce",
    "bien", "pas", "dans", "avec", "sur", "le", "la", "du", "au", "aux", "en", "il", "elle", "on",
    "payer", "paiement", "puis", "peux", "besoin", "parler", "conseiller", "humain", "réclamation",
}
_FRENCH_AMBIGUOUS = {"commande", "livraison", "prix", "stock", "montre", "confirme", "confirmer"}


@dataclass(frozen=True)
class Detection:
    lang: str
    confidence: float


def strip_accents(text: str) -> str:
    text = text.replace("œ", "oe").replace("Œ", "oe")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _is_latin_token(tok: str) -> bool:
    return bool(re.search(r"[a-z]", tok))


def _arabizi_token(tok: str) -> str:
    """Map isolated single digits inside a Latin word to Arabic letters (ch7al -> chحal)."""
    if not _is_latin_token(tok) or _UNIT_TOKEN.match(tok) or not re.search(r"\d", tok):
        return tok
    out = []
    for m in re.finditer(r"\d+|\D+", tok):
        part = m.group(0)
        if part.isdigit():
            out.append(ARABIZI.get(part, part) if len(part) == 1 else part)
        else:
            out.append(part)
    return "".join(out)


def normalize(text: str) -> str:
    """Lower-case, strip accents/diacritics, unify Arabic letter variants, map Arabizi numerals."""
    text = unicodedata.normalize("NFKC", text).lower().translate(_ARABIC_INDIC)
    text = _TASHKEEL.sub("", text)
    text = re.sub("[أإآ]", "ا", text).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    text = strip_accents(text).replace("'", " ").replace("’", " ")
    tokens = [_arabizi_token(t) for t in _TOKEN_RE.findall(text)]
    return " ".join(tokens)


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def detect_language(text: str) -> Detection:
    """Return ("darija" | "ar" | "fr" | "und", confidence).

    Arabic script -> "ar". Latin script is split between Darija (Arabizi / Maghrebi words) and French.
    """
    ar = len(_ARABIC_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    if ar and ar >= lat:
        return Detection(ARABIC, min(1.0, 0.6 + ar / 40))
    low = strip_accents(text.lower())
    toks = _TOKEN_RE.findall(low.replace("'", " "))
    d = f = 0.0
    for t in toks:
        if t in _DARIJA_WORDS:
            d += 1.0
        elif re.fullmatch(r"[a-z]+\d[a-z]*|[a-z]*\d[a-z]+", t) and not _UNIT_TOKEN.match(t) \
                and re.search(r"(?<!\d)[2356789](?!\d)", t):
            d += 1.5  # Arabizi numeral inside a word: strong Darija signal
        if t in _FRENCH_STRONG:
            f += 1.0
        elif t in _FRENCH_AMBIGUOUS:
            f += 0.3
    if d == 0 and f == 0:
        return Detection(UNKNOWN, 0.0)
    if d > f:
        return Detection(DARIJA, d / (d + f))
    if f > d:
        return Detection(FRENCH, f / (d + f))
    return Detection(UNKNOWN, 0.0)
