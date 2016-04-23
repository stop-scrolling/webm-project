from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^api/detect_screamers$', views.detect_screamers, name='detect_screamers'),
    url(r'^api/detect_screamers_batch$', views.detect_screamers_batch, name='detect_screamers_batch'),
]