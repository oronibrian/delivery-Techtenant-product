import datetime
import pytz
import csv

from django.conf.urls import url
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.gis import admin

from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Case, When
from django.db.models import Count
from django.db.models import Sum
from django.db.models.fields.files import FieldFile
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from rangefilter.filter import DateRangeFilter

from delivery_api.exceptions import PaymentException
from delivery_api.models import (
    KPI, RiderRevenu, BulkMessage, PaymentResponseLog, Ride,
    User, RideLog, RideMessage, LocationLog, SystemMessage,
    Payment, PaymentResponse, ErrorLog
)


def prep_field(request, obj, field, manyToManySep=';'):
    """ Returns the field as a unicode string. If the field is a callable, it
    attempts to call it first, without arguments.
    """
    if '__' in field:
        bits = field.split('__')
        field = bits.pop()

        for bit in bits:
            obj = getattr(obj, bit, None)

            if obj is None:
                return ""

    attr = getattr(obj, field)

    if isinstance(attr, (FieldFile,)):
        attr = request.build_absolute_uri(attr.url)

    output = attr() if callable(attr) else attr

    if isinstance(output, (list, tuple, QuerySet)):
        output = manyToManySep.join([str(item) for item in output])
    return unicode(output).encode('utf-8') if output else ""


def export_as_csv_action(description="Export as CSV", fields=None, exclude=None, header=True,
                         manyToManySep=';'):
    """ This function returns an export csv action. """

    def export_as_csv(modeladmin, request, queryset):
        """ 
        Generic csv export admin action.
        Based on http://djangosnippets.org/snippets/2712/
        """
        opts = modeladmin.model._meta
        field_names = [field.name for field in opts.fields]
        labels = []

        if exclude:
            field_names = [f for f in field_names if f not in exclude]

        elif fields:
            try:
                field_names = [field for field, _ in fields]
                labels = [label for _, label in fields]
            except ValueError:
                field_names = [field for field in fields]
                labels = field_names

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % (
            unicode(opts).replace('.', '_')
        )

        writer = csv.writer(response)

        if header:
            writer.writerow(labels if labels else field_names)

        for obj in queryset:
            writer.writerow([prep_field(request, obj, field, manyToManySep) for field in field_names])
        return response

    export_as_csv.short_description = description
    export_as_csv.acts_on_all = True
    return export_as_csv


class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('username', 'position', )


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ('username', 'position', )


