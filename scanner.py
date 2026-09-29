import subprocess
import sys

# Eksik kütüphaneleri otomatik yükle (GitHub Actions / Lokal)
for paket in ['yfinance', 'pandas', 'numpy', 'requests', 'openpyxl', 'tqdm']:
    try:
        __import__(paket)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paket])

import json
import os
import time
import warnings
from datetime import datetime
import numpy as np
import pandas as pd
import requests
from tqdm import tqdm
import yfinance as yf

warnings.filterwarnings('ignore')

# --- SİNYAL TAKİP DOSYASI AYARI ---
STATE_FILE = 'gonderilen_sinyaller.json'


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


# --- BIST PERİYOT AYARLARI (GÜNLÜK, HAFTALIK, AYLIK AKTİF) ---
TARAMA_YAPILACAK_PERIYOTLAR = {
    '30 Dakikalık': False,
    '1 Saatlik': False,
    '4 Saatlik': False,
    'Günlük': True,
    'Haftalık': True,
    'Aylık': True,
}

PERIYOT_AYARLARI = {
    '30 Dakikalık': {'interval': '30m', 'period': '30d', 'resample_rule': None},
    '1 Saatlik': {'interval': '60m', 'period': '60d', 'resample_rule': None},
    '4 Saatlik': {'interval': '60m', 'period': '60d', 'resample_rule': '4h'},
    'Günlük': {'interval': '1d', 'period': '1y', 'resample_rule': None},
    'Haftalık': {'interval': '1wk', 'period': '3y', 'resample_rule': None},
    'Aylık': {'interval': '1mo', 'period': 'max', 'resample_rule': None},
}

# --- STRATEJİ VE RSI AYARLARI ---
CCI_PERIYOT = 20
RSI_PERIYOT = 14
EMA_TREND = 20

# RSI Sınırları (Sadece 67 - 74 Arası)
RSI_MIN = 67.0
RSI_MAX = 74.0

# --- FİLTRE AKTİFLİK AYARLARI ---
HACIM_FILTRESI_AKTIF = True
HACIM_ORT_PERIYOT = 10
TREND_FILTRESI_AKTIF = True

