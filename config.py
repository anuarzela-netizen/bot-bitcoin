import os
from dotenv import load_dotenv

load_dotenv()

# === BINANCE ===
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# === TELEGRAM ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# === PARES A OPERAR ===
PARES = [
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USDT',
    'SOL/USDT',
    'ADA/USDT',
    'XRP/USDT'
]

# === CAPITAL Y RIESGO ===
CAPITAL_TOTAL = 100.0
RIESGO_POR_OPERACION = 0.04   # 4% del capital por operacion
MAX_POSICIONES_ABIERTAS = 3   # Maximo 3 operaciones simultaneas
MAX_RIESGO_TOTAL = 0.12       # Maximo 12% del capital en riesgo

# === PARAMETROS DE ESTRATEGIA ===
INTERVALO = '1h'
VELAS_ANALISIS = 100          # Cantidad de velas a analizar

# === RSI ===
RSI_PERIODO = 14
RSI_SOBRECOMPRA = 65
RSI_SOBREVENTA = 35

# === MACD ===
MACD_RAPIDO = 12
MACD_LENTO = 26
MACD_SIGNAL = 9

# === BOLLINGER BANDS ===
BB_PERIODO = 20
BB_DESVIACION = 2.0

# === MEDIAS MOVILES ===
EMA_RAPIDA = 9
EMA_MEDIA = 21
EMA_LENTA = 50
EMA_TENDENCIA = 200

# === STOP LOSS Y TAKE PROFIT ===
STOP_LOSS_PCT = 0.02          # 2% stop loss
TAKE_PROFIT_PCT = 0.06        # 6% take profit (ratio 1:3)
TRAILING_STOP_PCT = 0.015     # 1.5% trailing stop

# === PUNTUACION MINIMA PARA OPERAR ===
PUNTUACION_COMPRA = 5         # Minimo 5 puntos para comprar
PUNTUACION_VENTA = 4          # Minimo 4 puntos para vender

# === VOLUMEN ===
VOLUMEN_MINIMO_MULTIPLICADOR = 1.5  # Volumen debe ser 1.5x el promedio

# === HORARIOS (UTC) ===
HORAS_OPERAR = list(range(0, 24))   # Opera las 24 horas
EVITAR_HORAS = [3, 4, 5]            # Horas de baja liquidez a evitar

# === COMISIONES BINANCE ===
COMISION_BINANCE = 0.001      # 0.1% por operacion