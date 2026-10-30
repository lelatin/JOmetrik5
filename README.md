# JOMetrik — version GitHub Pages

Comparateur de prix de clés de jeux, **sans serveur** : GitHub Actions scrape les boutiques et écrit des fichiers JSON ; le site (`index.html`) les lit.

```
index.html            interface (identique à l'original, /api/* → data/*.json)
data/                 games.json · prices.json · news.json   (écrits par les Actions)
scraper/scrape.py     scrapers Selenium + RSS repris de app.py
.github/workflows/    update-prices (quotidien) · update-news (horaire)
```

## Mise en ligne
1. Créez un dépôt GitHub (public) et poussez tout ce dossier.
2. **Settings → Pages** → Source : *Deploy from a branch* → `main` / `(root)`.
3. **Settings → Actions → General → Workflow permissions** → *Read and write*.
4. **Actions** → lancez « Mise à jour des actualités » puis « Mise à jour des prix » (*Run workflow*, avec `limit: 3` pour tester).

Le site sera sur `https://<utilisateur>.github.io/<depot>/`.

## À savoir
- Tant que le scrape n'a pas tourné, `prices.json` contient des **prix simulés** (champ `"simulated": true`). Ils servent aussi de secours quand une boutique bloque le scraper, comme dans l'original.
- Les IP de GitHub Actions sont souvent bloquées par Kinguin, Eneba et Instant Gaming : attendez-vous à du secours simulé pour ces boutiques.
- Seuls les jeux de `scraper/games_db.py` sont consultables : un site statique ne peut pas scraper « à la demande ».
- Ajouter un jeu : l'ajouter dans `games_db.py` **et** dans `data/games.json`, puis relancer le workflow.
