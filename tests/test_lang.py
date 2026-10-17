import pytest

from dzshop.lang import detect_language, normalize


@pytest.mark.parametrize("text,lang", [
    ("slm, ch7al soum?", "darija"),
    ("bghit nakhod 2 w 3andi mochkil f 3enwan", "darija"),
    ("wach mazal kayn stock", "darija"),
    ("Bonjour, je voudrais le prix de la montre", "fr"),
    ("combien coûte la livraison à Oran ?", "fr"),
    ("السلام عليكم، بشحال الساعة؟", "ar"),
    ("كم سعر التوصيل لوهران", "ar"),
])
def test_detect(text, lang):
    assert detect_language(text).lang == lang


def test_unknown_for_neutral_text():
    assert detect_language("ok 123").lang == "und"


def test_arabizi_numerals_normalised():
    assert normalize("ch7al") == "chحal"
    assert normalize("3afak 9ima") == "عafak قima"
    assert normalize("n5ayyer") == "nخayyer"


def test_units_and_numbers_untouched():
    assert normalize("20000mAh x2 0661234567") == "20000mah x2 0661234567"


def test_accents_and_arabic_variants():
    assert normalize("Sétif") == "setif"
    assert normalize("أهلاً بالبليدة") == normalize("اهلا بالبليدة")
