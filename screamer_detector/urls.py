from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^api/detect_screamers$', views.detect_screamers, name='detect_screamers'),
]