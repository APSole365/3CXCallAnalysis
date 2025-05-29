
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="3CX Call Analyzer Pro", layout="wide")
st.title("📞 3CX Call Log Analyzer – Versione Avanzata")

uploaded_file = st.file_uploader("Carica un file CSV di log chiamate 3CX", type=["csv"])

@st.cache_data(show_spinner=False)
def load_and_process_data(file):
    df = pd.read_csv(file)
    df['Call Time'] = pd.to_datetime(df['Call Time'])

    def duration_to_seconds(s):
        try:
            t = datetime.strptime(s, "%H:%M:%S")
            return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second).total_seconds()
        except:
            return 0

    with st.spinner("⏳ Elaborazione colonne Ringing e Talking..."):
        df['Ringing_sec'] = df['Ringing'].fillna("00:00:00").apply(duration_to_seconds)
        df['Talking_sec'] = df['Talking'].fillna("00:00:00").apply(duration_to_seconds)
        df['Start'] = df['Call Time']
        df['End'] = df['Start'] + pd.to_timedelta(df['Ringing_sec'] + df['Talking_sec'], unit='s')

    df['Hour'] = df['Call Time'].dt.hour
    df['Date'] = df['Call Time'].dt.date
    df['User'] = df['Caller ID'].str.extract(r'\((.*?)\)')[0].fillna("Unknown")

    df['Status_clean'] = df['Status'].str.lower()
    df['Is_Transferred'] = df['Reason'].str.lower().str.contains("transferred|forwarded", na=False)

    return df

def calculate_concurrency(df, freq='1min'):
    time_points = pd.date_range(start=df['Start'].min(), end=df['End'].max(), freq=freq)
    intervals = pd.IntervalIndex.from_arrays(df['Start'], df['End'], closed='both')

    concurrency = []
    progress_text = "Calcolo delle chiamate contemporanee in corso..."
    my_bar = st.progress(0, text=progress_text)

    for i, t in enumerate(time_points):
        count = intervals.contains(t).sum()
        concurrency.append((t, count))
        if i % 10 == 0 or i == len(time_points) - 1:
            my_bar.progress(i / len(time_points), text=progress_text)
    my_bar.empty()

    concurrency_df = pd.DataFrame(concurrency, columns=['Time', 'Concurrent Calls'])
    return concurrency_df

if uploaded_file:
    df = load_and_process_data(uploaded_file)

    st.subheader("📈 Statistiche Generali")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totale Chiamate", len(df))
    col2.metric("Chiamate Risposte", (df['Status_clean'] == 'answered').sum())
    col3.metric("Chiamate Perse", (df['Status_clean'] == 'missed').sum())
    col4.metric("Chiamate Trasferite", df['Is_Transferred'].sum())

    st.subheader("📊 Analisi per Utente")
    selected_users = st.multiselect("Filtra per utente (Caller ID)", options=sorted(df['User'].unique()), default=None)
    user_df = df[df['User'].isin(selected_users)] if selected_users else df

    st.subheader("🕐 Analisi per Fascia Oraria")
    hour_range = st.slider("Seleziona fascia oraria", 0, 23, (0, 23))
    filtered_df = user_df[(user_df['Hour'] >= hour_range[0]) & (user_df['Hour'] <= hour_range[1])]

    if filtered_df.empty:
        st.warning("⚠️ Nessuna chiamata trovata nella fascia oraria selezionata.")
        st.stop()

    concurrency_df = calculate_concurrency(filtered_df)
    peak = concurrency_df['Concurrent Calls'].max()
    mean = concurrency_df['Concurrent Calls'].mean()

    st.write(f"**Picco chiamate contemporanee**: {peak}")
    st.write(f"**Media chiamate contemporanee**: {mean:.2f}")

    fig = px.line(concurrency_df, x='Time', y='Concurrent Calls', title='Chiamate contemporanee nel tempo')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Chiamate per Ora del Giorno")
    hourly_counts = filtered_df.groupby('Hour').size()
    fig2 = px.bar(hourly_counts, x=hourly_counts.index, y=hourly_counts.values,
                 labels={'x': 'Ora del giorno', 'y': 'Numero chiamate'},
                 title='Distribuzione chiamate per ora')
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Dati filtrati")
    with st.expander("Mostra tabella"), st.container():
        st.dataframe(filtered_df[['Call Time', 'Caller ID', 'Destination', 'Status', 'Ringing', 'Talking', 'Reason']])

    st.subheader("⬇️ Esporta i dati")
    csv_export = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Scarica CSV filtrato",
        data=csv_export,
        file_name="dati_filtrati.csv",
        mime="text/csv"
    )

else:
    st.info("Carica un file CSV per iniziare.")
