# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2020 - Naveen Rawat (rawat.nav@gmail.com)
"""

from django.db import models
from django.contrib.auth.models import User

class screener(models.Model):
    price = models.FloatField(default=0)
    epsActual = models.FloatField(default=0, null=True)
    epsEstimate = models.FloatField(default=0, null=True)
    epsSurprisePC = models.FloatField(default=0, null=True)
    options = models.BooleanField(default=False)
    mostRecentER = models.DateTimeField(null=True)
    sector = models.CharField(max_length=100, default='')
    industry = models.CharField(max_length=100, default='')
    marketCap = models.IntegerField(default=0) # in 1000
    symbol = models.CharField(max_length=1000, unique=True, primary_key=True)