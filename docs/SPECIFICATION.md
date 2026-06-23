# Bulletin Studio — Spécification & état

> **Source de vérité** du projet. Snapshot au 21 juin 2026.
> Historique visuel des itérations : `design/carte-decisions.html`. Captures : `design/*.png`.

---

## 1. Vision

Permettre à un service météo national (NMHS, ex. ANAM Burkina) de **produire et publier des bulletins** :

- un **bulletin = une page HTML Wagtail** (source unique) ;
- les **PDF / e-mail / carte sociale** sont des **rendus dérivés** de cette page ;
- la mise en page est **modélisée** (un modèle réutilisable, structure figée) ; chaque parution ne remplit que des **emplacements (slots)** ;
- les bulletins sont publiés **dans la section « Produits »** de Climweb ;
- à terme : **génération automatique** (données météo → texte → slots).

---

## 2. Décisions d'architecture (figées)

| Axe | Question | Décision |
|----|----------|----------|
| Format | sortie du bulletin | **Page HTML Wagtail** (pas PDF-first). PDF/e-mail/social dérivés. |
| Édition | comment remplir un numéro | **Slots (Model B)** : le modèle porte la mise en page ; le numéro = valeurs de slots → **formulaire court**. |
| Slots | comment les déclarer | **B-ii** : blocs « slot » explicites (`Slot texte`, `Slot image`). |
| Placement | où vit le bulletin | **Voie A** : le bulletin **est un `ProductItemPage` Climweb** → section Produits. |
| Édition riche | widgets de remplissage | **Composants Wagtail natifs** : Draftail (texte), AdminImageChooser (image). |

**Abandonné/retiré du code** : PDF-first (Phase A2) ; approches A1, A2 ; B-i (rôle sur bloc) ; modèle `SlotBulletin` ; pages A3 (`BulletinPage`/`BulletinIndexPage`/`BulletinPageTemplate`) ; `bulletin_pages.py`, `bulletin_create.py`, `slot_views.py` ; tout le legacy PDF.

---

## 3. État actuel (implémenté & vérifié)

