"""delivery URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers

from delivery_api import views
from delivery_api.views import HomeView,MapView, UserMapView, RideMapView, KpiView, DriverListView, DriverDetailView
from rest_framework_jwt.views import obtain_jwt_token


router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)

urlpatterns = [
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^map$', MapView.as_view(), name='map'),
    url(r'^map/(?P<pk>[0-9]+)$', RideMapView.as_view(), name='ride-map'),
    url(r'^user/(?P<pk>[0-9]+)$', UserMapView.as_view(), name='user-map'),
    url(r'^drivers/$', DriverListView.as_view(), name='driver-list'),
    url(r'^drivers/(?P<pk>[0-9]+)$', DriverDetailView.as_view(), name='driver-detail'),
    url(r'^kpi$', KpiView.as_view(), name='KpiView'),

    url(r'^api/', include(router.urls)),

    url(r'^payment/status$', views.MpesaStatusUpdate.as_view(), name='mpesa-status-update'),

    url(r'^api/rides/$', views.RideListView.as_view(), name='ride-list'),
    url(r'^api/rides/(?P<pk>[0-9]+)/$', views.RideDetailView.as_view(), name='ride-detail'),
    url(r'^api/recent-rides/$', views.RecentRideListView.as_view(), name='recent-ride-list'),

    url(r'^api/drivers/$', DriverListView.as_view(), name='driver-list'),
    url(r'^api/drivers/(?P<pk>[0-9]+)$', DriverDetailView.as_view(), name='driver-detail'),

    url(r'^api/accounts/mine$', views.AccountMeView.as_view(), name='account-me'),
    url(r'^api/accounts/$', views.AccountListView.as_view(), name='account-list'),
    url(r'^api/token-auth/', obtain_jwt_token,name='token-auth'),

    url(r'^api/location/$', views.LocationLogView.as_view(), name='location-log'),
    url(r'^api/auth/', include('rest_framework_social_oauth2.urls')),

    url(r'^api/errors/$', views.ErrorLogView.as_view(), name='error-log'),

    url(r'^jet/', include('jet.urls', 'jet')),  # Django JET URLS
    url(r'^jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),  # Django JET dashboard URLS
    url(r'^admin/', include(admin.site.urls)),

    # url(r'^admin/payouts/', include('payouts.urls')),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)


    admin.site.site_header = 'Delivery administration'
