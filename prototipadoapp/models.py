from django.db import models

# Create your models here.

class RolRBAC(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=30)
    privilegios = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=150)

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(RolRBAC, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=100)
    email_inst = models.CharField(max_length=100, unique=True)
    contraseña_hash = models.CharField(max_length=255)
    estado_cuenta = models.BooleanField(default=True)
    token_recuperacion = models.CharField(max_length=255, blank=True, null=True)


class Administrador(models.Model):
    id_usuario = models.OneToOneField(Usuario, primary_key= True ,on_delete=models.CASCADE, db_column='id_usuario')
    nivel_acceso = models.CharField(max_length=50)
    fecha_asignacion = models.DateField()


class CorredorAnalista(models.Model):
    id_usuario = models.OneToOneField(Usuario,  primary_key= True , on_delete=models.CASCADE, db_column='id_usuario')
    codigo_corredor = models.CharField(max_length=30)
    area_analisis = models.CharField(max_length=80)

class RespaldoBD(models.Model):
    id_usuario_admin = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_usuario')
    fecha_respaldo = models.DateTimeField(auto_now_add=True)
    ruta_copia_seguridad = models.CharField(max_length=255)
    archivos_antiguos_eliminados = models.PositiveIntegerField(default=0)
    estado_backup = models.CharField(max_length=30)

class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    rut = models.CharField(max_length=12, unique=True)
    razon_social = models.CharField(max_length=150)
    mercado = models.CharField(max_length=50)

class DocumentoFuente(models.Model):
    id_documento = models.AutoField(primary_key=True)
    id_usuario_carga = models.ForeignKey(Usuario,on_delete=models.PROTECT, db_column='id_usuario')
    id_empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, db_column='id_empresa')
    nombre_archivo = models.CharField(max_length=150)
    tipo_fuente = models.CharField(max_length=20)
    estructura_validada = models.BooleanField(default=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

class CalificacionTributaria(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    id_documento = models.OneToOneField(DocumentoFuente, on_delete=models.PROTECT, db_column= 'id_documento' )
    id_empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, db_column='id_empresa')
    id_usuario_corredor = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='id_usuario')
    periodo_anual = models.DateField()
    monto_declarado = models.DecimalField(max_digits=18, decimal_places=2)
    factor_calculado = models.DecimalField(max_digits=10, decimal_places=8)
    tipo_calificacion = models.CharField(max_length=150)
    detalles_calificacion = models.TextField()
    informacion_verificada = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

class LogAuditoria(models.Model):
    id_log = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='id_usuario')
    id_calificacion = models.ForeignKey(CalificacionTributaria, on_delete=models.PROTECT, db_column='id_calificacion')
    fecha_evento = models.DateTimeField(auto_now_add=True)
    accion_realizada = models.CharField(max_length=50)
    tipo_archivo = models.CharField(max_length=15)
    detalle_cambio_calificacion = models.TextField()

class CertificadoPDF(models.Model):
    id_documento = models.OneToOneField(DocumentoFuente,  primary_key= True , on_delete=models.CASCADE, db_column='id_documento')
    folio_certificado =  models.CharField(max_length=50)
    paginas = models.PositiveIntegerField(default=0)
    ingreso_manual = models.BooleanField(default=True)

class ArchivoMasivo(models.Model):
    id_documento = models.OneToOneField(DocumentoFuente,  primary_key= True , on_delete=models.CASCADE, db_column='id_documento')
    extension = models.CharField(max_length=10)
    cantidad_registros = models.PositiveIntegerField(default=0)
    estado_parseo = models.CharField(max_length=30)