### 3.1 Modèles (3)
- **`SlotBulletinTemplate`** (snippet, `PreviewableMixin`) — `name`, `slug`, `layout` (StreamField, palette B-ii). Preview live dans l'éditeur de snippet.
- **`BulletinItemPage(ProductItemPage)`** — `source_template` (FK), `slot_values` (JSON `{block_id: valeur}`), `issue_number`, `period_start` ; `date`/`valid_until` hérités. `parent_page_types=['products.ProductPage']`. Édité par un **formulaire de remplissage court** (pas l'éditeur de page). `apps.ready()` étend `ProductPage.subpage_types` pour l'autoriser sous une ProductPage.
- **`BulletinBrandingSettings`** (`BaseSiteSetting`) — couleurs de marque → variables CSS `--bm-*` dans `_styles.html`.

### 3.2 Palette de blocs B-ii (`SLOT_BLOCKS`)
| Bloc | Rôle | Contenu |
|------|------|---------|
| `masthead` | auto | en-tête (logo/titre/réf) + bandeau agence/pays + barre N°/période (lit les champs du numéro) |
| `summary` | fixe | « Dans ce numéro » (TOC) + « Sommaire » |
| `fixed_text` | fixe | titre + texte permanent (Draftail — **pas de tableaux**) |
| `html` | fixe | `RawHTMLBlock` : tableaux / HTML avancé (Draftail aplatit les tableaux) |
| `text_slot` | **slot** | texte à remplir par numéro |
| `image_slot` | **slot** | image à remplir par numéro |
| `map` | fixe | carte WMS interactive (réf. `dashboards.DashboardMap`) ; image statique en PDF/e-mail |
| `columns` | mise en page | **deux colonnes** ; chaque colonne contient fixed_text/html/text_slot/image_slot/map. Slots imbriqués gérés récursivement. |
| `data_field` | auto | valeur calculée (n°, date, période…) |
| `contact_footer` | fixe | pied : site / réseaux |

### 3.3 Remplissage d'un numéro
- **Formulaire court** `forms.BulletinFillForm` (dynamique, 1 champ par slot, **récursif** dans les colonnes) : `text_slot` → Draftail (`get_rich_text_editor_widget`), `image_slot` → `AdminImageChooser`, + métadonnées (N°, dates).
- **Aperçu live à la frappe** : `static/.../js/fill.js` POST le form à `pi_preview` → `iframe.srcdoc`. `pi_fill` et `pi_preview` partagent le form (conversion Draftail→HTML réutilisée).
- `slot_render.fill_slots()` (liste des slots) et `assemble_rows()` / `_build_row()` (fusion modèle+valeurs) sont **récursifs** (colonnes).

### 3.4 Rendu multi-format (une source)
- **Web** : `BulletinItemPage.template` → `_slot_body.html` (dans le site, URL Produits).
- **PDF** : `pi_pdf` (weasyprint), **e-mail** : `pi_email`, **carte sociale** : `pi_social` (+ OG).
- `_slot_body.html` rend : include_block (masthead/summary/contact/data_field), branches inline (fixed_text/text_slot/image_slot), `map` (web=interactif / non-web=image GetMap statique), `columns` (auto-include récursif).
- **Carte statique** : `blocks.wms_static_map_url()` + `wms_static_map_data()` (fetch serveur → data: URI, sinon placeholder). ⚠ le serveur eStation renvoie 502 sur GetMap → fallback placeholder pour l'instant (mécanisme correct).

### 3.5 Intégration Produits (Voie A)
`HomePage → ProductIndexPage → ProductPage → BulletinItemPage`. Le bulletin est listé nativement dans la page Produit (filtres année/mois, vignette/résumé surchargés), URL `/products/<produit>/<bulletin>/`.

### 3.6 Admin / UX
- **Une seule entrée de menu « Bulletin Studio »** → dashboard (`dev_dashboard`), style Wagtail natif (en-tête `wagtailadmin/shared/header.html`, onglets `w-tabs`, table `.listing`), contenu inspiré du mockup design (cartes de modèles + table des bulletins).
- Création : « Nouveau bulletin » (sous une ProductPage) → formulaire de remplissage.

### 3.7 Modèles générés (depuis PDF)
- **« Bulletin agrométéorologique décadaire »** (slug `bulletin-agromet-decadaire`) — depuis `BAD26061.pdf`. 2 colonnes (texte | figure), 14 slots. Commande `bulletin_studio_bad`.
- **« Bulletin vagues de chaleur et santé »** (slug `bulletin-vagues-chaleur-sante`) — depuis `Bulletin_climat_sante_*.pdf`. 2 colonnes (carte|situation ; tableau vigilance+vulnérables | précautions). Commande `bulletin_studio_chaleur`.

### 3.8 Génération automatique par règles (données → texte) — increment a+b ✅
Pré-remplit les `text_slot` d'un numéro à partir de **données numériques geomanager**, par **règles déterministes** (pas d'IA). L'humain relit/corrige dans le formulaire avant publication.

- **Source de données** (`data_sources.py`) : `extract_measurement(spec, issue)` enveloppe les helpers geomanager `get_raster_pixel_data` (point) et `get_geostore_data` (stat zonale `mean/sum/min/max` sur une `Geostore`), choisit le `LayerRasterFile` dont le `time` ≤ date du numéro. Dégrade en `None` si pas de donnée.
- **Moteur de règles** (`generation.py`) : `generate_slot_values(template, issue)` → `{block_id: html}`. Règles dans `SlotBulletinTemplate.generation_rules` (JSON), **clé = `slot_label`** :
  ```jsonc
  "Situation pluviométrique": {
    "measurements": {"cumul_moyen": {"layer":"Cumul pluviométrique décadaire","scope":"geostore","stat":"mean"}, ...},
    "bands": {"tendance": {"measurement":"cumul_moyen","thresholds":[[15,"faible"],[40,"modérée"],[null,"abondante"]]}},
    "text": "<p>… moyenne de {cumul_moyen} mm. Pluviométrie {tendance}.</p>", "decimals": 1
  }
  ```
  `{nom}` = nombre formaté (virgule décimale FR) ; `{nom}` défini dans `bands` = mot qualitatif (seuils). Slot sans donnée résolue → ignoré (non rempli). `scope` : `geostore` | `geostore:<nom zone>` | `point:<lon>,<lat>`.
