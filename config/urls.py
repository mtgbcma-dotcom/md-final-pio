from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from social import pages

urlpatterns = [
    path('admin/', admin.site.urls), path('api/', include('social.urls')),
    path('entrar/', pages.auth_page, name='login'),
    path('cadastro/', pages.auth_page, {'register': True}, name='register'),
    path('', pages.app_page, name='home'), path('explorar/', pages.app_page, name='explore'),
    path('configuracoes/', pages.app_page, name='settings'),
    path('salvos/', pages.app_page, name='saved'),
    path('perfil/<str:username>/', pages.app_page, name='profile'),
    path('post/<int:post_id>/', pages.app_page, name='post'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
