from climweb.base.registries import Plugin


class BulletinStudioPlugin(Plugin):
    type = "bulletin_studio_plugin"

    def get_urls(self):
        return []
