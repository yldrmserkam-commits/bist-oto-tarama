import json
import os
import subprocess
import sys
import warnings

# Eksik kütüphaneleri otomatik kur
for paket in ['yfinance', 'pandas', 'numpy', 'requests', 'openpyxl', 'tqdm']:
    try:
        __import__(paket)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paket])

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from tqdm import tqdm

warnings.filterwarnings('ignore')

# --- SİNYAL TAKİP DOSYASI ---
STATE_FILE = 'gonderilen_sinyaller.json'


def sinyalleri_yukle():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def sinyalleri_kaydet(state):
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f'Durum dosyası kaydedilemedi: {e}')


# --- PERİYOT AYARLARI (GÜNLÜK, HAFTALIK, AYLIK AKTİF) ---
TARAMA_YAPILACAK_PERIYOTLAR = {
    '15 Dakikalık': False,
    '30 Dakikalık': False,
    '1 Saatlik': False,
    '4 Saatlik': False,
    'Günlük': True,
    'Haftalık': True,
    'Aylık': True,
}

PERIYOT_AYARLARI = {
    '15 Dakikalık': {'interval': '15m', 'period': '1mo', 'resample_rule': None},
    '30 Dakikalık': {'interval': '30m', 'period': '2mo', 'resample_rule': None},
    '1 Saatlik': {'interval': '60m', 'period': '3mo', 'resample_rule': None},
    '4 Saatlik': {'interval': '60m', 'period': '6mo', 'resample_rule': '4h'},
    'Günlük': {'interval': '1d', 'period': '2y', 'resample_rule': None},
    'Haftalık': {'interval': '1wk', 'period': '5y', 'resample_rule': None},
    'Aylık': {'interval': '1mo', 'period': '10y', 'resample_rule': None},
}

# --- STRATEJİ VE İNDİKATÖR PARAMETRELERİ ---
CCI_PERIYOT = 20
RSI_PERIYOT = 14
EMA_TREND = 20
HACIM_ORT_PERIYOT = 10

# RSI Ayarları (Sadece 67 - 72 Arası)
RSI_MIN = 67.0
RSI_MAX = 72.0

# Filtre Aktiflikleri
HACIM_FILTRESI_AKTIF = True
TREND_FILTRESI_AKTIF = True
ICHIMOKU_FILTRESI_AKTIF = True

RISK_REWARD_TP1 = 1.5
RISK_REWARD_TP2 = 2.5
RISK_REWARD_TP3 = 4.0

# Telegram Bildirim Ayarları
TELEGRAM_AKTIF = True
TELEGRAM_BOT_TOKEN = os.environ.get(
    'TELEGRAM_BOT_TOKEN', '8911263447:AAHoyIaowzRMAD0SYrZqKQnx3BGv4Sv3dLs'
)
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '889982961')


def telegram_mesaj_gonder(mesaj):
    if not TELEGRAM_AKTIF:
        return
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mesaj,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True,
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f'Telegram mesajı gönderilemedi: {e}')


