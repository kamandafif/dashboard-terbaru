"""
dashboard_app.py
-----------------
Dashboard Interaktif Terintegrasi untuk Manajemen Efisiensi Energi
dan Mobilitas Cerdas pada Lingkungan Industri Berkelanjutan.

Jalankan dengan:
    streamlit run dashboard_app.py

Membutuhkan file "data_pabrik_simulasi.csv" pada folder yang sama
(dibuat lewat generate_data.py). Jika tidak ditemukan, dashboard akan
membuatnya otomatis saat pertama kali dijalankan.
"""

import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from generate_data import generate_dataset

# ============================================================
# KONFIGURASI HALAMAN & GAYA TAMPILAN
# ============================================================
st.set_page_config(
    page_title="DSS Energi & Mobilitas Cerdas",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# PALET WARNA UTAMA DASHBOARD (Biru & Putih)
# ------------------------------------------------------------
WARNA_BIRU_CERAH = "#1A73E8"   # aksen utama, tombol, garis grafik utama
WARNA_BIRU_TUA = "#0F3D91"     # judul, header, elemen formal
WARNA_PUTIH = "#FFFFFF"        # latar/ruang bernapas
WARNA_BIRU_MUDA = "#BBD4FF"    # aksen lembut, gradasi, latar sekunder

st.markdown(f"""
<style>
    .main {{ background-color: {WARNA_PUTIH}; }}
    section[data-testid="stSidebar"] {{
        background-color: {WARNA_BIRU_TUA};
    }}
    section[data-testid="stSidebar"] * {{ color: {WARNA_PUTIH} !important; }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background-color: {WARNA_PUTIH}; color: {WARNA_BIRU_TUA} !important;
    }}
    div[data-testid="stMetric"] {{
        background-color: {WARNA_PUTIH};
        border: 1px solid {WARNA_BIRU_MUDA};
        border-top: 4px solid {WARNA_BIRU_CERAH};
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(15,61,145,0.08);
    }}
    div[data-testid="stMetricLabel"] {{ font-weight: 600; color: {WARNA_BIRU_TUA}; }}
    div[data-testid="stMetricValue"] {{ color: {WARNA_BIRU_CERAH}; }}
    h1, h2, h3 {{ color: {WARNA_BIRU_TUA}; }}
    .app-subtitle {{ color: #5878B0; font-size: 0.95rem; }}
    .block-note {{
        background-color: {WARNA_BIRU_MUDA}; border-left: 4px solid {WARNA_BIRU_CERAH};
        padding: 10px 14px; border-radius: 6px; font-size: 0.9rem; color: {WARNA_BIRU_TUA};
    }}
    div[data-testid="stDataFrame"] {{ border: 1px solid {WARNA_BIRU_MUDA}; border-radius: 8px; }}
    .stButton > button, .stDownloadButton > button {{
        background-color: {WARNA_BIRU_CERAH}; color: {WARNA_PUTIH}; border: none; border-radius: 8px;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        background-color: {WARNA_BIRU_TUA}; color: {WARNA_PUTIH};
    }}
</style>
""", unsafe_allow_html=True)

KOLOM_WAJIB = [
    "Timestamp", "Daya_Mesin_kW", "Solar_Power_kW", "Emisi_CO2_kg",
    "AGV_01_SoC", "AGV_02_SoC", "AGV_03_SoC",
    "AGV_01_Charging", "AGV_02_Charging", "AGV_03_Charging",
    "Status_Charging_AGV", "Production_Output_Units",
]
DAFTAR_AGV = ["AGV_01", "AGV_02", "AGV_03"]


# ============================================================
# FUNGSI BANTUAN: MUAT DATA, VALIDASI, TEMPLATE, PERHITUNGAN
# ============================================================
@st.cache_data
def muat_data_default():
    """Memuat dataset dari CSV lokal; membuat data baru bila belum ada."""
    try:
        df = pd.read_csv("data_pabrik_simulasi.csv")
    except FileNotFoundError:
        df = generate_dataset()
        df.to_csv("data_pabrik_simulasi.csv", index=False)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df


def validasi_kolom(df):
    """Memastikan file unggahan memiliki seluruh kolom yang dibutuhkan dashboard."""
    kolom_hilang = [k for k in KOLOM_WAJIB if k not in df.columns]
    return kolom_hilang


def buat_template_excel():
    """Menyusun file Excel kosong (1 baris contoh) sebagai template input manual."""
    contoh = pd.DataFrame([{
        "Timestamp": "2026-08-01 08:00",
        "Daya_Mesin_kW": 70.0,
        "Solar_Power_kW": 15.0,
        "Emisi_CO2_kg": 9.5,
        "AGV_01_SoC": 85.0, "AGV_02_SoC": 80.0, "AGV_03_SoC": 90.0,
        "AGV_01_Charging": False, "AGV_02_Charging": False, "AGV_03_Charging": False,
        "Status_Charging_AGV": False,
        "Production_Output_Units": 12,
    }])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        contoh.to_excel(writer, index=False, sheet_name="Template")
    buffer.seek(0)
    return buffer


def hitung_emisi_ulang(df, faktor_emisi):
    """Menghitung ulang kolom emisi CO2 mengikuti perubahan Daya_Mesin_kW / Solar_Power_kW."""
    daya_bersih = np.maximum(0, df["Daya_Mesin_kW"] - df["Solar_Power_kW"])
    df["Emisi_CO2_kg"] = (daya_bersih * (15 / 60) * faktor_emisi).round(3)
    return df


# ============================================================
# SIDEBAR: SUMBER DATA
# ============================================================
st.sidebar.title("⚡ Navigasi Dashboard")

with st.sidebar.expander("📁 Sumber Data", expanded=True):
    sumber_data = st.radio(
        "Pilih sumber dataset:",
        ["Data Simulasi (Default)", "Unggah File Sendiri", "Edit Manual di Tabel"],
        label_visibility="collapsed",
    )

    st.download_button(
        "⬇️ Unduh Template Excel",
        data=buat_template_excel(),
        file_name="template_data_pabrik.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Gunakan format ini untuk mengunggah data Anda sendiri.",
    )

if "df_utama" not in st.session_state:
    st.session_state.df_utama = muat_data_default()

if sumber_data == "Unggah File Sendiri":
    berkas = st.sidebar.file_uploader("Unggah CSV atau Excel", type=["csv", "xlsx"])
    if berkas is not None:
        df_baru = pd.read_csv(berkas) if berkas.name.endswith(".csv") else pd.read_excel(berkas)
        kolom_hilang = validasi_kolom(df_baru)
        if kolom_hilang:
            st.sidebar.error(f"Kolom belum lengkap: {', '.join(kolom_hilang)}")
        else:
            df_baru["Timestamp"] = pd.to_datetime(df_baru["Timestamp"])
            st.session_state.df_utama = df_baru
            st.sidebar.success(f"Berhasil memuat {len(df_baru)} baris data.")

df = st.session_state.df_utama.copy()

if sumber_data == "Edit Manual di Tabel":
    st.sidebar.info("Ubah nilai langsung pada tabel di modul **Overview**, lalu klik *Terapkan Perubahan*.")

# ============================================================
# SIDEBAR: PARAMETER OPERASIONAL
# ============================================================
st.sidebar.subheader("⚙️ Parameter Operasional")
kapasitas_solar = st.sidebar.number_input("Kapasitas Solar Panel (kWp)", value=35.0, step=1.0)
faktor_emisi = st.sidebar.number_input("Faktor Emisi Grid (kg CO2/kWh)", value=0.85, step=0.01)
tarif_listrik = st.sidebar.number_input("Tarif Listrik PLN (Rp/kWh)", value=1500, step=50)
daya_charger_agv = st.sidebar.number_input("Daya Pengisian per Unit AGV (kW)", value=5.0, step=0.5)
batas_beban_puncak = st.sidebar.number_input("Batas Beban Puncak Pabrik (kW)", value=80.0, step=5.0)

st.sidebar.subheader("🎯 Threshold Baterai AGV")
min_soc = st.sidebar.slider("Batas Minimal SoC (%)", 0, 50, 20)
max_soc = st.sidebar.slider("Target SoC Penuh (%)", 50, 100, 90)

st.sidebar.subheader("🧭 Modul")
modul = st.sidebar.radio(
    "Pilih modul dashboard:",
    ["Overview", "Energi & Emisi", "Fleet AGV/EV", "Smart Recommendation", "Simulasi Skenario"],
    label_visibility="collapsed",
)

# Filter tanggal berlaku untuk seluruh modul
tgl_min, tgl_max = df["Timestamp"].dt.date.min(), df["Timestamp"].dt.date.max()
st.sidebar.subheader("📅 Filter Tanggal")
rentang_tanggal = st.sidebar.date_input(
    "Rentang tanggal analisis", value=(tgl_min, tgl_max), min_value=tgl_min, max_value=tgl_max
)
if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    mulai, selesai = rentang_tanggal
else:
    mulai, selesai = tgl_min, tgl_max

df = df[(df["Timestamp"].dt.date >= mulai) & (df["Timestamp"].dt.date <= selesai)].reset_index(drop=True)
df = hitung_emisi_ulang(df, faktor_emisi)

# ============================================================
# HEADER
# ============================================================
st.markdown("<h2 style='text-align:center;'>Dashboard Interaktif Manajemen Efisiensi Energi & Mobilitas Cerdas</h2>", unsafe_allow_html=True)
st.markdown("<p class='app-subtitle' style='text-align:center;'>Optimasi konsumsi daya pabrik, kontribusi energi surya, dan pengisian daya AGV secara berkelanjutan</p>", unsafe_allow_html=True)
st.write("")

# Metrik dasar yang dipakai berulang di beberapa modul
total_daya_kwh = df["Daya_Mesin_kW"].sum() / 4
total_solar_kwh = df["Solar_Power_kW"].sum() / 4
total_emisi = df["Emisi_CO2_kg"].sum()
emisi_tanpa_solar = (df["Daya_Mesin_kW"] * (15 / 60) * faktor_emisi).sum()
reduksi_emisi_persen = ((emisi_tanpa_solar - total_emisi) / emisi_tanpa_solar * 100) if emisi_tanpa_solar > 0 else 0
kontribusi_solar_persen = (total_solar_kwh / total_daya_kwh * 100) if total_daya_kwh > 0 else 0

# ============================================================
# MODUL 1: OVERVIEW
# ============================================================
if modul == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Konsumsi Listrik", f"{total_daya_kwh:,.0f} kWh")
    c2.metric("Kontribusi Energi Surya", f"{kontribusi_solar_persen:.1f}%")
    c3.metric("Reduksi Emisi CO2", f"{reduksi_emisi_persen:.1f}%")
    jumlah_agv_aktif = sum(df[f"{a}_SoC"].iloc[-1] > 0 for a in DAFTAR_AGV) if len(df) else 0
    c4.metric("Jumlah AGV Aktif", f"{jumlah_agv_aktif} / {len(DAFTAR_AGV)} unit")

    st.write("")
    st.subheader("Tabel Data Telemetri")
    if sumber_data == "Edit Manual di Tabel":
        df_edit = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="editor_utama")
        if st.button("✅ Terapkan Perubahan"):
            df_edit["Timestamp"] = pd.to_datetime(df_edit["Timestamp"])
            df_edit = hitung_emisi_ulang(df_edit, faktor_emisi)
            st.session_state.df_utama = df_edit
            st.success("Perubahan tersimpan. Nilai KPI dan grafik telah diperbarui.")
            st.rerun()
    else:
        st.dataframe(df.head(20), use_container_width=True)

