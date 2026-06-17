def setup(settings):
    """
    Called by climweb after its own Django settings are built but before Django
    starts (climweb imports `<app>.config.settings.plugin_settings` and calls
    `setup(settings)`). The app's `static/` and `templates/` folders are already
    discovered by Django's app loaders, so nothing else is required here yet.
    """
