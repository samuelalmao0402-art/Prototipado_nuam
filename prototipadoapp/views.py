
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authentication import authenticate
from django.contrib.auth import authenticate, login as auth_login

from django.shortcuts import render, get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, datetime



from .models import Administrador
from .models import CorredorAnalista
from .models import CalificacionTributaria
from .models import LogAuditoria
from .models import DocumentoFuente
from .models import CertificadoPDF
from .models import ArchivoMasivo
from .models import RolRBAC
from .models import RespaldoBD
from .models import Usuario
from .models import Empresa

# Create your views here.


# Funciones de renderizacion



def login(request):
    return render(request, 'prototipadoapp/login.html')

@login_required
def crear_calificacion(request):
    return render(request, 'prototipadoapp/corredor.html')

@login_required
def eliminar_calificacion(request):
    return render(request, 'prototipadoapp/corredor.html')

@login_required
def actualizar_calificacion(request):
    return render(request,'prototipadoapp/corredor.html')

@login_required
def ver_calificacion(request):
    return render(request,'prototipadoapp/corredor.html')

#API LOGICA

class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email_inst')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {'error': 'El correo institucional y la contraseña son obligatorios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Autenticar utilizando email_inst como identificador principal
        user = authenticate(request, email_inst=email, password=password)

        if user is None:
            return Response(
                {'error': 'Credenciales inválidas.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.estado_cuenta:
            return Response(
                {'error': 'La cuenta se encuentra inactiva.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # ACTIVAR LA SESIÓN INTERNA DE DJANGO PARA LAS VISTAS HTML
        auth_login(request, user)

        # Generar tokens JWT con SimpleJWT
        refresh = RefreshToken.for_user(user)

        # Evaluamos el nombre del rol asociado a través de la relación id_rol
        role_name = getattr(user.id_rol, 'nombre_rol', '').lower() if user.id_rol else ''

        if 'admin' in role_name:
            session_duration = timedelta(hours=6)  # Administrador: 6 horas máx.
        else:
            session_duration = timedelta(hours=8)  # Corredor / Analista: 8 horas máx.

        # Sobrescribir la expiración del token de refresco dinámicamente
        refresh.set_exp(lifetime=session_duration)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Crear respuesta exitosa
        response = Response(
            {'mensaje': 'Inicio de sesión exitoso.'}, 
            status=status.HTTP_200_OK
        )

        max_age_seconds = int(session_duration.total_seconds())

        # Configurar cookies HttpOnly y Secure para mitigar ataques XSS
        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=False,  
            samesite='Lax',
            max_age=60 * 15  # 15 minutos
        )
        
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite='Lax',
            max_age=max_age_seconds
        )

        return response

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            eliminar = Response({
                'mensaje': 'Sesión cerrada exitosamente.'
            }, status=status.HTTP_200_OK)
            eliminar.delete_cookie('access_token')
            eliminar.delete_cookie('refresh_token')
            return eliminar

        except Exception:
            response = Response({
                'error': 'No se encontró una sesión activa o el token es inválido.'
            }, status=status.HTTP_400_BAD_REQUEST)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response


class CalificacionAPIView(APIView):

    def get(self, request):

        calificaciones = CalificacionTributaria.objects.select_related()

        calificacion_datos = []

        for calificacion in calificaciones:
            calificacion_datos.append({

                'id_calificacion': calificacion.id_calificacion,
                'rut_emisor':calificacion.empresa.rut_emisor,
                'razon_social':calificacion.empresa.razon_social,
                'mercado':calificacion.empresa.mercado,
                'periodo_anual':calificacion.periodo_anual,
                'monto_declarado':calificacion.monto_declarado,
                'factor_calculado':calificacion.factor_calculado,
                'fuente': calificacion.id_documento.tipo_fuente,
                'informacion_verificada': calificacion.informacion_verificada,
            })
        return Response(calificacion_datos, status=status.HTTP_200_OK)

    def post(self,request):
            rut_emisor = request.data.get('rut_emisor')
            razon_social = request.data.get('razon_social')
            mercado = request.data.get('mercado')
            periodo_anual = request.data.get('periodo_anual')
            monto_declarado = request.data.get('monto_declarado')
            factor_calculado = request.data.get('factor_calculado')
            fuente = request.data.get('fuente', 'PDF Manual')
            tipo_calificacion = request.data.get('tipo_calificacion', 'Certificado PDF')
            detalles_calificacion = request.data.get('detalles_calificacion', '')
            folio_certificado = request.data.get('folio_certificado', 'SIN-FOLIO')
            
            accion_realizada = request.data.get('accion_realizada', 'CREAR_CALIFICACION')
            tipo_archivo = request.data.get('tipo_archivo', 'PDF')
            detalle_cambio_calificacion = request.data.get('detalle_cambio_calificacion', f"Ingreso manual para empresa {rut_emisor}")

            # Validación de campos obligatorios básicos
            if not rut_emisor or not razon_social or not mercado or not periodo_anual or not monto_declarado or not factor_calculado:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            # Validar formato del período anual (YYYYMM de 6 dígitos)
            if periodo_anual:
                try:

                    fecha_obj = datetime.strptime(periodo_anual, '%Y-%m-%d').date()
                    año_actual = datetime.now().year

                    if fecha_obj.year > 2100:
                        return Response({
                        'error': 'El año ingresado es demasiado lejano. Por favor, ingresa una fecha adecuada para nuestro siglo.'
                        }, status=status.HTTP_400_BAD_REQUEST)

                except ValueError:
                    return Response({
                        'error':'La fecha debe tener formato YYYY-MM-DD'
                    },status=status.HTTP_400_BAD_REQUEST)

            # Validar que el monto declarado sea un número válido y mayor a cero
            try:
                monto_num = float(monto_declarado)
                if monto_num <= 0:
                    return Response(status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response(status=status.HTTP_400_BAD_REQUEST)

            try:
                empresa = Empresa.objects.filter(rut=rut_emisor).first()

                if empresa:
                    empresa.razon_social = razon_social
                    empresa.mercado = mercado
                    empresa.save()
                else:
                    empresa = Empresa.objects.create(
                        rut=rut_emisor,
                        razon_social=razon_social,
                        mercado=mercado
                    )

                with transaction.atomic():
                    documento = DocumentoFuente.objects.create(
                        id_usuario_carga=request.user,
                        id_empresa=empresa,
                        nombre_archivo=f"Certificado_Manual_{rut_emisor}_{periodo_anual}.pdf",
                        tipo_fuente=fuente,
                        estructura_validada=True
                    )

                    CertificadoPDF.objects.create(
                        id_documento=documento,
                        folio_certificado=folio_certificado,
                        paginas=1,
                        ingreso_manual=True
                    )

                    calificacion = CalificacionTributaria.objects.create(
                        id_documento=documento,
                        id_empresa=empresa,
                        id_usuario_corredor=request.user,
                        periodo_anual=periodo_anual,
                        monto_declarado=monto_declarado,
                        factor_calculado=factor_calculado,
                        tipo_calificacion=tipo_calificacion,
                        detalles_calificacion=detalles_calificacion,
                        informacion_verificada=True
                    )

                    LogAuditoria.objects.create(
                        id_usuario=request.user,
                        id_calificacion=calificacion,
                        accion_realizada=accion_realizada,
                        tipo_archivo=tipo_archivo,
                        detalle_cambio_calificacion=detalle_cambio_calificacion
                    )

                    return Response(status=status.HTTP_201_CREATED)

            except Exception:
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CalificacionDetalleAPIView(APIView):

    def get(self, request):

        calificaciones = CalificacionTributaria.objects.all()

        buscador = request.GET.get('buscador')
        mercado = request.GET.get('mercado')
        periodo_anual = request.GET.get('periodo_anual')

        if buscador:
            buscador_limpio = buscador.replace('.', '').replace('-', '').strip()
            # Limitar la longitud máxima (por ejemplo, un RUT válido no supera los 12 caracteres)
            if len(buscador_limpio) > 12:
                return Response({'error': 'El RUT ingresado supera el largo permitido.'}, status=status.HTTP_400_BAD_REQUEST)
            calificaciones = calificaciones.filter(id_empresa__rut__icontains=buscador_limpio)
        if mercado:
            calificaciones = calificaciones.filter(id_empresa__mercado=mercado)
        if periodo_anual:
            calificaciones = calificaciones.filter(periodo_anual=periodo_anual)

        detalle_calificacion = [{
            'id_calificacion': item.id_calificacion,
            'rut_emisor': item.id_empresa.rut,
            'razon_social': item.id_empresa.razon_social,
            'mercado': item.id_empresa.mercado,
            'periodo_anual': item.periodo_anual,
            'monto_declarado': item.monto_declarado,
            'factor_calculado': item.factor_calculado,
        } for item in calificaciones]

        return Response(detalle_calificacion, status=status.HTTP_200_OK)


    def put(self, request,pk):

        calificacion = get_object_or_404(CalificacionTributaria, pk=pk)

        rut_emisor = request.data.get('rut_emisor')
        razon_social = request.data.get('razon_social')
        mercado = request.data.get('mercado')
        periodo_anual = request.data.get('periodo_anual')
        monto_declarado = request.data.get('monto_declarado')
        factor_calculado = request.data.get('factor_calculado')
        tipo_calificacion = request.data.get('tipo_calificacion')
        detalles_calificacion = request.data.get('detalles_calificacion', '')

        if not rut_emisor or not razon_social or not mercado or not periodo_anual or not monto_declarado or not factor_calculado:
            return Response({'error': 'Faltan campos obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        if periodo_anual:
            try:
                fecha_obj = datetime.strptime(str(periodo_anual), '%Y-%m-%d').date()
                if fecha_obj.year > 2100:
                    return Response({'error': 'El año ingresado es demasiado lejano.'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'error': 'La fecha debe tener formato YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            monto_num = float(monto_declarado)
            if monto_num <= 0:
                return Response({'error': 'El monto declarado debe ser mayor a cero.'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'El monto declarado no es un número válido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                empresa = calificacion.id_empresa
                empresa.rut = rut_emisor
                empresa.razon_social = razon_social
                empresa.mercado = mercado
                empresa.save()

                calificacion.periodo_anual = periodo_anual
                calificacion.monto_declarado = monto_declarado
                calificacion.factor_calculado = factor_calculado
                calificacion.tipo_calificacion = tipo_calificacion
                calificacion.detalles_calificacion = detalles_calificacion
                calificacion.save()

                LogAuditoria.objects.create(
                    id_usuario=request.user if request.user.is_authenticated else None,
                    id_calificacion=calificacion,
                    accion_realizada="ACTUALIZAR_CALIFICACION",
                    tipo_archivo="PDF",
                    detalle_cambio_calificacion=f"Calificación #{calificacion.id_calificacion} actualizada para empresa {rut_emisor}"
                )

            return Response({'mensaje': 'Actualizado correctamente'}, status=status.HTTP_200_OK)

        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk):
        calificacion = get_object_or_404(CalificacionTributaria, pk=pk)
        empresa = calificacion.id_empresa

        rut_emisor = request.data.get('rut_emisor')
        razon_social = request.data.get('razon_social')
        mercado = request.data.get('mercado')

        if rut_emisor:
            empresa.rut = rut_emisor
        if razon_social:
            empresa.razon_social = razon_social
        if mercado:
            empresa.mercado = mercado
        empresa.save()

        periodo_anual = request.data.get('periodo_anual')
        if periodo_anual:
            try:
                fecha_obj = datetime.strptime(str(periodo_anual), '%Y-%m-%d').date()
                if fecha_obj.year > 2100:
                    return Response({'error': 'El año ingresado es demasiado lejano.'}, status=status.HTTP_400_BAD_REQUEST)
                calificacion.periodo_anual = periodo_anual
            except ValueError:
                return Response({'error': 'La fecha debe tener formato YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        monto_declarado = request.data.get('monto_declarado')
        if monto_declarado is not None:
            try:
                monto_num = float(monto_declarado)
                if monto_num <= 0:
                    return Response({'error': 'El monto declarado debe ser mayor a cero.'}, status=status.HTTP_400_BAD_REQUEST)
                
                calificacion.monto_declarado = monto_declarado
                # Cálculo automático del factor a partir del monto
                calificacion.factor_calculado = round(monto_num * 0.0000041, 8)
            except (ValueError, TypeError):
                return Response({'error': 'El monto declarado no es un número válido.'}, status=status.HTTP_400_BAD_REQUEST)

        if 'tipo_calificacion' in request.data:
            calificacion.tipo_calificacion = request.data.get('tipo_calificacion')

        calificacion.save()

        LogAuditoria.objects.create(
            id_usuario=request.user if request.user.is_authenticated else None,
            id_calificacion=calificacion,
            accion_realizada="ACTUALIZAR_PARCIAL_CALIFICACION",
            tipo_archivo="PDF",
            detalle_cambio_calificacion=f"Calificación #{calificacion.id_calificacion} actualizada parcialmente"
        )

        return Response({'mensaje': 'Actualizado parcialmente correctamente'}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        # Buscamos la calificación o devuelve 404 estricto si no existe
        calificacion = get_object_or_404(CalificacionTributaria, pk=pk)

        # Aplicamos el SoftDelete (cambio de estado lógico)
        calificacion.informacion_verificada = False
        calificacion.save()

        # Registramos la acción en la bitácora de auditoría inmutable
        LogAuditoria.objects.create(
            id_usuario=request.user if request.user.is_authenticated else None,
            id_calificacion=calificacion,
            accion_realizada="SOFT_DELETE",
            tipo_archivo="PDF",
            detalle_cambio_calificacion=f"Borrado lógico aplicado al registro #{calificacion.id_calificacion} (Preservado para el SII)"
        )

        return Response({'mensaje': 'Calificación dada de baja lógicamente con éxito.'}, status=status.HTTP_204_NO_CONTENT)
