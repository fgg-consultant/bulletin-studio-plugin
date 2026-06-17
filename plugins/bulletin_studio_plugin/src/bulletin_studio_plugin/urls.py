from django.urls import path
from django.views.i18n import JavaScriptCatalog

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('jsi18n/', JavaScriptCatalog.as_view(packages=['bulletin_studio_plugin']), name='js_catalog'),

    # palette (editor sidebar / wizard data)
    path('api/palette/geomanager/', views.geomanager_tree, name='geomanager_tree'),
    path('api/palette/publication/', views.publication_palette, name='publication_palette'),
    path('api/layers/<uuid:layer_id>/timestamps/', views.layer_timestamps, name='layer_timestamps'),

    # setup wizard
    path('api/setup/run/', views.setup_run, name='setup_run'),

    # templates
    path('api/templates/', views.template_list, name='template_list'),
    path('api/templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('api/templates/<int:pk>/layout/', views.template_layout_save, name='template_layout_save'),
    path('api/templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('api/templates/<int:pk>/duplicate/', views.template_duplicate, name='template_duplicate'),

    # map preview (template editor, stateless)
    path('api/map-preview/<uuid:layer_id>.png', views.map_preview, name='map_preview'),

    # issues
    path('api/templates/<int:pk>/issues/', views.issue_list_create, name='issue_list_create'),
    path('api/issues/<int:pk>/', views.issue_detail, name='issue_detail'),
    path('api/issues/<int:pk>/elements/<str:element_id>/render/', views.issue_element_render,
         name='issue_element_render'),
    path('api/issues/<int:pk>/generate/', views.issue_generate, name='issue_generate'),
    path('api/issues/<int:pk>/pdf/', views.issue_pdf, name='issue_pdf'),
    path('api/issues/<int:pk>/publish/', views.issue_publish, name='issue_publish'),
    path('api/issues/<int:pk>/delete/', views.issue_delete, name='issue_delete'),
]
