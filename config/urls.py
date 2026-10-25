from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import JsonResponse

def root_health_view(request):
    return JsonResponse({
        "status": "online",
        "service": "Harmony Factory Suite Backend API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin/",
            "api_v1": "/api/v1/",
        }
    })

urlpatterns = [
    path('', root_health_view, name='root-health'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('audit_logs.urls')),
    path('api/v1/purchase/', include('factory.purchase.supplier.urls')),
    path('api/v1/sales/', include('factory.sales.customer.urls')),
    path('api/v1/factory/', include('factory.loom.urls')),
    path('api/v1/factory/', include('factory.beam.urls')),
    path('api/v1/', include('factory.beam.urls')),
    path('api/v1/factory/', include('factory.cloth.urls')),
    path('api/v1/', include('factory.cloth.urls')),

    path('api/v1/', include('factory.yarn.yarn_buyer.urls')),
    path('api/v1/', include('factory.yarn.yarn_name.urls')),
    path('api/v1/', include('factory.yarn.yarn_type.urls')),
    path('api/v1/', include('factory.yarn.yarn_count.urls')),
    path('api/v1/', include('factory.yarn.yarn_stock.urls')),
    path('api/v1/', include('factory.yarn.yarn_intake.urls')),
    path('api/v1/', include('factory.yarn.yarn_outcome.urls')),
    path('api/v1/', include('factory.yarn.sizing.urls')),
    path('api/v1/', include('factory.yarn.warping.urls')),
    path('api/v1/', include('factory.yarn.b_grade_yarn.urls')),
    path('api/v1/', include('factory.bank_account.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
