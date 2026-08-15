# Veille VUS Québec

Une V1 locale et sans service payant pour conserver l'historique des annonces,
noter deux stratégies d'achat et produire un dashboard HTML partageable.

## Démarrage

Prérequis : Python 3.11 ou plus récent.

```bash
python -m veille_vus.cli init
python -m veille_vus.cli collect
open output/index.html
```

Le collecteur continue même si une source est temporairement indisponible. La
base SQLite est dans `data/vehicles.sqlite3`. Une annonce non revue pendant 7
jours passe à **Disparu**, mais n'est jamais supprimée.

Pour ajouter une annonce ponctuelle :

```bash
python -m veille_vus.cli add-url 'https://exemple.ca/annonce/123'
```

L'extraction manuelle est volontairement prudente : titre, année, modèle, prix,
kilométrage et quelques attributs lorsqu'ils sont présents. Les champs inconnus
restent vides plutôt que d'être inventés.

## Scoring

Toutes les pondérations et notes de modèles sont dans `config.toml`. Les deux
scores sont calculés séparément, puis combinés dans `overall_score`; l'agrément
de conduite vaut seulement 5 %. Les notes sont des hypothèses initiales de
décision, pas des garanties mécaniques. Ajustez-les selon votre expérience et
faites toujours inspecter un véhicule avant achat.

## Ajouter une source

Les sources V1 lisent les objets `Vehicle` Schema.org publiés par Occasion
Beaucage, Mazda Chatel, Honda de la Capitale, Lévis Toyota, Lévis Subaru et
Desjardins Subaru. Le collecteur vérifie `robots.txt` avant les pages, fait un
seul passage quotidien et ne contourne aucune protection. Pour un flux RSS
autorisé, ajoutez une section `[[sources]]` avec `name`,
`type = "rss"`, `url` et, facultativement, `default_location`.

Pour un nouveau format, créez une fonction dans `veille_vus/sources.py` qui
retourne des dictionnaires normalisés, puis routez ce type dans `run_collect`.
Chaque dictionnaire doit au minimum contenir `source`, `external_id` et `url`.
Avant toute intégration : vérifier les conditions d'utilisation et `robots.txt`,
préférer une API/RSS/JSON officielle, limiter à une collecte quotidienne, ne pas
contourner CAPTCHA, connexion ou protection anti-robot, et ajouter un test avec
une fixture locale. Évitez d'enregistrer des données personnelles inutiles.

## Tests

Les tests essentiels n'ont aucune dépendance :

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions

Le workflow quotidien ne demande aucun secret : `GITHUB_TOKEN` suffit pour
committer la base et le dashboard, puis publier directement le dossier `output/`
sur GitHub Pages. Dans **Settings → Pages → Build and deployment**, choisissez
**GitHub Actions** comme source. Dans **Settings → Actions → General**, autorisez
les Actions à écrire dans le dépôt. SQLite dans Git convient à cette petite V1;
le workflow empêche deux publications Pages simultanées. La page et les annonces
qu'elle contient sont publiques.

## Limites V1

- La couverture RSS québécoise peut être faible; l'ajout manuel est prévu pour
  les annonces trouvées ailleurs.
- La disparition est déterminée par absence après 7 jours, pas par confirmation
  de vente.
- Les taxes, accidents et propriétaires sont stockables mais souvent absents
  des flux publics.
- Les seuils « Montréal exceptionnel » et « À contacter » reposent sur le score;
  ils doivent être recalibrés après quelques semaines de vraies annonces.
