import datetime
from datetime import datetime
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.db.models import Avg
from django.utils.timezone import now
from djmoney.models.fields import MoneyField
from django_extensions.db.fields import (ModificationDateTimeField,
                                         CreationDateTimeField)
from moneyed.classes import Money
from django_fsm import FSMField, transition
from django.contrib.postgres.fields import JSONField
from location_field.models.spatial import LocationField

from django.contrib.gis.geos import Point

class User(AbstractUser):

    STATE_CHOICES = (
        ('available', 'Available'),
        ('requested', 'Requested'),
        ('driving', 'Driving'),
        ('unavailable', 'Unavailable'),
        ('not-responding', 'Not responding')
    )

    phone = models.CharField(max_length=20, null=False, blank=True)
    avatar = models.ImageField(upload_to='profile_picture/', blank=True, null=True)
    position = models.PointField(null=True, blank=True)
    is_driver = models.BooleanField(default=False)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='available')
    gcm_token = models.CharField(max_length=160, null=True, blank=True)
    last_ping = models.DateTimeField(null=True, blank=True)

    customer_flow = models.BooleanField(null=False, default=False, blank=True, help_text='If rider has Android phone and can sign in the app: let rider go through customer flow', verbose_name='Customer flow')
    rider_flow = models.BooleanField(null=False, default=False, blank=True, help_text='Change to IS DRIVER under EXTRA INFO and let rider go through rider flow', verbose_name='Rider flow')
    rider_profile = models.BooleanField(null=False, default=False, blank=True, help_text='Fill RIDER INFO fields', verbose_name='Rider info')
    drivers_license = models.FileField(upload_to='drivers_license/', blank=True, null=True, help_text='If licence (G and F) is valid make a clear photo')
    insurance = models.FileField(upload_to='insurance/', blank=True, null=True, help_text='If motorbike insurance is valid make a clear photo')
    id_card = models.FileField(upload_to='id_card/', blank=True, null=True, help_text='If minimum age of 20 make a clear photo')
    conduct = models.FileField(upload_to='conduct/', blank=True, null=True, help_text='If Code of Good Conduct is valid make a clear photo', verbose_name='Code of Good Conduct')
    profile_picture = models.ImageField(upload_to='profile_picture/', blank=True, null=True, help_text='Make a clear profile photo of the rider')
    test_ride = models.BooleanField(null=False, default=False, blank=True, help_text='Check rider on customer service, safety and traffic rules, and app use')    
    motorbike_check = models.BooleanField(null=False, default=False, blank=True, help_text='Check rider and customer helmet, lights, mirrors, chain, exhaust, horn, tyre profile, and brakes')    
    starters_package = models.BooleanField(null=False, default=False, blank=True, help_text='Rider received a complete starters package')
    delivery_rider = models.BooleanField(null=False, default=False, blank=True, help_text='All boxes are checked (except for clear boxes), and all files are uploaded: click SAVE. Rider is now a TWENDE RIDER!')

    base = models.CharField(max_length=80, null=False, default="", blank=True)
    birthdate = models.CharField(max_length=20, null=False, default="", blank=True, help_text='Day-Month-Year. Example: 01-01-1980')
    experience = models.CharField(max_length=20, null=False, default=" years", blank=True, help_text='Minimum of at least 2 years experience required')
    license_number = models.CharField(max_length=20, null=False, default="", blank=True, verbose_name='Plate number', help_text='Example: KMEF-082Y')
    association = models.CharField(max_length=40, null=False, default="", blank=True)
    slogan = models.CharField(max_length=80, null=False, default="", blank=True, help_text='Example: Safety First')
    documents = models.FileField(upload_to='documents/', blank=True, null=True)
    is_active       = models.BooleanField(default=True, null=False)
    is_staff        = models.BooleanField(default=False, null=False)
    
    objects = UserManager()
    geo_objects = models.GeoManager()    


    @property
    def rating(self):
        if self.is_driver:
            rate = self.driver_ride.filter(customer_rating__gt=0).aggregate(rate=Avg('customer_rating'))['rate']
        else:
            rate = self.customer_ride.filter(driver_rating__gt=0).aggregate(rate=Avg('driver_rating'))['rate']
        if rate:
            return round(rate, 1)
        return None


    def name(self):
        return "{0} {1}".format(self.first_name, self.last_name)

    def get_jwt_token(self):
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER

        payload = jwt_payload_handler(self)
        token = jwt_encode_handler(payload)
        return token