- **UX** : bouton **« Pré-remplir depuis les données »** sur le formulaire (visible si `template.has_generation_rules`) → `pi_fill?generate=1` : les valeurs deviennent l'`initial` des champs Draftail concernés, pastille **✦ généré — à relire** + bannière. Rien n'est sauvé tant que l'utilisateur n'a pas cliqué Enregistrer.
- **Règles semées** dans `bulletin_studio_bad` pour le modèle agromet (slots « Situation pluviométrique » et « Évolution de la température moyenne »).
- **Données de démo** (`bulletin_studio_demo_data`) : ⚠ **synthétiques, pas de vraies données ANAM**. Sème 2 couches raster geomanager (« Cumul pluviométrique décadaire », « Température moyenne sous abri ») sur l'emprise Burkina, 2 décades chacune, + la hiérarchie Category/SubCategory/Dataset minimale. Vérifié bout-en-bout : extraction → texte FR → formulaire pré-rempli → save → rendu public (colonnes).

---

## 4. Carte des fichiers
```
plugins/bulletin_studio_plugin/src/bulletin_studio_plugin/
├─ blocks.py            # blocs identité partagés (Masthead, Summary, DataField, DashboardMap, ContactFooter) + wms_static_map_url/data
├─ slot_blocks.py       # palette B-ii (SLOT_BLOCKS) : FixedText, Html, TextSlot, ImageSlot, TwoColumns + sets de types
├─ slot_models.py       # SlotBulletinTemplate (snippet + preview + generation_rules JSON)
├─ product_item.py      # BulletinItemPage (= ProductItemPage)
├─ product_item_views.py# pi_create / pi_fill (?generate=1) / pi_render / pi_preview / pi_pdf / pi_email / pi_social
├─ forms.py             # BulletinFillForm (Draftail + AdminImageChooser, récursif, param `generated`)
├─ data_sources.py      # extract_measurement : valeurs numériques depuis geomanager (raster pixel / zonal)
├─ generation.py        # generate_slot_values : règles (données → texte FR), bands/seuils
├─ slot_render.py       # fill_slots, assemble_rows/_build_row, _resolve_image, sample_page (récursifs)
├─ branding.py          # BulletinBrandingSettings
├─ dev.py               # dashboard
├─ apps.py              # ready(): étend ProductPage.subpage_types
├─ wagtail_hooks.py     # MenuItem « Bulletin Studio »
├─ urls.py
├─ static/bulletin_studio_plugin/{css/fill.css, js/fill.js, css|js/locked_bulletin.* (vestige)}
├─ templates/bulletin_studio_plugin/
│   ├─ _styles.html, _slot_body.html
│   ├─ slot/render.html
│   ├─ product_item/{bulletin_item, fill, create}.html
│   ├─ pdf/bulletin_pdf.html, email/bulletin_email.html, social/bulletin_social.html
│   ├─ dev/{dashboard, _bulletins_table}.html
│   └─ blocks/{masthead, summary, contact_footer, data_field, dashboard_map}.html
└─ management/commands/
    ├─ bulletin_studio_bad.py            # modèle agromet décadaire (+ generation_rules)
    ├─ bulletin_studio_chaleur.py        # modèle chaleur/santé
    ├─ bulletin_studio_setup_products.py # chaîne Produits + bulletin démo
    ├─ bulletin_studio_demo_data.py      # ⚠ couches raster geomanager SYNTHÉTIQUES (démo génération auto)
    └─ bulletin_studio_seed.py           # ancien seed (modèle simple) — à nettoyer éventuellement
```
Migrations : jusqu'à **0017** (`generation_rules` JSON sur SlotBulletinTemplate).

---

## 5. Commandes utiles
```
docker compose -f docker-compose.dev.yml up -d        # http://localhost/admin (admin/admin)
docker compose -f docker-compose.dev.yml restart climweb-dev   # après import cassé / changements
climweb bulletin_studio_bad             # (re)génère le modèle agromet décadaire (+ règles)
climweb bulletin_studio_chaleur         # (re)génère le modèle chaleur/santé
climweb bulletin_studio_setup_products  # (re)crée la chaîne Produits + un bulletin démo
climweb bulletin_studio_demo_data       # sème les couches raster SYNTHÉTIQUES (pour la génération auto)
climweb collectstatic --noinput         # sert les static du plugin
```

