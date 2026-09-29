import json
import os
import subprocess
import sys
import time
import warnings
from datetime import datetime

# Eksik kütüphaneleri otomatik yükle
for paket in ['yfinance', 'pandas', 'numpy', 'requests', 'openpyxl', 'tqdm']:
    try:
        __import__(paket)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paket])

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm
import yfinance as yf

warnings.filterwarnings('ignore')

STATE_FILE = 'gonderilen_wavetrend_rsi_hacim_sinyalleri.json'

TARAMA_1SAATLIK = True
TARAMA_4SAATLIK = True

# --- FİLTRE PARAMETRELERİ ---
HACIM_KATLAMA_ORANI = 1.15  # Son mumda en az %15 hacim artışı
RSI_TAVAN = 34.0  # RSI kesinlikle 34'ün altında olacak (30 ve altı dahil)


def sinyalleri_yukle():
    bugun = datetime.now().strftime('%Y-%m-%d')
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('_tarih') != bugun:
                    return {'_tarih': bugun}
                return data
        except Exception:
            return {'_tarih': bugun}
    return {'_tarih': bugun}


def sinyalleri_kaydet(state):
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f'Durum dosyası kaydedilemedi: {e}')


def rsi_hesapla(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def wavetrend_hesapla(df, n1=10, n2=21):
    ap = (df['High'] + df['Low'] + df['Close']) / 3
    esa = ap.ewm(span=n1, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = ci.ewm(span=n2, adjust=False).mean()
    wt2 = wt1.rolling(window=4, min_periods=1).mean()
    return wt1, wt2


TELEGRAM_AKTIF = True
TELEGRAM_BOT_TOKEN = os.getenv(
    'TELEGRAM_BOT_TOKEN', '8911263447:AAHoyIaowzRMAD0SYrZqKQnx3BGv4Sv3dLs'
)
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '889982961')


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


ham_tickers = [
    'A1CAP.IS',
    'ACSEL.IS',
    'ADEL.IS',
    'AEFES.IS',
    'AGHOL.IS',
    'AKBNK.IS',
    'AKSA.IS',
    'AKSEN.IS',
    'ALARK.IS',
    'ALBRK.IS',
    'ARCLK.IS',
    'ASELS.IS',
    'ASTOR.IS',
    'BIMAS.IS',
    'BRSAN.IS',
    'CCOLA.IS',
    'CIMSA.IS',
    'DOAS.IS',
    'DOHOL.IS',
    'EKGYO.IS',
    'ENJSA.IS',
    'ENKAI.IS',
    'EREGL.IS',
    'FROTO.IS',
    'GARAN.IS',
    'GESAN.IS',
    'GUBRF.IS',
    'HALKB.IS',
    'HEKTS.IS',
    'ISCTR.IS',
    'KCHOL.IS',
    'KONTR.IS',
    'KORDS.IS',
    'KRDMD.IS',
    'MAVI.IS',
    'MGROS.IS',
    'MIATK.IS',
    'ODAS.IS',
    'OTKAR.IS',
    'OYAKC.IS',
    'PETKM.IS',
    'PGSUS.IS',
    'SAHOL.IS',
    'SASA.IS',
    'SISE.IS',
    'SOKM.IS',
    'TCELL.IS',
    'THYAO.IS',
    'TOASO.IS',
    'TSKB.IS',
    'TTKOM.IS',
    'TUPRS.IS',
    'VAKBN.IS',
    'VESTL.IS',
    'YKBNK.IS',
]

ticker_symbols = sorted(list(set(ham_tickers)))
results = []
gonderilenler = sinyalleri_yukle()

print('🔍 RSI < 34 Dip + Hacimli Son Mum Taraması Başlatılıyor...')

try:
    data_1h = yf.download(
        tickers=ticker_symbols,
        period='60d',
        interval='60m',
        group_by='ticker',
        progress=False,
    )
except Exception as e:
    print(f'Veri çekilirken hata oluştu: {e}')
    sys.exit()

for ticker_symbol in tqdm(ticker_symbols, desc='Hisseler Taranıyor'):
    ticker = ticker_symbol.replace('.IS', '')
    try:

        def df_get(data_source, symbol):
            try:
                df = data_source[symbol].copy()
                if (
                    isinstance(df.index, pd.DatetimeIndex)
                    and df.index.tz is not None
                ):
                    df.index = df.index.tz_localize(None)
                return df
            except KeyError:
                return pd.DataFrame()

        df_h1 = df_get(data_1h, ticker_symbol).dropna(how='all')

        if df_h1.empty or len(df_h1) < 30:
            continue

        # 4 Saatlik Periyot
        df_h4 = (
            df_h1.resample('4h')
            .agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum',
            })
            .dropna()
        )

        def dip_hacimli_donus_var_mi(df):
            df['RSI'] = rsi_hesapla(df['Close'])
            df['WT1'], df['WT2'] = wavetrend_hesapla(df)
            df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()

            if len(df) < 20:
                return False, 0, 0, 0, 0

            rsi_curr = float(df['RSI'].iloc[-1])
            rsi_prev = float(df['RSI'].iloc[-2])

            wt1_curr = float(df['WT1'].iloc[-1])
            wt2_curr = float(df['WT2'].iloc[-1])
            wt1_prev = float(df['WT1'].iloc[-2])

            vol_curr = float(df['Volume'].iloc[-1])
            vol_sma = float(df['Vol_SMA20'].iloc[-1])

            open_curr = float(df['Open'].iloc[-1])
            close_curr = float(df['Close'].iloc[-1])

            if (
                np.isnan(rsi_curr)
                or np.isnan(wt1_curr)
                or np.isnan(vol_sma)
                or vol_sma == 0
            ):
                return False, 0, 0, 0, 0

            # 1. RSI KOŞULU: RSI kesinlikle 34'ün altında ve yukarı kıvrılmış olmalı
            rsi_tamam = (rsi_curr < RSI_TAVAN) and (rsi_curr > rsi_prev)

            # 2. WAVETREND DIP KOŞULU: WaveTrend dip bölgesinde (<= 10) ve yönü yukarı
            vt_tamam = (wt1_curr <= 10) and (wt1_curr > wt1_prev)

            # 3. HACİMLİ SON MUM KOŞULU:
            # - Son mum yeşil olmalı (kapanış > açılış)
            # - Son mum hacmi 20 barlık hacim ortalamasının üzerinde olmalı
            vol_ratio = vol_curr / vol_sma
            hacim_tamam = (vol_ratio >= HACIM_KATLAMA_ORANI) and (
                close_curr > open_curr
            )

            sinyal = rsi_tamam and vt_tamam and hacim_tamam

            return sinyal, rsi_curr, wt1_curr, wt2_curr, vol_ratio

        periyotlar = []
        if TARAMA_1SAATLIK:
            periyotlar.append(('1 Saatlik', df_h1))
        if TARAMA_4SAATLIK:
            periyotlar.append(('4 Saatlik', df_h4))

        for periyot_adi, df_periyot in periyotlar:
            sinyal_var, rsi_val, wt1_val, wt2_val, vol_ratio = (
                dip_hacimli_donus_var_mi(df_periyot)
            )

            if sinyal_var:
                son_fiyat = float(df_periyot['Close'].iloc[-1])
                mum_zaman = pd.to_datetime(df_periyot.index[-1])
                mum_zaman_str = mum_zaman.strftime('%Y%m%d_%H%M')
                periyot_kod = '1H' if periyot_adi == '1 Saatlik' else '4H'
                sinyal_id = (
                    f'{ticker}_{periyot_kod}_RSI34DIP_{mum_zaman_str}'
                )

                bilgi = {
                    'Hisse': ticker,
                    'Son Fiyat': round(son_fiyat, 2),
                    'Sinyal Periyodu': periyot_adi,
                    'Hacim Katı (xSMA20)': round(vol_ratio, 2),
                    'RSI': round(rsi_val, 2),
                    'WaveTrend WT1': round(wt1_val, 2),
                    'WaveTrend WT2': round(wt2_val, 2),
                    'Tarih': str(mum_zaman),
                }
                results.append(bilgi)

                if sinyal_id not in gonderilenler:
                    tv_link = (
                        f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
                    )
                    msg = (
                        f'🎯 *BİST DIPTE HACİMLİ DÖNÜŞ SİNYALİ*\n'
                        f'*Hisse:* `{ticker}`\n'
                        f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n\n'
                        f'📉 *RSI:* `{rsi_val:.1f}` (< 34 Aşırı Dipte & Yönü Yukarı) 📈\n'
                        f'💥 *Son Mum Hacmi:* Ortalamanın `{vol_ratio:.2f}x` Katı (Yeşil Mum)\n'
                        f'⚡ *Periyot:* `{periyot_adi}`\n'
                        f'🌊 *WaveTrend:* `{wt1_val:.1f}` (Dip Dönüşü)\n\n'
                        f'🔗 [TradingView Grafiği Aç]({tv_link})'
                    )
                    telegram_mesaj_gonder(msg)
                    gonderilenler[sinyal_id] = True
                    time.sleep(0.02)

    except Exception:
        pass

sinyalleri_kaydet(gonderilenler)

if results:
    df_results = pd.DataFrame(results)
    excel_filename = 'BIST_Dipte_Hacimli_Donus_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(
        f'\n✅ Tarama tamamlandı! Toplam {len(results)} adet dipte hacimli dönüş sinyali bulundu.'
    )
else:
    print(
        '\n⚠️ Kriterleri karşılayan hisse bulunamadı (RSI < 34, WaveTrend Dipte ve Son Mum Hacimli Yeşil).'
    )
