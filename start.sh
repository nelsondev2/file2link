#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link - Versión Optimizada..."

# ===========================================
# FASE 1: VERIFICACIÓN DE VARIABLES DE ENTORNO
# ===========================================

echo "🔧 Verificando variables de entorno..."

# Verificar variables críticas
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
echo "⚡ Configuración optimizada para descargas de alta velocidad"

# ===========================================
# FASE 2: INICIO DE LA APLICACIÓN
# ===========================================

echo "🎯 Iniciando servicios optimizados..."
echo "==========================================="

# Mostrar configuración de velocidad
echo "📊 Configuración de Velocidad:"
echo "   • Chunk size: 2MB"
echo "   • Buffer size: 4MB"
echo "   • Threads: 100"
echo "   • Connection limit: 1000"
echo "==========================================="

# Ejecutar el bot optimizado
exec python main.py
