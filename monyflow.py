import asyncio
from telegram.ext import Application
from binance.client import Client
import time
from datetime import datetime

# ================ الإعدادات =================
API_KEY = 'ljFDkhsosOoARHpstgR549VMJhouc1DdIH6wq7haCTBFwWF2gWKhgKoVwNesZxOZ'
API_SECRET = '8q4GMabDuzuJElke6goo2DQBTlwWuRKXsNwE2mBmIie0wlfoSteeJAAoixuMeB52'
BOT_TOKEN = '8727431590:AAGG8FqwmePh-vrTpWus5f2SxxknNgelfKE'
CHAT_ID = 1248313592 # حط الـ ID حقك من @userinfobot
# ==========================================

client = Client(API_KEY, API_SECRET)

# إعدادات الفلترة - عدلها على كيفك
MIN_VOLUME_USDT = 500000 # أقل سيولة نهتم لها بالدولار
MIN_PRICE_CHANGE = 3 # أقل نسبة ارتفاع %
TIMEFRAME_SECONDS = 300 # نراقب الارتفاع خلال كم ثانية - 300 = 5 دقايق
CHECK_INTERVAL = 15 # كل كم ثانية نشيك السوق

# نخزن آخر البيانات للمقارنة
last_check_data = {}
alerted_symbols = set() # عشان ما نرسل تنبيه مرتين لنفس العملة

async def send_alert(text):
    app = Application.builder().token(BOT_TOKEN).build()
    await app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='HTML')

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.2f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return f"{num:.2f}"

def check_liquidity_spikes():
    global last_check_data
    try:
        all_tickers = client.get_ticker()
        current_time = time.time()

        for ticker in all_tickers:
            symbol = ticker['symbol']

            # نهتم بعملات USDT فقط ونستبعد العملات المستقرة
            if not symbol.endswith('USDT') or symbol in ['USDCUSDT', 'BUSDUSDT', 'TUSDUSDT', 'USDPUSDT']:
                continue

            try:
                volume = float(ticker['quoteVolume']) # السيولة بالدولار
                price = float(ticker['lastPrice'])
                price_change = float(ticker['priceChangePercent'])

                # الشرط 1: سيولة عالية + ارتفاع قوي
                if volume >= MIN_VOLUME_USDT and price_change >= MIN_PRICE_CHANGE:

                    # نشوف هل كانت موجودة في الفحص السابق
                    if symbol in last_check_data:
                        old_data = last_check_data[symbol]
                        old_price = old_data['price']
                        old_time = old_data['time']

                        # الشرط 2: الارتفاع صار خلال الفترة اللي نراقبها
                        time_diff = current_time - old_time
                        price_diff_pct = ((price - old_price) / old_price) * 100

                        if time_diff <= TIMEFRAME_SECONDS and price_diff_pct >= MIN_PRICE_CHANGE:
                            # نتأكد ما أرسلنا تنبيه قبل شوي
                            alert_key = f"{symbol}_{int(current_time//60)}"
                            if alert_key not in alerted_symbols:

                                coin_name = symbol.replace('USDT', '')
                                time_taken = int(time_diff)
                                minutes = time_taken // 60
                                seconds = time_taken % 60

                                msg = f"🚨 <b>سيولة داخلة + انفجار سعري</b>\n\n" \
                                      f"<b>العملة:</b> {coin_name}\n" \
                                      f"<b>السعر الحالي:</b> ${price}\n" \
                                      f"<b>نسبة الارتفاع:</b> +{price_diff_pct:.2f}%\n" \
                                      f"<b>الزمن:</b> خلال {minutes} دقيقة و {seconds} ثانية\n" \
                                      f"<b>الفوليوم 24س:</b> ${format_number(volume)}\n" \
                                      f"<b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}"

                                asyncio.run(send_alert(msg))
                                alerted_symbols.add(alert_key)
                                print(f"تم إرسال تنبيه لـ {symbol}")

                    # نحدث البيانات
                    last_check_data[symbol] = {'price': price, 'time': current_time, 'volume': volume}
                else:
                    # حتى لو ما انطبق الشرط، نخزن السعر للمقارنة لاحقاً
                    last_check_data[symbol] = {'price': price, 'time': current_time, 'volume': volume}

            except Exception as e:
                continue

    except Exception as e:
        print(f"خطأ في فحص السيولة: {e}")
        asyncio.run(send_alert(f"خطأ في البوت: {e}"))

async def main():
    await send_alert("✅ بوت تتبع السيولة اشتغل\nيراقب أي عملة ترتفع +3% بسيولة فوق 500K خلال 5 دقايق")

    while True:
        check_liquidity_spikes()
        # نحذف التنبيهات القديمة كل ساعة عشان لو العملة رجعت ارتفعت ننبه مرة ثانية
        if len(alerted_symbols) > 1000:
            alerted_symbols.clear()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())