# ============================================================
# MODUL 2: ENERGI & EMISI
# ============================================================
elif modul == "Energi & Emisi":
    st.subheader("Beban Listrik Pabrik vs Produksi Energi Surya")
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=df["Timestamp"], y=df["Daya_Mesin_kW"], name="Beban Mesin (kW)", line=dict(color=WARNA_BIRU_TUA)))
    fig_line.add_trace(go.Scatter(x=df["Timestamp"], y=df["Solar_Power_kW"], name="Solar Power (kW)", fill="tozeroy", line=dict(color=WARNA_BIRU_CERAH), fillcolor="rgba(187,212,255,0.5)"))
    fig_line.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1), margin=dict(t=30))
    st.plotly_chart(fig_line, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Proporsi Sumber Energi")
        fig_donut = px.pie(
            names=["Listrik PLN", "Panel Surya"],
            values=[max(total_daya_kwh - total_solar_kwh, 0), total_solar_kwh],
            hole=0.55,
            color_discrete_sequence=[WARNA_BIRU_TUA, WARNA_BIRU_CERAH],
        )
        fig_donut.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig_donut, use_container_width=True)
    with col_b:
        st.subheader("Tren Emisi CO2 Harian")
        emisi_harian = df.groupby(df["Timestamp"].dt.date)["Emisi_CO2_kg"].sum().reset_index()
        fig_bar = px.bar(emisi_harian, x="Timestamp", y="Emisi_CO2_kg", color_discrete_sequence=[WARNA_BIRU_CERAH])
        fig_bar.update_layout(margin=dict(t=10, b=10), xaxis_title="Tanggal", yaxis_title="Emisi CO2 (kg)")
        st.plotly_chart(fig_bar, use_container_width=True)

