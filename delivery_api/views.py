from django.shortcuts import render
import datetime
import json

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.db.models import Sum
from django.http import Http404
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView, View

from rest_framework import viewsets, generics, permissions, filters, exceptions

from delivery_api.models import Ride, User, Rating, LocationLog, ErrorLog, PaymentResponseLog
from delivery_api.permissions import IsCurrentUser
from delivery_api.serializers import (
    RideSerializer, UserSerializer, AccountSerializer, AccountCreateSerializer,
    RatingSerializer,
    DriverSerializer, LocationLogSerializer, ErrorLogSerializer)

# Create your views here.
class HomeView(TemplateView):
    template_name = 'home.html'






class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for users who are drivers
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)


class RatingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for users who are drivers
    """
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = (permissions.IsAuthenticated,)