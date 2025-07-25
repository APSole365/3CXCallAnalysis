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
    
    # Debug: mostra i primi valori della colonna Call Time
    st.write("🔍 **Debug - Primi 5 valori di Call Time:**")
    st.write(df['Call Time'].head())
    st.write(f"**Tipo di dato:** {df['Call Time'].dtype}")
    
    # Prova diversi formati di data comuni
    date_formats = [
        '%Y-%m-%d %H:%M:%S',    # 2024-01-15 14:30:25
        '%d/%m/%Y %H:%M:%S',    # 15/01/2024 14:30:25
        '%m/%d/%Y %H:%M:%S',    # 01/15/2024 14:30:25
        '%d-%m-%Y %H:%M:%S',    # 15-01-2024 14:30:25
        '%Y/%m/%d %H:%M:%S',    # 2024/01/15 14:30:25
        '%d.%m.%Y %H:%M:%S',    # 15.01.2024 14:30:25
        '%Y-%m-%d %H:%M',       # 2024-01-15 14:30
        '%d/%m/%Y %H:%M',       # 15/01/2024 14:30
        '%m/%d/%Y %H:%M',       # 01/15/2024 14:30
        '%d-%m-%Y %H:%M',       # 15-01-2024 14:30
        '%Y/%m/%d %H:%M',       # 2024/01/15 14:30
        '%d.%m.%Y %H:%M',       # 15.01.2024 14:30
    ]
    
    # Tenta di convertire la data con diversi formati
    call_time_converted = False
    for fmt in date_formats:
        try:
            df['Call Time'] = pd.to_datetime(df['Call Time'], format=fmt, errors='raise')
            st.success(f"✅ Formato data riconosciuto: {fmt}")
            call_time_converted = True
            break
        except:
            continue
    
    # Se nessun formato specifico funziona, prova il parsing automatico
    if not call_time_converted:
        try:
            df['Call Time'] = pd.to_datetime(df['Call Time'], errors='coerce', infer_datetime_format=True)
            st.warning("⚠️ Usato parsing automatico per le date. Controlla i risultati.")
            call_time_converted = True
        except Exception as e:
            st.error(f"❌ Impossibile convertire la colonna Call Time: {str(e)}")
            st.stop()
    
    # Rimuovi le righe con date non valide
    before_dropna = len(df)
    df = df.dropna(subset=['Call Time'])
    after_dropna = len(df)
    
    if before_dropna != after_dropna:
        st.warning(f"⚠️ Rimosse {before_dropna - after_dropna} righe con date non valide")

    def duration_to_seconds(s):
        if pd.isna(s) or s == '' or s is None:
            return 0
        try:
            # Gestisce formati come "00:05:30" o "5:30" o "30"
            s = str(s).strip()
            if ':' in s:
                parts = s.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
            else:
                # Solo secondi
                return int(float(s))
        except:
            return 0

    with st.spinner("⏳ Elaborazione colonne Ringing e Talking..."):
        df['Ringing_sec'] = df['Ringing'].fillna("00:00:00").apply(duration_to_seconds)
        df['Talking_sec'] = df['Talking'].fillna("00:00:00").apply(duration_to_seconds)
        df['Start'] = df['Call Time']
        df['End'] = df['Start'] + pd.to_timedelta(df['Ringing_sec'] + df['Talking_sec'], unit='s')

    df['Hour'] = df['Call Time'].dt.hour
    df['Date'] = df['Call Time'].dt.date
    
    # Gestione più robusta dell'estrazione dell'utente
    try:
        df['User'] = df['Caller ID'].str.extract(r'\((.*?)\)')[0].fillna("Unknown")
    except:
        df['User'] = df['Caller ID'].fillna("Unknown")

    df['Status_clean'] = df['Status'].str.lower()
    
    # Gestione più robusta del campo Reason
    try:
        df['Is_Transferred'] = df['Reason'].str.lower().str.contains("transferred|forwarded", na=False)
    except:
        df['Is_Transferred'] = False

    return df

