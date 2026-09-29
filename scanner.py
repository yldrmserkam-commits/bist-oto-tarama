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

STATE_FILE = 'gonderilen_wavetrend_rsi_sinyalleri.json'

# --- PERİYOT VE FİLTRE AYARLARI ---
TARAMA_1SAATLIK = True  # 1 Saatlik Tarama
TARAMA_4SAATLIK = True  # 4 Saatlik Tarama


def sinyalleri_yukle():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                bugun = datetime.now().strftime('%Y-%m-%d')
                if data.get('_tarih') != bugun:
                    return {'_tarih': bugun}
                return data
        except Exception:
            return {'_tarih': datetime.now().strftime('%Y-%m-%d')}
    return {'_tarih': datetime.now().strftime('%Y-%m-%d')}


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
    wt2 = wt1.rolling(window=4).mean()
    return wt1, wt2


# --- TELEGRAM AYARLARI ---
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

print('🔍 Büyük Trend Yükselişte + Kısa Vadeli Dip Dönüş Taraması...')

try:
    data_1h = yf.download(
        tickers=ticker_symbols,
        period='60d',
        interval='60m',
        group_by='ticker',
        progress=False,
        threads=True,
    )
    data_1d = yf.download(
        tickers=ticker_symbols,
        period='10y',
        interval='1d',
        group_by='ticker',
        progress=False,
        threads=True,
    )
except Exception as e:
    print(f'Veri çekilirken hata oluştu: {e}')
    sys.exit()

