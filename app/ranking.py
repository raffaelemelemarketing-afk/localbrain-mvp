import os, re
from typing import Dict

# Euristica leggera per MVP. Punteggi cumulativi.
KEYWORDS = {
    "lavoro": ["cercasi", "assunzioni", "offerta di lavoro", "selezioniamo", "contratto", "curriculum"],
    "bandi": ["bando", "finanziamento", "contributo", "graduatoria", "incentivi", "agevolazioni"],
    "eventi": ["evento", "festival", "incontro", "workshop", "seminario", "fiera"],
    "casa": ["affitto", "appartamento", "bilocale", "trilocale", "monolocale", "immobile"],
    "annunci": ["vendo", "cerco", "regalo", "annuncio", "offro"],
}

def classify_and_score(title: str, summary: str) -> Dict[str, float]:
    text = f"{title} {summary}".lower()
    best_cat, best_score = "altro", 0.0
    for cat, kws in KEYWORDS.items():
        score = 0.0
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                score += 1.0
        if score > best_score:
            best_score, best_cat = score, cat
    # Bonus se contiene la città (semplice)
    city = os.getenv("CITY", "Fiumicino").lower()
    if city in text:
        best_score += 0.5
    return {"category": best_cat, "score": float(best_score)}
