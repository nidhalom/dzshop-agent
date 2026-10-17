"""Templated replies for the offline agent, in Darija (Latin script), Arabic and French.

Only DB-derived values are ever interpolated (prices, fees, totals, stock come from tool results).
"""

from __future__ import annotations

from .db import SHOP_NAME

T: dict[str, dict[str, str]] = {
    "greet": {
        "darija": "Salam! Merhba bik fi " + SHOP_NAME + ". N9der n3awnek f: les prix, la commande (paiement 3and l'istilam), "
                  "livraison w suivi t3 commande. Chno t7eb?",
        "ar": "السلام عليكم! مرحبا بك في " + SHOP_NAME + ". نقدر نساعدك في الأسعار، الطلب (الدفع عند الاستلام)، "
              "التوصيل وتتبع الطلبية. كيفاش نخدمك؟",
        "fr": "Bonjour ! Bienvenue chez " + SHOP_NAME + ". Je peux vous aider pour les prix, passer une commande "
              "(paiement à la livraison), la livraison et le suivi. Que souhaitez-vous ?",
    },
    "catalog": {
        "darija": "Hado les produits li kaynin:\n{lines}\nQoul li chno y3jbek w n3tik soum w stock.",
        "ar": "هذه منتجاتنا:\n{lines}\nقل لي أي منتج يعجبك وسأعطيك السعر والمخزون.",
        "fr": "Voici nos produits :\n{lines}\nDites-moi lequel vous intéresse pour le prix et le stock.",
    },
    "price_in": {
        "darija": "{name}: {price} DA. Kayn {stock} pièces en stock. T7eb dir commande (paiement 3and l'istilam)?",
        "ar": "{name_ar}: {price} دج. عندنا {stock} قطعة متوفرة. تحب نسجل لك طلب (الدفع عند الاستلام)؟",
        "fr": "{name} : {price} DA. {stock} pièces en stock. Souhaitez-vous commander (paiement à la livraison) ?",
    },
    "price_out": {
        "darija": "{name}: {price} DA, ama mazal ma kaynch f stock (rupture). N9der n3tik produit akhor?",
        "ar": "{name_ar}: {price} دج، لكن غير متوفر حاليا (نفد المخزون). تحب منتج آخر؟",
        "fr": "{name} : {price} DA, mais il est actuellement en rupture de stock. Un autre produit ?",
    },
    "which_product": {
        "darija": "Wa9ila ma fhemtch chno men produit. Choisi wa7ed:\n{lines}",
        "ar": "لم أفهم أي منتج تقصد. اختر واحدا:\n{lines}",
        "fr": "Je n'ai pas bien compris quel produit. Choisissez-en un :\n{lines}",
    },
    "ship_quote": {
        "darija": "Livraison l {wilaya}: {fee} DA (valeur démo), 7oudoud {eta} ayam.",
        "ar": "التوصيل إلى {wilaya}: {fee} دج (قيمة تجريبية)، خلال حوالي {eta} أيام.",
        "fr": "Livraison vers {wilaya} : {fee} DA (valeur de démonstration), environ {eta} jours.",
    },
    "ship_ask": {
        "darija": "L ina wilaya t7eb nwasslou? (ex: Alger, Oran, Blida...)",
        "ar": "إلى أي ولاية تريد التوصيل؟ (مثلا: الجزائر، وهران، البليدة...)",
        "fr": "Vers quelle wilaya souhaitez-vous être livré ? (ex : Alger, Oran, Blida...)",
    },
    "wilaya_unknown": {
        "darija": "Hadi l wilaya ma 3andnach fiha fee f had la démo. Les wilayas li kaynin: {covered}.",
        "ar": "لا يوجد سعر توصيل لهذه الولاية في النسخة التجريبية. الولايات المتاحة: {covered}.",
        "fr": "Pas de tarif pour cette wilaya dans cette démo. Wilayas disponibles : {covered}.",
    },
    "ask_wilaya": {
        "darija": "Mzyan! {item}. L ina wilaya nwasslou?",
        "ar": "ممتاز! {item}. إلى أي ولاية نوصل؟",
        "fr": "Parfait ! {item}. Dans quelle wilaya devons-nous livrer ?",
    },
    "ask_name": {
        "darija": "{ship}\nChno smiytek (l'ism w l-la9ab)?",
        "ar": "{ship}\nما هو اسمك الكامل؟",
        "fr": "{ship}\nQuel est votre nom complet ?",
    },
    "ask_phone": {
        "darija": "Merci {name}. Rani 7tajlek numéro t3 telephone (ex: 0661234567) bach nconfirmiw m3ak.",
        "ar": "شكرا {name}. أحتاج رقم هاتفك (مثال: 0661234567) لتأكيد الطلب.",
        "fr": "Merci {name}. Quel est votre numéro de téléphone (ex : 0661234567) pour confirmer la commande ?",
    },
    "bad_phone": {
        "darija": "Numéro ma sa7ich. Lazem yebda b 05, 06 wla 07 w ykoun fih 10 chiffres. 3awed ktebou.",
        "ar": "رقم الهاتف غير صحيح. يجب أن يبدأ بـ 05 أو 06 أو 07 ويتكون من 10 أرقام. أعد كتابته من فضلك.",
        "fr": "Numéro invalide. Il doit commencer par 05, 06 ou 07 et comporter 10 chiffres. Pouvez-vous le renvoyer ?",
    },
    "ask_address": {
        "darija": "Mzyan. Chno l'3enwan complet t3 livraison (cité, rue, commune)?",
        "ar": "جيد. ما هو عنوان التوصيل الكامل (الحي، الشارع، البلدية)؟",
        "fr": "Très bien. Quelle est l'adresse de livraison complète (quartier, rue, commune) ?",
    },
    "order_summary": {
        "darija": "Commande {order_id} (en attente de confirmation):\n{lines}\nLivraison {wilaya}: {fee} DA\n"
                  "Total a payer 3and l'istilam: {total} DA\nKteb \"iyeh\" bach nconfirmiw la commande.",
        "ar": "الطلب {order_id} (بانتظار التأكيد):\n{lines}\nالتوصيل إلى {wilaya}: {fee} دج\n"
              "المجموع عند الاستلام: {total} دج\nاكتب \"نعم\" لتأكيد الطلب.",
        "fr": "Commande {order_id} (en attente de confirmation) :\n{lines}\nLivraison {wilaya} : {fee} DA\n"
              "Total à payer à la livraison : {total} DA\nRépondez \"oui\" pour confirmer la commande.",
    },
    "confirmed": {
        "darija": "Commande {order_id} confirmée! Total {total} DA 3and l'istilam. Code de suivi: {code}. "
                  "Tweslek f 7oudoud {eta} ayam. Saha!",
        "ar": "تم تأكيد الطلب {order_id}! المجموع {total} دج عند الاستلام. رمز التتبع: {code}. "
              "سيصلك خلال حوالي {eta} أيام.",
        "fr": "Commande {order_id} confirmée ! Total {total} DA à la livraison. Code de suivi : {code}. "
              "Livraison sous environ {eta} jours.",
    },
    "confirm_none": {
        "darija": "Ma 3andi 7ata commande f intizar t3 confirmation. T7eb dir wa7da jdida?",
        "ar": "ليس لديك طلب بانتظار التأكيد حاليا. هل تريد إنشاء طلب جديد؟",
        "fr": "Vous n'avez aucune commande en attente de confirmation. Voulez-vous en passer une ?",
    },
    "cancelled": {
        "darija": "Commande {order_id} tannulat. Ila t7eb, nebdaw men jdid.",
        "ar": "تم إلغاء الطلب {order_id}. يمكننا البدء من جديد متى أردت.",
        "fr": "Commande {order_id} annulée. Nous pouvons recommencer quand vous voulez.",
    },
    "draft_cancelled": {
        "darija": "Mzyan, annulit had la commande. Rani hna ila t7ewej 3la 7aja okhra.",
        "ar": "حسنا، ألغيت هذا الطلب. أنا هنا إن احتجت أي شيء آخر.",
        "fr": "D'accord, j'ai annulé cette commande. Je reste disponible si besoin.",
    },
    "need_order_id": {
        "darija": "3tini numéro t3 commande (ex: DZ-1001) w numéro t3 telephone li dert bih commande.",
        "ar": "أعطني رقم الطلب (مثال: DZ-1001) ورقم الهاتف الذي استعملته في الطلب.",
        "fr": "Donnez-moi le numéro de commande (ex : DZ-1001) et le téléphone utilisé pour la commande.",
    },
    "need_phone": {
        "darija": "Bach nchouf commande {order_id}, 3tini numéro t3 telephone li dert bih commande.",
        "ar": "للتحقق من الطلب {order_id} أعطني رقم الهاتف المستعمل عند الطلب.",
        "fr": "Pour consulter la commande {order_id}, donnez-moi le téléphone utilisé lors de la commande.",
    },
    "phone_mismatch": {
        "darija": "Numéro ma ytabe9ch m3a had la commande. T2ekked w 3awed.",
        "ar": "رقم الهاتف لا يطابق هذا الطلب. تأكد وأعد المحاولة.",
        "fr": "Ce numéro ne correspond pas à cette commande. Vérifiez et réessayez.",
    },
    "order_not_found": {
        "darija": "Ma lqitch had la commande. T2ekked men numéro (ex: DZ-1001).",
        "ar": "لم أجد هذا الطلب. تأكد من الرقم (مثال: DZ-1001).",
        "fr": "Je ne trouve pas cette commande. Vérifiez le numéro (ex : DZ-1001).",
    },
    "track": {
        "darija": "Commande {order_id}: {stage} — {location}. Total {total} DA 3and l'istilam. Code: {code}.",
        "ar": "الطلب {order_id}: {stage} — {location}. المجموع {total} دج عند الاستلام. الرمز: {code}.",
        "fr": "Commande {order_id} : {stage} — {location}. Total {total} DA à la livraison. Code : {code}.",
    },
    "status_noship": {
        "darija": "Commande {order_id}: l7ala {status}. Mazal ma tzedch shipment. Total {total} DA.",
        "ar": "الطلب {order_id}: الحالة {status}. لم يتم إنشاء شحنة بعد. المجموع {total} دج.",
        "fr": "Commande {order_id} : statut {status}. Aucune expédition pour l'instant. Total {total} DA.",
    },
    "escalate": {
        "darija": "Fhemtek, rani nwasselha l wa7ed mn l'équipe (ticket {ticket}). Ykellmek f a9reb wa9t.",
        "ar": "فهمت، سأحول محادثتك إلى أحد أفراد الفريق (تذكرة {ticket}). سيتواصل معك قريبا.",
        "fr": "Compris, je transmets votre conversation à un membre de l'équipe (ticket {ticket}). Il vous contactera bientôt.",
    },
    "thanks": {
        "darija": "Bla jmil! Ila 7tajit 7aja, rani hna.",
        "ar": "العفو! أنا هنا إن احتجت أي شيء.",
        "fr": "Avec plaisir ! Je reste disponible si besoin.",
    },
    "payment": {
        "darija": "Paiement 3and l'istilam (cash): tkhalles ki yjik l colis, w nconfirmiw la commande 9bel l'envoi.",
        "ar": "الدفع عند الاستلام (نقدا): تدفع عند وصول الطرد، ونؤكد الطلب معك قبل الشحن.",
        "fr": "Paiement à la livraison (espèces) : vous payez à la réception du colis, et nous confirmons la commande avant l'envoi.",
    },
    "unknown": {
        "darija": "Ma fhemtch mzyan. T9der t3awed b tari9a okhra? (prix, commande, livraison, suivi)",
        "ar": "لم أفهم جيدا. هل يمكنك إعادة الصياغة؟ (الأسعار، الطلب، التوصيل، التتبع)",
        "fr": "Je n'ai pas bien compris. Pouvez-vous reformuler ? (prix, commande, livraison, suivi)",
    },
    "stock_fail": {
        "darija": "Sma7 lina, {error}",
        "ar": "نعتذر، {error}",
        "fr": "Désolé, {error}",
    },
}

