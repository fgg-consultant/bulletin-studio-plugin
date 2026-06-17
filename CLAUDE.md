# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bulletin Studio Plugin for Climweb (Django/Wagtail framework). Generated from the official
climweb `plugin-boilerplate` cookiecutter template, following
https://climweb.readthedocs.io/en/stable/_docs/technical/extending-climweb/creating-a-plugin.html

Sibling reference project: `../dataset-helper-plugin` (mature Climweb plugin, same structure —
look there for conventions: services, models, templates, i18n, docs).
The local Climweb source (and the plugin boilerplate) lives in `../climweb`.

## Architecture

- Plugin package: `plugins/bulletin_studio_plugin/` (pip-installable, `package_dir src/`)
- Django app: `plugins/bulletin_studio_plugin/src/bulletin_studio_plugin/`
  - `apps.py` — `BulletinStudioConfig`, registers `BulletinStudioPlugin` in climweb's plugin registry on `ready()`
  - `plugins.py` — `BulletinStudioPlugin` (type `bulletin_studio_plugin`)
  - `wagtail_hooks.py` — admin URLs mounted at `/admin/bulletin-studio/` (namespace `bulletin_studio_plugin`) + root-level Wagtail admin menu item "Bulletin Studio"
  - `urls.py` / `views.py` / `templates/bulletin_studio_plugin/index.html` — index page
  - `config/settings/settings.py` — optional `setup(settings)` hook called before Django starts

Naming: package/repo use hyphens (`bulletin-studio-plugin`), Python module uses underscores
(`bulletin_studio_plugin`). Display name is "Bulletin Studio". The admin URL stays short
(`bulletin-studio/`).

## Development

```bash
docker compose -f docker-compose.dev.yml up -d   # http://localhost/admin
docker compose -f docker-compose.dev.yml build climweb-dev   # rebuild after requirements/Dockerfile changes
```

- `.env` required (see `.env.sample`): `DB_PASSWORD`, `PLUGIN_BUILD_UID`/`GID` (= `id -u` / `id -g`)
- `dev.Dockerfile` builds FROM `climweb_dev:latest` (built from `../climweb`)
- The plugin folder is bind-mounted into the container; Python code changes hot-reload,
  but new dependencies or packaging changes need a rebuild
- `docker-compose.yml` is a copy of `docker-compose.dev.yml` (kept identical)

## Gotchas

- **Do NOT let setuptools upgrade to >= 81 inside the climweb venv**: `pkg_resources` was
  removed in setuptools 81+, and climweb's `bulma` dependency still imports it at startup
  (crashes `django.setup()`). `requirements/dev.in` pins `setuptools<81`; never compile
  requirements with `pip-compile --allow-unsafe` (it pins pip/setuptools in the `.txt`,
  which then overwrite the venv's versions during the Docker build).
- New user-facing strings should be wrapped in `{% trans %}` / `gettext()` from the start
  (no locale catalogs exist yet; see `../dataset-helper-plugin` for the full i18n setup
  when they get added).