# ============================================================
# MODUL 3: FLEET AGV/EV
# ============================================================
elif modul == "Fleet AGV/EV":
    st.subheader("Status Terkini Baterai AGV")
    data_status = []
    for a in DAFTAR_AGV:
        soc_terkini = df[f"{a}_SoC"].iloc[-1] if len(df) else np.nan
        status = "🔌 Mengisi Daya" if df[f"{a}_Charging"].iloc[-1] else "🔋 Beroperasi"
        kondisi = "⚠️ Rendah" if soc_terkini <= min_soc else ("✅ Optimal" if soc_terkini >= max_soc else "🟡 Normal")
        data_status.append({"Unit AGV": a, "SoC Terkini (%)": soc_terkini, "Status": status, "Kondisi Baterai": kondisi})
    st.dataframe(pd.DataFrame(data_status), use_container_width=True, hide_index=True)

    st.write("")
    st.subheader("Tren Pengisian/Penurunan Daya Baterai")
    fig_agv = go.Figure()
    warna = {"AGV_01": WARNA_BIRU_CERAH, "AGV_02": WARNA_BIRU_TUA, "AGV_03": "#6FA0E8"}
    for a in DAFTAR_AGV:
        fig_agv.add_trace(go.Scatter(x=df["Timestamp"], y=df[f"{a}_SoC"], name=a, line=dict(color=warna[a])))
    fig_agv.add_hline(y=min_soc, line_dash="dot", line_color="#D64550", annotation_text="Batas Minimal")
    fig_agv.add_hline(y=max_soc, line_dash="dot", line_color=WARNA_BIRU_TUA, annotation_text="Target Penuh")
    fig_agv.update_layout(hovermode="x unified", yaxis_title="State of Charge (%)", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig_agv, use_container_width=True)

