#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link..."

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

# ===========================================
# FASE 2: INICIO DE LA APLICACIÓN
# ===========================================

echo "🎯 Iniciando bot..."
echo "==========================================="

# Ejecutar el bot
exec python main.py
