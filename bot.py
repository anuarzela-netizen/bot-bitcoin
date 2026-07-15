import ccxt
import pandas as pd
import numpy as np
import time
import ta
from datetime import datetime, timezone
from config import *
from telegram_bot import (
    enviar_mensaje,
    enviar_alerta_compra,
    enviar_alerta_venta,
    enviar_reporte
)

# ============================================================
# CONEXION A BINANCE
# ============================================================
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# ============================================================
# ESTADO DEL BOT
# ============================================================
posiciones_abiertas = {}
capital_actual = CAPITAL_TOTAL
capital_inicial = CAPITAL_TOTAL
operaciones_totales = 0
ganancia_total = 0.0
max_drawdown = 0.0
peak_capital = CAPITAL_TOTAL

# ============================================================
# OBTENER DATOS DE MERCADO
# ============================================================
def obtener_datos(par, intervalo=INTERVALO, limite=VELAS_ANALISIS):
    try:
        velas = exchange.fetch_ohlcv(par, intervalo, limit=limite)
        df = pd.DataFrame(velas, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"Error obteniendo datos de {par}: {e}")
        return None

# ============================================================
# CALCULAR INDICADORES TECNICOS
# ============================================================
def calcular_indicadores(df):
    try:
        # === RSI ===
        df['rsi'] = ta.momentum.RSIIndicator(
            df['close'], window=RSI_PERIODO
        ).rsi()

        # === MACD ===
        macd = ta.trend.MACD(
            df['close'],
            window_fast=MACD_RAPIDO,
            window_slow=MACD_LENTO,
            window_sign=MACD_SIGNAL
        )
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()

        # === BOLLINGER BANDS ===
        bb = ta.volatility.BollingerBands(
            df['close'],
            window=BB_PERIODO,
            window_dev=BB_DESVIACION
        )
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_pct'] = bb.bollinger_pband()

        # === MEDIAS MOVILES EMA ===
        df['ema9']  = ta.trend.EMAIndicator(df['close'], window=EMA_RAPIDA).ema_indicator()
        df['ema21'] = ta.trend.EMAIndicator(df['close'], window=EMA_MEDIA).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['close'], window=EMA_LENTA).ema_indicator()
        df['ema200']= ta.trend.EMAIndicator(df['close'], window=EMA_TENDENCIA).ema_indicator()

        # === STOCHASTIC RSI ===
        stoch = ta.momentum.StochRSIIndicator(df['close'], window=14)
        df['stoch_k'] = stoch.stochrsi_k()
        df['stoch_d'] = stoch.stochrsi_d()

        # === ATR (Average True Range) - Volatilidad ===
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()

        # === VOLUMEN ===
        df['vol_sma'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_sma']

        # === ADX (Fuerza de tendencia) ===
        adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()

        # === CCI (Commodity Channel Index) ===
        df['cci'] = ta.trend.CCIIndicator(
            df['high'], df['low'], df['close'], window=20
        ).cci()

        # === WILLIAMS %R ===
        df['williams_r'] = ta.momentum.WilliamsRIndicator(
            df['high'], df['low'], df['close'], lbp=14
        ).williams_r()

        # === MFI (Money Flow Index) ===
        df['mfi'] = ta.volume.MFIIndicator(
            df['high'], df['low'], df['close'], df['volume'], window=14
        ).money_flow_index()

        return df

    except Exception as e:
        print(f"Error calculando indicadores: {e}")
        return None

# ============================================================
# SISTEMA DE PUNTUACION PARA COMPRA
# ============================================================
def evaluar_compra(df):
    puntuacion = 0
    razones = []
    ultima = df.iloc[-1]
    anterior = df.iloc[-2]

    # --- RSI (0-2 puntos) ---
    if ultima['rsi'] < RSI_SOBREVENTA:
        puntuacion += 2
        razones.append(f"✅ RSI sobreventa: {ultima['rsi']:.1f}")
    elif ultima['rsi'] < 45:
        puntuacion += 1
        razones.append(f"✅ RSI bajo: {ultima['rsi']:.1f}")

    # --- MACD (0-2 puntos) ---
    if ultima['macd'] > ultima['macd_signal'] and anterior['macd'] <= anterior['macd_signal']:
        puntuacion += 2
        razones.append(f"✅ MACD cruce alcista")
    elif ultima['macd_hist'] > 0 and anterior['macd_hist'] < 0:
        puntuacion += 1
        razones.append(f"✅ MACD histograma positivo")

    # --- BOLLINGER BANDS (0-2 puntos) ---
    if ultima['close'] <= ultima['bb_lower']:
        puntuacion += 2
        razones.append(f"✅ Precio en banda inferior BB")
    elif ultima['bb_pct'] < 0.2:
        puntuacion += 1
        razones.append(f"✅ Precio cerca banda inferior BB")

    # --- MEDIAS MOVILES (0-2 puntos) ---
    if ultima['ema9'] > ultima['ema21'] and anterior['ema9'] <= anterior['ema21']:
        puntuacion += 2
        razones.append(f"✅ Cruce EMA9 sobre EMA21")
    elif ultima['ema21'] > ultima['ema50']:
        puntuacion += 1
        razones.append(f"✅ EMA21 sobre EMA50 (tendencia alcista)")

    # --- TENDENCIA GENERAL EMA200 (0-1 punto) ---
    if ultima['close'] > ultima['ema200']:
        puntuacion += 1
        razones.append(f"✅ Precio sobre EMA200 (tendencia alcista)")

    # --- VOLUMEN (0-1 punto) ---
    if ultima['vol_ratio'] >= VOLUMEN_MINIMO_MULTIPLICADOR:
        puntuacion += 1
        razones.append(f"✅ Volumen alto: {ultima['vol_ratio']:.2f}x promedio")

    # --- ADX Fuerza de tendencia (0-1 punto) ---
    if ultima['adx'] > 25 and ultima['adx_pos'] > ultima['adx_neg']:
        puntuacion += 1
        razones.append(f"✅ ADX tendencia fuerte alcista: {ultima['adx']:.1f}")

    # --- STOCHASTIC RSI (0-1 punto) ---
    if ultima['stoch_k'] < 0.2 and ultima['stoch_k'] > ultima['stoch_d']:
        puntuacion += 1
        razones.append(f"✅ StochRSI sobreventa con cruce")

    # --- CCI (0-1 punto) ---
    if ultima['cci'] < -100:
        puntuacion += 1
        razones.append(f"✅ CCI sobreventa: {ultima['cci']:.1f}")

    # --- WILLIAMS %R (0-1 punto) ---
    if ultima['williams_r'] < -80:
        puntuacion += 1
        razones.append(f"✅ Williams %R sobreventa: {ultima['williams_r']:.1f}")

    # --- MFI Money Flow (0-1 punto) ---
    if ultima['mfi'] < 20:
        puntuacion += 1
        razones.append(f"✅ MFI sobreventa: {ultima['mfi']:.1f}")

    razones_texto = "\n".join(razones)
    return puntuacion, razones_texto, ultima['close']

# ============================================================
# SISTEMA DE PUNTUACION PARA VENTA
# ============================================================
def evaluar_venta(df, posicion):
    puntuacion = 0
    razones = []
    ultima = df.iloc[-1]
    anterior = df.iloc[-2]
    precio_compra = posicion['precio_compra']
    precio_actual = ultima['close']
    ganancia_pct = (precio_actual - precio_compra) / precio_compra

    # --- STOP LOSS FIJO ---
    if ganancia_pct <= -STOP_LOSS_PCT:
        return 10, f"🛑 STOP LOSS activado ({ganancia_pct*100:.2f}%)", precio_actual

    # --- TAKE PROFIT FIJO ---
    if ganancia_pct >= TAKE_PROFIT_PCT:
        return 10, f"🎯 TAKE PROFIT alcanzado ({ganancia_pct*100:.2f}%)", precio_actual

    # --- TRAILING STOP ---
    precio_max = posicion.get('precio_max', precio_compra)
    if precio_actual > precio_max:
        posicion['precio_max'] = precio_actual
        precio_max = precio_actual

    trailing_nivel = precio_max * (1 - TRAILING_STOP_PCT)
    if precio_actual <= trailing_nivel and ganancia_pct > 0:
        return 10, f"📉 TRAILING STOP activado ({ganancia_pct*100:.2f}%)", precio_actual

    # --- RSI sobrecompra ---
    if ultima['rsi'] > RSI_SOBRECOMPRA:
        puntuacion += 2
        razones.append(f"⚠️ RSI sobrecompra: {ultima['rsi']:.1f}")

    # --- MACD cruce bajista ---
    if ultima['macd'] < ultima['macd_signal'] and anterior['macd'] >= anterior['macd_signal']:
        puntuacion += 2
        razones.append(f"⚠️ MACD cruce bajista")

    # --- Bollinger Band superior ---
    if ultima['close'] >= ultima['bb_upper']:
        puntuacion += 2
        razones.append(f"⚠️ Precio en banda superior BB")

    # --- EMA cruce bajista ---
    if ultima['ema9'] < ultima['ema21'] and anterior['ema9'] >= anterior['ema21']:
        puntuacion += 2
        razones.append(f"⚠️ Cruce bajista EMA9 bajo EMA21")

    # --- ADX bajista ---
    if ultima['adx'] > 25 and ultima['adx_neg'] > ultima['adx_pos']:
        puntuacion += 1
        razones.append(f"⚠️ ADX tendencia bajista")

    # --- Williams %R sobrecompra ---
    if ultima['williams_r'] > -20:
        puntuacion += 1
        razones.append(f"⚠️ Williams %R sobrecompra")

    # --- MFI sobrecompra ---
    if ultima['mfi'] > 80:
        puntuacion += 1
        razones.append(f"⚠️ MFI sobrecompra: {ultima['mfi']:.1f}")

    razones_texto = "\n".join(razones)
    return puntuacion, razones_texto, precio_actual

# ============================================================
# EJECUTAR COMPRA
# ============================================================
def ejecutar_compra(par, precio, puntuacion, razones):
    global capital_actual, operaciones_totales, posiciones_abiertas

    # Verificar maximo de posiciones abiertas
    if len(posiciones_abiertas) >= MAX_POSICIONES_ABIERTAS:
        print(f"⚠️ Maximo de posiciones abiertas alcanzado ({MAX_POSICIONES_ABIERTAS})")
        return False

    # Verificar que no hay posicion abierta en este par
    if par in posiciones_abiertas:
        print(f"⚠️ Ya hay posicion abierta en {par}")
        return False

    # Calcular capital a usar
    capital_operacion = capital_actual * RIESGO_POR_OPERACION
    if capital_operacion < 10:
        print(f"⚠️ Capital insuficiente para operar: ${capital_operacion:.2f}")
        return False

    # Calcular cantidad
    cantidad = capital_operacion / precio
    stop_loss = precio * (1 - STOP_LOSS_PCT)
    take_profit = precio * (1 + TAKE_PROFIT_PCT)

    try:
        # ORDEN REAL EN BINANCE
        orden = exchange.create_market_buy_order(par, cantidad)
        precio_real = orden['average'] if orden.get('average') else precio

        # Registrar posicion
        posiciones_abiertas[par] = {
            'precio_compra': precio_real,
            'cantidad': cantidad,
            'capital_usado': capital_operacion,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'precio_max': precio_real,
            'timestamp': datetime.now(timezone.utc),
            'orden_id': orden.get('id', 'N/A')
        }

        capital_actual -= capital_operacion
        operaciones_totales += 1

        print(f"✅ COMPRA ejecutada: {par} @ ${precio_real:.4f} | Cantidad: {cantidad:.6f}")
        enviar_alerta_compra(par, precio_real, cantidad, stop_loss, take_profit, puntuacion, razones)
        return True

    except Exception as e:
        print(f"❌ Error ejecutando compra en {par}: {e}")
        enviar_mensaje(f"❌ Error en compra {par}: {str(e)}")
        return False

# ============================================================
# EJECUTAR VENTA
# ============================================================
def ejecutar_venta(par, precio_actual, razon):
    global capital_actual, ganancia_total, posiciones_abiertas

    if par not in posiciones_abiertas:
        return False

    posicion = posiciones_abiertas[par]
    precio_compra = posicion['precio_compra']
    cantidad = posicion['cantidad']

    try:
        # ORDEN REAL EN BINANCE
        orden = exchange.create_market_sell_order(par, cantidad)
        precio_venta = orden['average'] if orden.get('average') else precio_actual

        # Calcular resultado
        ganancia_bruta = (precio_venta - precio_compra) * cantidad
        comision = (posicion['capital_usado'] + ganancia_bruta) * COMISION_BINANCE * 2
        ganancia_neta = ganancia_bruta - comision
        ganancia_pct = (precio_venta - precio_compra) / precio_compra * 100

        capital_actual += posicion['capital_usado'] + ganancia_neta
        ganancia_total += ganancia_neta

        print(f"{'✅' if ganancia_neta > 0 else '❌'} VENTA {par} @ ${precio_venta:.4f} | {ganancia_pct:+.2f}% | ${ganancia_neta:+.4f}")
        enviar_alerta_venta(par, precio_compra, precio_venta, ganancia_pct, ganancia_neta, razon)

        del posiciones_abiertas[par]
        return True

    except Exception as e:
        print(f"❌ Error ejecutando venta en {par}: {e}")
        enviar_mensaje(f"❌ Error en venta {par}: {str(e)}")
        return False

# ============================================================
# VERIFICAR HORA DE OPERACION
# ============================================================
def hora_valida():
    hora_actual = datetime.now(timezone.utc).hour
    return hora_actual not in EVITAR_HORAS

# ============================================================
# REPORTE PERIODICO (cada 6 horas)
# ============================================================
ultimo_reporte = time.time()

def enviar_reporte_periodico():
    global ultimo_reporte
    if time.time() - ultimo_reporte >= 21600:  # 6 horas
        enviar_reporte(
            capital_actual + sum(p['capital_usado'] for p in posiciones_abiertas.values()),
            capital_inicial,
            len(posiciones_abiertas),
            operaciones_totales,
            ganancia_total
        )
        ultimo_reporte = time.time()

# ============================================================
# CICLO PRINCIPAL DEL BOT
# ============================================================
def ciclo_principal():
    print(f"\n{'='*50}")
    print(f"🤖 BOT INICIADO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Capital: ${CAPITAL_TOTAL} | Pares: {len(PARES)}")
    print(f"{'='*50}\n")

    enviar_mensaje(
        f"🤖 <b>BOT INICIADO</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Capital: <b>${CAPITAL_TOTAL}</b>\n"
        f"📊 Pares: <b>{', '.join(PARES)}</b>\n"
        f"⏱️ Intervalo: <b>{INTERVALO}</b>\n"
        f"🎯 Stop Loss: <b>{STOP_LOSS_PCT*100}%</b>\n"
        f"🚀 Take Profit: <b>{TAKE_PROFIT_PCT*100}%</b>"
    )

    while True:
        try:
            hora = datetime.now().strftime('%H:%M:%S')
            print(f"\n⏰ [{hora}] Analizando mercado...")

            for par in PARES:
                print(f"  📊 Analizando {par}...")

                df = obtener_datos(par)
                if df is None or len(df) < 50:
                    print(f"  ⚠️ Datos insuficientes para {par}")
                    continue

                df = calcular_indicadores(df)
                if df is None:
                    continue

                # === LOGICA DE VENTA (primero verificar posiciones abiertas) ===
                if par in posiciones_abiertas:
                    puntuacion_venta, razon_venta, precio_actual = evaluar_venta(
                        df, posiciones_abiertas[par]
                    )
                    if puntuacion_venta >= PUNTUACION_VENTA:
                        ejecutar_venta(par, precio_actual, razon_venta)
                    else:
                        precio_compra = posiciones_abiertas[par]['precio_compra']
                        ganancia = (df.iloc[-1]['close'] - precio_compra) / precio_compra * 100
                        print(f"  📦 Posicion {par} activa | Ganancia actual: {ganancia:+.2f}%")

                # === LOGICA DE COMPRA ===
                elif hora_valida():
                    puntuacion_compra, razones_compra, precio_actual = evaluar_compra(df)
                    print(f"  📈 {par} | Puntuacion: {puntuacion_compra}/15 | Precio: ${precio_actual:,.4f}")

                    if puntuacion_compra >= PUNTUACION_COMPRA:
                        print(f"  🚀 SEÑAL DE COMPRA detectada en {par}!")
                        ejecutar_compra(par, precio_actual, puntuacion_compra, razones_compra)
                    else:
                        print(f"  ⏳ Sin señal suficiente ({puntuacion_compra}/{PUNTUACION_COMPRA} minimo)")
                else:
                    print(f"  🌙 Hora de baja liquidez, no se opera")

                time.sleep(1)  # Pausa entre pares

            # Reporte periodico
            enviar_reporte_periodico()

            # Esperar siguiente ciclo
            segundos = 3600 if INTERVALO == '1h' else 300
            print(f"\n⏳ Esperando {segundos//60} minutos para el siguiente ciclo...")
            time.sleep(segundos)

        except KeyboardInterrupt:
            print("\n🛑 Bot detenido por el usuario")
            enviar_mensaje("🛑 <b>Bot detenido manualmente</b>")
            break
        except Exception as e:
            print(f"❌ Error en ciclo principal: {e}")
            enviar_mensaje(f"⚠️ Error en bot: {str(e)}")
            time.sleep(60)

# ============================================================
# INICIAR BOT
# ============================================================
if __name__ == '__main__':
    ciclo_principal()