---

## 6. Limites connues & reste à faire
- **Génération automatique** : increment **a+b FAIT** (extraction raster geomanager + règles déterministes → texte FR ; bouton « Pré-remplir », cf. §3.8). **Reste** : (c) génération de l'`image_slot` carte depuis une couche ; génération de texte **LLM** en surcouche du brouillon réglé ; **vraies données** (pas de flux ANAM en dev, données de démo synthétiques) ; **UI admin** pour éditer `generation_rules` (aujourd'hui semées par commande, JSON non éditable dans l'admin).
- **Carte statique réelle en PDF/e-mail** : code correct, mais le serveur WMS eStation renvoie 502 sur GetMap → placeholder pour l'instant (vrai overlay interactif aussi affecté).
- **og:image PNG** de la carte sociale : nécessite un navigateur headless.
- **i18n** : chaînes FR en dur. **Tests** : aucun.
- **Éditeur** : Draftail ne gère pas les tableaux (→ bloc `html`). Pas de colonnes imbriquées dans colonnes.
- **Base dev volatile** : ProductPage/bulletins disparaissent parfois entre sessions → relancer `bulletin_studio_setup_products`. Les snippets-modèles persistent.

---

## 7. Gotchas dev
- `static/` servis seulement après `climweb collectstatic --noinput` (nginx sert `/static` depuis `STATIC_ROOT`).
- Autoreload meurt si un import casse → `restart climweb-dev` (proxy 502 quelques s après restart).
- Commentaires Django `{# #}` interdits multi-ligne → `{% comment %}`.
- iframe d'aperçu interne : vue décorée `@xframe_options_sameorigin`.
- JS d'un bloc `extra_js` : **wrapper dans `DOMContentLoaded`** (s'exécute avant le DOM sinon).
- Sous-classer un page model Climweb au `subpage_types` figé → l'étendre dans `apps.ready()`.
- `ProductPage` requiert `introduction_title` ET `introduction_text` (+ `service`, `product` OneToOne libre).
- Tableaux : Draftail les aplatit → utiliser le bloc `html` (RawHTMLBlock).
- Setuptools < 81 dans le venv climweb (cf. CLAUDE.md).
- **Ids de blocs explicites dans les commandes** : un bloc créé depuis un dict Python brut (`tpl.layout = LAYOUT`) **n'obtient pas d'`id` StreamField** → `child.id` reste `None`, ce qui casse les clés de `slot_values` ET la génération (tout collisionne sur `None`). Les commandes (`bulletin_studio_bad/chaleur`) attribuent donc un `id` explicite (`_bid()`) à **chaque** bloc, y compris imbriqués dans `columns`. Déterministe par ordre de construction (regen ⇒ mêmes ids ⇒ `slot_values` existants préservés ; réordonner le LAYOUT décale les ids).
- **Données geomanager pour la génération** : la base dev n'a aucune couche raster ingérée → lancer `bulletin_studio_demo_data` (couches synthétiques) sinon `generate_slot_values` renvoie `{}` (aucun slot pré-rempli, dégradation silencieuse voulue).

---

## 8. Historique des itérations (résumé)
Pivot PDF→HTML → comparaison 3 approches de verrou (A1/A2/A3, A3 retenue puis dépassée) → enrichissements (2 colonnes, MapBlock WMS, multi-format, identité Burkina) → 4 retours UX → « Niveau 1 » (preview snippet, save-as-template, theming) → discussion Model A vs B → **Model B (slots)** → **B-ii** → **Voie A (ProductItemPage)** → convergence (suppression A1/A2/B-i/legacy) → dashboard page unique (style Wagtail) → carte statique PDF (#2) → éditeur riche + image chooser natifs (#3) → modèles générés depuis PDF → réintroduction du bloc 2 colonnes (slots récursifs) → recréation chaîne Produits → **génération automatique par règles (increment a+b)** : extraction raster geomanager + moteur de règles → texte FR, bouton « Pré-remplir », données de démo synthétiques ; correction du bug latent des ids de blocs `None`.