# Telegram Bildirim Ayarları
TELEGRAM_AKTIF = True
TELEGRAM_BOT_TOKEN = os.getenv(
    'TELEGRAM_BOT_TOKEN', '8909661577:AAExPm7d6hohqkZV9XG_FMTcjjU_Z3hP92w'
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


def rsi_hesapla(series, period=14):
    """Wilder's Smoothing ile hassas RSI hesaplama"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


ham_tickers = [
    'A1CAP.IS',
    'A1YEN.IS',
    'AAGYO.IS',
    'ACSEL.IS',
    'ADEL.IS',
    'ADESE.IS',
    'ADGYO.IS',
    'AEFES.IS',
    'AFYON.IS',
    'AGESA.IS',
    'AGHOL.IS',
    'AGROT.IS',
    'AGYO.IS',
    'AHGAZ.IS',
    'AHSGY.IS',
    'AKBNK.IS',
    'AKCNS.IS',
    'AKENR.IS',
    'AKFGY.IS',
    'AKFIS.IS',
    'AKFYE.IS',
    'AKGRT.IS',
    'AKHAN.IS',
    'AKMGY.IS',
    'AKSA.IS',
    'AKSEN.IS',
    'AKSGY.IS',
    'AKSUE.IS',
    'AKYHO.IS',
    'ALARK.IS',
    'ALBRK.IS',
    'ALBTN.IS',
    'ALCAR.IS',
    'ALCTL.IS',
    'ALFAS.IS',
    'ALGYO.IS',
    'ALKA.IS',
    'ALKIM.IS',
    'ALKLC.IS',
    'ALTINS1.IS',
    'ALTNY.IS',
    'ALVES.IS',
    'ANELE.IS',
    'ANGEN.IS',
    'ANHYT.IS',
    'ANSGR.IS',
    'ARASE.IS',
    'ARCLK.IS',
    'ARDYZ.IS',
    'ARENA.IS',
    'ARFYE.IS',
    'ARMGD.IS',
    'ARSAN.IS',
    'ARTMS.IS',
    'ARZUM.IS',
    'ASELS.IS',
    'ASGYO.IS',
    'ASTOR.IS',
    'ASUZU.IS',
    'ATAGY.IS',
    'ATAKP.IS',
    'ATATP.IS',
    'ATATR.IS',
    'ATEKS.IS',
    'ATLAS.IS',
    'ATSYH.IS',
    'AVGYO.IS',
    'AVHOL.IS',
    'AVOD.IS',
    'AVPGY.IS',
    'AVTUR.IS',
    'AYCES.IS',
    'AYDEM.IS',
    'AYEN.IS',
    'AYES.IS',
    'AYGAZ.IS',
    'AZTEK.IS',
    'BAGFS.IS',
    'BAHKM.IS',
    'BAKAB.IS',
    'BALAT.IS',
    'BALSU.IS',
    'BANVT.IS',
    'BARMA.IS',
    'BASCM.IS',
    'BASGZ.IS',
    'BAYRK.IS',
    'BEGYO.IS',
    'BERA.IS',
    'BESLR.IS',
    'BESTE.IS',
    'BETAE.IS',
    'BEYAZ.IS',
    'BFREN.IS',
    'BIENY.IS',
    'BIGCH.IS',
    'BIGEN.IS',
    'BIGTK.IS',
    'BIMAS.IS',
    'BINBN.IS',
    'BINHO.IS',
    'BIOEN.IS',
    'BIZIM.IS',
    'BJKAS.IS',
    'BKRGY.IS',
    'BLCYT.IS',
    'BLUME.IS',
    'BMSCH.IS',
    'BMSTL.IS',
    'BNTAS.IS',
    'BOBET.IS',
    'BORLS.IS',
    'BORSK.IS',
    'BOSSA.IS',
    'BRISA.IS',
    'BRKO.IS',
    'BRKSN.IS',
    'BRKVY.IS',
    'BRLSM.IS',
    'BRMEN.IS',
    'BRSAN.IS',
    'BRYAT.IS',
    'BSOKE.IS',
    'BTCIM.IS',
    'BUCIM.IS',
    'BULGS.IS',
    'BURCE.IS',
    'BURVA.IS',
    'BVSAN.IS',
    'BYDNR.IS',
    'CANTE.IS',
    'CASA.IS',
    'CATES.IS',
    'CCOLA.IS',
    'CELHA.IS',
    'CEMAS.IS',
    'CEMTS.IS',
    'CEMZY.IS',
    'CEOEM.IS',
    'CGCAM.IS',
    'CIMSA.IS',
    'CITAS.IS',
    'CLEBI.IS',
    'CMBTN.IS',
    'CMENT.IS',
    'CONSE.IS',
    'COSMO.IS',
    'CRDFA.IS',
    'CRFSA.IS',
    'CUSAN.IS',
    'CVKMD.IS',
    'CWENE.IS',
    'DAGI.IS',
    'DAPGM.IS',
    'DARDL.IS',
    'DCTTR.IS',
    'DENGE.IS',
    'DERHL.IS',
    'DERIM.IS',
    'DESA.IS',
    'DESPC.IS',
    'DEVA.IS',
    'DGATE.IS',
    'DGGYO.IS',
    'DGNMO.IS',
    'DIRIT.IS',
    'DITAS.IS',
    'DMLKTG.IS',
    'DMRGD.IS',
    'DMSAS.IS',
    'DNISI.IS',
    'DOAS.IS',
    'DOCO.IS',
    'DOFER.IS',
    'DOFRB.IS',
    'DOGUB.IS',
    'DOHOL.IS',
    'DOKTA.IS',
    'DSTKF.IS',
    'DUNYH.IS',
    'DURDO.IS',
    'DURKN.IS',
    'DYOBY.IS',
    'DZGYO.IS',
    'EBEBK.IS',
    'ECILC.IS',
    'ECOGR.IS',
    'ECZYT.IS',
    'EDATA.IS',
    'EDIP.IS',
    'EFOR.IS',
    'EGEEN.IS',
    'EGEGY.IS',
    'EGEPO.IS',
    'EGGUB.IS',
    'EGPRO.IS',
    'EGSER.IS',
    'EKDMR.IS',
    'EKGYO.IS',
    'EKIM.IS',
    'EKIZ.IS',
    'EKOS.IS',
    'EKSUN.IS',
    'ELITE.IS',
    'EMKEL.IS',
    'EMNIS.IS',
    'EMPAE.IS',
    'ENDAE.IS',
    'ENERY.IS',
    'ENJSA.IS',
    'ENKAI.IS',
    'ENPRA.IS',
    'ENSRI.IS',
    'ENTRA.IS',
    'EPLAS.IS',
    'ERBOS.IS',
    'ERCB.IS',
    'EREGL.IS',
    'ERSU.IS',
    'ESCAR.IS',
    'ESCOM.IS',
    'ESEN.IS',
    'ETILR.IS',
    'ETYAT.IS',
    'EUHOL.IS',
    'EUKYO.IS',
    'EUPWR.IS',
    'EUREN.IS',
    'EUYO.IS',
    'EYGYO.IS',
    'FADE.IS',
    'FENER.IS',
    'FLAP.IS',
    'FMIZP.IS',
    'FONET.IS',
    'FORMT.IS',
    'FORTE.IS',
    'FRIGO.IS',
    'FRMPL.IS',
    'FROTO.IS',
    'FZLGY.IS',
    'GARAN.IS',
    'GARFA.IS',
    'GATEG.IS',
    'GEDIK.IS',
    'GEDZA.IS',
    'GENIL.IS',
    'GENKM.IS',
    'GENTS.IS',
    'GEREL.IS',
    'GESAN.IS',
    'GIPTA.IS',
    'GLBMD.IS',
    'GLCVY.IS',
    'GLRMK.IS',
    'GLRYH.IS',
    'GLYHO.IS',
    'GMTAS.IS',
    'GOKNR.IS',
    'GOLDA.IS',
    'GOLTS.IS',
    'GOODY.IS',
    'GOZDE.IS',
    'GRNYO.IS',
    'GRSEL.IS',
    'GRTHO.IS',
    'GSDDE.IS',
    'GSDHO.IS',
    'GSRAY.IS',
    'GUBRF.IS',
    'GUNDG.IS',
    'GWIND.IS',
    'GZNMI.IS',
    'HALKB.IS',
    'HATEK.IS',
    'HATSN.IS',
    'HDFGS.IS',
    'HEDEF.IS',
    'HEKTS.IS',
    'HKTM.IS',
    'HLGYO.IS',
    'HOROZ.IS',
    'HRKET.IS',
    'HTTBT.IS',
    'HUBVC.IS',
    'HUNER.IS',
    'HURGZ.IS',
    'ICBCT.IS',
    'ICUGS.IS',
    'IDGYO.IS',
    'IEYHO.IS',
    'IHAAS.IS',
    'IHEVA.IS',
    'IHGZT.IS',
    'IHLAS.IS',
    'IHLGM.IS',
    'IHYAY.IS',
    'IMASM.IS',
    'INDES.IS',
    'INFO.IS',
    'INGRM.IS',
    'INTEK.IS',
    'INTEM.IS',
    'INTET.IS',
    'INVEO.IS',
    'INVES.IS',
    'ISATR.IS',
    'ISBIR.IS',
    'ISBTR.IS',
    'ISCTR.IS',
    'ISDMR.IS',
    'ISFIN.IS',
    'ISGSY.IS',
    'ISGYO.IS',
    'ISKPL.IS',
    'ISKUR.IS',
    'ISMEN.IS',
    'ISSEN.IS',
    'ISVEA.IS',
    'ISYAT.IS',
    'IZENR.IS',
    'IZFAS.IS',
    'IZINV.IS',
    'IZMDC.IS',
    'JANTS.IS',
    'KAPLM.IS',
    'KARCL.IS',
    'KAREL.IS',
    'KARSN.IS',
    'KARTN.IS',
    'KATMR.IS',
    'KAYSE.IS',
    'KBORU.IS',
    'KCAER.IS',
    'KCHOL.IS',
    'KENT.IS',
    'KERVN.IS',
    'KFEIN.IS',
    'KGYO.IS',
    'KIMMR.IS',
    'KLGYO.IS',
    'KLKIM.IS',
    'KLMSN.IS',
    'KLNMA.IS',
    'KLRHO.IS',
    'KLSER.IS',
    'KLSYN.IS',
    'KLYPV.IS',
    'KMPUR.IS',
    'KNFRT.IS',
    'KOCMT.IS',
    'KONKA.IS',
    'KONTR.IS',
    'KONYA.IS',
    'KOPOL.IS',
    'KORDS.IS',
    'KOTON.IS',
    'KPEKS.IS',
    'KRDMA.IS',
    'KRDMB.IS',
    'KRDMD.IS',
    'KRGYO.IS',
    'KRONT.IS',
    'KRPLS.IS',
    'KRSTL.IS',
    'KRTEK.IS',
    'KRVGD.IS',
    'KSTUR.IS',
    'KTLEV.IS',
    'KTSKR.IS',
    'KUTPO.IS',
    'KUVVA.IS',
    'KUYAS.IS',
    'KZBGY.IS',
    'KZGYO.IS',
    'LIDER.IS',
    'LIDFA.IS',
    'LILAK.IS',
    'LINK.IS',
    'LKMNH.IS',
    'LMKDC.IS',
    'LOGO.IS',
    'LRSHO.IS',
    'LUKSK.IS',
    'LXGYO.IS',
    'LYDHO.IS',
    'LYDYE.IS',
    'MAALT.IS',
    'MACKO.IS',
    'MAGEN.IS',
    'MAKIM.IS',
    'MAKTK.IS',
    'MANAS.IS',
    'MARBL.IS',
    'MARMR.IS',
    'MARTI.IS',
    'MASFN.IS',
    'MAVI.IS',
    'MCARD.IS',
    'MEDTR.IS',
    'MEGAP.IS',
    'MEGMT.IS',
    'MEKAG.IS',
    'MEPET.IS',
    'MERCN.IS',
    'MERIT.IS',
    'MERKO.IS',
    'METEN.IS',
    'METRO.IS',
    'MEYSU.IS',
    'MGROS.IS',
    'MHRGY.IS',
    'MIATK.IS',
    'MMCAS.IS',
    'MNDRS.IS',
    'MNDTR.IS',
    'MOBTL.IS',
    'MOGAN.IS',
    'MOPAS.IS',
    'MPARK.IS',
    'MRGYO.IS',
    'MRSHL.IS',
    'MSGYO.IS',
    'MTRKS.IS',
    'MTRYO.IS',
    'MZHLD.IS',
    'NATEN.IS',
    'NETAS.IS',
    'NETCD.IS',
    'NIBAS.IS',
    'NTGAZ.IS',
    'NTHOL.IS',
    'NUGYO.IS',
    'NUHCM.IS',
    'OBAMS.IS',
    'OBASE.IS',
    'ODAS.IS',
    'ODINE.IS',
    'OFSYM.IS',
    'ONCSM.IS',
    'ONRYT.IS',
    'ORCAY.IS',
    'ORGE.IS',
    'ORMA.IS',
    'ORZAX.IS',
    'OSMEN.IS',
    'OSTIM.IS',
    'OTKAR.IS',
    'OTTO.IS',
    'OYAKC.IS',
    'OYAYO.IS',
    'OYLUM.IS',
    'OYYAT.IS',
    'OZATD.IS',
    'OZGYO.IS',
    'OZKGY.IS',
    'OZRDN.IS',
    'OZSUB.IS',
    'OZYSR.IS',
    'PAGYO.IS',
    'PAHOL.IS',
    'PAMEL.IS',
    'PAPIL.IS',
    'PARSN.IS',
    'PASEU.IS',
    'PATEK.IS',
    'PCILT.IS',
    'PEKGY.IS',
    'PENGD.IS',
    'PENTA.IS',
    'PETKM.IS',
    'PETUN.IS',
    'PGSUS.IS',
    'PINSU.IS',
    'PKART.IS',
    'PKENT.IS',
    'PLTUR.IS',
    'PNLSN.IS',
    'PNSUT.IS',
    'POLHO.IS',
    'POLTK.IS',
    'PRDGS.IS',
    'PRKAB.IS',
    'PRKME.IS',
    'PRZMA.IS',
    'PSDTC.IS',
    'PSGYO.IS',
    'QNBFK.IS',
    'QNBTR.IS',
    'QUAGR.IS',
    'QUICK.IS',
    'RALYH.IS',
    'RAYSG.IS',
    'REEDR.IS',
    'RGYAS.IS',
    'RNPOL.IS',
    'RODRG.IS',
    'RTALB.IS',
    'RUBNS.IS',
    'RUZYE.IS',
    'RYGYO.IS',
    'RYSAS.IS',
    'SAFKR.IS',
    'SAHOL.IS',
    'SAMAT.IS',
    'SANEL.IS',
    'SANKO.IS',
    'SARAE.IS',
    'SARKY.IS',
    'SASA.IS',
    'SAYAS.IS',
    'SDTTR.IS',
    'SEGMN.IS',
    'SEGYO.IS',
    'SEKFK.IS',
    'SEKUR.IS',
    'SELEC.IS',
    'SELVA.IS',
    'SERNT.IS',
    'SEYKM.IS',
    'SILVR.IS',
    'SISE.IS',
    'SKBNK.IS',
    'SKTAS.IS',
    'SKYLP.IS',
    'SKYMD.IS',
    'SMART.IS',
    'SMRTG.IS',
    'SMRVA.IS',
    'SNGYO.IS',
    'SNICA.IS',
    'SNPAM.IS',
    'SODSN.IS',
    'SOHOE.IS',
    'SOKE.IS',
    'SOKM.IS',
    'SONME.IS',
    'SRVGY.IS',
    'SSAAT.IS',
    'SUMAS.IS',
    'SUNTK.IS',
    'SURGY.IS',
    'SUWEN.IS',
    'SVGYO.IS',
    'TABGD.IS',
    'TARKM.IS',
    'TATEN.IS',
    'TATGD.IS',
    'TAVHL.IS',
    'TBORG.IS',
    'TCELL.IS',
    'TCKRC.IS',
    'TDGYO.IS',
    'TEHOL.IS',
    'TEKTU.IS',
    'TERA.IS',
    'TEZOL.IS',
    'TGSAS.IS',
    'THYAO.IS',
    'TKFEN.IS',
    'TKNKA.IS',
    'TKNSA.IS',
    'TLMAN.IS',
    'TMPOL.IS',
    'TMSN.IS',
    'TNZTP.IS',
    'TOASO.IS',
    'TRALT.IS',
    'TRCAS.IS',
    'TRENJ.IS',
    'TRGYO.IS',
    'TRHOL.IS',
    'TRILC.IS',
    'TRMET.IS',
    'TSGYO.IS',
    'TSKB.IS',
    'TSPOR.IS',
    'TTKOM.IS',
    'TTRAK.IS',
    'TUCLK.IS',
    'TUKAS.IS',
    'TUPRS.IS',
    'TUREX.IS',
    'TURGG.IS',
    'TURSG.IS',
    'UCAYM.IS',
    'UFUK.IS',
    'ULAS.IS',
    'ULKER.IS',
    'ULUFA.IS',
    'ULUSE.IS',
    'ULUUN.IS',
    'UMPAS.IS',
    'UNLU.IS',
    'USAK.IS',
    'USHOL.IS',
    'VAKBN.IS',
    'VAKFA.IS',
    'VAKFN.IS',
    'VAKKO.IS',
    'VANGD.IS',
    'VBTYZ.IS',
    'VERTU.IS',
    'VERUS.IS',
    'VESBE.IS',
    'VESTL.IS',
    'VEYAS.IS',
    'VKFYO.IS',
    'VKGYO.IS',
    'VKING.IS',
    'VRGYO.IS',
    'VSNMD.IS',
    'YAPRK.IS',
    'YATAS.IS',
    'YAYLA.IS',
    'YBTAS.IS',
    'YEOTK.IS',
    'YESIL.IS',
    'YGGYO.IS',
    'YIGIT.IS',
    'YKBNK.IS',
    'YKSLN.IS',
    'YONGA.IS',
    'YUNSA.IS',
    'YYAPI.IS',
    'YYLGD.IS',
    'ZEDUR.IS',
    'ZERGY.IS',
    'ZGYO.IS',
    'ZOREN.IS',
    'ZRGYO.IS',
]

ticker_symbols = sorted(list(set(ham_tickers)))
results = []
gonderilenler = sinyalleri_yukle()

for periyot_adi, aktif_mi in TARAMA_YAPILACAK_PERIYOTLAR.items():
    if not aktif_mi:
        continue

    print(f"\n🔍 '{periyot_adi}' periyodu için toplu veri indiriliyor...")
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

            if df.empty or len(df) < max(CCI_PERIYOT + 5, 25):
                continue

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

            if len(df) < max(CCI_PERIYOT + 5, 25):
                continue

            curr_vol = float(df['Volume'].iloc[-1])
            if curr_vol <= 0:
                continue

            close_curr = float(df['Close'].iloc[-1])

            # --- İNDİKATÖR HESAPLAMALARI ---
            ema20 = df['Close'].ewm(span=EMA_TREND, adjust=False).mean()

            # CCI
            tp = (df['High'] + df['Low'] + df['Close']) / 3
            sma_tp = tp.rolling(window=CCI_PERIYOT).mean()
            mad = tp.rolling(window=CCI_PERIYOT).apply(
                lambda x: np.abs(x - x.mean()).mean(), raw=True
            )
            mad_safe = np.where(mad == 0, 0.0001, mad)
            cci = (tp - sma_tp) / (0.015 * mad_safe)

            # RSI (Periyot: 14)
            df['RSI'] = rsi_hesapla(df['Close'], period=RSI_PERIYOT)

            ema20_curr = float(ema20.iloc[-1])
            curr_cci = float(cci.iloc[-1])
            prev_cci = float(cci.iloc[-2])
            curr_rsi = float(df['RSI'].iloc[-1])
            prev_rsi = float(df['RSI'].iloc[-2])
            prev_prev_rsi = float(df['RSI'].iloc[-3])

            # --- 1. CCI KOŞULU ---
            if not ((curr_cci > -100) and (curr_cci > prev_cci)):
                continue

            # --- 2. RSI ARALIK VE İVME KOŞULU (Sadece 67 - 74) ---
            rsi_ivme_yukari = (curr_rsi > prev_rsi) and (
                prev_rsi > prev_prev_rsi
            )
            if not (RSI_MIN <= curr_rsi <= RSI_MAX and rsi_ivme_yukari):
                continue

            sinyal_turu = f'RSI ({int(RSI_MIN)}-{int(RSI_MAX)}) Güçlü Trend'

            # --- 3. TREND FİLTRESİ (EMA 20) ---
            if TREND_FILTRESI_AKTIF and (close_curr < ema20_curr):
                continue

            # --- 4. HACİM FİLTRESİ ---
            vol_sma = df['Volume'].rolling(window=HACIM_ORT_PERIYOT).mean()
            vol_sma_curr = float(vol_sma.iloc[-1])
            if HACIM_FILTRESI_AKTIF and (curr_vol <= vol_sma_curr):
                continue

            # Sinyal Zaman Tanımı
            mum_zaman_str = pd.to_datetime(df.index[-1]).strftime('%Y%m%d')
            sinyal_id = f'{ticker}_{periyot_adi}_{sinyal_turu}_{mum_zaman_str}'

            hacim_oran = round(curr_vol / vol_sma_curr, 2)

            # --- 🎯 ENTRY, SL VE 3 HEDEF HESAPLAMA ---
            entry_fiyat = close_curr
            son_dusuk = float(df['Low'].iloc[-5:].min())
            stop_loss = son_dusuk * 0.992

            risk_marji = entry_fiyat - stop_loss
            if risk_marji <= 0:
                stop_loss = entry_fiyat * 0.97
                risk_marji = entry_fiyat - stop_loss

            tp1 = entry_fiyat + (risk_marji * 1.5)
            tp2 = entry_fiyat + (risk_marji * 2.5)
            tp3 = entry_fiyat + (risk_marji * 4.0)

            bilgi = {
                'Zaman Dilimi': periyot_adi,
                'Hisse': ticker,
                'Sinyal Türü': sinyal_turu,
                'Giriş (Entry)': round(entry_fiyat, 2),
                'Stop-Loss (SL)': round(stop_loss, 2),
                'Hedef 1 (TP1)': round(tp1, 2),
                'Hedef 2 (TP2)': round(tp2, 2),
                'Hedef 3 (TP3)': round(tp3, 2),
                'Son RSI': round(curr_rsi, 2),
                'Son CCI': round(curr_cci, 2),
                'Hacim/Ort': hacim_oran,
                'Tarih': str(df.index[-1].date()),
            }
            results.append(bilgi)

            # Yalnızca bu mum için daha önce mesaj gönderilmediyse Telegram'a at ve kaydet
            if sinyal_id not in gonderilenler:
                tv_link = (
                    f'https://www.tradingview.com/chart/?symbol=BIST:{ticker}'
                )
                msg = (
                    f'🔥 *BIST GÜÇLÜ TREND SİNYALİ*\n'
                    f'*Hisse:* `{ticker}` | *Periyot:* {periyot_adi}\n\n'
                    f'📈 *RSI (14):* `{curr_rsi:.2f}` (67-74 Yükselen İvme)\n'
                    f'📊 *CCI:* `{curr_cci:.2f}`\n\n'
                    f'🔵 *ENTRY:* `{entry_fiyat:.2f}`\n'
                    f'🔴 *SL (Stop):* `{stop_loss:.2f}`\n\n'
                    f'🎯 *TP1:* `{tp1:.2f}`\n'
                    f'🎯 *TP2:* `{tp2:.2f}`\n'
                    f'🎯 *TP3:* `{tp3:.2f}`\n\n'
                    f'📊 *Hacim Durumu:* Ortalamanın {hacim_oran}x katı\n\n'
                    f'📈 [TradingView Grafiği Aç]({tv_link})'
                )
                telegram_mesaj_gonder(msg)
                gonderilenler[sinyal_id] = True
                time.sleep(0.02)

        except Exception:
            pass

# Takip dosyasını GitHub repoda saklanmak üzere güncelle
sinyalleri_kaydet(gonderilenler)

if results:
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(
        by=['Zaman Dilimi', 'Hisse']
    ).reset_index(drop=True)
    excel_filename = 'BIST_Trend_Tarama_Sonuclari.xlsx'
    df_results.to_excel(excel_filename, index=False)
    print(
        f"\n✅ Tarama tamamlandı! Toplam {len(results)} hisse hedefleriyle birlikte Excel'e kaydedildi."
    )
else:
    print('\n⚠️ Seçili periyotlarda filtrelere takılan hisse bulunamadı.')
