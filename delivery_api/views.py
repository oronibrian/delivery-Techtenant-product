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





class HomeView(TemplateView):
    template_name = 'home.html'


class MapView(TemplateView):
    template_name = 'map.html'

    def get_context_data(self, **kwargs):
        context = super(MapView, self).get_context_data(**kwargs)
        rides = []
        for obj in Ride.objects.order_by('-created').filter(state__in=['finalized']).all()[0:10]:
            if obj.origin and obj.destination and obj.driver:
                rides += [{
                    'name': "{0} {1}".format(obj.driver.first_name, obj.created.strftime('%d-%m-%Y %H:%M')),
                    'route': obj.route

                }]
        context['rides'] = rides
        return context


class RideMapView(TemplateView):
    template_name = 'map.html'

    def get_context_data(self, **kwargs):
        context = super(RideMapView, self).get_context_data(**kwargs)
        rides = []
        pk = kwargs.get('pk', 4)
        obj = Ride.objects.get(pk=pk)
        rides = []
        if obj.origin and obj.destination and obj.driver:
            rides += [{
                'name': "{0} {1}".format(obj.driver.first_name, obj.created.strftime('%d-%m-%Y %H:%M')),
                'route': obj.route

            }]
        context['rides'] = rides
        return context


class UserMapView(TemplateView):
    template_name = 'map.html'

    def get_context_data(self, **kwargs):
        context = super(UserMapView, self).get_context_data(**kwargs)
        dots = []
        pk = kwargs.get('pk', 4)
        user = User.objects.get(pk=pk)
        for obj in user.locationlog_set.order_by('-created')[0:200]:
            loc = obj.location
            if loc:
                dots += [{
                    'name': str(user.first_name),
                    'is_driver': int(user.is_driver),
                    'longitude': loc.coords[0],
                    'latitude': loc.coords[1]
                }]
        context['dots'] = dots
        return context


class KpiView(View):

    def get(self, request):
        # Customer signups
        # Signups at beginning of the month (in this case 1 January 2017)
        customer_signups = User.objects.exclude(date_joined__gt=datetime.date(2017, 12, 31)).filter(
            is_driver=False).count()

        # New signups (organic and paid; in this case for January 2017)
        customer_signups_new = User.objects.filter(date_joined__month=1, date_joined__year=2017,
                                                   is_driver=False).count()

        # m/m growth new signups = New signups month 2 / New signups month 1 - 1 * 100 (to be added later)


        # Paying customers
        # Customers paying
        rides = Ride.objects.filter(created__month=7, created__year=2017, state='finalized')
        customer_paying = rides.values_list('customer', flat=False).distinct().count()

        # New customers paying
        customer_paying_new = User.objects.filter(date_joined__month=8, date_joined__year=2017, is_driver=False,
                                                  customer_ride=True).count()

        # Lost customers paying: customer_paying.lastmonth 
        # customer_lost_month=2 = customer_paying_month=1 - customer_paying_month=2 + customer_paying_new_month=2

        # Rider signups
        # Signups at beginning of the month (in this case 1 January 2017)
        rider_signups = User.objects.exclude(date_joined__gt=datetime.date(2016, 12, 31)).filter(is_driver=True).count()

        # New signups (organic and paid; in this case for January 2017)
        rider_signups_new = User.objects.filter(date_joined__month=10, date_joined__year=2017, is_driver=True).count()

        # m/m growth new signups = New signups month 2 / New signups month 1 - 1 * 100 (to be added later)        


        # Active riders
        # Riders available
        rider_available = User.objects.filter(last_ping__month=7, is_driver=True).count()

        # Riders active (test value with larger database since 'driver' might include customers)        
        rider_active = rides.values_list('driver', flat=True).distinct().count()

        # New riders active
        rider_active_new = User.objects.filter(date_joined__month=8, date_joined__year=2017, is_driver=True,
                                               driver_ride=True).count()

        # Engagement stats
        # Rides (finalized; in this case for January 2017)
        rides_finalized = Ride.objects.filter(created__month=12, created__year=2017, state='finalized').count()

        # Live stats
        # Customers (signups)
        customer_signups_live = User.objects.filter(is_driver=False).count()

        # Riders (signups)
        rider_signups_live = User.objects.filter(is_driver=True).count()

        # Riders available
        rider_available_live = User.objects.filter(state='available', is_driver=True).count()

        # Rides finalized
        rides_finalized_live = Ride.objects.filter(state='finalized').count()

        #Revenue table (total, cash, mpesa, twende)        
        revenue_total = Ride.objects.filter(created__month=10, created__year=2017, state='finalized').aggregate(Sum('fare')).get('fare__sum')

        revenue_cash = Ride.objects.filter(created__month=10, created__year=2017, state='finalized', payment_method='cash').aggregate(Sum('fare')).get('fare__sum')

        revenue_mpesa = Ride.objects.filter(created__month=10, created__year=2017, state='finalized', payment_method='mpesa').aggregate(Sum('fare')).get('fare__sum')

        # revenue_twende = revenue_total * 2/10

        # Table to test KPIs
        return HttpResponse("<h1>Signups: " + str(rides_finalized) + "</h1>" "<br>"
                                                                     "<h1>New signups: " + str(
            rider_signups_new) + "</h1>" "<br>"
                                 "<table>"
                                 "<tr>" "<th></th>" "<th>January</th>" "<th>February</th>" "<th>March</th>" "</str>"
                                 "<tr>" "<td>Rides</td>" "<td>" + str(customer_signups) + "</td>" "<td>" + str(
            customer_paying_new) + "</td>" "<td>March</td>" "</tr>"
                                   "</table>")

    
