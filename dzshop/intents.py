"""Offline intent classifier: small hand-written multilingual examples + char TF-IDF + logistic regression."""

from __future__ import annotations

from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .lang import normalize

TRAINING: dict[str, list[str]] = {
    "greeting": [
        "slm", "salam", "salam khouya", "slm wach rak", "ahlan", "marhba", "wesh", "salam 3alaykom",
        "bonjour", "bonsoir", "salut", "bjr", "hello", "coucou", "hi",
        "السلام عليكم", "سلام", "مرحبا", "أهلا", "صباح الخير", "مساء الخير", "اهلا وسهلا",
    ],
    "catalog": [
        "chno 3andkom", "wach kayn 3andkom", "chno kayn jdid", "wach 3andkom produits", "warini les produits",
        "wach kayn catalogue", "chno tbi3o", "chno kayn fi la boutique",
        "qu'est-ce que vous vendez", "vous avez quoi", "je veux voir le catalogue", "quels produits avez vous",
        "montrez moi vos articles", "liste des produits",
        "شنو عندكم", "واش كاين عندكم", "اعرض علي المنتجات", "ما هي منتجاتكم", "كاتالوج", "شنو تبيعو",
    ],
    "price": [
        "ch7al soum", "ch7al soumha", "ch7al el prix", "chhal t3 la montre", "b ch7al", "b ch7al hadi",
        "ch7al ghali", "wach mazal kayn", "wach kayn stock", "wach mazal disponible", "ch7al thamen",
        "kayn fi stock", "wach kayna", "prix?", "soum?", "bch7al el sac",
        "combien coûte la montre", "quel est le prix", "c'est combien", "combien ça coûte", "le prix svp",
        "est-ce disponible", "il reste en stock", "c'est disponible", "tarif de ce produit",
        "بشحال", "بقداش", "كم سعر الساعة", "كم الثمن", "شحال الثمن", "ما هو السعر", "واش مازال متوفر",
        "هل هو متوفر", "كم سعره",
    ],
    "shipping": [
        "ch7al tawsil l wahran", "livraison l oran ch7al", "tawsil l constantine b ch7al", "chhal l livraison",
        "wach tweslo l blida", "tweslo l setif", "kifach twsl l oran w ch7al", "livraison l alger", "wach kayn tawsil",
        "frais de livraison pour oran", "combien la livraison vers sétif", "vous livrez à constantine",
        "livraison pour blida", "délai de livraison alger", "quel est le prix de livraison",
        "كم التوصيل لوهران", "بشحال التوصيل", "التوصيل لقسنطينة", "واش توصلو لسطيف", "مصاريف التوصيل",
        "كم مدة التوصيل",
    ],
    "order": [
        "bghit nشري", "bghit n commandi", "n7eb ncommandi", "nheb nechri", "bghit nakhod hadi", "ndir commande",
        "bghit nchri zouj", "kayn commande n7eb ndir", "n7eb nakhod wahed", "bghit hadi", "nbghi nakhod",
        "je veux commander", "je voudrais acheter la montre", "je prends 2", "je veux passer une commande",
        "je le prends", "je veux acheter", "passer commande svp", "je veux deux pièces",
        "بغيت نطلب", "حاب نكوموندي", "نحب نشري", "نبغي ناخذ", "بغيت ساعة", "اريد الطلب", "اريد شراء",
        "بغيت نشري زوج",
    ],
    "confirm": [
        "iyeh confirmi", "wah confirmi", "iyeh nconfirmi", "ih d'accord", "wah ok", "iyeh nakhod", "confirmi",
        "wah mrigel", "ih saha", "iyeh kamal", "oui", "oui je confirme", "ok je confirme", "d'accord",
        "confirmer la commande", "c'est bon je confirme", "oui parfait", "ok confirmé", "oui merci",
        "نعم", "اكد الطلب", "نعم نأكد", "أكد", "موافق", "ايه", "واه", "نعم مؤكد", "تمام اكد",
    ],
    "cancel": [
        "ma bghitch", "n7eb nannuli", "annuli la commande", "ma bghitch nakhod", "n7eb nbatel", "batel commande",
        "annuler la commande", "je ne veux plus", "j'annule ma commande", "non annulez",
        "الغي الطلب", "ما بغيتش", "الغاء الطلب", "لا الغي", "بطل الطلب",
    ],
    "track": [
        "win wsslet commande", "win rahi ma commande", "win wsel colis", "fin rahi commande dz-1001",
        "suivi commande", "wach wsslet", "win el livreur", "wach tbe3t commande", "win el colis t3i",
        "wesh men 7ala t3 commande", "ch7al mazal yewsel colis", "tracking",
        "où est ma commande", "suivi de colis", "ma commande n'est pas arrivée", "quand est-ce que je reçois",
        "statut de ma commande", "où en est mon colis", "suivre ma livraison",
        "وين وصلت الطلبية", "وين الطلب تاعي", "تتبع الطلب", "اين طلبي", "وين وصل الكولي", "حالة الطلب",
        "متى يصل طلبي",
    ],
    "human": [
        "bghit nahder m3a chi wa7ed", "n7eb nahder m3a l'agent", "3tini wa7ed mn l'equipe", "bghit responsable",
        "makhdamtouch", "hadi mouchkil kbir", "ma3jebnich service", "bghit nrje3 l produit", "bghit remboursement",
        "produit m9ass", "le colis jani mkasser", "arnaqa", "3yit n7ker", "bghit nchki",
        "je veux parler à un humain", "passez moi un conseiller", "je veux un remboursement",
        "j'ai un problème avec ma commande", "je veux faire une réclamation", "retour produit défectueux",
        "service client svp", "je suis très mécontent",
        "بغيت نهدر مع شخص", "اريد التحدث مع موظف", "اريد استرجاع المال", "عندي مشكل", "شكوى", "المنتج مكسور",
        "اريد مسؤول", "خدمة الزبائن",
    ],
    "thanks": [
        "merci", "barakallah oufik", "sa7a", "saha", "yatik essa7a", "merci khouya", "merci barsha", "shokran",
        "merci beaucoup", "merci bien", "super merci", "parfait merci",
        "شكرا", "بارك الله فيك", "جزاك الله خيرا", "شكرا جزيلا", "يعطيك الصحة",
    ],
    "payment": [
        "wach nkhalas 3and l'istilam", "nkhalas f dar", "wach nkhalas ki ydiw l colis", "kifach nkhalas",
        "wach kayn paiement 3and la livraison", "nkhalas cash", "wach nkhalas par ccp", "nkhalas ki njib",
        "paiement à la livraison", "est-ce que je paye à la réception", "comment payer", "payer en cash",
        "paiement par ccp", "puis-je payer à la livraison",
        "الدفع عند الاستلام", "كيفاش ندفع", "واش ندفع عند التوصيل", "طريقة الدفع", "ندفع كاش",
    ],
}


@lru_cache(maxsize=1)
def _model():
    texts, labels = [], []
    for intent, examples in TRAINING.items():
        for ex in examples:
            texts.append(normalize(ex))
            labels.append(intent)
    model = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True),
        LogisticRegression(C=20, max_iter=2000),
    )
    model.fit(texts, labels)
    return model


def classify(text: str) -> tuple[str, float]:
    """Return (intent, probability) for a raw customer message."""
    norm = normalize(text)
    if not norm:
        return "unknown", 0.0
    model = _model()
    probs = model.predict_proba([norm])[0]
    i = probs.argmax()
    return str(model.classes_[i]), float(probs[i])
