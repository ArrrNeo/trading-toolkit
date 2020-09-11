# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2020 - Naveen Rawat (rawat.nav@gmail.com)
"""

from django.db import models
from django.contrib.auth.models import User

class screener(models.Model):
    symbol = models.CharField(max_length=1000, unique=True, primary_key=True)
    price  = models.FloatField()