class CustomUserAdmin(admin.OSMGeoAdmin, UserAdmin):

    openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_filter = (('date_joined', DateRangeFilter), 'is_driver', 'is_superuser', 'state', 'groups', 'last_ping')

    list_display = ('username', 'first_name', 'last_name',
                    'last_ping', 'date_joined',
                    'is_driver', 'state', 'rating',
                    'phone', 'email')

    actions = ('bulk_message', )

    readonly_fields = ('rider_rides', 'customer_rides')

    rider_fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Extra info'), {'fields': ('phone', 'avatar', 'gcm_token',
                                      'is_driver', 'state')}),
        (_('Rider Docs'), {'fields': ('customer_flow', 'rider_flow', 'drivers_license',
                                        'insurance', 'id_card', 'conduct', 'rider_profile',
                                        'profile_picture', 'test_ride', 'motorbike_check',
                                        'starters_package', 'delivery_rider')}),
        (_('Rider info'), {'fields': ('base', 'birthdate', 'experience', 'license_number',
                                        'association', 'slogan', 'documents')}),
        (_('Rides'), {'fields': ('rider_rides', 'customer_rides')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Location'), {'fields': ('position', )}))

    customer_fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Extra info'), {'fields': ('phone', 'avatar', 'gcm_token',
                                      'is_driver', 'state')}),
        (_('Rides'), {'fields': ('rider_rides', 'customer_rides')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Location'), {'fields': ('position', )}))

    def get_fieldsets(self, request, obj=None):
        if obj and obj.is_driver == True:
            return self.rider_fieldsets
        return self.customer_fieldsets

    def rider_rides(self, obj):
        rides = Ride.objects.filter(driver=obj)
        url = '{}?driver_id={}'.format(reverse('admin:delivery_api_ride_changelist'), obj.id)
        return format_html('<a href="{}">{} rides ({} finalized)</a>'.format(url, rides.count(),
                                                              rides.filter(state='finalized').count()))
    rider_rides.short_description = 'Rides as rider'

    def customer_rides(self, obj):
        rides = Ride.objects.filter(customer=obj)
        url = '{}?customer_id={}'.format(reverse('admin:delivery_api_ride_changelist'), obj.id)
        return format_html('<a href="{}">{} rides ({} finalized)</a>'.format(url, rides.count(),
                                                              rides.filter(state='finalized').count()))
    customer_rides.short_description = 'Rides as customer'

    def bulk_message(self, request, queryset):
        message = BulkMessage.objects.create()
        message.receivers = queryset
        url = reverse('admin:delivery_api_bulkmessage_change', args=(message.id, ))
        return redirect(url)
    bulk_message.short_description = "Send bulk message to selected users."


admin.site.register(User, CustomUserAdmin)


class LocationLogAdmin(admin.OSMGeoAdmin):

    openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    raw_id_fields = ('user', )
    list_display = ('created', 'user', 'position')
    readonly_fields = ('user', 'created')
    fields = readonly_fields + ('position', )

    def position(self, obj):
        if not obj.location.coords:
            return None
        return "{1},{0}".format(obj.location.coords[0], obj.location.coords[1])

admin.site.register(LocationLog, LocationLogAdmin)


class RideLogInline(admin.TabularInline):
    readonly_fields = ('created', 'state', 'location')
    fields = readonly_fields
    model = RideLog
    extra = 0
    can_delete = False

    def has_add_permission(self, request):
        return False


class RideMessageInline(admin.TabularInline):
    readonly_fields = ('created', 'ride_state', 'receiver', 'title', 'message')
    fields = readonly_fields + ('ride', )
    model = RideMessage
    extra = 0

    def has_add_permission(self, request):
        return False


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ('phone', 'status', 'remote_id', 'mpesa_code', 'amount', 'transaction_id')

    def has_add_permission(self, request):
        return False

    can_delete = False


class RideAdmin(admin.OSMGeoAdmin):

    openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    raw_id_fields = ('customer', 'driver')

    date_hierarchy = 'created'

    search_fields = ('customer__username', 'driver__username', 'state')

    list_filter = (('created', DateRangeFilter), 'state', 'payment_method')

    list_display = (
        'id', 'customer', 'driver',
        'ride_date', 'ride_time',
        'ride_week', 'state',
        'waypoints_distance', 'fare',
        'payment_method', 'customer_rating',
        'driver_rating',)

    readonly_fields = (
        'rider_distance', 'ride_distance',
        'waypoints_distance',
        'live', 'fare', 'live_fare', 'map')

    fieldsets = (
        (None, {'fields': ('customer', 'driver', 'state', 'payment_method',
                                         'customer_rating', 'driver_rating',)}),
        (_('Detail'), {'fields': ('rider_distance', 'ride_distance','waypoints_distance',
                                         'live', 'fare', 'live_fare', 'map',)}),
        (_('Maps'), {'fields': ('origin', 'origin_text',
                                         'destination', 'destination_text',)}))

    export_fields = [
        ('created', 'date'),
        ('customer__username', 'customer'),
        ('driver__username', 'driver'),
        ('state', 'state'),
        ('meters', 'distance'),
        ('orig', 'origin'),
        ('dest', 'destination'),
        ('fare__amount', 'fare'),
        ('payment_method', 'payment method'),
    ]

    actions = (export_as_csv_action(fields=export_fields),)

    def map(self, obj):
        return "<iframe style='width:600px; height: 400px; border: 0'" \
               " src='{0}/map/{1}'></iframe>".format('127.0.0.1:8000', obj.id)

    map.allow_tags = True

    def rider_distance(self, obj):
        if not obj.driver_distance:
            return '-'
        return '{0}, {1}'.format(obj.driver_distance['distance'], obj.driver_distance['duration'])

    def live(self, obj):
        if not obj.live_distance:
            return '-'
        return '{0}, {1}'.format(obj.live_distance['distance'], obj.live_distance['duration'])

    def ride_distance(self, obj):
        if not obj.distance:
            return '-'
        return '{0}'.format(obj.distance['distance'])
    ride_distance.admin_order_field = 'distance'

    def ride_date(self, obj):
        created_tz_naive = pytz.timezone('Africa/Nairobi')
        created_tz_aware = obj.created.astimezone(created_tz_naive)
        if not obj.created:
            return '-'
        return datetime.datetime.date(obj.created)
    ride_date.admin_order_field = 'created'
    ride_date.short_description = 'date'

    def ride_time(self, obj):
        created_tz_naive = pytz.timezone('Africa/Nairobi')
        created_tz_aware = obj.created.astimezone(created_tz_naive)
        if not obj.created:
            return '-'
        return datetime.datetime.time(created_tz_aware)
    ride_time.admin_order_field = 'created'
    ride_time.short_description = 'time'

    def ride_week(self, obj):
        if not obj.created:
            return '-'
        return datetime.datetime.date(obj.created).isocalendar()[1]
    ride_week.admin_order_field = 'created'
    ride_week.short_description = 'week'

    def waypoints_distance(self, obj):
        return obj.waypoints_distance
    waypoints_distance.short_description = 'dist.' 

    inlines = (RideLogInline, RideMessageInline, PaymentInline)

    class Media:
        js = ('assets/js/auto-refresh.js',)

admin.site.register(Ride, RideAdmin)

# admin.site.register(Ride, admin.OSMGeoAdmin)

class SystemMessageAdmin(admin.ModelAdmin):

    model = SystemMessage
    list_display = ('created', 'receiver', 'subject', 'message')
    raw_id_fields = ('receiver', )
    fields = ('receiver', 'subject', 'message', 'sent')

admin.site.register(SystemMessage, SystemMessageAdmin)


class BulkMessageAdmin(admin.ModelAdmin):

    model = BulkMessage
    list_display = ('created', 'subject', 'message')
    raw_id_fields = ('receivers', )
    fields = ('subject', 'message', 'receivers', 'sent')

admin.site.register(BulkMessage, BulkMessageAdmin)


class PaymentResponseInline(admin.StackedInline):

    model = PaymentResponse
    readonly_fields = ('created', 'response')
    fields = readonly_fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request):
        return False


class PaymentAdmin(admin.ModelAdmin):

    model = Payment
    list_display = ('created', 'status', 'phone', 'amount', 'ride')
    actions = ['check_statuses', 'payment_request']
    raw_id_fields = ('ride', )
    inlines = [PaymentResponseInline]

    def get_urls(self):
        urls = super(PaymentAdmin, self).get_urls()
        process_urls = [
            url(r'^check_status/(?P<pk>\d+)/$',
                self.check_status,
                name="api_payments_check"),
            url(r'^start/(?P<pk>\d+)/$',
                self.start,
                name="api_payments_start"),
            url(r'^check_request/(?P<pk>\d+)/$',
                self.check_request,
                name="api_payments_check_request"),
        ]
        return process_urls + urls

    def check_status(self, request, pk=None):
        payment = Payment.objects.get(pk=pk)
        try:
            payment.check_status()
        except PaymentException as e:
            self.message_user(request=request,
                              message='Payment status check failed: {}'.format(e),
                              level='ERROR')
        payment_url = reverse('admin:delivery_api_payment_change', args=(payment.id,))
        return HttpResponseRedirect(payment_url)

    def start(self, request, pk=None):
        payment = Payment.objects.get(pk=pk)
        try:
            payment.start_payment_request()
        except PaymentException as e:
            self.message_user(request=request,
                              message='Payment initiation failed: {}'.format(e),
                              level='ERROR')
        payment_url = reverse('admin:delivery_api_payment_change', args=(payment.id,))
        return HttpResponseRedirect(payment_url)

    def check_request(self, request, pk=None):
        payment = Payment.objects.get(pk=pk)
        try:
            payment.check_request_status()
        except PaymentException as e:
            self.message_user(request=request,
                              message='Error checking payment: {}'.format(e),
                              level='ERROR')
        payment_url = reverse('admin:delivery_api_payment_change', args=(payment.id,))
        return HttpResponseRedirect(payment_url)

    def check_statuses(self, request, queryset):
        for payment in queryset:
            payment.check_status()
    check_statuses.short_description = 'Check status'

    def payment_request(self, request, queryset):
        for payment in queryset:
            payment.start_payment_request()
    payment_request.short_description = 'Start payment request'


admin.site.register(Payment, PaymentAdmin)


class PaymentResponseLogAdmin(admin.ModelAdmin):

    readonly_fields = ('created', )
    list_display = ('created', )
    fields = ('created', 'response', 'request')


admin.site.register(PaymentResponseLog, PaymentResponseLogAdmin)


class RideLogAdmin(admin.OSMGeoAdmin):

    openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    model = RideLog
    list_display = ('created', 'ride', 'state', 'position')
    list_filter = ('state',)

    def position(self, obj):
        if not obj.location or obj.location.coords:
            return None
        return "{1},{0}".format(obj.location.coords[0], obj.location.coords[1])


admin.site.register(RideLog, RideLogAdmin)


class ErrorLogAdmin(admin.ModelAdmin):

    readonly_fields = ('created', 'ride', 'user', 'message', 'data')
    list_display = ('created', 'level', 'message', 'user')

    list_filter = ('level', )

admin.site.register(ErrorLog, ErrorLogAdmin)


@admin.register(RiderRevenu)
class RiderRevenuAdmin(admin.ModelAdmin):

    date_hierarchy = 'created'

    search_fields = ('driver__first_name', 'driver__last_name', 'driver__base')

    list_filter = ('driver__base', ('created', DateRangeFilter))

    change_list_template = 'admin_dashboard/rider_revenu.html'
    def changelist_view(self, request, extra_context=None):

        response = super(RiderRevenuAdmin, self).changelist_view(request, extra_context=None)

        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response

        metrics = {
            'revenu_cash': Coalesce(Sum(Case(When(payment_method='cash', then='fare'))), 0),
            'revenu_mpesa': Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0),
            'revenu_total': Coalesce(Sum('fare'), 0),
            'fee_cash': Coalesce(Sum(Case(When(payment_method='cash', then='fare'))), 0) * 2/10,
            'fee_mpesa': Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0) * 2/10,
            'fee_total': Coalesce(Sum('fare'), 0) * 2/10,
            'balance_cash': Coalesce(Sum(Case(When(payment_method='cash', then='fare'))), 0) * 2/10 * -1,
            'balance_mpesa': Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0)
                 - Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0) * 2/10,
            'balance_total': (Coalesce(Sum(Case(When(payment_method='cash', then='fare'))), 0) * 2/10 * -1)
                 + (Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0)
                 - Coalesce(Sum(Case(When(payment_method='mpesa', then='fare'))), 0) * 2/10),
            }

        response.context_data['revenu'] = list(qs
            .values('driver__first_name', 'driver__last_name', 'driver__base').distinct()
            .annotate(**metrics).order_by('driver__first_name'))

        response.context_data['revenu_total'] = dict(qs.aggregate(**metrics))

        return response


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):

    date_hierarchy = 'date_joined'

    change_list_template = 'admin_dashboard/kpi.html'

    def changelist_view(self, request, extra_context=None):

        response = super(KPIAdmin, self).changelist_view(request, extra_context=None)

        truncate_date = connection.ops.date_trunc_sql('month', 'date_joined')
        qs = User.objects.extra({'month': truncate_date})

        metrics = {
            'total_customer': Count(Case(When(is_driver=False, then='pk'))),
            'total_rider': Count(Case(When(is_driver=True, then='pk'))),
            }

        response.context_data['signups'] = qs.values('month').annotate(**metrics).order_by('month')
        response.context_data['signups_total'] = dict(qs.aggregate(**metrics))

        return response