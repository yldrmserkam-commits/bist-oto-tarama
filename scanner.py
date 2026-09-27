# Gerekli kütüphanelerin yüklenmesi
!pip install yfinance pandas openpyxl requests tqdm -q

import os
import json
import warnings
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from tqdm import tqdm

warnings.filterwarnings('ignore')

# --- SİNYAL TAKİP DOSYASI AYARI (GitHub / Bulut İçin) ---
STATE_FILE = "gonderilen_sinyaller.json"

def sinyalleri_yukle():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def sinyalleri_kaydet(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Durum dosyası kaydedilemedi: {e}")

# --- PERİYOT AYARLARI (TÜMÜ AKTİF) ---
TARAMA_YAPILACAK_PERIYOTLAR = {
    "30 Dakikalık": True,
    "1 Saatlik": True,
    "4 Saatlik": True,
    "Günlük": True,
    "Haftalık": True,
    "Aylık": True,        
}

# --- STRATEJİ AYARLARI (RSI 68-75 & YUKARI İVME - HACİMSİZ) ---
RSI_PERIOD = 14
RSI_MIN = 68             # Alt sınır
RSI_MAX = 75             # Üst sınır

# Risk / Ödül Seviyeleri
RISK_REWARD_TP1 = 1.5
RISK_REWARD_TP2 = 2.5
RISK_REWARD_TP3 = 3.5

# Telegram Bildirim Ayarları
TELEGRAM_AKTIF = True
TELEGRAM_BOT_TOKEN = "8911263447:AAHoyIaowzRMAD0SYrZqKQnx3BGv4Sv3dLs"
TELEGRAM_CHAT_ID = "889982961"

def telegram_mesaj_gonder(mesaj):
    if not TELEGRAM_AKTIF:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mesaj,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def rsi_hesapla(series, period=14):
    """Wilder's Smoothing ile RSI hesaplar"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def guclu_yukselis_kontrol(df):
    min_len = 36  
    if len(df) < min_len:
        return False, 0, 0, 0, 0, 0, 0, 0

    df['RSI'] = rsi_hesapla(df['Close'], period=RSI_PERIOD)
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()

    if len(df) >= 50:
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        ema50_check = df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]
    else:
        ema50_check = True

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    close_val = curr['Close']
    high_val = curr['High']
    low_val = curr['Low']
    curr_rsi = curr['RSI']
    prev_rsi = prev['RSI']
    curr_vol = curr['Volume']
    ema20 = curr['EMA20']

    if pd.isna(curr_rsi) or pd.isna(prev_rsi):
        return False, 0, 0, 0, 0, 0, 0, 0
    
    if not (RSI_MIN <= curr_rsi <= RSI_MAX and curr_rsi > prev_rsi):
        return False, 0, 0, 0, 0, 0, 0, 0

    if not (close_val > ema20 and ema50_check):
        return False, 0, 0, 0, 0, 0, 0, 0

    candle_range = high_val - low_val
    if candle_range > 0:
        close_position = (close_val - low_val) / candle_range
        if close_position < 0.65:
            return False, 0, 0, 0, 0, 0, 0, 0

    lookback = min(15, len(df))
    sl_level = float(np.min(df['Low'].values[-lookback:]))
    risk = close_val - sl_level

    if risk > 0:
        tp1 = close_val + (risk * RISK_REWARD_TP1)
        tp2 = close_val + (risk * RISK_REWARD_TP2)
        tp3 = close_val + (risk * RISK_REWARD_TP3)
        return True, close_val, sl_level, tp1, tp2, tp3, curr_rsi, curr_vol

    return False, 0, 0, 0, 0, 0, 0, 0

PERIYOT_AYARLARI = {
    "30 Dakikalık": {"interval": "30m", "period": "2mo", "resample_rule": None},
    "1 Saatlik": {"interval": "60m", "period": "3mo", "resample_rule": None},
    "4 Saatlik": {"interval": "60m", "period": "6mo", "resample_rule": "4h"},
    "Günlük": {"interval": "1d", "period": "2y", "resample_rule": None},
    "Haftalık": {"interval": "1wk", "period": "5y", "resample_rule": None},
    "Aylık": {"interval": "1mo", "period": "10y", "resample_rule": None},
}

ham_tickers = [
    'A1CAP', 'A1YEN', 'AAGYO', 'ACSEL', 'ADEL', 'ADESE', 'ADGYO',
    'AEFES', 'AFYON', 'AGESA', 'AGHOL', 'AGROT', 'AGYO', 'AHGAZ',
    'AHSGY', 'AKBNK', 'AKCNS', 'AKENR', 'AKFGY', 'AKFIS', 'AKFYE',
    'AKGRT', 'AKHAN', 'AKMGY', 'AKSA', 'AKSEN', 'AKSGY', 'AKSUE',
    'AKYHO', 'ALARK', 'ALBRK', 'ALBTN', 'ALCAR', 'ALCTL', 'ALFAS',
    'ALGYO', 'ALKA', 'ALKIM', 'ALKLC', 'ALTNY', 'ALVES', 'ANELE',
    'ANGEN', 'ANHYT', 'ANSGR', 'ARASE', 'ARCLK', 'ARDYZ', 'ARENA',
    'ARSAN', 'ARTMS', 'ARZUM', 'ASELS', 'ASGYO', 'ASTOR', 'ASUZU',
    'ATAKP', 'ATATP', 'ATEKS', 'AVGYO', 'AYCES', 'AYDEM', 'AYEN',
    'AYGAZ', 'AZTEK', 'BAGFS', 'BANVT', 'BARMA', 'BERA', 'BFREN',
    'BIENY', 'BIGCH', 'BIMAS', 'BINBN', 'BIOEN', 'BIZIM', 'BOBET',
    'BORLS', 'BORSK', 'BOSSA', 'BRISA', 'BRSAN', 'BRYAT', 'BSOKE',
    'BTCIM', 'BUCIM', 'CANTE', 'CATES', 'CCOLA', 'CEMAS', 'CEMTS',
    'CIMSA', 'CLEBI', 'CONSE', 'CWENE', 'DAPGM', 'DARDL', 'DEVA',
    'DGATE', 'DGGYO', 'DGNMO', 'DOAS', 'DOCO', 'DOHOL', 'EBEBK',
    'ECILC', 'ECZYT', 'EDATA', 'EGEEN', 'EGGUB', 'EGPRO', 'EKGYO',
    'EKSUN', 'ENERY', 'ENJSA', 'ENKAI', 'ENPRA', 'ENTRA', 'ERBOS',
    'EREGL', 'EUPWR', 'EUREN', 'EYGYO', 'FROTO', 'GARAN', 'GEDIK',
    'GENIL', 'GENTS', 'GEREL', 'GESAN', 'GLYHO', 'GOKNR', 'GOLTS',
    'GOODY', 'GOZDE', 'GRSEL', 'GSDHO', 'GSRAY', 'GUBRF', 'GWIND',
    'HALKB', 'HATSN', 'HEKTS', 'HKTM', 'HTTBT', 'HUNER', 'INDES',
    'INFO', 'INVEO', 'INVES', 'ISCTR', 'ISDMR', 'ISGYO', 'ISMEN',
    'IZENR', 'JANTS', 'KCAER', 'KCHOL', 'KFEIN', 'KLKIM', 'KLSER',
    'KMPUR', 'KONTR', 'KONYA', 'KORDS', 'KOTON', 'KOZAL', 'KOZAA',
    'KRVGD', 'KYDHO', 'LIDER', 'LMKDC', 'LOGO', 'MAGEN', 'MAVI',
    'MEDTR', 'MGROS', 'MIATK', 'MOBTL', 'MOGAN', 'MPARK', 'MTRKS',
    'NATEN', 'NETAS', 'NTGAZ', 'NTHOL', 'NUHCM', 'OBAMS', 'ODAS',
    'ODINE', 'OFSYM', 'ONCSM', 'ORGE', 'OTKAR', 'OYAKC', 'OYYAT',
    'OZKGY', 'PATEK', 'PENTA', 'PETKM', 'PGSUS', 'PNLSN', 'POLHO',
    'RALYH', 'REEDR', 'RUBNS', 'RYGYO', 'RYSAS', 'SAHOL', 'SARKY',
    'SASA', 'SAYAS', 'SDTTR', 'SISE', 'SKBNK', 'SMRTG', 'SOKM',
    'TABGD', 'TARKM', 'TATEN', 'TAVHL', 'TCELL', 'TCKRC', 'TERA',
    'TEZOL', 'THYAO', 'TKFEN', 'TKNSA', 'TMSN', 'TOASO', 'TRGYO',
    'TSKB', 'TTKOM', 'TTRAK', 'TUKAS', 'TUPRS', 'TURSG', 'ULKER',
    'ULUUN', 'UNLU', 'VAKBN', 'VESBE', 'VESTL', 'VRGYO', 'YEOTK',
    'YKBNK', 'YUNSA', 'YYLGD', 'ZOREN'
]

ticker_symbols = sorted(list(set([f"{t}.IS" for t in ham_tickers])))
results = []
gonderilenler = sinyalleri_yukle()

# Taramayı Başlat
for periyot_adi, aktif_mi in TARAMA_YAPILACAK_PERIYOTLAR.items():
    if not aktif_mi:
        continue

    print(f"\n⚡ '{periyot_adi}' periyodu taranıyor...")
    ayar = PERIYOT_AYARLARI[periyot_adi]

    try:
        data = yf.download(
            tickers=ticker_symbols,
            period=ayar["period"],
            interval=ayar["interval"],
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"Veri indirilirken hata oluştu: {e}")
        continue

    for ticker_symbol in tqdm(ticker_symbols, desc=f"{periyot_adi} Taranıyor"):
        ticker = ticker_symbol.replace('.IS', '')
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker_symbol not in data.columns.levels[0]:
                    continue
                df = data[ticker_symbol].copy().dropna(how="all")
            else:
                df = data.copy().dropna(how="all")

            if df.empty or len(df) < 35:
                continue

            if ayar["resample_rule"]:
                df = df.resample(ayar["resample_rule"]).agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()

            is_valid, entry, sl, tp1, tp2, tp3, rsi_val, _ = guclu_yukselis_kontrol(df)

            if is_valid:
                mum_tarihi = str(df.index[-1].strftime('%Y-%m-%d'))
                sinyal_id = f"{ticker}_{periyot_adi}_{mum_tarihi}"

                bilgi = {
                    'Zaman Dilimi': periyot_adi,
                    'Hisse': ticker,
                    'Giriş (ENTRY)': round(entry, 2),
                    'RSI (14)': round(rsi_val, 2),
                    'Stop (SL)': round(sl, 2),
                    'TP1': round(tp1, 2),
                    'TP2': round(tp2, 2),
                    'TP3': round(tp3, 2),
                    'Tarih': mum_tarihi
                }
                results.append(bilgi)

                if sinyal_id not in gonderilenler:
                    tv_link = f"https://www.tradingview.com/chart/?symbol=BIST:{ticker}"
                    msg = (
                        f"🔥 *YENİ RSI KESİŞİM SİNYALİ*\n\n"
                        f"📌 *Hisse:* `{ticker}`\n"
                        f"⏱ *Periyot:* {periyot_adi}\n"
                        f"📈 *RSI:* `{rsi_val:.2f}` (İvmede)\n\n"
                        f"🔹 *ENTRY:* `{entry:.2f}`\n"
                        f"🔻 *SL:* `{sl:.2f}`\n\n"
                        f"🎯 *TP1:* `{tp1:.2f}`\n"
                        f"🎯 *TP2:* `{tp2:.2f}`\n"
                        f"🎯 *TP3:* `{tp3:.2f}`\n\n"
                        f"[TradingView Grafiği Aç]({tv_link})"
                    )
                    telegram_mesaj_gonder(msg)
                    gonderilenler[sinyal_id] = True

        except Exception:
            pass

# Takip dosyasını güncelle
sinyalleri_kaydet(gonderilenler)

# Excel Çıktısı
if results:
    df_results = pd.DataFrame(results)
    excel_filename = "RSI_Tarama_Sonuclari.xlsx"
    df_results.to_excel(excel_filename, index=False)
    print(f"\n✅ Tarama tamamlandı! Toplam {len(results)} hisse bulundu.")
else:
    print("\n⚠️ Kriterlere uyan hisse bulunamadı.")
