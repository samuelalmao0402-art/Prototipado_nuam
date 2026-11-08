
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authentication import authenticate

from django.shortcuts import render, get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import datetime

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

class LoginAPIView(APIView):
    permission_classes = [AllowAny]

