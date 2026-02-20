from django.urls import path
from . import views

app_name = 'activation'

urlpatterns = [
    path('activate/<str:token>/', views.activate_account, name='activate_account'),
    path('email-sent/', views.email_sent, name='activation_email_sent'),
    path('success/', views.activation_success, name='activation_success'),
    path('error/', views.activation_error, name='activation_error'),
]