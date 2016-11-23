import django.dispatch

pre_validation = django.dispatch.Signal(providing_args=['created'])
post_validation = django.dispatch.Signal(providing_args=['created'])
