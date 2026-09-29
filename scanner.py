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
    """TradingView WaveTrend (VT Cross) Hesaplaması"""
    ap = (df['High'] + df['Low'] + df['Close']) / 3
    esa = ap.ewm(span=n1, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = ci.ewm(span=n2, adjust=False).mean()
    wt2 = wt1.rolling(window=4).mean()
    return wt1, wt2


# --- GÜNCELLENMİŞ TELEGRAM AYARLARI ---
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

print(
    '🔍 Büyük Trend Yükselişte + Kısa Vadeli Dip Dönüşü (VT Cross & RSI) Taraması Başlatılıyor...'
)

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
        period='2y',
        interval='1d',
        group_by='ticker',
        progress=False,
        threads=True,
    )
except Exception as e:
    print(f'Veri çekilirken hata oluştu: {e}')
    sys.exit()

for ticker_symbol in tqdm(ticker_symbols, desc='Düzeltme Bitişleri Taranıyor'):
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

        if df_h1.empty or df_d1.empty or len(df_h1) < 40 or len(df_d1) < 100:
            continue

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

        if len(df_weekly) < 15 or len(df_monthly) < 10:
            continue

        # 1. MAKRO TREND KONTROLÜ (AYLIK VE HAFTALIK YÜKSELİŞ)
        df_monthly['EMA20'] = (
            df_monthly['Close'].ewm(span=20, adjust=False).mean()
        )
        df_weekly['EMA20'] = (
            df_weekly['Close'].ewm(span=20, adjust=False).mean()
        )

        aylik_yukseliste = float(df_monthly['Close'].iloc[-1]) > float(
            df_monthly['EMA20'].iloc[-1]
        )
        haftalik_yukseliste = float(df_weekly['Close'].iloc[-1]) > float(
            df_weekly['EMA20'].iloc[-1]
        )

        if not (aylik_yukseliste and haftalik_yukseliste):
            continue

        # 2. KISA VADE DİP VE DÖNÜŞ SİNYALİ KONTROLÜ (1H veya 4H)
        for df in [df_h1, df_h4]:
            df['RSI'] = rsi_hesapla(df['Close'])
            df['WT1'], df['WT2'] = wavetrend_hesapla(df)

        def dip_donus_var_mi(df):
            rsi_curr = float(df['RSI'].iloc[-1])
            rsi_prev = float(df['RSI'].iloc[-2])

            wt1_curr = float(df['WT1'].iloc[-1])
            wt2_curr = float(df['WT2'].iloc[-1])
            wt1_prev = float(df['WT1'].iloc[-2])
            wt2_prev = float(df['WT2'].iloc[-2])

            # RSI 30-34 Bandında Yukarı Kesişim / İvme
            rsi_dip_donus = (rsi_prev <= 34) and (rsi_curr > rsi_prev)

            # WaveTrend (VT Cross) Kesişimi veya Yukarı İvme
            vt_al_sinyali = (wt1_prev <= wt2_prev and wt1_curr > wt2_curr) or (
                wt1_curr > wt2_curr and wt1_curr > wt1_prev
            )

            return (
                rsi_dip_donus
                and vt_al_sinyali,
                rsi_curr,
                wt1_curr,
                wt2_curr,
            )

        h1_sinyal, h1_rsi, h1_wt1, h1_wt2 = dip_donus_var_mi(df_h1)
        h4_sinyal, h4_rsi, h4_wt1, h4_wt2 = dip_donus_var_mi(df_h4)

        if not (h1_sinyal or h4_sinyal):
            continue

        periyot_label = '1 Saatlik' if h1_sinyal else '4 Saatlik'
        aktif_rsi = h1_rsi if h1_sinyal else h4_rsi

        son_fiyat = float(df_h1['Close'].iloc[-1])
        mum_zaman_str = pd.to_datetime(df_h1.index[-1]).strftime('%Y%m%d_%H%M')
        sinyal_id = f'{ticker}_DIP_DONUS_{mum_zaman_str}'

        bilgi = {
            'Hisse': ticker,
            'Son Fiyat': round(son_fiyat, 2),
            'Sinyal Periyodu': periyot_label,
            'RSI': round(aktif_rsi, 2),
            'WaveTrend WT1': round(h1_wt1 if h1_sinyal else h4_wt1, 2),
            'WaveTrend WT2': round(h1_wt2 if h1_sinyal else h4_wt2, 2),
            'Aylık & Haftalık': 'Yükselişte 🟢',
            'Tarih': str(df_h1.index[-1]),
        }
        results.append(bilgi)

        if sinyal_id not in gonderilenler:
            tv_link = f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
            msg = (
                f'🎯 *BİST DÜZELTME BİTİŞİ & DİP DÖNÜŞ SİNYALİ*\n'
                f'*Hisse:* `{ticker}`\n'
                f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n\n'
                f'🌳 *Ana Trend:* Aylık & Haftalık Yükselişte 🟢\n'
                f'⚡ *Sinyal Periyodu:* {periyot_label}\n'
                f'📊 *RSI (Dip Dönüşü):* `{aktif_rsi:.1f}` (30-34 Bandı Kesişimi)\n'
                f'🌊 *VT Cross:* Alım İvmesi Teyit Edildi (WT1 > WT2)\n\n'
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
    excel_filename = 'BIST_Dip_Donus_VT_RSI_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(
        f"\n✅ Tarama tamamlandı! Toplam {len(results)} hissede dip dönüş sinyali tespit edildi."
    )
else:
    print(
        '\n⚠️ Aylık/Haftalık yükselişte olup saatlik/4 saatlikte dip dönüşü veren hisse bulunamadı.'
    )
