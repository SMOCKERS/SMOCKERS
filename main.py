import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from binance.client import Client

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("BINANCE_API")
API_SECRET = os.getenv("BINANCE_SECRET")
client = Client(API_KEY, API_SECRET)

LEVERAGE = 5
WATCHLIST = ["DOGEUSDT", "1000PEPEUSDT", "1000BONKUSDT", "WIFUSDT"]
AUTO_ON = False
SL_PCT = 0.02
TP_PCT = 0.04
OWNER_ID = None

def ema_calc(prices, period):
    k = 2/(period+1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p*k + ema*(1-k)
    return ema

def get_ema_signal(symbol):
    try:
        klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=30)
        closes = [float(k[4]) for k in klines]
        ema9_now = ema_calc(closes[-10:], 9)
        ema21_now = ema_calc(closes[-22:], 21)
        ema9_prev = ema_calc(closes[-11:-1], 9)
        ema21_prev = ema_calc(closes[-23:-1], 21)
        if ema9_prev < ema21_prev and ema9_now > ema21_now:
            return "LONG"
        if ema9_prev > ema21_prev and ema9_now < ema21_now:
            return "SHORT"
    except Exception as e:
        print(e)
    return None

async def pasang_sltp(symbol, side, entry):
    sl = entry*(1-SL_PCT) if side=="LONG" else entry*(1+SL_PCT)
    tp = entry*(1+TP_PCT) if side=="LONG" else entry*(1-TP_PCT)
    try:
        s_side = "SELL" if side=="LONG" else "BUY"
        client.futures_create_order(symbol=symbol, side=s_side, type='STOP_MARKET', stopPrice=round(sl,6), closePosition=True)
        client.futures_create_order(symbol=symbol, side=s_side, type='TAKE_PROFIT_MARKET', stopPrice=round(tp,6), closePosition=True)
    except: pass
    return sl,tp

async def open_auto(symbol, side, usdt, app):
    price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    qty = (usdt*0.10*LEVERAGE)/price
    qty = int(qty) if "1000" in symbol else round(qty,0)
    if qty==0: qty=1
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except: pass
    client.futures_create_order(symbol=symbol, side='BUY' if side=='LONG' else 'SELL', type='MARKET', quantity=qty)
    sl,tp = await pasang_sltp(symbol, side, price)
    if app and OWNER_ID:
        await app.bot.send_message(chat_id=OWNER_ID, text=f"🤖 AUTO {side} {symbol}\nEntry {price}\nSL {sl:.6f} -2% TP {tp:.6f} +4%\nModal $2 | 5x")
    return qty

async def auto_loop(app):
    global AUTO_ON
    while True:
        if AUTO_ON and OWNER_ID:
            try:
                tickers = client.futures_ticker()
                vols = {t['symbol']: float(t['quoteVolume']) for t in tickers if t['symbol'] in WATCHLIST}
                top_coin = max(vols, key=vols.get)
                has_pos=False
                for s in WATCHLIST:
                    pos=client.futures_position_information(symbol=s)
                    if any(float(p['positionAmt'])!=0 for p in pos):
                        has_pos=True; break
                if has_pos:
                    await asyncio.sleep(300); continue
                signal = get_ema_signal(top_coin)
                if signal:
                    bal=client.futures_account_balance()
                    usdt=float([b for b in bal if b['asset']=='USDT'][0]['balance'])
                    if usdt>=3: await open_auto(top_coin, signal, usdt, app)
            except Exception as e: print(e)
        await asyncio.sleep(300)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID; OWNER_ID=update.effective_chat.id
    await update.message.reply_text("🤖 FULL AUTO FIXED! Tanpa pandas jadi ga crash!\n/auto - NYALAIN\n/stopauto - MATI\n/posisi - CEK")

async def posisi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal=client.futures_account_balance()
    usdt=float([b for b in bal if b['asset']=='USDT'][0]['balance'])
    msg=f"💰 ${usdt:.2f} | Auto {'ON 🟢' if AUTO_ON else 'OFF 🔴'}\n"
    for s in WATCHLIST:
        pos=client.futures_position_information(symbol=s)
        for p in pos:
            if float(p['positionAmt'])!=0: msg+=f"📌 {s} {p['positionAmt']} PnL {float(p['unRealizedProfit']):.4f}$\n"
    if "📌" not in msg: msg+="Ga ada posisi, nunggu sinyal..."
    await update.message.reply_text(msg)

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_ON, OWNER_ID; AUTO_ON=True; OWNER_ID=update.effective_chat.id
    await update.message.reply_text("✅ AUTO ON! Bot scan 5 menit sekali, full otomatis LONG/SHORT + SLTP. Ga perlu pencet apa2 lagi!")
    asyncio.create_task(auto_loop(context.application))

async def stopauto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_ON; AUTO_ON=False
    await update.message.reply_text("🛑 AUTO OFF!")

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for s in WATCHLIST:
        try:
            pos=client.futures_position_information(symbol=s)
            for p in pos:
                amt=float(p['positionAmt'])
                if amt!=0: client.futures_create_order(symbol=s, side='SELL' if amt>0 else 'BUY', type='MARKET', quantity=abs(amt))
            client.futures_cancel_all_open_orders(symbol=s)
        except: pass
    await update.message.reply_text("✅ SEMUA DITUTUP!")

app=ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("posisi", posisi))
app.add_handler(CommandHandler("auto", auto))
app.add_handler(CommandHandler("stopauto", stopauto))
app.add_handler(CommandHandler("close", close))
print("FULL AUTO NO PANDAS JALAN...")
app.run_polling()
