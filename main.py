import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

st.set_page_config(layout="wide")

# --- BACA DATA ---
df_mingguan = pd.read_csv('rekap_mingguan.csv')

# --- FILTER NILAI RASIO VALID ---
df_mingguan = df_mingguan[(df_mingguan['ratio_timely'].notna()) & (df_mingguan['ratio_timely'] > 0)]

# --- KONVERSI TANGGAL ---
df_mingguan['tanggal_awal_minggu'] = pd.to_datetime(df_mingguan['tanggal_awal_minggu'], errors='coerce')

# --- PILIH GRANULARITAS ---
granularity = st.selectbox("Lihat berdasarkan:", ['Week', 'Month'])
x_col = 'tanggal_awal_minggu' if granularity == 'Week' else 'month'

# --- PILIH MODE PLOT ---
mode = st.radio("Pilih mode tampilan data:", ['Tampilkan data per grup', 'Hanya lihat rata-rata (overall)'])

# --- PILIH KODE ---
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

# --- FILTER SESUAI KODE ---
df_filtered = df_mingguan[df_mingguan['kode'].astype(int).isin(selected_kode)].copy()

# --- ROLLING WINDOW ---
window = st.slider("Smoothing window:", min_value=1, max_value=100, value=30, step=1)

# --- WARNA PERIODE ---
warna_periode = {
    'before_covid': '#e0f7fa',
    'during_covid': '#ffc4c4',
    'after_covid':  '#c8e6c9',
}

# --- SIMPAN OVERALL UNTUK ANNOTASI RASIO PER PERIODE ---
df_overall_for_ratio = (
    df_filtered
    .groupby(['periode_covid'])[['timely', 'total']]
    .sum()
    .assign(ratio=lambda d: d['timely'] / d['total'] * 100)
)

# === MODE: PER GRUP ===
if mode == 'Tampilkan data per grup':
    hue_options = ['kabupaten', 'sex', 'jenis_wilayah', 'dosis', 'periode_covid_Tgl Lahir']
    hue_col = st.selectbox("Pilih kategori pewarnaan garis (hue):", hue_options)


    if granularity == 'Week':
        df_filtered = df_filtered.sort_values([hue_col, 'tanggal_awal_minggu']).copy()
        df_filtered['ratio_timely_smooth'] = (
            df_filtered.groupby(hue_col)['ratio_timely']
            .transform(lambda x: x.rolling(window, center=True, min_periods=1).mean())
        )
    else:
        df_filtered = (
            df_filtered
            .groupby([x_col, hue_col, 'periode_covid'], as_index=False)
            .agg({'timely': 'sum', 'untimely': 'sum', 'total': 'sum'})
        )
        df_filtered['ratio_timely'] = df_filtered['timely'] / df_filtered['total'] * 100
        df_filtered['ratio_timely_smooth'] = df_filtered['ratio_timely']

    # Tambahkan Overall
    tampilkan_overall = st.checkbox("Tampilkan garis Overall", value=True)
    if tampilkan_overall:
        if granularity == 'Week':
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
        else:
            df_overall = (
                df_filtered
                .groupby(['month', 'periode_covid'], as_index=False)[['timely', 'untimely', 'total']]
                .sum()
            )
            df_overall[hue_col] = 'Overall'
            df_overall['ratio_timely'] = df_overall['timely'] / df_overall['total'] * 100
            df_overall['ratio_timely_smooth'] = df_overall['ratio_timely']

        df_filtered = pd.concat([df_filtered, df_overall], ignore_index=True)

else:
    hue_col = 'Kelompok'
    df_overall = (
        df_filtered
        .groupby([x_col, 'periode_covid'])[['timely', 'untimely', 'total']]
        .sum()
        .reset_index()
    )
    df_overall[hue_col] = 'Overall'
    df_overall['ratio_timely'] = df_overall['timely'] / df_overall['total'] * 100
    df_overall = df_overall.sort_values(by=x_col)
    df_overall['ratio_timely_smooth'] = (
        df_overall['ratio_timely'].rolling(window=window, center=True, min_periods=1).mean()
        if granularity == 'Week' else df_overall['ratio_timely']
    )
    df_filtered = df_overall.copy()

# --- COLOR MAP ---
color_discrete_map = {'Overall': '#FFFFFF'}

# --- PLOT ---
fig = px.line(
    df_filtered,
    x=x_col,
    y='ratio_timely_smooth',
    color=hue_col,
    title=f'Timely Vaccination Ratio by {x_col.title()} (kode: {", ".join(map(str, selected_kode))})',
    labels={x_col: 'Time', 'ratio_timely_smooth': 'Timely Ratio (%)'},
    template='plotly_white',
    color_discrete_map=color_discrete_map
)

# --- SHADING PERIODE COVID ---
batas_periode = (
    df_mingguan.groupby('periode_covid')['tanggal_awal_minggu']
    .agg(['min', 'max'])
    .dropna()
    .sort_values('min')
)
from datetime import timedelta
tanggal_awal_covid = pd.to_datetime("2020-03-02", format="%Y-%m-%d")
tanggal_akhir_covid = pd.to_datetime("2023-06-21", format="%Y-%m-%d")

for periode, row in batas_periode.iterrows():
    fig.add_vrect(
        x0=row['min'],
        x1=row['max'],
        fillcolor=warna_periode.get(periode, "#000000"),
        opacity=0.3,
        layer='below',
        line_width=0.5,
    )
    # Garis vertikal awal
    fig.add_vline(
        x=datetime.datetime.strptime(tanggal_awal_covid.strftime("%Y-%m-%d"), "%Y-%m-%d").timestamp() * 1000,
        line=dict(color="red", width=1, dash="dot"),
        layer='above',
        annotation_text = '2020-03-02',
        annotation_position="top"
    )

    # Garis vertikal akhir
    fig.add_vline(
        x=datetime.datetime.strptime(tanggal_akhir_covid.strftime("%Y-%m-%d"), "%Y-%m-%d").timestamp() * 1000,
        line=dict(color="red", width=1, dash="dot"),
        layer='above',
        annotation_text = '2023-06-21',
        annotation_position="top"
    )
    if periode in df_overall_for_ratio.index:
        rasio = df_overall_for_ratio.loc[periode, 'ratio']
        start = row['min']
        end = row['max']
        tengah = start + (end - start) / 2
        tengah = tengah
        fig.add_annotation(
            x=tengah,
            y=110,
            text=f"{periode.replace('_', ' ').title()}<br><b>{rasio:.1f}%</b>",
            showarrow=False,
            font=dict(size=10, color="white"),
            align='center'
        )

# --- LAYOUT ---
fig.update_layout(
    yaxis=dict(range=[0, 115]),
    xaxis_title='Time',
    yaxis_title='Timely Vaccination Ratio (%)',
    legend_title=hue_col.title(),
    margin=dict(t=60, b=10, l=10, r=40),
    height=600
)

st.plotly_chart(fig, use_container_width=True)
