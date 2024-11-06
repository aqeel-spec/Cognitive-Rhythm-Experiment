# api/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static
from experiment.views import (
    RhythmSequenceViewSet,  # Ensure this import now works
    # StartExperimentAPIView,
    # RecordTapAPIView,
)

router = routers.DefaultRouter()
router.register(r'rhythm-sequences', RhythmSequenceViewSet)

urlpatterns = [
    path('', include('experiment.urls')),  # Includes paths from experiment/urls.py
    path('set_language/', set_language, name='set_language'),  # Language switching view

    # OpenAPI schema and documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),  # JSON schema
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),  # Swagger UI
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  # Redoc UI

    path('api/', include(router.urls)),
    # path('api/start-experiment/', StartExperimentAPIView.as_view(), name='start-experiment'),
    # path('api/record-tap/', RecordTapAPIView.as_view(), name='record-tap'),
]

# Wrap the admin path with i18n_patterns
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)