STAGE_LABELS = {
    "label_created": {"darija": "tsejjlat l'expédition", "ar": "تم إنشاء الشحنة", "fr": "expédition enregistrée"},
    "picked_up": {"darija": "tstalmat men l'entrepôt", "ar": "تم استلام الشحنة", "fr": "colis pris en charge"},
    "in_transit": {"darija": "f tari9", "ar": "في الطريق", "fr": "en transit"},
    "at_local_hub": {"darija": "wslat l hub t3 wilayetek", "ar": "وصلت مركز ولايتك", "fr": "arrivé au hub local"},
    "out_for_delivery": {"darija": "m3a l livreur lyoum", "ar": "مع الموزع اليوم", "fr": "en cours de livraison"},
    "delivered": {"darija": "twasslat", "ar": "تم التسليم", "fr": "livré"},
}
STATUS_LABELS = {
    "pending_confirmation": {"darija": "f intizar t3 confirmation", "ar": "بانتظار التأكيد", "fr": "en attente de confirmation"},
    "confirmed": {"darija": "mconfirmya", "ar": "مؤكد", "fr": "confirmée"},
    "shipped": {"darija": "tbe3t", "ar": "تم الشحن", "fr": "expédiée"},
    "delivered": {"darija": "twasslat", "ar": "تم التسليم", "fr": "livrée"},
    "cancelled": {"darija": "mannulya", "ar": "ملغى", "fr": "annulée"},
}


WILAYA_AR = {"Alger": "الجزائر", "Oran": "وهران", "Constantine": "قسنطينة", "Blida": "البليدة", "Sétif": "سطيف",
             "Annaba": "عنابة", "Tizi Ouzou": "تيزي وزو", "Béjaïa": "بجاية", "Batna": "باتنة",
             "Tlemcen": "تلمسان", "Ghardaïa": "غرداية"}


def wname(wilaya: str, lang: str) -> str:
    return WILAYA_AR.get(wilaya, wilaya) if lang == "ar" else wilaya


def render(key: str, lang: str, **kw) -> str:
    lang = lang if lang in ("darija", "ar", "fr") else "fr"
    return T[key][lang].format(**kw)
