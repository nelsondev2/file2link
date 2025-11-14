#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de Anime..."

# ===========================================
# FASE 1: VERIFICACIÓN DE FFMPEG
# ===========================================

echo "🔍 Verificando FFmpeg..."

if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version | head -n1 | cut -d' ' -f3)
    echo "🎬 FFmpeg disponible: versión $ffmpeg_version"
else
    echo "⚠️ FFmpeg no disponible - Usando modo compatible"
fi

if command -v ffprobe &> /dev/null; then
    echo "📊 FFprobe disponible"
else
    echo "⚠️ FFprobe no disponible - Duración estimada"
fi

# ===========================================
# FASE 2: VERIFICACIÓN DE VARIABLES DE ENTORNO
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
# FASE 3: INICIO DE LA APLICACIÓN
# ===========================================

echo "🎯 Iniciando bot..."
echo "==========================================="

# Ejecutar el bot
exec python main.py
