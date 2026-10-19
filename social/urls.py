from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')
router.register('posts', views.PostViewSet, basename='post')
urlpatterns = [
    path('auth/csrf/', views.CSRFView.as_view()), path('auth/register/', views.RegisterView.as_view()),
    path('auth/login/', views.LoginView.as_view()), path('auth/logout/', views.LogoutView.as_view()),
    path('me/', views.MeView.as_view()), path('me/password/', views.PasswordView.as_view()),
    path('posts/<int:post_id>/comments/', views.CommentListCreateView.as_view()),
    path('comments/<int:pk>/', views.CommentDetailView.as_view()), path('', include(router.urls)),
]
