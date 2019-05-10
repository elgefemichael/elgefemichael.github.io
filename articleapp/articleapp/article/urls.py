from django.urls import path
from article import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('articles/', views.ArticleListView.as_view(), name='article'),
    path('article/<uuid:pk>', views.ArticleDetailView.as_view(), name='article-detail')
]

