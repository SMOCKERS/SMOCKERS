import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from binance.client import Client

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("BINANCE_API") or os.getenv("API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET") or os.getenv("API_SECRET")

# proxy support biar ga kena blokir US
proxies = None
proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
if proxy_url:
    proxies = {"http": proxy_url, "https": proxy_url}
    client = Client(API_KEY, API_SECRET, requests_params={"proxies": proxies, "timeout": 30})
else:
    client = Client(API_KEY, API_SECRET)

WATCHLIST = ["DOGEUSDT", "1000PEPEUSDT", "1000BONKUSDT", "WIFUSDT"]
AUTO_ON = False
OWNER_ID = None

def ema_calc(prices, period):
    k = 2/(period+1)
    ema = prices[0]
    for p in prices[1:]: ema = p*k + ema*(1-k)
    return ema

def get_signal(sym):
    try:
        kl = client.futures_klines(symbol=sym, interval=Client.KLINE_INTERVAL_15MINUTE, limit=30)
        closes = [float(x[4]) for x in kl]
        e9_now = ema_calc(closes[-10:],9)
        e21_now = ema_calc(closes[-22:],21)
        e9_prev = ema_calc(closes[-11:-1],9)
        e21_prev = ema_calc(closes[-23:-1],21)
        if e9_prev < e21_prev and e9_now > e21_now: return "LONG"
        if e9_prev > e21_prev and e9_now < e21_now: return "SHORT"
    except: return None
    return None

async def posisi(u,c):
    try:
        bal = client.futures_account_balance()
        usdt = float([b for b in bal if b['asset']=='USDT'][0]['balance'])
        msg = f"💰 BINANCE ${usdt:.2f} | Auto {'ON 🟢' if AUTO_ON else 'OFF 🔴'}\n"
        for s in WATCHLIST:
            pos = client.futures_position_information(symbol=s)
            for p in pos:
                if float(p['positionAmt'])!=0:
                    msg+=f"📌 {s} {p['positionAmt']} PnL {float(p['unRealizedProfit']):.3f}\n"
        if "📌" not in msg: msg+="Ga ada posisi, nunggu sinyal EMA 15m..."
        await u.message.reply_text(msg)
    except Exception as e:
        await u.message.reply_text(f"❌ Binance blokir US: {e}\n\nSOLUSI: Pindah deploy ke Render.com region Singapore. Railway US emang diblokir Binance permanen met.")

async def start(u,c):
    global OWNER_ID; OWNER_ID=u.effective_chat.id
    await u.message.reply_text("🤖 SMOCKERS BINANCE FIXED!\n/posisi - CEK SALDO\n/auto - AUTO PILOT LONG/SHORT + SL 2% TP 4%\n/close - TUTUP SEMUA")

async def open_auto(sym, side, usdt, app):
    price = float(client.futures_symbol_ticker(symbol=sym)['price'])
    qty = (usdt*0.10*5)/price
    qty = int(qty) if "1000" in sym else round(qty,0)
    if qty==0: qty=1
    try:
        client.futures_change_leverage(symbol=sym, leverage=5)
        client.futures_change_margin_type(symbol=sym, marginType='ISOLATED')
    except: pass
    client.futures_create_order(symbol=sym, side='BUY' if side=='LONG' else 'SELL', type='MARKET', quantity=qty)
    sl = price*0.98 if side=="LONG" else price*1.02
    tp = price*1.04 if side=="LONG" else price*0.96
    try:
        side_close = "SELL" if side=="LONG" else "BUY"
        client.futures_create_order(symbol=sym, side=side_close, type='STOP_MARKET', stopPrice=round(sl,6), closePosition=True)
        client.futures_create_order(symbol=sym, side=side_close, type='TAKE_PROFIT_MARKET', stopPrice=round(tp,6), closePosition=True)
    except: pass
    if app and OWNER_ID:
        await app.bot.send_message(chat_id=OWNER_ID, text=f"🤖 AUTO {side} {sym}\nEntry {price}\nSL {sl:.6f} -2% TP {tp:.6f} +4%")

async def auto_loop(app):
    global AUTO_ON
    while True:
        if AUTO_ON and OWNER_ID:
            try:
                has=False
                for s in WATCHLIST:
                    pos=client.futures_position_information(symbol=s)
                    if any(float(p['positionAmt'])!=0 for p in pos): has=True; break
                if has: await asyncio.sleep(300); continue
                tickers=client.futures_ticker()
                vols={t['symbol']:float(t['quoteVolume']) for t in tickers if t['symbol'] in WATCHLIST}
                top=max(vols, key=vols.get) if vols else "DOGEUSDT"
                sig=get_signal(top)
                if sig:
                    bal=float([b for b in client.futures_account_balance() if b['asset']=='USDT'][0]['balance'])
                    if bal>=3: await open_auto(top,sig,bal,app)
            except Exception as e: print(e)
        await asyncio.sleep(300)

async def auto(u,c):
    global AUTO_ON, OWNER_ID; AUTO_ON=True; OWNER_ID=u.effective_chat.id
    await u.message.reply_text("✅ FULL AUTO BINANCE ON! Scan tiap 5 menit, auto LONG/SHORT + SLTP 2%/4%. Kita pantau bareng ya met!")
    asyncio.create_task(auto_loop(c.application))

async def stopauto(u,c):
    global AUTO_ON; AUTO_ON=False; await u.message.reply_text("🛑 AUTO OFF")

async def close(u,c):
    for s in WATCHLIST:
        try:
            pos=client.futures_position_information(symbol=s)
            for p in pos:
                amt=float(p['positionAmt'])
                if amt!=0: client.futures_create_order(symbol=s, side='SELL' if amt>0 else 'BUY', type='MARKET', quantity=abs(amt))
            client.futures_cancel_all_open_orders(symbol=s)
        except: pass
    await u.message.reply_text("✅ DITUTUP!")

app=ApplicationBuilder().token(TOKEN).build()
for cmd,fn in [("start",start),("posisi",posisi),("auto",auto),("stopauto",stopauto),("close",close)]:
    app.add_handler(CommandHandler(cmd,fn))
print("BINANCE FIXED BOT JALAN...")
app.run_polling()
