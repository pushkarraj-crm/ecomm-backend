from django.urls import path
from .views import LoginView, MeView, OverviewView, ResourceView
urlpatterns=[
 path('login/',LoginView.as_view()),path('me/',MeView.as_view()),path('overview/',OverviewView.as_view()),
 path('resources/<str:resource>/',ResourceView.as_view()),
 path('resources/<str:resource>/<int:pk>/',ResourceView.as_view()),
]
