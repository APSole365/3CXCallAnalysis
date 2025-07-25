import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="3CX Call Analyzer Pro", layout="wide")
st.title("📞 3CX Call Log Analyzer – Analisi Avanzata 2025")

uploaded_file = st.file_uploader("Carica un file CSV di log chiamate 3CX", type=["csv"])

@st.cache_data(show_spinner=False)
def load_and_process_data(file):
    df = pd.read_csv(file)
    
    # Debug: mostra informazioni sul file caricato
    st.write("🔍 **Debug - Informazioni file CSV:**")
    st.write(f"**Colonne disponibili:** {list(df.columns)}")
    st.write(f"**Numero di righe:** {len(df)}")
    st.write("**Primi 3 valori di Call Time:**")
    st.write(df['Call Time'].head(3).tolist())
    
    # Prova diversi formati di data comuni, incluso il formato ISO
    date_formats = [
        '%Y-%m-%dT%H:%M:%S',    # 2025-07-25T11:41:48 (formato ISO)
        '%Y-%m-%d %H:%M:%S',    # 2024-01-15 14:30:25
        '%d/%m/%Y %H:%M:%S',    # 15/01/2024 14:30:25
        '%m/%d/%Y %H:%M:%S',    # 01/15/2024 14:30:25
        '%d-%m-%Y %H:%M:%S',    # 15-01-2024 14:30:25
        '%Y/%m/%d %H:%M:%S',    # 2024/01/15 14:30:25
        '%d.%m.%Y %H:%M:%S',    # 15.01.2024 14:30:25
        '%Y-%m-%d %H:%M',       # 2024-01-15 14:30
        '%d/%m/%Y %H:%M',       # 15/01/2024 14:30
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
        df['Total_Duration_sec'] = df['Ringing_sec'] + df['Talking_sec']
        df['Start'] = df['Call Time']
        df['End'] = df['Start'] + pd.to_timedelta(df['Total_Duration_sec'], unit='s')

    # Analisi temporale
    df['Hour'] = df['Call Time'].dt.hour
    df['Date'] = df['Call Time'].dt.date
    df['DayOfWeek'] = df['Call Time'].dt.day_name()
    df['Week'] = df['Call Time'].dt.isocalendar().week
    df['Month'] = df['Call Time'].dt.month
    
    # Adatta alle nuove colonne: usa 'From' invece di 'Caller ID'
    try:
        # Estrae il nome/numero dalla colonna From (formato: "59004 Cassa 04 (59004)")
        df['User'] = df['From'].str.extract(r'(.*?)\s*\(.*?\)')[0].fillna(df['From'])
        df['User_Number'] = df['From'].str.extract(r'\((.*?)\)')[0].fillna("Unknown")
    except:
        df['User'] = df['From'].fillna("Unknown")
        df['User_Number'] = "Unknown"

    # Crea campo destination dalla colonna To
    try:
        df['Destination'] = df['To'].str.extract(r'(.*?)\s*\(.*?\)')[0].fillna(df['To'])
        df['Destination_Number'] = df['To'].str.extract(r'\((.*?)\)')[0].fillna("Unknown")
    except:
        df['Destination'] = df['To'].fillna("Unknown")
        df['Destination_Number'] = "Unknown"

    # Analisi avanzata degli status
    df['Status_clean'] = df['Status'].str.lower().str.strip()
    
    # Categorizzazione più dettagliata
    df['Is_Internal'] = df['Direction'].str.lower() == 'internal'
    df['Is_Inbound'] = df['Direction'].str.lower() == 'inbound' 
    df['Is_Outbound'] = df['Direction'].str.lower() == 'outbound'
    
    # Analisi dettagliata dello status
    df['Is_Answered'] = df['Status_clean'].isin(['answered', 'connected'])
    df['Is_Missed'] = df['Status_clean'].isin(['missed', 'unanswered', 'no answer'])
    df['Is_Busy'] = df['Status_clean'].isin(['busy', 'user busy'])
    df['Is_Failed'] = df['Status_clean'].isin(['failed', 'error', 'rejected'])
    df['Is_Abandoned'] = df['Status_clean'].isin(['abandoned', 'caller hangup'])
    
    # Analisi durata per categorizzare meglio
    df['Has_Talking_Time'] = df['Talking_sec'] > 0
    df['Has_Only_Ringing'] = (df['Ringing_sec'] > 0) & (df['Talking_sec'] == 0)
    df['No_Duration'] = (df['Ringing_sec'] == 0) & (df['Talking_sec'] == 0)
    
    # Categorizzazione corretta basata sui dati reali
    df['Real_Conversation'] = (df['Status_clean'] == 'answered') & (df['Talking_sec'] > 0)
    df['Likely_Abandoned'] = (df['Status_clean'] == 'answered') & (df['Talking_sec'] == 0)
    df['Other_Status'] = df['Status_clean'] != 'answered'
    
    # Considera come trasferiti quelli con activity details che contengono "transfer" o "forward"
    if 'Call Activity Details' in df.columns:
        df['Is_Transferred'] = df['Call Activity Details'].str.lower().str.contains("transfer|forward", na=False)
        df['Ended_By_Caller'] = df['Call Activity Details'].str.lower().str.contains("ended by.*\(", na=False)
    else:
        df['Is_Transferred'] = False
        df['Ended_By_Caller'] = False

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
        
        # ANALISI AVANZATA DEGLI STATUS
        st.subheader("🔍 Analisi Dettagliata degli Status")
        
        # Mostra tutti gli status unici trovati nel dataset
        unique_statuses = df['Status'].value_counts()
        st.write("**Status trovati nel dataset:**")
        status_df = pd.DataFrame({
            'Status': unique_statuses.index,
            'Conteggio': unique_statuses.values,
            'Percentuale': (unique_statuses.values / len(df) * 100).round(2)
        })
        st.dataframe(status_df)
        
        # Analisi chiamate "Answered" ma senza conversazione
        answered_no_talk = df[(df['Status_clean'] == 'answered') & (df['Talking_sec'] == 0)]
        st.write(f"🔍 **Chiamate 'Answered' ma senza conversazione**: {len(answered_no_talk)} ({len(answered_no_talk)/len(df)*100:.1f}%)")
        st.write("*Queste sono chiamate che il sistema ha risposto ma senza tempo di conversazione - probabilmente abbandonate dal chiamante*")
        
        # Distribuzione durate per chiamate "answered"
        answered_calls = df[df['Status_clean'] == 'answered']
