import os, asyncio, pandas as pd
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

def get_ema_signal(symbol):
    # ambil 50 candle 15m
    klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=50)
    closes = [float(k[4]) for k in klines]
    df = pd.DataFrame(closes, columns=['close'])
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    # cross up = LONG, cross down = SHORT
    if prev['ema9'] < prev['ema21'] and last['ema9'] > last['ema21']:
        return "LONG"
    if prev['ema9'] > prev['ema21'] and last['ema9'] < last['ema21']:
        return "SHORT"
    return None

async def pasang_sltp(symbol, side, entry):
    sl = entry*(1-SL_PCT) if side=="LONG" else entry*(1+SL_PCT)
    tp = entry*(1+TP_PCT) if side=="LONG" else entry*(1-TP_PCT)
    try:
        s_side = "SELL" if side=="LONG" else "BUY"
        client.futures_create_order(symbol=symbol, side=s_side, type='STOP_MARKET', stopPrice=round(sl,6), closePosition=True)
        client.futures_create_order(symbol=symbol, side=s_side, type='TAKE_PROFIT_MARKET', stopPrice=round(tp,6), closePosition=True)
    except Exception as e: print(e)
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
        await app.bot.send_message(chat_id=OWNER_ID, text=f"🤖 AUTO {side} {symbol}\nEntry {price}\nQty {qty} | 5x\nSL {sl:.6f} -2%\nTP {tp:.6f} +4%\nSinyal EMA 9x21 15m")
    return qty

async def auto_loop(app):
    global AUTO_ON
    while True:
        if AUTO_ON and OWNER_ID:
            try:
                # scan koin paling rame dulu
                tickers = client.futures_ticker()
                vols = {t['symbol']: float(t['quoteVolume']) for t in tickers if t['symbol'] in WATCHLIST}
                top_coin = max(vols, key=vols.get)

                # cek ada posisi ga
                has_pos = False
                for s in WATCHLIST:
                    pos = client.futures_position_information(symbol=s)
                    if any(float(p['positionAmt'])!=0 for p in pos):
                        has_pos = True
                        break
                if has_pos:
                    await asyncio.sleep(300)
                    continue

                signal = get_ema_signal(top_coin)
                if signal:
                    bal = client.futures_account_balance()
                    usdt = float([b for b in bal if b['asset']=='USDT'][0]['balance'])
                    if usdt >= 3:
                        await open_auto(top_coin, signal, usdt, app)
            except Exception as e:
                print(f"loop err {e}")
        await asyncio.sleep(300) # cek tiap 5 menit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    OWNER_ID = update.effective_chat.id
    await update.message.reply_text(
        "🤖💸 FULL AUTO PILOT ON BOS!\n\n"
        "/auto - NYALAIN BOT (bot kerja sendiri)\n"
        "/stopauto - STOP\n"
        "/posisi - CEK SALDO + POSISI\n"
        "/close - TUTUP SEMUA DARURAT\n\n"
        "Bot baca EMA 9x21 TF 15m\n"
        "Cross up = LONG, Cross down = SHORT\n"
        "Auto SL 2% TP 4% + cuma pake $2/trade"
    )

async def posisi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = client.futures_account_balance()
    usdt = float([b for b in bal if b['asset']=='USDT'][0]['balance'])
    msg = f"💰 ${usdt:.2f} | Auto: {'ON 🟢' if AUTO_ON else 'OFF 🔴'}\n\n"
    for s in WATCHLIST:
        pos = client.futures_position_information(symbol=s)
        for p in pos:
            if float(p['positionAmt'])!=0:
                msg+=f"📌 {s} {p['positionAmt']} PnL {float(p['unRealizedProfit']):.4f}$\n"
    if "📌" not in msg: msg+="Ga ada posisi - nunggu sinyal EMA..."
    await update.message.reply_text(msg)

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_ON, OWNER_ID
    AUTO_ON = True
    OWNER_ID = update.effective_chat.id
    await update.message.reply_text("✅ FULL AUTO ON MET! Bot scan tiap 5 menit:\n1. Cari koin micin paling rame\n2. Cek EMA 9 cross 21 di 15m\n3. Kalo ada sinyal LONG/SHORT auto masuk + SLTP\n\nLu tinggal pantau, bot yang kerja!")
    asyncio.create_task(auto_loop(context.application))

async def stopauto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_ON
    AUTO_ON = False
    await update.message.reply_text("🛑 AUTO OFF - Bot berhenti buka posisi baru.")

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for s in WATCHLIST:
        try:
            pos = client.futures_position_information(symbol=s)
            for p in pos:
                amt=float(p['positionAmt'])
                if amt!=0: client.futures_create_order(symbol=s, side='SELL' if amt>0 else 'BUY', type='MARKET', quantity=abs(amt))
            client.futures_cancel_all_open_orders(symbol=s)
        except: pass
    await update.message.reply_text("✅ SEMUA DITUTUP DARURAT!")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("posisi", posisi))
app.add_handler(CommandHandler("auto", auto))
app.add_handler(CommandHandler("stopauto", stopauto))
app.add_handler(CommandHandler("close", close))
print("FULL AUTO BOT JALAN...")
app.run_polling()