@method_decorator(csrf_exempt, name='dispatch')
class MpesaStatusUpdate(View):

    def post(self, request, *args, **kwargs):
        try:
            body = json.dumps(eval(request.body))
        except SyntaxError:
            body = json.dumps(request.POST)
        PaymentResponseLog.objects.create(
            request=body,
            response=json.dumps(kwargs)
        )
        return HttpResponse('success')

# API views

class AccountListView(generics.CreateAPIView):
    """
    Create an account
    """
    queryset = User.objects.all()
    serializer_class = AccountCreateSerializer


class LocationLogView(generics.CreateAPIView):
    """
    Update geo location
    """
    queryset = LocationLog.objects.all()
    serializer_class = LocationLogSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AccountMeView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsCurrentUser,)
    queryset = User.objects.all()
    serializer_class = AccountSerializer

    def get_object(self):
        if self.request.user.is_authenticated():
            user = self.request.user
            update_last_login(None, user)
            return user
        raise Http404


class DriverListView(generics.ListAPIView):
    """
    API endpoint for users who are drivers
    """
    queryset = User.geo_objects.filter(is_driver=True)
    serializer_class = DriverSerializer
    filter_backends = (filters.OrderingFilter,)

    def get_queryset(self):
        if 'latitude' in self.request.query_params and \
                        'longitude' in self.request.query_params:
            point = Point(float(self.request.query_params['longitude']),
                          float(self.request.query_params['latitude']))
        else:
            raise exceptions.ParseError('Latitude and longitude are required')
        qs = self.queryset
        qs = qs.filter(position__distance_lt=(point, Distance(km=settings.MAXIMUM_DRIVER_DISTANCE)))
        qs = qs.distance(point).order_by('distance')
        qs = qs.filter(state='available')
        return qs

    def get_serializer_context(self):
        return {'request': self.request}


class DriverDetailView(generics.RetrieveAPIView):
    """
    API endpoint for users who are drivers
    """
    queryset = User.geo_objects.filter(is_driver=True)
    serializer_class = DriverSerializer
    filter_backends = (filters.OrderingFilter,)

    def get_queryset(self):
        if 'latitude' in self.request.query_params and \
                        'longitude' in self.request.query_params:
            point = Point(float(self.request.query_params['longitude']),
                          float(self.request.query_params['latitude']))
        else:
            raise exceptions.ParseError('Latitude and longitude are required')
        qs = self.queryset
        qs = qs.filter(position__distance_lt=(point, Distance(km=settings.MAXIMUM_DRIVER_DISTANCE)))
        qs = qs.distance(point).order_by('distance')
        return qs

    def get_serializer_context(self):
        return {'request': self.request}


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


class RideDetailView(generics.RetrieveUpdateAPIView):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        rides = self.queryset
        if self.request.user.is_driver:
            rides = rides.filter(driver=self.request.user)
        else:
            rides = rides.filter(customer=self.request.user)
        return rides

    def perform_update(self, serializer):
        if self.request.user.is_driver:
            return serializer.save(driver=self.request.user)
        return serializer.save()


class RideListView(generics.ListCreateAPIView):
    """
    API endpoint for rides
    """
    queryset = Ride.objects.order_by('-created').all()
    serializer_class = RideSerializer
    permission_classes = (permissions.IsAuthenticated,)


    def get_queryset(self):
        rides = self.queryset
        if self.request.user.is_driver:
            rides = rides.filter(driver=self.request.user)
        else:
            rides = rides.filter(customer=self.request.user)        
        if rides.count():
            ride = rides[0]
            # check that the latest ride has a relevant state 
            if ride.state in ['requested', 'accepted', 'driving', 'dropoff', 'payment', 'rating']:
                # Return only the latest ride
                return [rides[0]]
        # Return empty results set
        return []

    def perform_create(self, serializer):
        return serializer.save(customer=self.request.user)


class RecentRideListView(generics.ListAPIView):
    """
    API endpoint for recent rides
    """
    queryset = Ride.objects.order_by('-created').filter(state='finalized').all()
    serializer_class = RideSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        rides = self.queryset
        if self.request.user.is_driver:
            rides = rides.filter(driver=self.request.user)
        else:
            rides = rides.filter(customer=self.request.user)
        if rides.count():
            # Return only the latest 10 rides
            return rides[0:10]
        return rides


class ErrorLogView(generics.CreateAPIView):

    queryset = ErrorLog.objects
    serializer_class = ErrorLogSerializer
