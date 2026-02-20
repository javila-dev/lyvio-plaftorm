from django.urls import path
from . import views

app_name = 'bot_builder'

urlpatterns = [
    path('', views.bot_config, name='config'),
    path('configure/', views.bot_configure, name='configure'),
    path('document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('flow-builder/', views.flow_builder, name='flow-builder'),
    path('preview/', views.preview_bot, name='preview'),
    path('save/', views.save_config, name='save'),
    path('save-flow/', views.save_flow, name='save-flow'),
]