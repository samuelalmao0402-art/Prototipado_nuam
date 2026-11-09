from django.urls import path
from . import views

urlpatterns =[
    path('', views.login, name='login'),

    path('login/', views.login, name='login'),
    path('api/login/', views.LoginAPIView.as_view(), name='login_api'),
    path('api/logout/', views.LogoutAPIView.as_view(), name='logout_api'),
    path('corredor/crear/', views.crear_calificacion, name='crear_calificacion_view'),
    path('corredor/eliminar/', views.eliminar_calificacion, name='eliminar_calificacion_view'),
    path('corredor/actualizar/', views.actualizar_calificacion, name='actualizar_calificacion_view'),
    path('corredor/ver/', views.ver_calificacion, name='ver_calificacion_view'),

    path('api/calificaciones/', views.CalificacionAPIView.as_view(), name='api_calificaciones_list_create'),

    path('api/carga-masiva/', views.CargaMasivaAPIView.as_view(), name='carga_masiva'),

    path('api/admin/usuarios/', views.UsuarioAdminAPIView.as_view(), name='api_admin_usuarios'),
    path('api/admin/respaldos/', views.RespaldoAPIView.as_view(), name='api_admin_respaldos'),
    path('admin-dashboard/', views.vista_admin, name='admin_dashboard_view'),
    path('api/admin/bitacora/', views.BitacoraAPIView.as_view(), name='api_admin_bitacora'),
#Ruta para buscar/filtrar listado (GET), editar completo (PUT), editar parcial (PATCH) y SoftDelete (DELETE) usando el id (pk)
    path('api/calificaciones/<int:pk>/', views.CalificacionDetalleAPIView.as_view(), name='api_calificacion_detalle'),

#Si quieres mantener la ruta de búsqueda general limpia que ya tenías en CalificacionDetalleAPIView.get sin pk:
    path('api/calificaciones/buscar/', views.CalificacionDetalleAPIView.as_view(), name='api_calificacion_buscar'),
]