# ============================================================
# MODUL 4: SMART RECOMMENDATION ENGINE
# ============================================================
elif modul == "Smart Recommendation":
    st.subheader("Deteksi Pengisian Daya AGV Saat Beban Puncak")

    # Logika IF-ELSE: pengisian daya bersamaan dengan beban di atas batas puncak
    kejadian_puncak = df[(df["Daya_Mesin_kW"] > batas_beban_puncak) & (df["Status_Charging_AGV"])]
    jumlah_kejadian = len(kejadian_puncak)

    if jumlah_kejadian > 0:
        energi_terdampak_kwh = jumlah_kejadian * daya_charger_agv * (15 / 60)
        estimasi_biaya = energi_terdampak_kwh * tarif_listrik

        st.warning(
            f"⚠️ **Peringatan Beban Puncak:** terdeteksi **{jumlah_kejadian} interval** "
            f"pengisian daya AGV bersamaan dengan beban pabrik melebihi {batas_beban_puncak:.0f} kW."
        )
        st.info(
            "💡 **Rekomendasi:** alihkan jadwal pengisian daya AGV ke rentang pukul 11.00–14.00 "
            "saat produksi panel surya berada di puncaknya, guna mengurangi tarikan daya dari PLN."
        )
        c1, c2 = st.columns(2)
        c1.metric("Estimasi Energi Terdampak", f"{energi_terdampak_kwh:,.1f} kWh")
        c2.metric("Estimasi Potensi Penghematan", f"Rp {estimasi_biaya:,.0f}")
    else:
        st.success("✅ **Kondisi Optimal:** pengisian daya AGV berjalan efisien tanpa memicu beban puncak.")

    st.write("")
    st.subheader("Detail Interval Bermasalah")
    if jumlah_kejadian > 0:
        st.dataframe(
            kejadian_puncak[["Timestamp", "Daya_Mesin_kW", "Solar_Power_kW", "Status_Charging_AGV"]],
            use_container_width=True, hide_index=True,
        )
    else:
        st.markdown("<div class='block-note'>Tidak ada interval bermasalah pada rentang tanggal yang dipilih.</div>", unsafe_allow_html=True)

