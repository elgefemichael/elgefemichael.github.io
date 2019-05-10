from django.shortcuts import render
from django.http import HttpResponse
from article.models import Article, Author
from django.views import generic

class ArticleListView(generic.ListView):
    model = Article

class ArticleDetailView(generic.DetailView):
    model = Article

def index(request):
    """View function for home page of site."""

    # Generate counts of some of the main objects
    num_articles = Article.objects.all().count()
    
    # The 'all()' is implied by default.    
    num_authors = Author.objects.count()
    
    context = {
        'num_articles': num_articles,
        'num_authors': num_authors,
    }
    # Render the HTML template index.html with the data in the context variable
    return render(request, 'index.html', context=context)

def about(request):
    return render(request, 'about.html')
# Create your views here.