def calculate_concurrency(df, freq='1min'):
    if df.empty:
        return pd.DataFrame(columns=['Time', 'Concurrent Calls'])
    
    time_points = pd.date_range(start=df['Start'].min(), end=df['End'].max(), freq=freq)
    intervals = pd.IntervalIndex.from_arrays(df['Start'], df['End'], closed='both')

    concurrency = []
    progress_text = "Calcolo delle chiamate contemporanee in corso..."
    my_bar = st.progress(0, text=progress_text)

    for i, t in enumerate(time_points):
        count = intervals.contains(t).sum()
        concurrency.append((t, count))
        if i % 10 == 0 or i == len(time_points) - 1:
            my_bar.progress((i + 1) / len(time_points), text=progress_text)
    my_bar.empty()

    concurrency_df = pd.DataFrame(concurrency, columns=['Time', 'Concurrent Calls'])
    return concurrency_df

if uploaded_file:
    try:
        df = load_and_process_data(uploaded_file)
        
        st.subheader("📈 Statistiche Generali")
        col1, col2, col3, col4 = st.columns(4)
        
        total_calls = len(df)
        answered_calls = (df['Status_clean'] == 'answered').sum()
        missed_calls = (df['Status_clean'] == 'missed').sum()
        transferred_calls = df['Is_Transferred'].sum()
        
        col1.metric("Totale Chiamate", total_calls)
        col2.metric("Chiamate Risposte", answered_calls)
        col3.metric("Chiamate Perse", missed_calls)
        col4.metric("Chiamate Trasferite", transferred_calls)

        st.subheader("📊 Analisi per Utente")
        unique_users = sorted(df['User'].unique())
        selected_users = st.multiselect("Filtra per utente (Caller ID)", options=unique_users, default=None)
        user_df = df[df['User'].isin(selected_users)] if selected_users else df

        st.subheader("🕐 Analisi per Fascia Oraria")
        hour_range = st.slider("Seleziona fascia oraria", 0, 23, (0, 23))
        filtered_df = user_df[(user_df['Hour'] >= hour_range[0]) & (user_df['Hour'] <= hour_range[1])]

        if filtered_df.empty:
            st.warning("⚠️ Nessuna chiamata trovata nella fascia oraria selezionata.")
        else:
            concurrency_df = calculate_concurrency(filtered_df)
            
            if not concurrency_df.empty:
                peak = concurrency_df['Concurrent Calls'].max()
                mean = concurrency_df['Concurrent Calls'].mean()

                st.write(f"**Picco chiamate contemporanee**: {peak}")
                st.write(f"**Media chiamate contemporanee**: {mean:.2f}")

                fig = px.line(concurrency_df, x='Time', y='Concurrent Calls', 
                             title='Chiamate contemporanee nel tempo')
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("📊 Chiamate per Ora del Giorno")
            hourly_counts = filtered_df.groupby('Hour').size()
            fig2 = px.bar(hourly_counts, x=hourly_counts.index, y=hourly_counts.values,
                         labels={'x': 'Ora del giorno', 'y': 'Numero chiamate'},
                         title='Distribuzione chiamate per ora')
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("📋 Dati filtrati")
            with st.expander("Mostra tabella"):
                # Mostra solo le colonne che esistono
                available_columns = ['Call Time', 'Caller ID', 'Destination', 'Status', 'Ringing', 'Talking']
                if 'Reason' in df.columns:
                    available_columns.append('Reason')
                
                display_columns = [col for col in available_columns if col in filtered_df.columns]
                st.dataframe(filtered_df[display_columns])

            st.subheader("⬇️ Esporta i dati")
            csv_export = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Scarica CSV filtrato",
                data=csv_export,
                file_name="dati_filtrati.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione del file: {str(e)}")
        st.write("**Suggerimenti per risolvere il problema:**")
        st.write("1. Verifica che il file CSV sia correttamente formattato")
        st.write("2. Controlla che la colonna 'Call Time' contenga date valide")
        st.write("3. Assicurati che il file non sia danneggiato")

else:
    st.info("Carica un file CSV per iniziare l'analisi.")
    st.write("**Formato CSV richiesto:**")
    st.write("- Colonna 'Call Time': data e ora della chiamata")
    st.write("- Colonna 'Caller ID': identificativo del chiamante")
    st.write("- Colonna 'Status': stato della chiamata (answered, missed, etc.)")
    st.write("- Colonne 'Ringing' e 'Talking': durata in formato HH:MM:SS")
