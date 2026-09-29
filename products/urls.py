from django.urls import path
from .views import (
    CreateProductView,
    ProductListView,
    ProductDetailView,
    AddReviewView,
    CategoryListView,
    TrackProductInteractionView,
)

urlpatterns = [
    path('', ProductListView.as_view()),                 # GET all products
    path('categories/', CategoryListView.as_view()),     # GET seller category tree
    path('create/', CreateProductView.as_view()),        # POST create
    path('review/', AddReviewView.as_view()),            # POST review
    path('<int:product_id>/track/', TrackProductInteractionView.as_view()),
    path('<int:product_id>/', ProductDetailView.as_view()),  # GET single
]
