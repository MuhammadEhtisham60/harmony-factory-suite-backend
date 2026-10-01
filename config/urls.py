from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('audit_logs.urls')),
    path('api/v1/purchase/', include('factory.purchase.supplier.urls')),
    path('api/v1/sales/', include('factory.sales.customer.urls')),
    path('api/v1/factory/', include('factory.loom.urls')),
    path('api/v1/factory/', include('factory.beam.urls')),
    path('api/v1/', include('factory.yarn.yarn_buyer.urls')),
    path('api/v1/', include('factory.yarn.yarn_intake.urls')),
    path('api/v1/', include('factory.yarn.yarn_outcome.urls')),
    path('api/v1/', include('factory.yarn.sizing.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
