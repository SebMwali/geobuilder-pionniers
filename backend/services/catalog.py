"""
Catalogue produits Geobuilder (en dur pour démarrer).
Évolution : lire depuis l'onglet 07_Ressources.
"""

# Clés normalisées -> infos produit
CATALOG = {
    "G20_MOJA": {
        "label": "G20 Moja",
        "garantie_mois": 24,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/fiches-techniques/g20_moja.html",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/manuels/g20_moja.html",
        "image_cloudinary_id": "g20_moja",
    },
    "G30_HOME": {
        "label": "G30 Home",
        "garantie_mois": 24,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/fiches-techniques/g30_home.html",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/manuels/g30_home.html",
        "image_cloudinary_id": "g30",
    },
    "SOURCE": {
        "label": "Source",
        "garantie_mois": 24,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/fiches-techniques/source.html",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/manuels/source.html",
        "image_cloudinary_id": "source",
    },
    "OCEAN_500": {
        "label": "Ocean 500",
        "garantie_mois": 36,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/fiches-techniques/ocean_500.html",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/manuels/ocean_500.html",
        "image_cloudinary_id": "ocean_500",
    },
    "TITAN_1000": {
        "label": "Titan 1000",
        "garantie_mois": 60,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/fiches-techniques/titan_1000.html",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/manuels/titan_1000.html",
        "image_cloudinary_id": "titan_1000",
    },
}


def normalize_product_key(label_or_key: str) -> str:
    """Normalise une chaîne produit en clé catalogue."""
    if not label_or_key:
        return ""
    k = label_or_key.upper().replace(" ", "_").replace("-", "_")
    # Recherche exacte
    if k in CATALOG:
        return k
    # Recherche partielle (G20 -> G20_MOJA, etc.)
    for key in CATALOG:
        if k in key or key.startswith(k):
            return key
    return k


def get_product(label_or_key: str) -> dict:
    """Retourne les infos produit, ou un fallback générique si non trouvé."""
    k = normalize_product_key(label_or_key)
    return CATALOG.get(k, {
        "label": label_or_key or "Produit Geobuilder",
        "garantie_mois": 24,
        "fiche_technique_url": "",
        "manuel_url": "",
        "image_cloudinary_id": "",
    })
