import json

from django import forms
from django.contrib.gis.geos import Point

from drf_extra_fields.fields import Base64ImageField
from oauth2_provider.models import AccessToken
from rest_framework import serializers

from delivery_api.models import Ride, User, LocationLog, ErrorLog, Payment
from sorl.thumbnail import get_thumbnail


class ImageSerializer(Base64ImageField):

    def to_representation(self, instance):
        avatar = get_thumbnail(instance, '200x200', quality=99, format='JPEG')
        if avatar:
            return avatar.url
        return None


class PointSerializer(serializers.Serializer):

    def to_internal_value(self, value):
        if not value or len(value) == 1:
            return Point(0, 0)
        return Point(value['longitude'], value['latitude'])

    def to_representation(self, value):
        if not value:
            return {}
        return {'longitude': value.coords[0], 'latitude': value.coords[1]}


class DistanceSerializer(serializers.Serializer):

    def to_representation(self, value):
        return value


class UserSerializer(serializers.ModelSerializer):
    avatar = ImageSerializer(required=False)
    position = PointSerializer(required=False)
    distance = DistanceSerializer(read_only=True)

    def to_internal_value(self, data):
        return User.objects.get(pk=data)

    class Meta:
        model = User
        fields = (
            'avatar',
            'distance',
            'first_name',
            'id',
            'last_name',
            'name',
            'phone',
            'position',
            'rating',
            'state',
            'username',
        )


class DriverSerializer(UserSerializer):
    distance = serializers.IntegerField(source='distance.m')
    base = serializers.CharField(required=False, allow_blank=True)
    experience = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    association = serializers.CharField(required=False, allow_blank=True)
    slogan = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'association',
            'avatar',
            'base',
            'email',
            'distance',
            'experience',
            'first_name',
            'gcm_token',
            'id',
            'is_driver',
            'last_name',
            'license_number',
            'name',
            'password',
            'phone',
            'position',
            'rating',
            'slogan',
            'state',
            'username',
        )


class PasswordField(serializers.CharField):
    """
    Special field to update a password field.
    """
    widget = forms.widgets.PasswordInput
    hidden_password_string = '********'

    def to_internal_value(self, value):
        """
        Hash if new value sent, else retrieve current password.
        """
        from django.contrib.auth.hashers import make_password
        if value == self.hidden_password_string or value == '':
            return self.parent.object.password
        else:
            return make_password(value)

    def to_representation(self, value):
        """
        Hide hashed-password in API display.
        """
        return self.hidden_password_string


class PhoneNumberSerializer(serializers.CharField):

    def to_internal_value(self, data):
        # validate_international_phonenumber("{}".format(data))
        return "{}".format(data)


class PlainMoneySerializer(serializers.CharField):

    def to_internal_value(self, data):
        return {
            'amount': round(data.amount),
            'currency': data.currency
        }

    def to_representation(self, value):
        if value.amount:
            return "{0} {1}".format(int(value.amount), value.currency)
        return None


class MoneySerializer(serializers.CharField):

    def to_internal_value(self, data):
        return {
            'amount': round(data.amount),
            'currency': data.currency
        }

    def to_representation(self, value):
        if value.amount:
            return {
                'amount': value.amount,
                'currency': str(value.currency)
            }
        return None


class LocationLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    location = PointSerializer()

    class Meta:
        model = LocationLog
        fields = (
            'location',
            'user',
        )


class AccountCreateSerializer(serializers.ModelSerializer):
    position = PointSerializer(required=False)
    email = serializers.EmailField(required=True)
    password = PasswordField(required=True, write_only=True, max_length=255)
    phone = PhoneNumberSerializer(required=True)

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'is_driver',
            'password',
            'phone',
            'position',
            'username',
        )


class AccountSerializer(serializers.ModelSerializer):
    position = PointSerializer(required=False, allow_null=True)
    avatar = ImageSerializer(required=False)
    password = PasswordField(required=False, write_only=True, max_length=255)
    gcm_token = serializers.CharField(required=False, write_only=True)

    base = serializers.CharField(required=False, allow_blank=True)
    experience = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    association = serializers.CharField(required=False, allow_blank=True)
    slogan = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'association',
            'avatar',
            'base',
            'email',
            'experience',
            'first_name',
            'gcm_token',
            'id',
            'is_driver',
            'last_name',
            'license_number',
            'password',
            'phone',
            'position',
            'slogan',
            'state',
            'username',
        )


class RiderProfileSerializer(serializers.ModelSerializer):
    base = serializers.CharField(required=False, allow_blank=True)
    experience = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    association = serializers.CharField(required=False, allow_blank=True)
    slogan = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'association',
            'avatar',
            'base',
            'email',
            'experience',
            'first_name',
            'gcm_token',
            'id',
            'is_driver',
            'last_name',
            'license number',
            'password',
            'phone',
            'position',
            'slogan',
            'state',
            'username',
        )


class PaymentSerializer(serializers.ModelSerializer):



    class Meta:
        model = Payment
        fields = (
            'mpesa_code',
            'status',
        )


class RideSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    driver = UserSerializer(required=False, allow_null=True)
    origin = PointSerializer(required=False)
    destination = PointSerializer(required=False, allow_null=True)
    distance = DistanceSerializer(read_only=True)
    driver_distance = DistanceSerializer(read_only=True)
    live_fare = PlainMoneySerializer(read_only=True)
    fare = PlainMoneySerializer(read_only=True)
    ride_fare = MoneySerializer(read_only=True, source='fare')
    payment = PaymentSerializer(source='mpesa_payment', read_only=True)

    class Meta:
        model = Ride
        fields = (
            'customer',
            'customer_rating',
            'destination',
            'destination_text',
            'distance',
            'waypoints_distance',
            'driver',
            'driver_distance',
            'driver_rating',
            'end',
            'fare',
            'id',
            'live_fare',
            'origin',
            'origin_text',
            'payment',
            'payment_method',
            'ride_fare',
            'start',
            'state',
        )


class RatingSerializer(serializers.ModelSerializer):
    ride = RideSerializer(read_only=True)

    class Meta:
        fields = (
            'comments',
            'grade',
            'ride',
        )


class ErrorLogSerializer(serializers.ModelSerializer):

    ride = serializers.PrimaryKeyRelatedField(queryset=Ride.objects, required=False)

    def to_internal_value(self, data):
        ret = super(ErrorLogSerializer, self).to_internal_value(data)
        try:
            ret['user'] = AccessToken.objects.get(token=data['token']).user
        except (AccessToken.DoesNotExist, KeyError):
            pass
        return ret

    class Meta:
        model = ErrorLog
        fields = (
            'data',
            'level',
            'message',
            'ride',
            'token',
        )
