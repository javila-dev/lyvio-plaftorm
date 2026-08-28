from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('features/', views.features, name='features'),
    path('contact/', views.contact, name='contact'),
]
