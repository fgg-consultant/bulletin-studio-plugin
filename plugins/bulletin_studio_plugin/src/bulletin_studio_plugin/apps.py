from django.apps import AppConfig

from climweb.base.registries import plugin_registry


class BulletinStudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "bulletin_studio_plugin"

    def ready(self):
        from .plugins import BulletinStudioPlugin

        plugin_registry.register(BulletinStudioPlugin())
