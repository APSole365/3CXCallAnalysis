import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="3CX Call Analyzer Pro", layout="wide")
st.title("📞 3CX Call Log Analyzer – Versione Aggiornata 2025")

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
        df['Start'] = df['Call Time']
        df['End'] = df['Start'] + pd.to_timedelta(df['Ringing_sec'] + df['Talking_sec'], unit='s')

    df['Hour'] = df['Call Time'].dt.hour
    df['Date'] = df['Call Time'].dt.date
    
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

    df['Status_clean'] = df['Status'].str.lower()
    
    # Gestione del campo Direction per identificare trasferimenti
    df['Is_Internal'] = df['Direction'].str.lower() == 'internal'
    df['Is_Inbound'] = df['Direction'].str.lower() == 'inbound' 
    df['Is_Outbound'] = df['Direction'].str.lower() == 'outbound'
    
    # Considera come trasferiti quelli con activity details che contengono "transfer" o "forward"
    if 'Call Activity Details' in df.columns:
        df['Is_Transferred'] = df['Call Activity Details'].str.lower().str.contains("transfer|forward", na=False)
    else:
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
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_calls = len(df)
        answered_calls = (df['Status_clean'] == 'answered').sum()
        missed_calls = (df['Status_clean'] == 'missed').sum()
        internal_calls = df['Is_Internal'].sum()
        transferred_calls = df['Is_Transferred'].sum()
        
        col1.metric("Totale Chiamate", total_calls)
        col2.metric("Chiamate Risposte", answered_calls)
        col3.metric("Chiamate Perse", missed_calls)
        col4.metric("Chiamate Interne", internal_calls)
        col5.metric("Chiamate Trasferite", transferred_calls)

        # Statistiche aggiuntive
        st.subheader("📊 Analisi per Direzione")
        direction_counts = df['Direction'].value_counts()
        fig_direction = px.pie(values=direction_counts.values, names=direction_counts.index, 
                              title="Distribuzione per tipo di chiamata")
        st.plotly_chart(fig_direction, use_container_width=True)

        st.subheader("👥 Analisi per Utente")
        unique_users = sorted(df['User'].unique())
        selected_users = st.multiselect("Filtra per utente (From)", options=unique_users, default=None)
        user_df = df[df['User'].isin(selected_users)] if selected_users else df

        st.subheader("🕐 Analisi per Fascia Oraria")
        hour_range = st.slider("Seleziona fascia oraria", 0, 23, (0, 23))
        filtered_df = user_df[(user_df['Hour'] >= hour_range[0]) & (user_df['Hour'] <= hour_range[1])]

        if filtered_df.empty:
            st.warning("⚠️ Nessuna chiamata trovata nella fascia oraria selezionata.")
        else:
            # Metriche per i dati filtrati
            st.write(f"**Chiamate nella selezione**: {len(filtered_df)}")
            
            concurrency_df = calculate_concurrency(filtered_df)
            
            if not concurrency_df.empty:
                peak = concurrency_df['Concurrent Calls'].max()
                mean = concurrency_df['Concurrent Calls'].mean()

                col1, col2 = st.columns(2)
                col1.metric("Picco chiamate contemporanee", peak)
                col2.metric("Media chiamate contemporanee", f"{mean:.2f}")

                fig = px.line(concurrency_df, x='Time', y='Concurrent Calls', 
                             title='Chiamate contemporanee nel tempo')
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("📊 Chiamate per Ora del Giorno")
            hourly_counts = filtered_df.groupby('Hour').size()
            fig2 = px.bar(hourly_counts, x=hourly_counts.index, y=hourly_counts.values,
                         labels={'x': 'Ora del giorno', 'y': 'Numero chiamate'},
                         title='Distribuzione chiamate per ora')
            st.plotly_chart(fig2, use_container_width=True)

            # Analisi durata chiamate
            st.subheader("⏱️ Analisi Durata Chiamate")
            avg_talking = filtered_df['Talking_sec'].mean()
            avg_ringing = filtered_df['Ringing_sec'].mean()
            
            col1, col2 = st.columns(2)
            col1.metric("Durata media conversazione", f"{avg_talking:.0f} sec")
            col2.metric("Tempo medio di risposta", f"{avg_ringing:.0f} sec")

            # Top utenti per numero di chiamate
            st.subheader("🏆 Top Utenti per Chiamate")
            user_stats = filtered_df.groupby('User').agg({
                'Call ID': 'count',
                'Talking_sec': 'mean',
                'Status_clean': lambda x: (x == 'answered').sum()
            }).round(2)
            user_stats.columns = ['Num_Chiamate', 'Durata_Media_Sec', 'Chiamate_Risposte']
            user_stats = user_stats.sort_values('Num_Chiamate', ascending=False).head(10)
            st.dataframe(user_stats)

            st.subheader("📋 Dati filtrati")
            with st.expander("Mostra tabella dettagliata"):
                # Mostra le colonne più rilevanti
                display_columns = ['Call Time', 'From', 'To', 'Direction', 'Status', 'Ringing', 'Talking']
                if 'Call Activity Details' in filtered_df.columns:
                    display_columns.append('Call Activity Details')
                
                st.dataframe(filtered_df[display_columns])

            st.subheader("⬇️ Esporta i dati")
            csv_export = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Scarica CSV filtrato",
                data=csv_export,
                file_name=f"3cx_analisi_filtrati_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione del file: {str(e)}")
        st.write("**Dettagli errore per debug:**")
        st.code(str(e))
        st.write("**Suggerimenti per risolvere il problema:**")
        st.write("1. Verifica che il file CSV sia correttamente formattato")
        st.write("2. Controlla che la colonna 'Call Time' contenga date valide")
        st.write("3. Assicurati che il file non sia danneggiato")

else:
    st.info("📁 Carica un file CSV per iniziare l'analisi.")
    st.write("**Formato CSV supportato (nuovo formato 3CX 2025):**")
    st.write("- **Call Time**: data e ora della chiamata (formato ISO: 2025-07-25T11:41:48)")
    st.write("- **From**: utente che effettua la chiamata")
    st.write("- **To**: destinatario della chiamata") 
    st.write("- **Direction**: direzione (Internal, Inbound, Outbound)")
    st.write("- **Status**: stato della chiamata (Answered, Missed, etc.)")
    st.write("- **Ringing** e **Talking**: durata in formato HH:MM:SS")
    
    st.write("**Nuove funzionalità:**")
    st.write("✅ Supporto per il nuovo formato CSV di 3CX 2025")
    st.write("✅ Analisi per direzione chiamata (Interna/In entrata/In uscita)")
    st.write("✅ Statistiche utenti con durata media e chiamate risposte")
    st.write("✅ Gestione automatica formato data ISO")
