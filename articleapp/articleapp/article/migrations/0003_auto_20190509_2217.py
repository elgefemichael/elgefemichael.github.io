# Generated by Django 2.2.1 on 2019-05-09 13:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('article', '0002_auto_20190508_2337'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