class LocationLog(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    created = CreationDateTimeField()
    location = models.PointField(null=True)

    class Meta:
        ordering = ('-created', )


class Ride(models.Model):

    def __init__(self, *args, **kwargs):
        super(Ride, self).__init__(*args, **kwargs)
        self.previous_state = self.state

    state_choices = (
        ('new', 'New'),
        ('selecting', 'Selecting'),
        ('requested', 'Requested'),
        ('accepted', 'Accepted'),
        ('driving', 'Driving'),
        ('dropoff', 'Dropping Off'),
        ('payment', 'Payment'),
        ('rating', 'Rating'),
        ('declined', 'Declined'),
        ('canceled', 'Canceled'),
        ('finalized', 'Finalized'),
    )

    payment_choices = (
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa')
    )

    customer = models.ForeignKey('delivery_api.User', related_name='customer_ride', null=True)
    driver = models.ForeignKey('delivery_api.User', null=True, blank=True, related_name='driver_ride')

    origin_text = models.CharField(max_length=500, null=True, blank=True)
    origin = LocationField(based_fields=['origin_text'], zoom=7, default=Point(1.0, 1.0))

    destination_text = models.CharField(max_length=500, null=True, blank=True)
    destination = LocationField(based_fields=['destination_text'], zoom=7, default=Point(1.0, 1.0))

    customer_start_location = models.PointField(null=True)
    driver_start_location = models.PointField(null=True)
    ride_start_location = models.PointField(null=True)
    ride_end_location = models.PointField(null=True)

    # payout = models.ForeignKey('payouts.Payout', null=True,
    #                            related_name='payout_rides',
    #                            on_delete=models.SET_NULL)

    @property
    def start(self):
        if self.ridelog_set.filter(state='driving').count():
            return self.ridelog_set.order_by('created').filter(state='driving')[0].created
        if self.state in ['accepted', 'requested']:
            return now()
        return self.created

    @property
    def end(self):
        if self.ridelog_set.filter(state='dropoff').count():
            return self.ridelog_set.order_by('created').filter(state='dropoff')[0].created
        if self.state in ['accepted', 'driving', 'dropoff']:
            return now()
        return self.updated

    @property
    def mpesa_payment(self):
        if self.payment_set.count():
            return self.payment_set.order_by('-created').all()[0]
        return None

    state = FSMField(default='new', choices=state_choices)
    payment_method = models.CharField(max_length=30, choices=payment_choices, blank=True, null=True, verbose_name='method')

    customer_rating = models.IntegerField(null=True, blank=True, verbose_name='rating cs')
    driver_rating = models.IntegerField(null=True, blank=True, verbose_name='rating rd')

    created = CreationDateTimeField()
    updated = ModificationDateTimeField()

    fare = MoneyField(decimal_places=2, max_digits=20,
                      default_currency='KES', null=True)

    live_fare = MoneyField(decimal_places=2, max_digits=20,
                           default_currency='KES', null=True)

    driver_distance = JSONField(null=True)
    distance = JSONField(null=True)
    live_distance = JSONField(null=True)

    @property
    def route(self):
        logs = self.route_points
        return [{'lat': log.coords[1], 'lng': log.coords[0]} for log in logs]

    @property
    def route_points(self):
        points = []
        try:
            until = self.end if self.end else now()
            ls = LocationLog.objects.filter(user=self.driver, created__gte=self.start, created__lte=until)
            for l in ls.all():
                points.append(l.location)
        except ValueError:
            pass
        return points

    @property
    def waypoints_distance(self):
        prev = None
        dist = 0
        for loc in self.route_points:
            if prev:
                dist += prev.distance(loc)
            prev = loc
        return "%.1f" % (dist * 100)

    def update_route(self):
        if self.driver and self.state in ['driving', 'dropoff']:
            self.destination = self.driver.position

        if not self.destination:
            self.destination = self.origin

        if self.state in ['requested', 'accepted'] and self.origin:
            self.driver_distance = calculate_distance(self.origin, self.driver.position)

        if self.state in ['driving', 'dropoff'] and self.origin and self.destination:
            self.live_distance = calculate_distance(self.origin, self.driver.position)

        if not self.destination:
            self.destination = self.origin

        if self.live_distance:
            self.live_fare = Money(calculate_fare(self.live_distance['meters']), 'KES')

        if self.driver and self.driver.position and self.customer.position and self.state in ['accepted']:
            self.driver_distance = calculate_distance(self.driver.position, self.customer.position)

        # Fare on basis of Waypoints Distance
        if self.state in ['dropoff', 'payment', 'finalized']:
            self.distance = {
                'distance': '%s km' % self.waypoints_distance,
                'duration': '-',
                'distance_meters': 1000 * float(self.waypoints_distance)
            }
            self.fare = Money(calculate_fare(int(1000 * float(self.waypoints_distance))), 'KES')

    @transition(field=state, source='new', target='requested')
    def request(self):
        self.driver.state = 'requested'
        self.driver.save()

    @transition(field=state, source='requested', target='accepted')
    def accept(self):
        self.driver.state = 'driving'
        self.driver.save()

    @transition(field=state, source='new', target='declined')
    def decline(self):
        self.driver.state = 'available'
        self.driver.save()

    @transition(field=state, source='*', target='canceled')
    def cancel(self):
        self.driver.state = 'not-responding'
        self.driver.save()

    @transition(field=state, source='accepted', target='dropoff')
    def dropoff(self):
        self.driver.state = 'driving'
        self.driver.save()

    @transition(field=state, source='*', target='payment')
    def payment(self):
        self.driver.state = 'driving'
        self.driver.save()

    @transition(field=state, source='*', target='rating')
    def rate(self):
        self.driver.state = 'driving'
        self.driver.save()

    @transition(field=state, source='*', target='finalized')
    def finalize(self):
        self.driver.state = 'available'
        self.driver.save()

    @property
    def meters(self):
        try:
            return self.distance['meters']
        except KeyError:
            return 0

    @property
    def orig(self):
        return "{},{}".format(self.origin[0], self.origin[1])

    @property
    def dest(self):
        return "{},{}".format(self.destination[0], self.destination[1])

    def __unicode__(self):
        return 'Ride {0}'.format(self.id)

    def save(self, *args, **kwargs):
        self.update_route()
        if self.driver and self.state == 'new':
            self.state = 'requested'

        # If payment method
        if self.payment_method == 'cash' and self.state == 'payment':
            self.state = 'rating'

        super(Ride, self).save(*args, **kwargs)


class RideMessage(models.Model):
    ride = models.ForeignKey('delivery_api.Ride')
    ride_state = models.CharField(max_length=20, choices=Ride.state_choices)
    title = models.CharField(max_length=100, blank=True, default='')
    message = models.CharField(max_length=100, blank=True, default='')
    receiver = models.ForeignKey('delivery_api.User')
    created = CreationDateTimeField()
    sent = models.DateTimeField(null=True)
    updated = ModificationDateTimeField()
    sound = models.CharField(max_length=200, default='default', blank=True)
    notify_helpdesk = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if RideMessage.objects.exclude(id=self.id).filter(
                ride=self.ride, receiver=self.receiver,
                ride_state=self.ride_state).count() and self.title:
            raise ValueError('Already got a message like that')
        super(RideMessage, self).save(*args, **kwargs)

    def send(self):
        # Send the message if not yet sent
        if not self.sent:
            data = {
                'title': self.title,
                'sound': self.sound,
                'message': self.message,
                'ride': self.ride.id
            }
            gcm.json_request(registration_ids=[self.receiver.gcm_token],
                             data=data,
                             priority='high')
            self.sent = now()
            self.save()


class SystemMessage(models.Model):
    subject = models.CharField(max_length=100)
    message = models.CharField(max_length=100)
    receiver = models.ForeignKey('delivery_api.User')
    sent = models.DateTimeField(null=True, blank=True, help_text="Clear datetime and send message with 'save'")
    created = CreationDateTimeField()
    updated = ModificationDateTimeField()


class BulkMessage(models.Model):
    subject = models.CharField(max_length=100)
    message = models.CharField(max_length=100)
    receivers = models.ManyToManyField('delivery_api.User')
    sent = models.DateTimeField(null=True, blank=True, help_text="Clear datetime and send message with 'save'")
    created = CreationDateTimeField()
    updated = ModificationDateTimeField()


class RideLog(models.Model):
    ride = models.ForeignKey('delivery_api.Ride')
    created = CreationDateTimeField()
    state = models.CharField(max_length=50, null=True)
    location = models.PointField(null=True)
    user = models.ForeignKey('delivery_api.User', null=True)


class Rating(models.Model):
    ride = models.ForeignKey('delivery_api.Ride')
    comments = models.CharField(max_length=256, null=True, blank=True)
    grade = models.IntegerField()


class Payment(models.Model):
    created = CreationDateTimeField()
    updated = ModificationDateTimeField()

    ride = models.ForeignKey('delivery_api.Ride')
    amount = MoneyField(decimal_places=2, max_digits=20,
                        default_currency='KES', null=True)
    phone = models.CharField(max_length=20,  null=False, blank=True)
    remote_id = models.CharField(max_length=50,  null=False, blank=True)
    transaction_id = models.CharField(max_length=50,  null=False, blank=True)
    status = models.CharField(max_length=20,  null=False, blank=True, default='New')
    mpesa_code = models.CharField(max_length=50, null=False, blank=True)

    def _get_payment_service(self):
        return PaymentService(
            consumer_key=settings.MPESA_CONSUMER_KEY,
            consumer_password=settings.MPESA_CONSUMER_SECRET,
            shortcode=settings.MPESA_SHORTCODE,
            passphrase=settings.MPESA_PASSPHRASE,
            live=settings.MPESA_LIVE_PAYMENTS
        )

    def start_payment_request(self):
        ps = self._get_payment_service()
        self.transaction_id = 'techtenat{0}'.format(self.id)
        response = ps.process_request(
            phone_number=self.phone,
            amount=int(self.amount.amount),
            callback_url='https://api.techtenant.co.ke/payment/status',
            reference=self.ride.id,
            description="Payment for Delivery ride"
        )
        PaymentResponse.objects.create(
            payment=self,
            response=response
        )
        try:
            self.remote_id = response['request_id']
            self.status = 'Started'
        except AttributeError:
            self.status = 'Failed'
        self.save()


    def check_status(self):
        ps = self._get_payment_service()
        response = ps.query_request(self.remote_id)
        PaymentResponse.objects.create(
            payment=self,
            response=response
        )

        if response['status'] == 'Failed':
            self.status = 'Failed'
            self.save()
            raise PaymentException(response['error'])
        else:
            self.status = response['status']
        self.save()

    def check_request_status(self):
        ps = self._get_payment_service()
        response = ps.transaction_status_request(
            self.phone,
            self.remote_id,
            result_url='https://api.techtenant.co.ke/payment/status'
        )
        PaymentResponse.objects.create(
            payment=self,
            response=response
        )

        if 'error' in response:
            self.status = 'failed'
            raise PaymentException(response['error'])
            self.ride.state = 'payment'
        else:
            self.status = response['status']
        self.save()

    def fake(self):
        ps = self._get_payment_service()
        response = ps.simulate_transaction(self.amount.amount, self.phone, self.remote_id)
        if 'error' in response:
            raise PaymentException(response['error'])
        self.status = response['status']
        PaymentResponse.objects.create(
            payment=self,
            response=response
        )
        self.save()

    @classmethod
    def start_payment(cls, ride):
        payment, created = Payment.objects.get_or_create(ride=ride)
        if created or not payment.remote_id:
            payment.amount = ride.fare
            payment.phone = ride.customer.phone

            payment.save()
            payment.start_payment_request()

        else:
            payment.check_status()


class PaymentResponse(models.Model):
    payment = models.ForeignKey('delivery_api.Payment', )
    created = CreationDateTimeField()
    response = models.TextField(blank=True)


class PaymentResponseLog(models.Model):
    created = CreationDateTimeField()
    response = models.TextField(blank=True)
    request = models.TextField(blank=True)


class ErrorLog(models.Model):
    ride = models.ForeignKey('delivery_api.Ride', null=True)
    user = models.ForeignKey('delivery_api.User', null=True)
    created = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=1000)
    level = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    data = models.TextField(blank=True)


class RiderRevenu(Ride):
    class Meta:
        proxy = True


class KPI(User):
    class Meta:
        proxy = True

