import pandas as pd
from datetime import timedelta, datetime

# Django
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password

# Django REST Framework & JWT
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken

# Modelos NUAM
from .models import (
    Administrador, CorredorAnalista, CalificacionTributaria, 
    LogAuditoria, DocumentoFuente, CertificadoPDF, ArchivoMasivo, 
    RolRBAC, RespaldoBD, Usuario, Empresa
)



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

def vista_admin(request):
    return render(request, 'prototipadoapp/admin.html')
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

        if len(password) < 12 or len(password) > 15:
            return Response(
                {'error': 'La contraseña debe tener entre 12 y 15 caracteres.'}, 
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
        role_name = getattr(user.id_rol, 'nombre_rol', '').lower() if getattr(user, 'id_rol', None) else ''

        if 'admin' in role_name or user.is_superuser:
            session_duration = timedelta(hours=6)  # Administrador: 6 horas máx.
            ruta_destino = '/admin-dashboard/'     # Redirección al panel de admin
        else:
            session_duration = timedelta(hours=8)  # Corredor / Analista: 8 horas máx.
            ruta_destino = '/corredor/ver/'        # Redirección al mantenedor

        # Sobrescribir la expiración del token de refresco dinámicamente
        refresh.set_exp(lifetime=session_duration)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Crear respuesta exitosa enviando la URL de redirección
        response = Response(
            {
                'mensaje': 'Inicio de sesión exitoso.',
                'redirect_url': ruta_destino
            }, 
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
        # Es buena práctica agregar el select_related correcto para optimizar la consulta
        calificaciones = CalificacionTributaria.objects.select_related('id_empresa', 'id_documento')

        calificacion_datos = []

        for calificacion in calificaciones:
            calificacion_datos.append({
                'id_calificacion': calificacion.id_calificacion,
                'rut_emisor': calificacion.id_empresa.rut,            # CORREGIDO
                'razon_social': calificacion.id_empresa.razon_social, # CORREGIDO
                'mercado': calificacion.id_empresa.mercado,           # CORREGIDO
                'periodo_anual': calificacion.periodo_anual,
                'monto_declarado': calificacion.monto_declarado,
                'factor_calculado': calificacion.factor_calculado,
                'fuente': calificacion.id_documento.tipo_fuente,      # CORREGIDO
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


class CargaMasivaAPIView(APIView):
    # Esto le dice a Django que esta vista recibe archivos (form-data)
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get('archivo_masivo')
        
        if not archivo:
            return Response({'error': 'No se proporcionó ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        nombre_archivo = archivo.name
        extension = nombre_archivo.split('.')[-1].lower()

        if extension not in ['csv', 'xlsx']:
            return Response({'error': 'Formato no soportado. Usa CSV o XLSX.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Leer el archivo con Pandas
            if extension == 'csv':
                df = pd.read_csv(archivo)
            else:
                df = pd.read_excel(archivo)

            # Limpiar valores nulos
            df = df.fillna('')
            registros_creados = 0

            # 2. Procesar cada fila en una sola transacción segura
            with transaction.atomic():
                for index, row in df.iterrows():
                    # Extraer columnas (Asegúrate de que tu Excel/CSV tenga estas cabeceras exactas)
                    rut = str(row.get('rut_emisor', '')).strip()
                    razon_social = str(row.get('razon_social', '')).strip()
                    mercado = str(row.get('mercado', 'Chile (BCS)')).strip()
                    periodo = str(row.get('periodo_anual', '')).strip()
                    monto = row.get('monto_declarado', 0)

                    # Saltar si falta el RUT o el Monto
                    if not rut or not monto:
                        continue 

                    try:
                        monto_num = float(monto)
                        if monto_num <= 0: continue
                        factor = round(monto_num * 0.0000041, 8) # Cálculo automático
                    except ValueError:
                        continue

                    # A. Crear o buscar Empresa
                    empresa, created = Empresa.objects.get_or_create(
                        rut=rut,
                        defaults={'razon_social': razon_social, 'mercado': mercado}
                    )

                    # B. Crear DocumentoFuente (1 por registro por la relación OneToOne de tu modelo)
                    documento = DocumentoFuente.objects.create(
                        id_usuario_carga=request.user,
                        id_empresa=empresa,
                        nombre_archivo=nombre_archivo,
                        tipo_fuente=f"{extension.upper()} Masivo",
                        estructura_validada=True
                    )

                    # C. Crear ArchivoMasivo
                    ArchivoMasivo.objects.create(
                        id_documento=documento,
                        extension=extension.upper(),
                        cantidad_registros=len(df),
                        estado_parseo="Completado"
                    )

                    # D. Crear CalificacionTributaria
                    calificacion = CalificacionTributaria.objects.create(
                        id_documento=documento,
                        id_empresa=empresa,
                        id_usuario_corredor=request.user,
                        periodo_anual=periodo,
                        monto_declarado=monto_num,
                        factor_calculado=factor,
                        tipo_calificacion="Carga Masiva",
                        detalles_calificacion=f"Registro masivo lote: {nombre_archivo}",
                        informacion_verificada=True
                    )

                    # E. Generar Log de Auditoría
                    LogAuditoria.objects.create(
                        id_usuario=request.user,
                        id_calificacion=calificacion,
                        accion_realizada="CARGA_MASIVA",
                        tipo_archivo=extension.upper(),
                        detalle_cambio_calificacion=f"Registro masivo importado desde {nombre_archivo}"
                    )
                    
                    registros_creados += 1

            return Response({'mensaje': f'Se procesaron {registros_creados} registros exitosamente.'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"ERROR EN CARGA MASIVA: {e}") # Para depurar en consola
            return Response({'error': 'Error interno al procesar el archivo. Verifica el formato de las columnas.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UsuarioAdminAPIView(APIView):
    def get(self, request):
        try:
            usuarios = Usuario.objects.all()
            data = []
            for u in usuarios:
                # Failsafe: Si el usuario no tiene rol (como el superuser), no crashea
                try:
                    rol_nombre = u.id_rol.nombre_rol if u.id_rol else 'Sin Rol Asignado'
                except AttributeError:
                    rol_nombre = 'Sin Rol Asignado'

                data.append({
                    'id': u.id_usuario,
                    'nombre': u.nombre or 'Usuario Sistema',
                    'email': u.email_inst,
                    'rol': rol_nombre,
                    'estado': 'Activo' if u.estado_cuenta else 'Inactivo'
                })
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error cargando usuarios: {e}")
            return Response([], status=status.HTTP_200_OK) # Devuelve lista vacía en vez de error 500

    def post(self, request):
        nombre = request.data.get('nombre')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not nombre or not email or not password:
            return Response({'error': 'Faltan datos obligatorios'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # get_or_create asegura que si la tabla RolRBAC está vacía, crea el rol para que no falle
            rol_corredor, created = RolRBAC.objects.get_or_create(
                nombre_rol='Corredor / Analista',
                defaults={'privilegios': 'Lectura/Escritura', 'descripcion': 'Perfil estándar de corredor'}
            )
            
            nuevo_usuario = Usuario.objects.create(
                nombre=nombre,
                email_inst=email,
                password=make_password(password), 
                id_rol=rol_corredor,
                estado_cuenta=True
            )
            return Response({'mensaje': 'Usuario corredor creado exitosamente'}, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error al crear usuario: {e}")
            return Response({'error': 'El correo ya existe o hubo un error interno de base de datos.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BitacoraAPIView(APIView):
    def get(self, request):
        # Traemos los últimos 15 registros de auditoría
        try:
            logs = LogAuditoria.objects.select_related('id_usuario').order_by('-fecha_evento')[:15]
            data = []
            for log in logs:
                data.append({
                    'id': log.id_log,
                    'usuario': log.id_usuario.nombre if log.id_usuario else 'Sistema',
                    'fecha': log.fecha_evento.strftime("%d-%m-%Y %H:%M"),
                    'accion': log.accion_realizada,
                    'detalle': log.detalle_cambio_calificacion
                })
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error en bitácora: {e}")
            return Response([], status=status.HTTP_200_OK)
        
class RespaldoAPIView(APIView):
    def get(self, request):
        # Traemos los últimos 10 respaldos ordenados por fecha
        respaldos = RespaldoBD.objects.order_by('-fecha_respaldo')[:10]
        data = []
        for r in respaldos:
            fecha_str = r.fecha_respaldo.strftime("%d-%m-%Y %H:%M") if r.fecha_respaldo else "N/A"
            data.append({
                'id': getattr(r, 'id_respaldo', r.id),
                'fecha': fecha_str,
                'ruta': r.ruta_copia_seguridad,
                'estado': r.estado_backup
            })
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        # Generar la ruta dinámica simulando un guardado real en la nube
        fecha_actual = timezone.now()
        ruta_s3 = f"s3://nuam-vault/pg_{fecha_actual.strftime('%Y%m%d_%H%M%S')}.dump"
        
        try:
            # Crear el registro de auditoría en PostgreSQL
            nuevo_respaldo = RespaldoBD.objects.create(
                id_usuario_admin=request.user if request.user.is_authenticated else None,
                ruta_copia_seguridad=ruta_s3,
                archivos_antiguos_eliminados=1,
                estado_backup="Completado"
            )
            return Response({'mensaje': 'Respaldo generado exitosamente', 'ruta': ruta_s3}, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"Error al generar backup: {e}")
            return Response({'error': 'Error interno al generar el respaldo.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EstadisticasDashboardAPIView(APIView):
    def get(self, request):
        try:
            # Contamos los registros reales en la base de datos
            total_calificaciones = CalificacionTributaria.objects.count()
            total_manuales = CertificadoPDF.objects.count()
            total_masivas = ArchivoMasivo.objects.count()
            
            return Response({
                'calificaciones': total_calificaciones,
                'manuales': total_manuales,
                'masivas': total_masivas
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error cargando estadísticas: {e}")
            return Response({'calificaciones': 0, 'manuales': 0, 'masivas': 0}, status=status.HTTP_200_OK)