def rsi_hesapla(series, period=14):
    """Wilder's Smoothing ile RSI hesaplar"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def cci_hesapla(df, period=20):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    mad = mad.replace(0, 0.0001)
    return (tp - sma_tp) / (0.015 * mad)


def gelişmiş_strateji_kontrol(df):
    """Tüm indikatör filtrelerini kontrol eden gelişmiş strateji fonksiyonu"""
    if len(df) < max(CCI_PERIYOT + 5, 78):
        return False, {}, ''

    # --- İNDİKATÖR HESAPLAMALARI ---
    df['EMA20'] = df['Close'].ewm(span=EMA_TREND, adjust=False).mean()
    df['CCI'] = cci_hesapla(df, CCI_PERIYOT)
    df['RSI'] = rsi_hesapla(df['Close'], RSI_PERIYOT)

    # Ichimoku Kijun-sen (52 periyot)
    kijun_sen = (
        df['High'].rolling(window=52).max() + df['Low'].rolling(window=52).min()
    ) / 2

    curr_close = float(df['Close'].iloc[-1])
    curr_vol = float(df['Volume'].iloc[-1])

    if curr_vol <= 0:
        return False, {}, ''

    ema20_curr = float(df['EMA20'].iloc[-1])
    curr_cci = float(df['CCI'].iloc[-1])
    prev_cci = float(df['CCI'].iloc[-2])

    curr_rsi = float(df['RSI'].iloc[-1])
    prev_rsi = float(df['RSI'].iloc[-2])
    prev_prev_rsi = float(df['RSI'].iloc[-3])

    # 1. CCI KOŞULU (>-100 ve yukarı yönlü ivme)
    if not (curr_cci > -100 and curr_cci > prev_cci):
        return False, {}, ''

    # 2. RSI KOŞULU (Sadece 67 - 72 Arası + Yükseliş İvmesi)
    rsi_ivme_yukari = (curr_rsi > prev_rsi) and (prev_rsi > prev_prev_rsi)
    if not (RSI_MIN <= curr_rsi <= RSI_MAX and rsi_ivme_yukari):
        return False, {}, ''

    sinyal_turu = f'RSI ({int(RSI_MIN)}-{int(RSI_MAX)}) Güçlü Trend'

    # 3. TREND FİLTRESİ (EMA 20)
    if TREND_FILTRESI_AKTIF and (curr_close < ema20_curr):
        return False, {}, ''

    # 4. ICHIMOKU FİLTRESİ
    if ICHIMOKU_FILTRESI_AKTIF:
        curr_kijun = float(kijun_sen.iloc[-1])
        fiyat_kriteri = (curr_kijun < curr_close) and (
            curr_close <= curr_kijun * 1.10
        )

        if len(df) >= 78:
            gecmis_kijun = float(kijun_sen.iloc[-26])
            chikou_kijun_kosulu = (
                gecmis_kijun * 0.98 <= curr_close <= gecmis_kijun * 1.015
            )
        else:
            chikou_kijun_kosulu = True

        if not (fiyat_kriteri and chikou_kijun_kosulu):
            return False, {}, ''

    # 5. HACİM FİLTRESİ
    vol_sma = df['Volume'].rolling(window=HACIM_ORT_PERIYOT).mean()
    vol_sma_curr = float(vol_sma.iloc[-1])
    if HACIM_FILTRESI_AKTIF and (curr_vol <= vol_sma_curr):
        return False, {}, ''

    hacim_oran = round(curr_vol / (vol_sma_curr + 1e-5), 2)

    # --- ENTRY, STOP LOSS VE TARGET HESAPLARI ---
    entry_fiyat = curr_close
    son_dusuk = float(df['Low'].iloc[-5:].min())
    stop_loss = son_dusuk * 0.992  # %0.8 tolerans payı

    risk_marji = entry_fiyat - stop_loss
    if risk_marji <= 0:
        stop_loss = entry_fiyat * 0.97
        risk_marji = entry_fiyat - stop_loss

    tp1 = entry_fiyat + (risk_marji * RISK_REWARD_TP1)
    tp2 = entry_fiyat + (risk_marji * RISK_REWARD_TP2)
    tp3 = entry_fiyat + (risk_marji * RISK_REWARD_TP3)

    hesaplanan_veriler = {
        'entry': entry_fiyat,
        'sl': stop_loss,
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'rsi': curr_rsi,
        'cci': curr_cci,
        'hacim_oran': hacim_oran,
    }

    return True, hesaplanan_veriler, sinyal_turu


ham_tickers = [
    'A1CAP',
    'A1YEN',
    'AAGYO',
    'ACSEL',
    'ADEL',
    'ADESE',
    'ADGYO',
    'AEFES',
    'AFYON',
    'AGESA',
    'AGHOL',
    'AGROT',
    'AGYO',
    'AHGAZ',
    'AHSGY',
    'AKBNK',
    'AKCNS',
    'AKENR',
    'AKFGY',
    'AKFIS',
    'AKFYE',
    'AKGRT',
    'AKHAN',
    'AKMGY',
    'AKSA',
    'AKSEN',
    'AKSGY',
    'AKSUE',
    'AKYHO',
    'ALARK',
    'ALBRK',
    'ALBTN',
    'ALCAR',
    'ALCTL',
    'ALFAS',
    'ALGYO',
    'ALKA',
    'ALKIM',
    'ALKLC',
    'ALTNY',
    'ALVES',
    'ANELE',
    'ANGEN',
    'ANHYT',
    'ANSGR',
    'ARASE',
    'ARCLK',
    'ARDYZ',
    'ARENA',
    'ARSAN',
    'ARTMS',
    'ARZUM',
    'ASELS',
    'ASGYO',
    'ASTOR',
    'ASUZU',
    'ATAKP',
    'ATATP',
    'ATEKS',
    'AVGYO',
    'AYCES',
    'AYDEM',
    'AYEN',
    'AYGAZ',
    'AZTEK',
    'BAGFS',
    'BANVT',
    'BARMA',
    'BERA',
    'BFREN',
    'BIENY',
    'BIGCH',
    'BIMAS',
    'BINBN',
    'BIOEN',
    'BIZIM',
    'BOBET',
    'BORLS',
    'BORSK',
    'BOSSA',
    'BRISA',
    'BRSAN',
    'BRYAT',
    'BSOKE',
    'BTCIM',
    'BUCIM',
    'CANTE',
    'CATES',
    'CCOLA',
    'CEMAS',
    'CEMTS',
    'CIMSA',
    'CLEBI',
    'CONSE',
    'CWENE',
    'DAPGM',
    'DARDL',
    'DEVA',
    'DGATE',
    'DGGYO',
    'DGNMO',
    'DOAS',
    'DOCO',
    'DOHOL',
    'EBEBK',
    'ECILC',
    'ECZYT',
    'EDATA',
    'EGEEN',
    'EGGUB',
    'EGPRO',
    'EKGYO',
    'EKSUN',
    'ENERY',
    'ENJSA',
    'ENKAI',
    'ENPRA',
    'ENTRA',
    'ERBOS',
    'EREGL',
    'EUPWR',
    'EUREN',
    'EYGYO',
    'FROTO',
    'GARAN',
    'GEDIK',
    'GENIL',
    'GENTS',
    'GEREL',
    'GESAN',
    'GLYHO',
    'GOKNR',
    'GOLTS',
    'GOODY',
    'GOZDE',
    'GRSEL',
    'GSDHO',
    'GSRAY',
    'GUBRF',
    'GWIND',
    'HALKB',
    'HATSN',
    'HEKTS',
    'HKTM',
    'HTTBT',
    'HUNER',
    'INDES',
    'INFO',
    'INVEO',
    'INVES',
    'ISCTR',
    'ISDMR',
    'ISGYO',
    'ISMEN',
    'IZENR',
    'JANTS',
    'KCAER',
    'KCHOL',
    'KFEIN',
    'KLKIM',
    'KLSER',
    'KMPUR',
    'KONTR',
    'KONYA',
    'KORDS',
    'KOTON',
    'KOZAL',
    'KOZAA',
    'KRVGD',
    'KYDHO',
    'LIDER',
    'LMKDC',
    'LOGO',
    'MAGEN',
    'MAVI',
    'MEDTR',
    'MGROS',
    'MIATK',
    'MOBTL',
    'MOGAN',
    'MPARK',
    'MTRKS',
    'NATEN',
    'NETAS',
    'NTGAZ',
    'NTHOL',
    'NUHCM',
    'OBAMS',
    'ODAS',
    'ODINE',
    'OFSYM',
    'ONCSM',
    'ORGE',
    'OTKAR',
    'OYAKC',
    'OYYAT',
    'OZKGY',
    'PATEK',
    'PENTA',
    'PETKM',
    'PGSUS',
    'PNLSN',
    'POLHO',
    'RALYH',
    'REEDR',
    'RUBNS',
    'RYGYO',
    'RYSAS',
    'SAHOL',
    'SARKY',
    'SASA',
    'SAYAS',
    'SDTTR',
    'SISE',
    'SKBNK',
    'SMRTG',
    'SOKM',
    'TABGD',
    'TARKM',
    'TATEN',
    'TAVHL',
    'TCELL',
    'TCKRC',
    'TERA',
    'TEZOL',
    'THYAO',
    'TKFEN',
    'TKNSA',
    'TMSN',
    'TOASO',
    'TRGYO',
    'TSKB',
    'TTKOM',
    'TTRAK',
    'TUKAS',
    'TUPRS',
    'TURSG',
    'ULKER',
    'ULUUN',
    'UNLU',
    'VAKBN',
    'VESBE',
    'VESTL',
    'VRGYO',
    'YEOTK',
    'YKBNK',
    'YUNSA',
    'YYLGD',
    'ZOREN',
]

ticker_symbols = sorted(list(set([f'{t}.IS' for t in ham_tickers])))
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
            period=ayar['period'],
            interval=ayar['interval'],
            group_by='ticker',
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f'Veri indirilirken hata oluştu: {e}')
        continue

    for ticker_symbol in tqdm(ticker_symbols, desc=f'{periyot_adi} Taranıyor'):
        ticker = ticker_symbol.replace('.IS', '')
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker_symbol not in data.columns.levels[0]:
                    continue
                df = data[ticker_symbol].copy().dropna(how='all')
            else:
                df = data.copy().dropna(how='all')

            if df.empty or len(df) < 52:
                continue

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

            if ayar['resample_rule']:
                df = (
                    df.resample(ayar['resample_rule'])
                    .agg({
                        'Open': 'first',
                        'High': 'max',
                        'Low': 'min',
                        'Close': 'last',
                        'Volume': 'sum',
                    })
                    .dropna()
                )

            is_valid, veri, sinyal_turu = gelişmiş_strateji_kontrol(df)

            if is_valid:
                mum_tarihi = str(df.index[-1].strftime('%Y-%m-%d'))
                sinyal_id = f'{ticker}_{periyot_adi}_{sinyal_turu}_{df.index[-1].strftime("%Y%m%d")}'

                bilgi = {
                    'Zaman Dilimi': periyot_adi,
                    'Hisse': ticker,
                    'Sinyal Türü': sinyal_turu,
                    'Giriş (ENTRY)': round(veri['entry'], 2),
                    'RSI': round(veri['rsi'], 2),
                    'CCI': round(veri['cci'], 2),
                    'Hacim/Ort': veri['hacim_oran'],
                    'Stop (SL)': round(veri['sl'], 2),
                    'TP1': round(veri['tp1'], 2),
                    'TP2': round(veri['tp2'], 2),
                    'TP3': round(veri['tp3'], 2),
                    'Tarih': mum_tarihi,
                }
                results.append(bilgi)

                if sinyal_id not in gonderilenler:
                    tv_link = f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
                    msg = (
                        f'🔥 *BIST GÜÇLÜ TREND SİNYALİ*\n\n'
                        f'📌 *Hisse:* `{ticker}` | *Periyot:* {periyot_adi}\n'
                        f'📈 *RSI:* `{veri["rsi"]:.2f}` (67-72 Aralığında İvmede)\n'
                        f'📊 *CCI:* `{veri["cci"]:.2f}` | *Hacim:* `{veri["hacim_oran"]}x` Katı\n\n'
                        f'🔵 *ENTRY:* `{veri["entry"]:.2f}`\n'
                        f'🔴 *SL (Stop):* `{veri["sl"]:.2f}`\n\n'
                        f'🎯 *TP1:* `{veri["tp1"]:.2f}`\n'
                        f'🎯 *TP2:* `{veri["tp2"]:.2f}`\n'
                        f'🎯 *TP3:* `{veri["tp3"]:.2f}`\n\n'
                        f'🔗 [TradingView Grafiği Aç]({tv_link})'
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
    df_results = df_results.sort_values(
        by=['Zaman Dilimi', 'Hisse']
    ).reset_index(drop=True)
    excel_filename = 'BIST_Gundelik_Tarama_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(
        f'\n✅ Tarama tamamlandı! Toplam {len(results)} hisse filtrelere uydu ve kaydedildi.'
    )
else:
    print('\n⚠️ Kriterlere uyan hisse bulunamadı.')
