# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-05-08 05:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0041_recipe_configopts'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagecomparisonrecipe',
            name='sha256sum',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
