# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-02-17 08:00
from __future__ import unicode_literals

import django.contrib.gis.geos.point
from django.db import migrations
import location_field.models.spatial


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ride',
            name='destination',
            field=location_field.models.spatial.LocationField(default=django.contrib.gis.geos.point.Point(1.0, 1.0), srid=4326),
        ),
        migrations.AlterField(
            model_name='ride',
            name='origin',
            field=location_field.models.spatial.LocationField(default=django.contrib.gis.geos.point.Point(1.0, 1.0), srid=4326),
        ),
    ]