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

STATE_FILE = 'gonderilen_bist_rsi_28_32_sinyalleri.json'

# --- PERİYOT AYARLARI ---
TARAMA_30DK = True
TARAMA_1SAATLIK = True
TARAMA_4SAATLIK = True

# --- RSI PARAMETRELERİ ---
RSI_ALT_SINIR = 28.0
RSI_UST_SINIR = 32.0
RSI_PERIYOT = 14


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


# TradingView Standardına Uygun RSI (Wilder's Smoothing)
def rsi_hesapla(series, period=14):
  delta = series.diff()
  gain = delta.where(delta > 0, 0.0)
  loss = -delta.where(delta < 0, 0.0)
  avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
  avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
  rs = avg_gain / avg_loss.replace(0, np.nan)
  return 100 - (100 / (1 + rs))


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

print('🔍 BİST RSI 28-32 Yukarı Dönüş Taraması Başlatılıyor...')

# 30 Dakikalık veri indirme (30m için period 30d yeterlidir)
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

    # 1 Saatlik Veri Oluşturma
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

    # 4 Saatlik Veri Oluşturma
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

    def rsi_donus_var_mi(df):
      df['RSI'] = rsi_hesapla(df['Close'], RSI_PERIYOT)

      if len(df) < RSI_PERIYOT + 2:
        return False, 0, 0

      rsi_curr = float(df['RSI'].iloc[-1])
      rsi_prev = float(df['RSI'].iloc[-2])

      if np.isnan(rsi_curr) or np.isnan(rsi_prev):
        return False, 0, 0

      # TEK ŞART: RSI 28 ile 32 arasında olacak VE önceki muma göre YUKARI yönelecek
      rsi_kosulu = (
          RSI_ALT_SINIR <= rsi_curr <= RSI_UST_SINIR
      ) and (rsi_curr > rsi_prev)

      return rsi_kosulu, rsi_curr, rsi_prev

    periyotlar = []
    if TARAMA_30DK:
      periyotlar.append(('30 Dakikalık', df_30m, '30M'))
    if TARAMA_1SAATLIK:
      periyotlar.append(('1 Saatlik', df_1h, '1H'))
    if TARAMA_4SAATLIK:
      periyotlar.append(('4 Saatlik', df_4h, '4H'))

    for periyot_adi, df_periyot, periyot_kod in periyotlar:
      sinyal_var, rsi_val, rsi_prev_val = rsi_donus_var_mi(df_periyot)

      if sinyal_var:
        son_fiyat = float(df_periyot['Close'].iloc[-1])
        mum_zaman = pd.to_datetime(df_periyot.index[-1])
        mum_zaman_str = mum_zaman.strftime('%Y%m%d_%H%M')

        sinyal_id = f'{ticker}_{periyot_kod}_RSI28_32_{mum_zaman_str}'

        bilgi = {
            'Hisse': ticker,
            'Son Fiyat': round(son_fiyat, 2),
            'Periyot': periyot_adi,
            'Anlık RSI': round(rsi_val, 2),
            'Önceki RSI': round(rsi_prev_val, 2),
            'Tarih': str(mum_zaman),
        }
        results.append(bilgi)

        if sinyal_id not in gonderilenler:
          tv_link = f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
          msg = (
              f'📈 *BİST RSI 28-32 DİP DÖNÜŞ SİNYALİ*\n'
              f'*Hisse:* `{ticker}`\n'
              f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n'
              f'📊 *Periyot:* `{periyot_adi}`\n\n'
              f'📉 *RSI (14):* `{rsi_val:.2f}` (Önceki: `{rsi_prev_val:.2f}`) ↗️\n\n'
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
  excel_filename = 'BIST_RSI_28_32_Donus_Sonuclari.xlsx'
  df_results.to_excel(excel_filename, index=False)
  print(
      f'\n✅ Tarama tamamlandı! Toplam {len(results)} adet RSI 28-32 arası yukarıkıvrılan hisse bulundu.'
  )
else:
  print('\n⚠️ Kriterleri karşılayan hisse bulunamadı (RSI 28-32 arası ve yukarı kıvrılan).')