for ticker_symbol in tqdm(ticker_symbols, desc='Hisseler Taranıyor'):
    ticker = ticker_symbol.replace('.IS', '')
    try:

        def df_get(data_source, symbol):
            if isinstance(data_source.columns, pd.MultiIndex):
                if symbol in data_source.columns.levels[0]:
                    return data_source[symbol].copy()
                elif symbol in data_source.columns.levels[1]:
                    return data_source.xs(
                        symbol, axis=1, level=1, drop_level=True
                    ).copy()
                return pd.DataFrame()
            return data_source.copy()

        df_h1 = df_get(data_1h, ticker_symbol).dropna(how='all')
        df_d1 = df_get(data_1d, ticker_symbol).dropna(how='all')

        if df_h1.empty or df_d1.empty or len(df_h1) < 30 or len(df_d1) < 60:
            continue

        # 4 Saatlik Periyot Oluştur
        df_h4 = (
            df_h1.resample('4h', origin='start')
            .agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum',
            })
            .dropna()
        )

        # Haftalık ve Aylık Grafikler (Ana Trend Tespiti İçin)
        df_weekly = (
            df_d1.resample('1W-FRI')
            .agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum',
            })
            .dropna()
        )

        df_monthly = (
            df_d1.resample('1ME')
            .agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum',
            })
            .dropna()
        )

        # 1. BÜYÜK RESİM / MAKRORTREND KONTROLÜ (Haftalık & Aylık EMA)
        # Yeterli veri varsa EMA100, az veri varsa EMA50 kontrol edilir.
        p_w = 100 if len(df_weekly) >= 100 else 50
        p_m = 50 if len(df_monthly) >= 50 else 20

        df_weekly['EMA'] = (
            df_weekly['Close'].ewm(span=p_w, adjust=False).mean()
        )
        df_monthly['EMA'] = (
            df_monthly['Close'].ewm(span=p_m, adjust=False).mean()
        )

        haftalik_ok = (
            df_weekly['EMA'].isna().iloc[-1]
            or float(df_weekly['Close'].iloc[-1])
            >= float(df_weekly['EMA'].iloc[-1])
        )
        aylik_ok = (
            df_monthly['EMA'].isna().iloc[-1]
            or float(df_monthly['Close'].iloc[-1])
            >= float(df_monthly['EMA'].iloc[-1])
        )

        # Ana trend yükselişte değilse hisseyi geç
        if not (haftalik_ok and aylik_ok):
            continue

        # 2. KISA VADEDE DİPTEN DÖNÜŞ KONTROLÜ (1H ve 4H)
        def dip_donus_var_mi(df):
            df['RSI'] = rsi_hesapla(df['Close'])
            df['WT1'], df['WT2'] = wavetrend_hesapla(df)

            if len(df) < 5:
                return False, 0, 0, 0

            rsi_curr = float(df['RSI'].iloc[-1])
            rsi_prev = float(df['RSI'].iloc[-2])

            wt1_curr = float(df['WT1'].iloc[-1])
            wt2_curr = float(df['WT2'].iloc[-1])
            wt1_prev = float(df['WT1'].iloc[-2])
            wt2_prev = float(df['WT2'].iloc[-2])

            # A) RSI KOŞULU: 28 - 34 Arasında OLACAK ve Yönü YUKARI bakacak
            rsi_tamam = (28 <= rsi_curr <= 34) and (rsi_curr > rsi_prev)

            # B) WAVETREND (VT) DİPTEN DÖNÜŞ KOŞULU:
            # - WT1, WT2'yi yukarı kesmiş veya üstünde duruyor
            # - WT1'in kendi eğimi yukarı bakıyor (WT1_curr > WT1_prev)
            # - WT1 dip/düzeltme bölgesinde (Örn: WT1 < 15, tepe noktası olmamalı)
            vt_kesisim = (
                (wt1_prev <= wt2_prev and wt1_curr > wt2_curr)
                or (wt1_curr > wt2_curr)
            )
            vt_egim_yukari = wt1_curr > wt1_prev
            vt_dip_bolgesinde = wt1_curr <= 20  # Dip bölgesinden dönüş

            vt_tamam = vt_kesisim and vt_egim_yukari and vt_dip_bolgesinde

            return (
                rsi_tamam and vt_tamam,
                rsi_curr,
                wt1_curr,
                wt2_curr,
            )

        periyotlar = []
        if TARAMA_1SAATLIK:
            periyotlar.append(('1 Saatlik', df_h1))
        if TARAMA_4SAATLIK:
            periyotlar.append(('4 Saatlik', df_h4))

        for periyot_adi, df_periyot in periyotlar:
            sinyal_var, rsi_val, wt1_val, wt2_val = dip_donus_var_mi(df_periyot)

            if sinyal_var:
                son_fiyat = float(df_periyot['Close'].iloc[-1])
                mum_zaman_str = pd.to_datetime(df_periyot.index[-1]).strftime(
                    '%Y%m%d_%H%M'
                )
                periyot_kod = '1H' if periyot_adi == '1 Saatlik' else '4H'
                sinyal_id = f'{ticker}_{periyot_kod}_DIP_{mum_zaman_str}'

                bilgi = {
                    'Hisse': ticker,
                    'Son Fiyat': round(son_fiyat, 2),
                    'Sinyal Periyodu': periyot_adi,
                    'RSI': round(rsi_val, 2),
                    'WaveTrend WT1': round(wt1_val, 2),
                    'WaveTrend WT2': round(wt2_val, 2),
                    'Ana Trend': 'Haftalık / Aylık Yükselişte 🟢',
                    'Tarih': str(df_periyot.index[-1]),
                }
                results.append(bilgi)

                if sinyal_id not in gonderilenler:
                    tv_link = (
                        f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
                    )
                    msg = (
                        f'🚀 *BİST KISA VADELİ DİPTEN DÖNÜŞ SİNYALİ*\n'
                        f'*Hisse:* `{ticker}`\n'
                        f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n\n'
                        f'🌳 *Ana Trend:* Haftalık/Aylık Trend Pozitif 🟢\n'
                        f'⚡ *Sinyal Periyodu:* `{periyot_adi}`\n'
                        f'📊 *RSI:* `{rsi_val:.1f}` (28-34 Bandında & Yukarı Eğilimli)\n'
                        f'🌊 *WaveTrend:* Dip Bölgesinden Yukarı Dönüş Başladı ↗️\n\n'
                        f'📈 [TradingView Grafiği Aç]({tv_link})'
                    )
                    telegram_mesaj_gonder(msg)
                    gonderilenler[sinyal_id] = True
                    time.sleep(0.02)

    except Exception:
        pass

sinyalleri_kaydet(gonderilenler)

if results:
    df_results = pd.DataFrame(results)
    excel_filename = 'BIST_TrendIci_DipDonus_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(
        f'\n✅ Tarama tamamlandı! Toplam {len(results)} adet dipten dönüş sinyali bulundu.'
    )
else:
    print(
        '\n⚠️ Şu anda bu kriterleri (Ana trend yukarı + 1H/4H RSI 28-34 arası eğim yukarı + VT dipten dönüş) karşılayan hisse bulunamadı.'
    )