# ============================================================
# MODUL 5: SIMULASI SKENARIO
# ============================================================
elif modul == "Simulasi Skenario":
    st.subheader("Simulasi Dampak Perubahan Kapasitas Solar & Pola Pengisian AGV")

    col1, col2 = st.columns(2)
    with col1:
        tambahan_kapasitas = st.slider("Penambahan Kapasitas Solar Panel (kWp)", 0, 50, 0, step=5)
    with col2:
        pergeseran_charging = st.slider("Persentase Pengisian AGV Dialihkan ke Jam Puncak Solar (%)", 0, 100, 0, step=10)

    # Proyeksi solar baru: skala linear terhadap penambahan kapasitas
    faktor_skala = (kapasitas_solar + tambahan_kapasitas) / kapasitas_solar if kapasitas_solar > 0 else 1
    solar_proyeksi = (df["Solar_Power_kW"] * faktor_skala).clip(upper=kapasitas_solar + tambahan_kapasitas)

    # Proyeksi pengisian AGV yang dialihkan ke jam puncak solar dianggap disuplai penuh oleh solar
    kejadian_puncak_now = (df["Daya_Mesin_kW"] > batas_beban_puncak) & (df["Status_Charging_AGV"])
    pengurangan_beban = kejadian_puncak_now * daya_charger_agv * (pergeseran_charging / 100)
    daya_mesin_proyeksi = (df["Daya_Mesin_kW"] - pengurangan_beban).clip(lower=0)

    daya_bersih_proyeksi = np.maximum(0, daya_mesin_proyeksi - solar_proyeksi)
    emisi_proyeksi = (daya_bersih_proyeksi * (15 / 60) * faktor_emisi).sum()
    delta_emisi = total_emisi - emisi_proyeksi
    persen_reduksi_tambahan = (delta_emisi / total_emisi * 100) if total_emisi > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Emisi CO2 Saat Ini", f"{total_emisi:,.1f} kg")
    c2.metric("Emisi CO2 Proyeksi", f"{emisi_proyeksi:,.1f} kg", delta=f"-{delta_emisi:,.1f} kg")
    c3.metric("Reduksi Tambahan", f"{persen_reduksi_tambahan:.1f}%")

    fig_sim = go.Figure()
    fig_sim.add_trace(go.Bar(name="Emisi Saat Ini", x=["Total Emisi CO2 (kg)"], y=[total_emisi], marker_color=WARNA_BIRU_TUA))
    fig_sim.add_trace(go.Bar(name="Emisi Proyeksi", x=["Total Emisi CO2 (kg)"], y=[emisi_proyeksi], marker_color=WARNA_BIRU_CERAH))
    fig_sim.update_layout(barmode="group", margin=dict(t=20))
    st.plotly_chart(fig_sim, use_container_width=True)

    st.markdown(
        f"<div class='block-note'>Skenario ini mengasumsikan produksi solar meningkat secara "
        f"linear terhadap penambahan kapasitas, dan bahwa daya charging yang dialihkan sepenuhnya "
        f"disuplai dari solar tanpa menambah beban PLN.</div>",
        unsafe_allow_html=True,
    )
