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

STATE_FILE = 'gonderilen_yeni_strateji_sinyalleri.json'

# --- PERİYOT AYARLARI (Sadece 15dk ve 30dk Aktif) ---
TARAMA_15DK = True
TARAMA_30DK = True
TARAMA_1SAATLIK = False
TARAMA_4SAATLIK = False

# --- 500+ BİST HİSSE LİSTESİ ---
ticker_symbols = [
    'A1CAP', 'A1YEN', 'AAGYO', 'ACSEL', 'ADEL', 'ADESE', 'ADGYO', 'AEFES', 'AFYON', 'AGESA',
    'AGHOL', 'AGROT', 'AGYO', 'AHGAZ', 'AHSGY', 'AKBNK', 'AKCNS', 'AKENR', 'AKFGY', 'AKFIS',
    'AKFYE', 'AKGRT', 'AKHAN', 'AKMGY', 'AKSA', 'AKSEN', 'AKSGY', 'AKSUE', 'AKYHO', 'ALARK',
    'ALBRK', 'ALBTN', 'ALCAR', 'ALCTL', 'ALFAS', 'ALGYO', 'ALKA', 'ALKIM', 'ALKLC', 'ALTINS1',
    'ALTNY', 'ALVES', 'ANELE', 'ANGEN', 'ANHYT', 'ANSGR', 'ARASE', 'ARCLK', 'ARDYZ', 'ARENA',
    'ARFYE', 'ARMGD', 'ARSAN', 'ARTMS', 'ARZUM', 'ASELS', 'ASGYO', 'ASTOR', 'ASUZU', 'ATAGY',
    'ATAKP', 'ATATP', 'ATATR', 'ATEKS', 'ATLAS', 'ATSYH', 'AVGYO', 'AVHOL', 'AVOD', 'AVPGY',
    'AVTUR', 'AYCES', 'AYDEM', 'AYEN', 'AYES', 'AYGAZ', 'AZTEK', 'BAGFS', 'BAHKM', 'BAKAB',
    'BALAT', 'BALSU', 'BANVT', 'BARMA', 'BASCM', 'BASGZ', 'BAYRK', 'BEGYO', 'BERA', 'BESLR',
    'BESTE', 'BETAE', 'BEYAZ', 'BFREN', 'BIENY', 'BIGCH', 'BIGEN', 'BIGTK', 'BIMAS', 'BINBN',
    'BINHO', 'BIOEN', 'BIZIM', 'BJKAS', 'BKRGY', 'BLCYT', 'BLUME', 'BMSCH', 'BMSTL', 'BNTAS',
    'BOBET', 'BORLS', 'BORSK', 'BOSSA', 'BRISA', 'BRKO', 'BRKSN', 'BRKVY', 'BRLSM', 'BRMEN',
    'BRSAN', 'BRYAT', 'BSOKE', 'BTCIM', 'BUCIM', 'BULGS', 'BURCE', 'BURVA', 'BVSAN', 'BYDNR',
    'CANTE', 'CASA', 'CATES', 'CCOLA', 'CELHA', 'CEMAS', 'CEMTS', 'CEMZY', 'CEOEM', 'CGCAM',
    'CIMSA', 'CITAS', 'CLEBI', 'CMBTN', 'CMENT', 'CONSE', 'COSMO', 'CRDFA', 'CRFSA', 'CUSAN',
    'CVKMD', 'CWENE', 'DAGI', 'DAPGM', 'DARDL', 'DCTTR', 'DENGE', 'DERHL', 'DERIM', 'DESA',
    'DESPC', 'DEVA', 'DGATE', 'DGGYO', 'DGNMO', 'DIRIT', 'DITAS', 'DMLKTG', 'DMRGD', 'DMSAS',
    'DNISI', 'DOAS', 'DOCO', 'DOFER', 'DOFRB', 'DOGUB', 'DOHOL', 'DOKTA', 'DSTKF', 'DUNYH',
    'DURDO', 'DURKN', 'DYOBY', 'DZGYO', 'EBEBK', 'ECILC', 'ECOGR', 'ECZYT', 'EDATA', 'EDIP',
    'EFOR', 'EGEEN', 'EGEGY', 'EGEPO', 'EGGUB', 'EGPRO', 'EGSER', 'EKDMR', 'EKGYO', 'EKIM',
    'EKIZ', 'EKOS', 'EKSUN', 'ELITE', 'EMKEL', 'EMNIS', 'EMPAE', 'ENDAE', 'ENERY', 'ENJSA',
    'ENKAI', 'ENPRA', 'ENSRI', 'ENTRA', 'EPLAS', 'ERBOS', 'ERCB', 'EREGL', 'ERSU', 'ESCAR',
    'ESCOM', 'ESEN', 'ETILR', 'ETYAT', 'EUHOL', 'EUKYO', 'EUPWR', 'EUREN', 'EUYO', 'EYGYO',
    'FADE', 'FENER', 'FLAP', 'FMIZP', 'FONET', 'FORMT', 'FORTE', 'FRIGO', 'FRMPL', 'FROTO',
    'FZLGY', 'GARAN', 'GARFA', 'GATEG', 'GEDIK', 'GEDZA', 'GENIL', 'GENKM', 'GENTS', 'GEREL',
    'GESAN', 'GIPTA', 'GLBMD', 'GLCVY', 'GLRMK', 'GLRYH', 'GLYHO', 'GMTAS', 'GOKNR', 'GOLDA',
    'GOLTS', 'GOODY', 'GOZDE', 'GRNYO', 'GRSEL', 'GRTHO', 'GSDDE', 'GSDHO', 'GSRAY', 'GUBRF',
    'GUNDG', 'GWIND', 'GZNMI', 'HALKB', 'HATEK', 'HATSN', 'HDFGS', 'HEDEF', 'HEKTS', 'HKTM',
    'HLGYO', 'HOROZ', 'HRKET', 'HTTBT', 'HUBVC', 'HUNER', 'HURGZ', 'ICBCT', 'ICUGS', 'IDGYO',
    'IEYHO', 'IHAAS', 'IHEVA', 'IHGZT', 'IHLAS', 'IHLGM', 'IHYAY', 'IMASM', 'INDES', 'INFO',
    'INGRM', 'INTEK', 'INTEM', 'INTET', 'INVEO', 'INVES', 'ISATR', 'ISBIR', 'ISBTR', 'ISCTR',
    'ISDMR', 'ISFIN', 'ISGSY', 'ISGYO', 'ISKPL', 'ISKUR', 'ISMEN', 'ISSEN', 'ISVEA', 'ISYAT',
    'IZENR', 'IZFAS', 'IZINV', 'IZMDC', 'JANTS', 'KAPLM', 'KARCL', 'KAREL', 'KARSN', 'KARTN',
    'KATMR', 'KAYSE', 'KBORU', 'KCAER', 'KCHOL', 'KENT', 'KERVN', 'KFEIN', 'KGYO', 'KIMMR',
    'KLGYO', 'KLKIM', 'KLMSN', 'KLNMA', 'KLRHO', 'KLSER', 'KLSYN', 'KLYPV', 'KMPUR', 'KNFRT',
    'KOCMT', 'KONKA', 'KONTR', 'KONYA', 'KOPOL', 'KORDS', 'KOTON', 'KPEKS', 'KRDMA', 'KRDMB',
    'KRDMD', 'KRGYO', 'KRONT', 'KRPLS', 'KRSTL', 'KRTEK', 'KRVGD', 'KSTUR', 'KTLEV', 'KTSKR',
    'KUTPO', 'KUVVA', 'KUYAS', 'KZBGY', 'KZGYO', 'LIDER', 'LIDFA', 'LILAK', 'LINK', 'LKMNH',
    'LMKDC', 'LOGO', 'LRSHO', 'LUKSK', 'LXGYO', 'LYDHO', 'LYDYE', 'MAALT', 'MACKO', 'MAGEN',
    'MAKIM', 'MAKTK', 'MANAS', 'MARBL', 'MARMR', 'MARTI', 'MASFN', 'MAVI', 'MCARD', 'MEDTR',
    'MEGAP', 'MEGMT', 'MEKAG', 'MEPET', 'MERCN', 'MERIT', 'MERKO', 'METEN', 'METRO', 'MEYSU',
    'MGROS', 'MHRGY', 'MIATK', 'MMCAS', 'MNDRS', 'MNDTR', 'MOBTL', 'MOGAN', 'MOPAS', 'MPARK',
    'MRGYO', 'MRSHL', 'MSGYO', 'MTRKS', 'MTRYO', 'MZHLD', 'NATEN', 'NETAS', 'NETCD', 'NIBAS',
    'NTGAZ', 'NTHOL', 'NUGYO', 'NUHCM', 'OBAMS', 'OBASE', 'ODAS', 'ODINE', 'OFSYM', 'ONCSM',
    'ONRYT', 'ORCAY', 'ORGE', 'ORMA', 'ORZAX', 'OSMEN', 'OSTIM', 'OTKAR', 'OTTO', 'OYAKC',
    'OYAYO', 'OYLUM', 'OYYAT', 'OZATD', 'OZGYO', 'OZKGY', 'OZRDN', 'OZSUB', 'OZYSR', 'PAGYO',
    'PAHOL', 'PAMEL', 'PAPIL', 'PARSN', 'PASEU', 'PATEK', 'PCILT', 'PEKGY', 'PENGD', 'PENTA',
    'PETKM', 'PETUN', 'PGSUS', 'PINSU', 'PKART', 'PKENT', 'PLTUR', 'PNLSN', 'PNSUT', 'POLHO',
    'POLTK', 'PRDGS', 'PRKAB', 'PRKME', 'PRZMA', 'PSDTC', 'PSGYO', 'QNBFK', 'QNBTR', 'QUAGR',
    'QUICK', 'RALYH', 'RAYSG', 'REEDR', 'RGYAS', 'RNPOL', 'RODRG', 'RTALB', 'RUBNS', 'RUZYE',
    'RYGYO', 'RYSAS', 'SAFKR', 'SAHOL', 'SAMAT', 'SANEL', 'SANFM', 'SANKO', 'SARAE', 'SARKY',
    'SASA', 'SAYAS', 'SDTTR', 'SEGMN', 'SEGYO', 'SEKFK', 'SEKUR', 'SELEC', 'SELVA', 'SERNT',
    'SEYKM', 'SILVR', 'SISE', 'SKBNK', 'SKTAS', 'SKYLP', 'SKYMD', 'SMART', 'SMRTG', 'SMRVA',
    'SNGYO', 'SNICA', 'SNPAM', 'SODSN', 'SOHOE', 'SOKE', 'SOKM', 'SONME', 'SRVGY', 'SSAAT',
    'SUMAS', 'SUNTK', 'SURGY', 'SUWEN', 'SVGYO', 'TABGD', 'TARKM', 'TATEN', 'TATGD', 'TAVHL',
    'TBORG', 'TCELL', 'TCKRC', 'TDGYO', 'TEHOL', 'TEKTU', 'TERA', 'TEZOL', 'TGSAS', 'THYAO',
    'TKFEN', 'TKNKA', 'TKNSA', 'TLMAN', 'TMPOL', 'TMSN', 'TNZTP', 'TOASO', 'TRALT', 'TRCAS',
    'TRENJ', 'TRGYO', 'TRHOL', 'TRILC', 'TRMET', 'TSGYO', 'TSKB', 'TSPOR', 'TTKOM', 'TTRAK',
    'TUCLK', 'TUKAS', 'TUPRS', 'TUREX', 'TURGG', 'TURSG', 'UCAYM', 'UFUK', 'ULAS', 'ULKER',
    'ULUFA', 'ULUSE', 'ULUUN', 'UMPAS', 'UNLU', 'USAK', 'USHOL', 'VAKBN', 'VAKFA', 'VAKFN',
    'VAKKO', 'VANGD', 'VBTYZ', 'VERTU', 'VERUS', 'VESBE', 'VESTL', 'VEYAS', 'VKFYO', 'VKGYO',
    'VKING', 'VRGYO', 'VSNMD', 'YAPRK', 'YATAS', 'YAYLA', 'YBTAS', 'YEOTK', 'YESIL', 'YGGYO',
    'YIGIT', 'YKBNK', 'YKSLN', 'YONGA', 'YUNSA', 'YYAPI', 'YYLGD', 'ZEDUR', 'ZERGY', 'ZGYO',
    'ZOREN', 'ZRGYO'
]

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

