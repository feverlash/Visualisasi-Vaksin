import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
# --- BACA DATA ---
df_mingguan = pd.read_csv('rekap_mingguan.csv')

# --- FILTER NILAI RASIO VALID ---
df_mingguan = df_mingguan[(df_mingguan['ratio_timely'].notna()) & (df_mingguan['ratio_timely'] > 0)]

# --- PILIH MODE PLOT ---
mode = st.radio("Pilih mode tampilan data:", ['Tampilkan data per grup', 'Hanya lihat rata-rata (overall)'])

# --- PILIH KODE PAKAI CHECKBOX ---
st.markdown("### Pilih kode yang ingin ditampilkan:")
pakai_kode_1 = st.checkbox("Tampilkan kode 1", value=True)
pakai_kode_2 = st.checkbox("Tampilkan kode 2", value=True)

selected_kode = []
if pakai_kode_1:
    selected_kode.append(1)
if pakai_kode_2:
    selected_kode.append(2)

if not selected_kode:
    st.warning("Silakan pilih minimal satu kode.")
    st.stop()

# --- FILTER SESUAI KODE TERPILIH ---
df_filtered = df_mingguan[df_mingguan['kode'].astype(int).isin(selected_kode)]
# Pastikan kolom tanggal_awal_minggu sudah dalam format datetime
df_filtered['tanggal_awal_minggu'] = pd.to_datetime(df_filtered['tanggal_awal_minggu'], errors='coerce')


# --- ROLLING WINDOW ---
window = st.slider("Smoothing window:", min_value=1, max_value=100, value=30, step=1)

# --- WARNA PERIODE ---
warna_periode = {
    'before_covid': '#e0f7fa',
    'during_covid': '#ffc4c4',
    'after_covid':  '#c8e6c9',
}

# --- SIMPAN OVERALL UNTUK RASIO PER PERIODE (SEBELUM DIPLOT) ---
df_overall_for_ratio = (
    df_filtered
    .groupby(['periode_covid'])[['timely', 'total']]
    .sum()
    .assign(ratio=lambda d: d['timely'] / d['total'] * 100)
)

# === MODE: PER GRUP ===
if mode == 'Tampilkan data per grup':
    hue_col = st.selectbox(
        "Pilih kategori pewarnaan garis (hue):",
        ['kabupaten', 'sex', 'jenis_wilayah', 'dosis']
    )

    df_filtered = df_filtered.sort_values([hue_col, 'tanggal_awal_minggu']).copy()
    df_filtered['ratio_timely_smooth'] = (
        df_filtered.groupby(hue_col)['ratio_timely']
        .transform(lambda x: x.rolling(window, center=True, min_periods=1).mean())
    )

    if hue_col == 'dosis':
        kategori_valid = ['dosis_1', 'dosis_2', 'dosis_3', 'booster']
        df_filtered = df_filtered[df_filtered['dosis'].isin(kategori_valid)]

    # Tambahkan Overall
    tampilkan_overall = st.checkbox("Tampilkan garis Overall", value=True)
    if tampilkan_overall:
        df_overall = (
            df_filtered
            .groupby(['tanggal_awal_minggu', 'periode_covid'])[['timely', 'untimely', 'total']]
            .sum()
            .reset_index()
        )
        df_overall[hue_col] = 'Overall'
        df_overall['ratio_timely'] = df_overall['timely'] / df_overall['total'] * 100
        df_overall = df_overall.sort_values(['tanggal_awal_minggu'])
        df_overall['ratio_timely_smooth'] = (
            df_overall['ratio_timely'].rolling(window=window, center=True, min_periods=1).mean()
        )
        df_filtered = pd.concat([df_filtered, df_overall], ignore_index=True)

