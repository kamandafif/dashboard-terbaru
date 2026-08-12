"""
generate_data.py
-----------------
Skrip pembuatan dataset sintetis untuk studi:
"Pengembangan Dashboard Interaktif Terintegrasi untuk Manajemen Efisiensi
Energi dan Mobilitas Cerdas pada Lingkungan Industri Berkelanjutan"

Output: data_pabrik_simulasi.csv (30 hari, interval 15 menit)
"""

import pandas as pd
import numpy as np

# ============================================================
# PARAMETER DASAR SIMULASI
# ============================================================
SEED = 42
TANGGAL_MULAI = "2026-08-01 00:00"
TANGGAL_SELESAI = "2026-08-30 23:45"   # genap 30 hari (1-30 Agustus)
INTERVAL = "15min"
FAKTOR_EMISI_KGKWH = 0.85              # faktor emisi grid PLN (kg CO2 / kWh)
KAPASITAS_SOLAR_KWP = 35               # kapasitas terpasang panel surya


def buat_rentang_waktu():
    """Membentuk rentang waktu 30 hari dengan interval 15 menit."""
    return pd.date_range(start=TANGGAL_MULAI, end=TANGGAL_SELESAI, freq=INTERVAL)


def simulasi_beban_mesin(waktu, rng):
    """
    Simulasi beban listrik pabrik.
    Beban dasar (mesin standby) berjalan 24 jam, ditambah lonjakan
    produksi pada jam kerja (08.00-17.00) sehingga rentang harian
    berada pada kisaran 50-90 kW saat jam operasional.
    """
    jam = waktu.hour
    n = len(waktu)
    beban_dasar = rng.normal(loc=45, scale=4, size=n)
    lonjakan_kerja = np.where(
        (jam >= 8) & (jam <= 17),
        rng.normal(loc=35, scale=7, size=n),   # tambahan beban saat produksi aktif
        rng.normal(loc=3, scale=2, size=n)     # beban minim di luar jam kerja
    )
    daya = np.clip(beban_dasar + lonjakan_kerja, 20, 95)
    return daya.round(2)


def simulasi_solar_power(waktu, rng):
    """
    Simulasi produksi panel surya: aktif pukul 06.00-18.00 mengikuti
    kurva sinusoidal dengan puncak produksi pada pukul 12.00.
    """
    jam_desimal = waktu.hour + waktu.minute / 60
    n = len(waktu)
    faktor_kurva = np.maximum(0, np.sin((jam_desimal - 6) * np.pi / 12))
    derau = rng.normal(0, 1.2, n)
    solar = np.where(
        (jam_desimal >= 6) & (jam_desimal <= 18),
        faktor_kurva * KAPASITAS_SOLAR_KWP * 0.9 + derau,
        0
    )
    return np.clip(solar, 0, KAPASITAS_SOLAR_KWP).round(2)


def hitung_emisi_co2(daya_mesin_kw, solar_power_kw):
    """
    Emisi CO2 dihitung dari konsumsi daya bersih (setelah dikurangi
    kontribusi solar) dikonversi ke kWh per interval, dikali faktor emisi.
    """
    daya_bersih_pln = np.maximum(0, daya_mesin_kw - solar_power_kw)
    energi_kwh_per_interval = daya_bersih_pln * (15 / 60)
    return (energi_kwh_per_interval * FAKTOR_EMISI_KGKWH).round(3)


def simulasi_agv(waktu, seed_offset, laju_pakai, laju_isi, soc_awal=None):
    """
    Simulasi siklus State of Charge (SoC) baterai AGV secara stateful:
    SoC menurun saat AGV beroperasi (lebih cepat pada jam kerja) dan
    naik saat status charging aktif (dipicu ketika SoC <= 20%,
    berhenti mengisi saat SoC >= 95%).
    """
    n = len(waktu)
    rng = np.random.default_rng(SEED + seed_offset)
    soc = np.empty(n)
    sedang_charging = np.empty(n, dtype=bool)

    soc_now = rng.uniform(70, 100) if soc_awal is None else soc_awal
    status = False

    for i in range(n):
        jam = waktu[i].hour
        if status:
            soc_now += laju_isi + rng.normal(0, 0.3)
            if soc_now >= 95:
                status = False
        else:
            pemakaian = laju_pakai * (1.6 if 8 <= jam <= 17 else 0.4)
            soc_now -= pemakaian + rng.normal(0, 0.2)
            if soc_now <= 20:
                status = True
        soc_now = float(np.clip(soc_now, 5, 100))
        soc[i] = soc_now
        sedang_charging[i] = status

    return soc.round(1), sedang_charging


def simulasi_produksi(waktu, rng):
    """Simulasi output produksi per interval (unit); hanya aktif pada jam kerja."""
    jam = waktu.hour
    n = len(waktu)
    output = np.where((jam >= 8) & (jam <= 17), rng.poisson(lam=12, size=n), 0)
    return output.astype(int)


def generate_dataset():
    """Merangkai seluruh komponen simulasi menjadi satu dataframe akhir."""
    rng = np.random.default_rng(SEED)
    waktu = buat_rentang_waktu()

    daya_mesin = simulasi_beban_mesin(waktu, rng)
    solar_power = simulasi_solar_power(waktu, rng)
    emisi = hitung_emisi_co2(daya_mesin, solar_power)

    soc_01, cas_01 = simulasi_agv(waktu, seed_offset=1, laju_pakai=0.9, laju_isi=1.8)
    soc_02, cas_02 = simulasi_agv(waktu, seed_offset=2, laju_pakai=1.1, laju_isi=1.6)
    soc_03, cas_03 = simulasi_agv(waktu, seed_offset=3, laju_pakai=0.7, laju_isi=2.0)

    produksi = simulasi_produksi(waktu, rng)

    df = pd.DataFrame({
        "Timestamp": waktu.strftime("%Y-%m-%d %H:%M"),
        "Daya_Mesin_kW": daya_mesin,
        "Solar_Power_kW": solar_power,
        "Emisi_CO2_kg": emisi,
        "AGV_01_SoC": soc_01,
        "AGV_02_SoC": soc_02,
        "AGV_03_SoC": soc_03,
        "AGV_01_Charging": cas_01,
        "AGV_02_Charging": cas_02,
        "AGV_03_Charging": cas_03,
        # Status gabungan: True bila salah satu unit AGV sedang mengisi daya
        "Status_Charging_AGV": cas_01 | cas_02 | cas_03,
        "Production_Output_Units": produksi,
    })
    return df


if __name__ == "__main__":
    df_hasil = generate_dataset()
    df_hasil.to_csv("data_pabrik_simulasi.csv", index=False)
    print(f"Dataset berhasil dibuat: {len(df_hasil)} baris -> data_pabrik_simulasi.csv")
