import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from binance.client import Client
from binance.exceptions import BinanceAPIException
import threading
import time

# ================ الإعدادات - عدلها =================
API_KEY = 'ljFDkhsosOoARHpstgR549VMJhouc1DdIH6wq7haCTBFwWF2gWKhgKoVwNesZxOZ'
API_SECRET = '8q4GMabDuzuJElke6goo2DQBTlwWuRKXsNwE2mBmIie0wlfoSteeJAAoixuMeB52'
BOT_TOKEN = '8086608166:AAHE6ZOLiRr37TUCE1oVJQAdPCFZuYKIHTw'
CHAT_ID = 1248313592

client = Client(API_KEY, API_SECRET)

# إعدادات التداول
favorite_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
TRADE_PERCENTAGE = 0.30
MAX_OPEN_TRADES = 3
TAKE_PROFIT = 1.02
STOP_LOSS = 0.99
VOLUME_FILTER = 1000
PRICE_CHANGE_FILTER = 5
open_trades = {}

async def send_msg(text):
    app = Application.builder().token(BOT_TOKEN).build()
    await app.bot.send_message(chat_id=CHAT_ID, text=text)

def get_usdt_balance():
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free'])
    except Exception as e:
        asyncio.run(send_msg(f"خطأ جلب الرصيد: {e}"))
        return 0

def trading_loop():
    while True:
        try:
            # نتفقد الصفقات المفتوحة للبيع
            for symbol in list(open_trades.keys()):
                current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
                buy_price = open_trades[symbol]['buy_price']

                if current_price >= buy_price * TAKE_PROFIT:
                    asyncio.run(send_msg(f"🎯 {symbol} وصل هدف الربح"))
                    sell_symbol(symbol)
                elif current_price <= buy_price * STOP_LOSS:
                    asyncio.run(send_msg(f"🛑 {symbol} وصل وقف الخسارة"))
                    sell_symbol(symbol)

            # ندور فرص جديدة
            if len(open_trades) < MAX_OPEN_TRADES:
                tickers = client.get_ticker()
                usdt_balance = get_usdt_balance()
                trade_amount = (usdt_balance * TRADE_PERCENTAGE) / MAX_OPEN_TRADES

                for ticker in tickers:
                    symbol = ticker['symbol']
                    if symbol in favorite_symbols and symbol not in open_trades:
                        volume = float(ticker['quoteVolume'])
                        price_change = float(ticker['priceChangePercent'])
                        if volume > VOLUME_FILTER and price_change > PRICE_CHANGE_FILTER and trade_amount > 10:
                            asyncio.run(send_msg(f"🔍 فرصة في {symbol}\nالسيولة: {volume:.0f} USDT\nالتغير: {price_change}%"))
                            buy_symbol(symbol, trade_amount)
                            time.sleep(2)
                            break
        except Exception as e:
            asyncio.run(send_msg(f"خطأ في الحلقة الرئيسية: {e}"))
        time.sleep(60)

def buy_symbol(symbol, usdt_amount):
    try:
        price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        quantity = usdt_amount / price
        info = client.get_symbol_info(symbol)
        step_size = float([f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
        precision = len(str(step_size).split('.')[-1].rstrip('0'))
        quantity = round(quantity, precision)
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        buy_price = float(order['fills'][0]['price'])
        open_trades[symbol] = {'buy_price': buy_price, 'quantity': quantity}
        asyncio.run(send_msg(f"✅ شراء {symbol}\nالكمية: {quantity}\nالسعر: {buy_price}"))
    except BinanceAPIException as e:
        asyncio.run(send_msg(f"❌ فشل شراء {symbol}: {e}"))

def sell_symbol(symbol):
    try:
        quantity = open_trades[symbol]['quantity']
        order = client.order_market_sell(symbol=symbol, quantity=quantity)
        sell_price = float(order['fills'][0]['price'])
        buy_price = open_trades[symbol]['buy_price']
        profit_pct = ((sell_price - buy_price) / buy_price) * 100
        asyncio.run(send_msg(f"✅ بيع {symbol}\nسعر الشراء: {buy_price}\nسعر البيع: {sell_price}\nالربح: {profit_pct:.2f}%"))
        del open_trades[symbol]
    except BinanceAPIException as e:
        asyncio.run(send_msg(f"❌ فشل بيع {symbol}: {e}"))

# ================ أوامر تليجرام =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('بوت التداول اشتغل ✅\n/add BTCUSDT لإضافة عملة\n/remove BTCUSDT لحذف عملة\n/list عرض المفضلة\n/status عرض الصفقات')

async def add_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('استخدم الأمر كذا: /add BTCUSDT')
        return
    symbol = context.args[0].upper()
    if symbol not in favorite_symbols:
        favorite_symbols.append(symbol)
        await update.message.reply_text(f'تم إضافة {symbol} للمفضلة')
    else:
        await update.message.reply_text(f'{symbol} موجودة بالفعل')

async def remove_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('استخدم الأمر كذا: /remove BTCUSDT')
        return
    symbol = context.args[0].upper()
    if symbol in favorite_symbols:
        favorite_symbols.remove(symbol)
        await update.message.reply_text(f'تم حذف {symbol} من المفضلة')
    else:
        await update.message.reply_text(f'{symbol} مو موجودة')

async def list_symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('العملات المفضلة:\n' + '\n'.join(favorite_symbols))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not open_trades:
        await update.message.reply_text('لا توجد صفقات مفتوحة حالياً')
    else:
        msg = 'الصفقات المفتوحة:\n'
        for sym, data in open_trades.items():
            msg += f"{sym}: شراء {data['buy_price']}\n"
        await update.message.reply_text(msg)

def main():
    # نشغل حلقة التداول في ثريد منفصل
    threading.Thread(target=trading_loop, daemon=True).start()

    # نشغل بوت التليجرام
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('add', add_symbol))
    app.add_handler(CommandHandler('remove', remove_symbol))
    app.add_handler(CommandHandler('list', list_symbols))
    app.add_handler(CommandHandler('status', status))

    asyncio.run(send_msg("🚀 البوت اشتغل"))
    app.run_polling()

if __name__ == '__main__':
    main()