# --- İNDİKATÖR HESAPLAMA FONKSİYONLARI ---
def hesapla_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hesapla_adx_di(df, period=14):
    df = df.copy()
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)

    df['+DM'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    df['-DM'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)

    tr_smooth = df['TR'].rolling(window=period).sum()
    plus_di = 100 * (df['+DM'].rolling(window=period).sum() / tr_smooth)
    minus_di = 100 * (df['-DM'].rolling(window=period).sum() / tr_smooth)

    return plus_di, minus_di

def hesapla_obv(df):
    obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    return obv

TELEGRAM_AKTIF = True
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def telegram_mesaj_gonder(mesaj):
    if not TELEGRAM_AKTIF:
        print("ℹ️ Telegram kapalı (TELEGRAM_AKTIF = False)")
        return
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 KRİTİK HATA: TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID GitHub Secrets'da tanımlı değil!")
        return
    
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mesaj,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        print(f"📤 Telegram'a mesaj gönderiliyor (Chat ID: {TELEGRAM_CHAT_ID})...")
        response = requests.post(url, json=payload, timeout=10)
        
        print(f"📥 Telegram Sunucu Yanıt Kodu: {response.status_code}")
        print(f"📥 Telegram Yanıt İçeriği: {response.text}")
        
        if response.status_code != 200:
            print(f"❌ Telegram mesajı reddetti! Detay: {response.text}")
        else:
            print("✅ Telegram mesajı başarıyla iletildi!")
    except Exception as e:
        print(f'❌ Telegram bağlantı sırasında kritik hata: {e}')

results = []
gonderilenler = sinyalleri_yukle()

print(f'🔍 15dk & 30dk Taraması Başlatılıyor ({len(ticker_symbols)} Hisse)...')

CHUNK_SIZE = 100
all_data_15m = pd.DataFrame()

# YFinance için .IS eklerini otomatik ekliyoruz
ticker_symbols_yf = [f"{t}.IS" for t in ticker_symbols]

for i in range(0, len(ticker_symbols_yf), CHUNK_SIZE):
    chunk = ticker_symbols_yf[i:i + CHUNK_SIZE]
    try:
        data_chunk = yf.download(
            tickers=chunk,
            period='30d',
            interval='15m',
            group_by='ticker',
            progress=False
        )
        if all_data_15m.empty:
            all_data_15m = data_chunk
        else:
            all_data_15m = pd.concat([all_data_15m, data_chunk], axis=1)
    except Exception as e:
        print(f'Grup veri indirme hatası: {e}')

def df_get(data_source, symbol):
    try:
        if symbol in data_source.columns.levels[0]:
            df = data_source[symbol].copy()
            if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

for ticker in tqdm(ticker_symbols, desc='Hisseler İşleniyor'):
    ticker_symbol = f"{ticker}.IS"
    try:
        df_15m = df_get(all_data_15m, ticker_symbol).dropna(how='all')

        if df_15m.empty or len(df_15m) < 30:
            continue

        # 30 Dakikalık Periyot Oluşturma
        df_30m = df_15m.resample('30m').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        def yeni_strateji_filtrele(df):
            df['EMA5'] = df['Close'].ewm(span=5, adjust=False).mean()
            df['EMA8'] = df['Close'].ewm(span=8, adjust=False).mean()
            df['SMA20'] = df['Close'].rolling(window=20).mean()
            df['DI_PLUS'], df['DI_MINUS'] = hesapla_adx_di(df, 14)
            df['RSI'] = hesapla_rsi(df['Close'], 14)
            df['OBV'] = hesapla_obv(df)

            if len(df) < 25:
                return False, {}

            c_curr = df['Close'].iloc[-1]

            ema5_c, ema5_p = df['EMA5'].iloc[-1], df['EMA5'].iloc[-2]
            ema8_c, ema8_p = df['EMA8'].iloc[-1], df['EMA8'].iloc[-2]
            ema_kesisim = (ema5_c > ema8_c) and (ema5_p <= ema8_p)

            sma20_c = df['SMA20'].iloc[-1]
            fiyat_sma_ustu = c_curr > sma20_c

            di_p_c, di_p_p = df['DI_PLUS'].iloc[-1], df['DI_PLUS'].iloc[-2]
            di_m_c, di_m_p = df['DI_MINUS'].iloc[-1], df['DI_MINUS'].iloc[-2]
            di_kesisim = (di_p_c > di_m_c) and (di_p_p <= di_m_p)

            rsi_c = df['RSI'].iloc[-1]
            rsi_p = df['RSI'].iloc[-2]
            rsi_ok = (rsi_c >= 48) and (rsi_c > rsi_p)

            obv_c, obv_p = df['OBV'].iloc[-1], df['OBV'].iloc[-2]
            obv_ok = obv_c > obv_p

            tam_uyum = ema_kesisim and fiyat_sma_ustu and di_kesisim and rsi_ok and obv_ok

            if not tam_uyum:
                return False, {}

            detaylar = {
                'Fiyat': c_curr,
                'EMA5': ema5_c,
                'EMA8': ema8_c,
                'SMA20': sma20_c,
                'DI+': di_p_c,
                'DI-': di_m_c,
                'RSI': rsi_c,
            }

            return True, detaylar

        periyotlar = []
        if TARAMA_15DK:
            periyotlar.append(('15 Dakikalık', df_15m, '15M'))
        if TARAMA_30DK:
            periyotlar.append(('30 Dakikalık', df_30m, '30M'))

        for periyot_adi, df_periyot, periyot_kod in periyotlar:
            sinyal_var, detay = yeni_strateji_filtrele(df_periyot)

            if sinyal_var:
                son_fiyat = float(df_periyot['Close'].iloc[-1])
                mum_zaman = pd.to_datetime(df_periyot.index[-1])
                mum_zaman_str = mum_zaman.strftime('%Y%m%d_%H%M')

                sinyal_id = f'{ticker}_{periyot_kod}_YENI_STRATEJI_{mum_zaman_str}'

                bilgi = {
                    'Hisse': ticker,
                    'Son Fiyat': round(son_fiyat, 2),
                    'Periyot': periyot_adi,
                    'RSI': round(detay['RSI'], 2),
                    'SMA20': round(detay['SMA20'], 2),
                    'Tarih': str(mum_zaman)
                }
                results.append(bilgi)

                if sinyal_id not in gonderilenler:
                    tv_link = f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
                    msg = (
                        f'🚀 *15M/30M AL SİNYALİ*\n'
                        f'*Hisse:* `{ticker}`\n'
                        f'💵 *Fiyat:* `{son_fiyat:.2f}` TL\n'
                        f'📊 *Periyot:* `{periyot_adi}`\n\n'
                        f'✅ EMA 5 x EMA 8 Yukarı Kesti\n'
                        f'✅ Fiyat > SMA(20) Üstünde (`{detay["SMA20"]:.2f}`)\n'
                        f'✅ DI+ x DI- Yukarı Kesti\n'
                        f'✅ RSI >= 48 ve Artıyor (`{detay["RSI"]:.1f}`)\n'
                        f'✅ OBV Yönü Yukarı\n\n'
                        f'🔗 [TradingView Grafiği Aç]({tv_link})'
                    )
                    telegram_mesaj_gonder(msg)
                    gonderilenler[sinyal_id] = True
                    time.sleep(0.02)

    except Exception as e:
        print(f"⚠️ İşlem Hatası [{ticker_symbol}]: {e}")

sinyalleri_kaydet(gonderilenler)

if results:
    df_results = pd.DataFrame(results)
    excel_filename = 'Yeni_Strateji_15m_30m_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(f'\n✅ Tarama tamamlandı! 15m ve 30m periyotlarında şartları sağlayan {len(results)} sinyal bulundu.')
else:
    print(f'\n⚠ {len(ticker_symbols)} BİST hissesi taranmış olup 15m/30m periyotlarında şartları sağlayan hisse çıkmadı.')
