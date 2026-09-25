import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pybit.unified_trading import HTTP

TOKEN = os.getenv("BOT_TOKEN")
BYBIT_KEY = os.getenv("BYBIT_KEY")
BYBIT_SECRET = os.getenv("BYBIT_SECRET")

client = HTTP(testnet=False, api_key=BYBIT_KEY, api_secret=BYBIT_SECRET)

WATCHLIST = ["DOGEUSDT", "PEPEUSDT", "BONKUSDT", "WIFUSDT"]
AUTO_ON = False
OWNER_ID = None

def get_ema_signal(symbol):
    try:
        klines = client.get_kline(category="linear", symbol=symbol, interval="15", limit=30)['result']['list']
        closes = [float(k[4]) for k in reversed(klines)] # bybit return kebalik
        def ema_calc(prices, period):
            k = 2/(period+1)
            ema = prices[0]
            for p in prices[1:]: ema = p*k + ema*(1-k)
            return ema
        e9_now = ema_calc(closes[-10:],9)
        e21_now = ema_calc(closes[-22:],21)
        e9_prev = ema_calc(closes[-11:-1],9)
        e21_prev = ema_calc(closes[-23:-1],21)
        if e9_prev < e21_prev and e9_now > e21_now: return "LONG"
        if e9_prev > e21_prev and e9_now < e21_now: return "SHORT"
    except Exception as e: print(e)
    return None

async def open_auto(symbol, side, usdt, app):
    try:
        price = float(client.get_tickers(category="linear", symbol=symbol)['result']['list'][0]['lastPrice'])
        qty = (usdt*0.10*5)/price
        qty = int(qty) if "PEPE" in symbol or "BONK" in symbol else round(qty,1)
        if qty==0: qty=1
        # set leverage 5x isolated
        try: client.set_leverage(category="linear", symbol=symbol, buyLeverage="5", sellLeverage="5")
        except: pass
        client.place_order(category="linear", symbol=symbol, side="Buy" if side=="LONG" else "Sell", orderType="Market", qty=str(qty), takeProfit=str(price*1.04 if side=="LONG" else price*0.96), stopLoss=str(price*0.98 if side=="LONG" else price*1.02))
        if app and OWNER_ID:
            await app.bot.send_message(chat_id=OWNER_ID, text=f"🤖 BYBIT AUTO {side} {symbol}\nEntry {price}\nQty {qty} | 5x\nSL -2% TP +4% AUTO KEPASANG!\nModal $2 - Aman dari blokir US!")
    except Exception as e:
        print(f"open err {e}")

async def auto_loop(app):
    global AUTO_ON
    while True:
        if AUTO_ON and OWNER_ID:
            try:
                # cek ada posisi ga
                pos = client.get_positions(category="linear", settleCoin="USDT")['result']['list']
                has_pos = any(float(p['size'])!=0 for p in pos)
                if has_pos:
                    await asyncio.sleep(300); continue
                # cari top volume
                tickers = client.get_tickers(category="linear")['result']['list']
                vols = {}
                for t in tickers:
                    if t['symbol'] in WATCHLIST: vols[t['symbol']] = float(t['turnover24h'])
                top = max(vols, key=vols.get) if vols else "DOGEUSDT"
                sig = get_ema_signal(top)
                if sig:
                    bal = float(client.get_wallet_balance(accountType="UNIFIED")['result']['list'][0]['coin'][0]['walletBalance'])
                    if bal>=3: await open_auto(top, sig, bal, app)
            except Exception as e: print(e)
        await asyncio.sleep(300)

async def start(u,c):
    global OWNER_ID; OWNER_ID=u.effective_chat.id
    await u.message.reply_text("🤖 BYBIT AUTO ANTI BLOKIR ON!\n/auto - START AUTOPILOT\n/posisi - CEK SALDO\n/close - TUTUP SEMUA")

async def posisi(u,c):
    try:
        bal = float(client.get_wallet_balance(accountType="UNIFIED")['result']['list'][0]['coin'][0]['walletBalance'])
        pos = client.get_positions(category="linear", settleCoin="USDT")['result']['list']
        msg = f"💰 ${bal:.2f} | Auto {'ON 🟢' if AUTO_ON else 'OFF 🔴'}\n\n"
        for p in pos:
            if float(p['size'])!=0: msg+=f"📌 {p['symbol']} {p['side']} {p['size']} PnL {p['unrealisedPnl']}$\n"
        if "📌" not in msg: msg+="Ga ada posisi, nunggu sinyal EMA 15m..."
        await u.message.reply_text(msg)
    except Exception as e: await u.message.reply_text(f"Error: {e}")

async def auto(u,c):
    global AUTO_ON, OWNER_ID; AUTO_ON=True; OWNER_ID=u.effective_chat.id
    await u.message.reply_text("✅ BYBIT AUTO ON! Bot scan 5 menit sekali, full otomatis LONG/SHORT + SL 2% TP 4%. Ga kena blokir US lagi!")
    asyncio.create_task(auto_loop(c.application))

async def stopauto(u,c):
    global AUTO_ON; AUTO_ON=False; await u.message.reply_text("🛑 OFF")

async def close(u,c):
    try:
        pos = client.get_positions(category="linear", settleCoin="USDT")['result']['list']
        for p in pos:
            if float(p['size'])!=0:
                client.place_order(category="linear", symbol=p['symbol'], side="Sell" if p['side']=="Buy" else "Buy", orderType="Market", qty=str(p['size']))
        await u.message.reply_text("✅ SEMUA DITUTUP!")
    except Exception as e: await u.message.reply_text(f"Error: {e}")

app = ApplicationBuilder().token(TOKEN).build()
for cmd, fn in [("start", start), ("posisi", posisi), ("auto", auto), ("stopauto", stopauto), ("close", close)]:
    app.add_handler(CommandHandler(cmd, fn))
print("BYBIT BOT JALAN - NO BLOCK...")
app.run_polling()
