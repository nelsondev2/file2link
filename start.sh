#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link - Versión OPTIMIZADA para Render.com..."

# ===========================================
# FASE 1: OPTIMIZACIONES DEL SISTEMA PARA BAJOS RECURSOS
# ===========================================

echo "⚡ Aplicando optimizaciones para plan gratuito (0.1 CPU)..."

# Optimizar para usar menos memoria
export PYTHONMALLOC=malloc
export PYTHONUNBUFFERED=1

# Configurar Python para usar menos memoria
export PYTHONOPTIMIZE=1

# Aumentar límites del sistema para descargas grandes
ulimit -n 65536 2>/dev/null || true
echo "  ✓ Límites de archivos aumentados"

# Configurar buffer TCP más pequeño para usar menos memoria
sysctl -w net.core.rmem_max=8388608 2>/dev/null || true
sysctl -w net.core.wmem_max=8388608 2>/dev/null || true
sysctl -w net.core.rmem_default=65536 2>/dev/null || true
sysctl -w net.core.wmem_default=65536 2>/dev/null || true
echo "  ✓ Buffers TCP optimizados para baja memoria"

# ===========================================
# FASE 2: VERIFICACIÓN DE VARIABLES DE ENTORNO
# ===========================================

echo "🔧 Verificando variables de entorno..."

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

if [ -z "$API_ID" ]; then
    echo "❌ ERROR: API_ID no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "❌ ERROR: API_HASH no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

echo "✅ Todas las variables de entorno configuradas"

# ===========================================
# FASE 3: CONFIGURACIÓN DE LÍMITES
# ===========================================

echo "📊 Configuración de límites activa:"
echo "   • Tamaño máximo por parte: 500 MB"
echo "   • Total máximo para empaquetar: 1000 MB"
echo "   • Máximo de archivos: 20"
echo "   • Buffer descarga: 64KB"
echo "   • Timeout empaquetado: 5 minutos"
echo "   • CPU límite: 70%"
echo "==========================================="

# ===========================================
# FASE 4: INICIO DE LA APLICACIÓN
# ===========================================

echo "🎯 Iniciando bot optimizado para bajos recursos..."
echo "💡 Para archivos grandes (>1GB):"
echo "   1. Usa partes más pequeñas (/pack 200)"
echo "   2. Divide manualmente antes de subir"
echo "   3. El servidor tiene solo 0.1 CPU"
echo "==========================================="

# Ejecutar el bot con garbage collector activo
exec python -c "import gc; gc.set_threshold(700, 10, 5)" main.py
