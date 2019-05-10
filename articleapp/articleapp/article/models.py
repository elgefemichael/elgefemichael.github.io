from django.db import models
from django.urls import reverse 
import uuid 

class Article(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey('Author', on_delete=models.SET_NULL, null=True)    
    body = models.TextField(max_length=1000, default=True, help_text='Enter a brief description of the Article')
    create_date= models.DateField(null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, help_text='Unique ID')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('article-detail', args=[str(self.id)])

class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_death = models.DateField('Died', null=True, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.last_name}, {self.first_name}'
# Create your models here.
