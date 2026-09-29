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

STATE_FILE = 'gonderilen_smi_eksi40_sinyalleri.json'

# --- PERİYOT AYARLARI ---
TARAMA_30DK = True
TARAMA_1SAATLIK = True
TARAMA_4SAATLIK = True

# --- STOCHASTIC MOMENTUM INDEX (SMI) PARAMETRELERİ ---
SMI_K_PERIYOT = 10  # %K Periyodu (Standart: 10)
SMI_D_PERIYOT = 3  # %D Yumuşatma (Standart: 3)
SMI_YUMUSATMA_1 = 3  # İlk EMA Periyodu
SMI_YUMUSATMA_2 = 3  # İkinci EMA Periyodu
SMI_ESIK = -40.0  # -40 Altındaki hisseleri arar


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


# TradingView Standartlarında Stochastic Momentum Index (SMI) Hesabı
def smi_hesapla(df, k_length=10, smooth1=3, smooth2=3):
  hh = df['High'].rolling(window=k_length).max()
  ll = df['Low'].rolling(window=k_length).min()

  center = (hh + ll) / 2
  rel_diff = df['Close'] - center
  diff_range = hh - ll

  # Çift EMA Yumuşatması
  numerator = (
      rel_diff.ewm(span=smooth1, adjust=False)
      .mean()
      .ewm(span=smooth2, adjust=False)
      .mean()
  )

  denominator = (
      diff_range.ewm(span=smooth1, adjust=False)
      .mean()
      .ewm(span=smooth2, adjust=False)
      .mean()
      / 2
  )

  smi = 100 * (numerator / denominator.replace(0, np.nan))
  return smi


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

print('🔍 BİST Stochastic Momentum Index (SMI) < -40 Taraması Başlatılıyor...')

try:
  data_30m = yf.download(
      tickers=ticker_symbols,
      period='30d',
      interval='30m',
      group_by='ticker',
      progress=False,
  )
except Exception as e:
  print(f'Veri çekilirken hata oluştu: {e}')
  sys.exit()


def df_get(data_source, symbol):
  try:
    df = data_source[symbol].copy()
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
      df.index = df.index.tz_localize(None)
    return df
  except KeyError:
    return pd.DataFrame()


for ticker_symbol in tqdm(ticker_symbols, desc='Hisseler Taranıyor'):
  ticker = ticker_symbol.replace('.IS', '')
  try:
    df_30m = df_get(data_30m, ticker_symbol).dropna(how='all')

    if df_30m.empty or len(df_30m) < 30:
      continue

    # 1 Saatlik Veri
    df_1h = (
        df_30m.resample('1h')
        .agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum',
        })
        .dropna()
    )

    # 4 Saatlik Veri
    df_4h = (
        df_30m.resample('4h')
        .agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum',
        })
        .dropna()
    )

    def smi_filtrele(df):
      df['SMI'] = smi_hesapla(
          df, SMI_K_PERIYOT, SMI_YUMUSATMA_1, SMI_YUMUSATMA_2
      )

      if len(df) < SMI_K_PERIYOT + 5:
        return False, 0

      smi_curr = float(df['SMI'].iloc[-1])

      if np.isnan(smi_curr):
        return False, 0

      # TEK ŞART: SMI değerinin -40'ın altında olması
      sinyal = smi_curr < SMI_ESIK

      return sinyal, smi_curr

    periyotlar = []
    if TARAMA_30DK:
      periyotlar.append(('30 Dakikalık', df_30m, '30M'))
    if TARAMA_1SAATLIK:
      periyotlar.append(('1 Saatlik', df_1h, '1H'))
    if TARAMA_4SAATLIK:
      periyotlar.append(('4 Saatlik', df_4h, '4H'))

    for periyot_adi, df_periyot, periyot_kod in periyotlar:
      sinyal_var, smi_val = smi_filtrele(df_periyot)

      if sinyal_var:
        son_fiyat = float(df_periyot['Close'].iloc[-1])
        mum_zaman = pd.to_datetime(df_periyot.index[-1])
        mum_zaman_str = mum_zaman.strftime('%Y%m%d_%H%M')

        sinyal_id = f'{ticker}_{periyot_kod}_SMI_EKSI40_{mum_zaman_str}'

        bilgi = {
            'Hisse': ticker,
            'Son Fiyat': round(son_fiyat, 2),
            'Periyot': periyot_adi,
            'SMI': round(smi_val, 2),
            'Tarih': str(mum_zaman),
        }
        results.append(bilgi)

        if sinyal_id not in gonderilenler:
          tv_link = f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
          msg = (
              f'📉 *BİST STOCHASTIC MOMENTUM INDEX (SMI) < -40 SİNYALİ*\n'
              f'*Hisse:* `{ticker}`\n'
              f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n'
              f'📊 *Periyot:* `{periyot_adi}`\n\n'
              f'🌊 *SMI Değeri:* `{smi_val:.2f}` (< -40)\n\n'
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
  excel_filename = 'BIST_SMI_Eksi40_Sonuclari.xlsx'
  df_results.to_excel(excel_filename, index=False)
  print(
      f'\n✅ Tarama tamamlandı! Toplam {len(results)} adet SMI değeri -40 altı olan hisse bulundu.'
  )
else:
  print('\n⚠️ Kriterleri karşılayan hisse bulunamadı (SMI < -40).')
