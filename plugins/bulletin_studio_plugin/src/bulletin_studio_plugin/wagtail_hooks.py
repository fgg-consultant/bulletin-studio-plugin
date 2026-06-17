from django.urls import path, reverse, include
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from . import urls as plugin_urls


@hooks.register('register_admin_urls')
def register_bulletin_studio_plugin_urls():
    return [
        path('bulletin-studio/', include((plugin_urls, 'bulletin_studio_plugin'))),
    ]


@hooks.register('register_admin_menu_item')
def register_bulletin_studio_plugin_menu_item():
    url = reverse('bulletin_studio_plugin:index')
    return MenuItem('Bulletin Studio', url, icon_name='doc-full', order=200)
