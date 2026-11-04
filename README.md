# JOMetrik — version GitHub Pages

Comparateur de prix de clés de jeux, **sans serveur** : GitHub Actions scrape les boutiques et écrit des fichiers JSON ; le site (`index.html`) les lit.

```
index.html              interface (/api/* → fichiers JSON statiques)
data/index.json         liste légère des jeux (suggestions, ticker « Top drops »)
data/prices/<slug>.json un fichier par jeu : offres, image, historique des prix réels
data/news.json          actualités (RSS)
scraper/scrape.py       scrapers Selenium + RSS
.github/workflows/      update-prices (quotidien) · update-news (horaire)
```

## Mise en ligne
1. Dépôt GitHub public, tout le dossier poussé.
2. **Settings → Pages** → *Deploy from a branch* → `main` / `(root)`.
3. **Settings → Actions → General → Workflow permissions** → *Read and write*.
4. **Actions** → lancez « Mise à jour des actualités » puis « Mise à jour des prix » (`limit: 3` pour tester).

## À savoir
- Le site ne charge que le fichier du jeu consulté (~3 Ko) au lieu d'une base de 786 Ko.
- Les offres avec `"simulated": true` sont des **estimations** (secours quand une boutique bloque le scraper, fréquent pour Kinguin, Eneba et Instant Gaming depuis GitHub Actions). Le site les affiche avec un badge « ESTIMATION », ne les utilise pas pour le « meilleur prix » s'il existe des prix réels, et ne les enregistre jamais dans l'historique.
- `history` : un relevé par jour (prix réel minimum), 90 jours conservés. La courbe apparaît à partir de 2 relevés.
- Ajouter un jeu : l'ajouter dans `scraper/games_db.py` puis lancer le workflow (l'index est reconstruit automatiquement). Reconstruire l'index seul : `python scraper/scrape.py --index`.
- Partager un jeu : `https://<site>/?jeu=Elden%20Ring`.
