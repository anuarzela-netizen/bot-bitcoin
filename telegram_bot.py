import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def enviar_mensaje(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mensaje,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error enviando mensaje Telegram: {e}")
        return None

def enviar_alerta_compra(par, precio, cantidad, stop_loss, take_profit, puntuacion, razones):
    mensaje = (
        f"🟢 <b>COMPRA EJECUTADA</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Par: <b>{par}</b>\n"
        f"💰 Precio: <b>${precio:,.4f}</b>\n"
        f"📦 Cantidad: <b>{cantidad:.6f}</b>\n"
        f"🛑 Stop Loss: <b>${stop_loss:,.4f}</b>\n"
        f"🎯 Take Profit: <b>${take_profit:,.4f}</b>\n"
        f"⭐ Puntuación: <b>{puntuacion}/10</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Señales:\n{razones}"
    )
    return enviar_mensaje(mensaje)

def enviar_alerta_venta(par, precio_compra, precio_venta, ganancia_pct, ganancia_usd, razon):
    emoji = "🟢" if ganancia_pct > 0 else "🔴"
    mensaje = (
        f"{emoji} <b>VENTA EJECUTADA</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Par: <b>{par}</b>\n"
        f"📈 Precio compra: <b>${precio_compra:,.4f}</b>\n"
        f"📉 Precio venta: <b>${precio_venta:,.4f}</b>\n"
        f"💵 Resultado: <b>{ganancia_pct:+.2f}%</b>\n"
        f"💰 Ganancia: <b>${ganancia_usd:+.4f}</b>\n"
        f"📋 Razón: <b>{razon}</b>"
    )
    return enviar_mensaje(mensaje)

def enviar_reporte(capital_actual, capital_inicial, posiciones, operaciones_totales, ganancia_total):
    rentabilidad = ((capital_actual - capital_inicial) / capital_inicial) * 100
    emoji = "📈" if rentabilidad >= 0 else "📉"
    mensaje = (
        f"📊 <b>REPORTE DEL BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Capital inicial: <b>${capital_inicial:.2f}</b>\n"
        f"💵 Capital actual: <b>${capital_actual:.2f}</b>\n"
        f"{emoji} Rentabilidad: <b>{rentabilidad:+.2f}%</b>\n"
        f"📦 Posiciones abiertas: <b>{posiciones}</b>\n"
        f"🔄 Operaciones totales: <b>{operaciones_totales}</b>\n"
        f"💸 Ganancia total: <b>${ganancia_total:+.4f}</b>"
    )
    return enviar_mensaje(mensaje)