else:
    # === MODE: HANYA OVERALL ===
    hue_col = 'Kelompok'
    df_overall = (
        df_filtered
        .groupby(['tanggal_awal_minggu', 'periode_covid'])[['timely', 'untimely', 'total']]
        .sum()
        .reset_index()
    )
    df_overall[hue_col] = 'Overall'
    df_overall['ratio_timely'] = df_overall['timely'] / df_overall['total'] * 100
    df_overall = df_overall.sort_values(['tanggal_awal_minggu'])
    df_overall['ratio_timely_smooth'] = (
        df_overall['ratio_timely'].rolling(window=window, center=True, min_periods=1).mean()
    )
    df_filtered = df_overall.copy()

color_discrete_map = {
    'Overall': '#FFFFFF'  # biru muda cerah
}

# --- PLOT ---
fig = px.line(
    df_filtered,
    x='tanggal_awal_minggu',
    y='ratio_timely_smooth',
    color=hue_col,
    title=f'Timely Vaccination Ratio per Week by {hue_col if mode == "Tampilkan data per grup" else "Overall"} (kode: {", ".join(map(str, selected_kode))})',
    labels={'tanggal_awal_minggu': 'Week', 'ratio_timely_smooth': 'Timely Ratio (%)'},
    template='plotly_white',
    color_discrete_map=color_discrete_map  # << Tambahkan baris ini
)

tanggal_awal_covid = pd.to_datetime("2020-03-02")
tanggal_akhir_covid = pd.to_datetime("2023-06-21")

import datetime

# fig.add_vline(
#     x=datetime.datetime.strptime("2020-03-02", "%Y-%m-%d").timestamp() * 1000,
#     line=dict(color="black", dash="dot"),
#     annotation_text="2020-03-02",
#     annotation_position="top"
# )

# fig.add_vline(
#     x=datetime.datetime.strptime("2023-06-21", "%Y-%m-%d").timestamp() * 1000,
#     line=dict(color="black", dash="dot"),
#     annotation_text="2023-06-21",
#     annotation_position="top"
# )

# --- SHADING PERIODE COVID ---
batas_periode = (
    df_filtered.groupby('periode_covid')['tanggal_awal_minggu']
    .agg(['min', 'max'])
    .dropna()
    .sort_values('min')
)

for periode, row in batas_periode.iterrows():
    fig.add_vrect(
        x0=row['min'],
        x1=row['max'],
        fillcolor=warna_periode.get(periode, "#000000"),
        opacity=0.3,
        layer='below',
        line_width=0.5,
        # annotation_text=periode.replace('_', ' ').title(),
        # annotation_position='top',
        # annotation_font_size=10
    )

    # Tambahkan teks rasio total timely per periode
    if periode in df_overall_for_ratio.index:
        rasio = df_overall_for_ratio.loc[periode, 'ratio']
        tengah = row['min'] + (row['max'] - row['min']) / 2
        fig.add_annotation(
            x=tengah,
            y=110,
            text=f"{periode.replace('_', ' ').title()}<br><b>{rasio:.1f}%</b>",
            showarrow=False,
            font=dict(size=10, color="white"),
            align='center'
        )

# --- LAYOUT ---
# Ambil tanggal paling awal dan paling akhir dari data
tanggal_awal = df_filtered['tanggal_awal_minggu'].min()
tanggal_akhir = df_filtered['tanggal_awal_minggu'].max()

# Tentukan titik-titik yang akan ditampilkan pada sumbu X
tickvals = [tanggal_awal, tanggal_awal_covid, tanggal_akhir_covid, tanggal_akhir]
ticktext = [tanggal.strftime('%Y-%m-%d') for tanggal in tickvals]

fig.update_layout(
    yaxis=dict(range=[0, 115]),
    xaxis=dict(
        title='Date',
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext
    ),
    yaxis_title='Timely Vaccination Ratio (%)',
    legend_title=hue_col.title(),
    margin=dict(t=60, b=10, l=10, r=40),
    height=600
)

st.plotly_chart(fig, use_container_width=True)
