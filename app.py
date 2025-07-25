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
        
        # DEBUG: Mostra le prime righe con status non-answered
        st.subheader("🐛 DEBUG: Analisi Status Non-Answered")
        non_answered_debug = df[df['Status_clean'] != 'answered']
        st.write(f"**Trovate {len(non_answered_debug)} chiamate con status non-answered**")
        
        if len(non_answered_debug) > 0:
            st.write("**Primi 10 esempi di chiamate non-answered:**")
            debug_cols = ['Call Time', 'From', 'To', 'Direction', 'Status', 'Status_clean', 'Ringing', 'Talking']
            if 'Call Activity Details' in non_answered_debug.columns:
                debug_cols.append('Call Activity Details')
            st.dataframe(non_answered_debug[debug_cols].head(10))
            
            # Mostra i valori unici degli status
            st.write("**Status originali unici (non-answered):**")
            unique_non_answered = non_answered_debug['Status'].value_counts()
            st.write(unique_non_answered)
            
            st.write("**Status_clean unici (non-answered):**")
            unique_clean_non_answered = non_answered_debug['Status_clean'].value_counts()
            st.write(unique_clean_non_answered)
            
            # Verifica se ci sono valori null
            st.write("**Verifica valori null negli status:**")
            st.write(f"Status null: {non_answered_debug['Status'].isnull().sum()}")
            st.write(f"Status vuoti: {(non_answered_debug['Status'] == '').sum()}")
        else:
            st.write("⚠️ Strano: il conteggio dice 2348 ma il filtro non trova niente!")
            st.write("Verifichiamo la colonna Status...")
            st.write("**Tutti gli status nel dataset:**")
            st.write(df['Status'].value_counts(dropna=False))
        
        # ANALISI APPROFONDITA DEI NON-ANSWERED
        non_answered = df[df['Status_clean'] != 'answered']
        if len(non_answered) > 0:
            st.subheader("🔍 APPROFONDIMENTO: Chiamate NON-Answered")
            st.write(f"**Totale chiamate non-answered: {len(non_answered)} ({len(non_answered)/len(df)*100:.1f}%)**")
            
            # Status dettagliato per i non-answered
            non_answered_status = non_answered['Status'].value_counts()
            st.write("**Breakdown dettagliato degli status non-answered:**")
            non_answered_df = pd.DataFrame({
                'Status': non_answered_status.index,
                'Conteggio': non_answered_status.values,
                'Percentuale_del_Totale': (non_answered_status.values / len(df) * 100).round(2),
                'Percentuale_dei_NonAnswered': (non_answered_status.values / len(non_answered) * 100).round(2)
            })
            st.dataframe(non_answered_df)
            
            # Grafico a barre per i non-answered
            if len(non_answered_status) > 0:
                fig_non_answered = px.bar(non_answered_df, x='Status', y='Conteggio',
                                        title='Distribuzione degli status non-answered',
                                        labels={'Status': 'Tipo di Status', 'Conteggio': 'Numero chiamate'})
                fig_non_answered.update_xaxes(tickangle=45)
                st.plotly_chart(fig_non_answered, use_container_width=True)
            
            # Analisi durate per i non-answered
            st.write("**Analisi durate per chiamate non-answered:**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Con tempo di squillo", (non_answered['Ringing_sec'] > 0).sum())
            col2.metric("Con tempo di conversazione", (non_answered['Talking_sec'] > 0).sum())
            col3.metric("Senza durata", ((non_answered['Ringing_sec'] == 0) & (non_answered['Talking_sec'] == 0)).sum())
            
            # Analisi per direzione dei non-answered
            non_answered_by_direction = non_answered.groupby(['Direction', 'Status']).size().reset_index(name='Count')
            if len(non_answered_by_direction) > 0:
                fig_direction_status = px.bar(non_answered_by_direction, x='Direction', y='Count', color='Status',
                                            title='Chiamate non-answered per direzione e status',
                                            barmode='stack')
                st.plotly_chart(fig_direction_status, use_container_width=True)
            
            # Campione di chiamate non-answered per analisi manuale
            st.write("**Campione di chiamate non-answered (prime 10 per ogni status):**")
            sample_non_answered = pd.DataFrame()
            for status in non_answered['Status'].unique()[:5]:  # Prime 5 tipologie
                status_sample = non_answered[non_answered['Status'] == status].head(10)
                sample_non_answered = pd.concat([sample_non_answered, status_sample])
            
            if not sample_non_answered.empty:
                display_cols = ['Call Time', 'From', 'To', 'Direction', 'Status', 'Ringing', 'Talking']
                if 'Call Activity Details' in sample_non_answered.columns:
                    display_cols.append('Call Activity Details')
                st.dataframe(sample_non_answered[display_cols])
        
        # Analisi chiamate "Answered" ma senza conversazione
        answered_no_talk = df[(df['Status_clean'] == 'answered') & (df['Talking_sec'] == 0)]
        st.write(f"🔍 **Chiamate 'Answered' ma senza conversazione**: {len(answered_no_talk)} ({len(answered_no_talk)/len(df)*100:.1f}%)")
        st.write("*Queste sono chiamate che il sistema ha risposto ma senza tempo di conversazione - probabilmente abbandonate dal chiamante*")
        
        # Distribuzione durate per chiamate "answered"
        answered_calls = df[df['Status_clean'] == 'answered']
        if len(answered_calls) > 0:
            fig_duration = px.histogram(answered_calls, x='Talking_sec', 
                                      title='Distribuzione durata conversazioni (chiamate Answered)',
                                      nbins=50, 
                                      labels={'Talking_sec': 'Durata conversazione (secondi)', 'count': 'Numero chiamate'})
            st.plotly_chart(fig_duration, use_container_width=True)
        
        st.subheader("📈 Statistiche Generali Avanzate")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        total_calls = len(df)
        answered_calls_count = (df['Status_clean'] == 'answered').sum()
        real_conversations = df['Real_Conversation'].sum()
        likely_abandoned = df['Likely_Abandoned'].sum()
        other_status = df['Other_Status'].sum()
        transferred_calls = df['Is_Transferred'].sum()
        
        col1.metric("Totale Chiamate", total_calls)
        col2.metric("Status 'Answered'", answered_calls_count)
        col3.metric("Conversazioni Reali", real_conversations)
        col4.metric("Abbandonate (0 sec talking)", likely_abandoned)
        col5.metric("Altri Status", other_status)
        col6.metric("Trasferite", transferred_calls)
        
        # BREAKDOWN DETTAGLIATO
        st.subheader("📊 Breakdown Dettagliato delle chiamate")
        
        breakdown_data = {
            'Categoria': [
                'Conversazioni reali (answered + talking > 0)',
                'Answered ma senza conversazione (0 sec talking)',
                'Altri status (non answered)',
                'TOTALE'
            ],
            'Conteggio': [
                real_conversations,
                likely_abandoned,
                other_status,
                total_calls
            ]
        }
        
        breakdown_df = pd.DataFrame(breakdown_data)
        breakdown_df['Percentuale'] = (breakdown_df['Conteggio'] / total_calls * 100).round(1)
        
        st.dataframe(breakdown_df)
        
        # Grafico a torta del breakdown
        fig_pie = px.pie(breakdown_df[:-1], values='Conteggio', names='Categoria', 
                        title='Distribuzione dettagliata delle chiamate')
        st.plotly_chart(fig_pie, use_container_width=True)

        # ANALISI PER DIREZIONE
        st.subheader("📊 Analisi per Direzione")
        direction_stats = df.groupby('Direction').agg({
            'Call ID': 'count',
            'Real_Conversation': 'sum',
            'Talking_sec': 'mean',
            'Ringing_sec': 'mean'
        }).round(2)
        direction_stats.columns = ['Totale', 'Conversazioni_Reali', 'Durata_Media_Talking', 'Durata_Media_Ringing']
        direction_stats['Tasso_Conversazione_%'] = (direction_stats['Conversazioni_Reali'] / direction_stats['Totale'] * 100).round(1)
        st.dataframe(direction_stats)

        # Distribuzione per direzione
        direction_counts = df['Direction'].value_counts()
        fig_direction = px.pie(values=direction_counts.values, names=direction_counts.index, 
                              title="Distribuzione per tipo di chiamata")
        st.plotly_chart(fig_direction, use_container_width=True)

        # ANALISI TEMPORALE AVANZATA
        st.subheader("📅 Analisi Temporale Avanzata")
        
        # Filtri temporali
        col1, col2 = st.columns(2)
        with col1:
            date_range = st.date_input("Seleziona periodo", 
                                     value=[df['Date'].min(), df['Date'].max()],
                                     min_value=df['Date'].min(),
                                     max_value=df['Date'].max())
        with col2:
            selected_directions = st.multiselect("Filtra per direzione", 
                                                options=df['Direction'].unique(),
                                                default=df['Direction'].unique())
        
        # Applica filtri
        if len(date_range) == 2:
            mask = (df['Date'] >= date_range[0]) & (df['Date'] <= date_range[1])
            filtered_df = df[mask]
        else:
            filtered_df = df.copy()
            
        filtered_df = filtered_df[filtered_df['Direction'].isin(selected_directions)]

        st.subheader("👥 Analisi per Utente")
        unique_users = sorted(df['User'].unique())
        selected_users = st.multiselect("Filtra per utente (From)", options=unique_users, default=None)
        if selected_users:
            filtered_df = filtered_df[filtered_df['User'].isin(selected_users)]

        st.subheader("🕐 Analisi per Fascia Oraria")
        hour_range = st.slider("Seleziona fascia oraria", 0, 23, (0, 23))
        filtered_df = filtered_df[(filtered_df['Hour'] >= hour_range[0]) & (filtered_df['Hour'] <= hour_range[1])]

        if filtered_df.empty:
            st.warning("⚠️ Nessuna chiamata trovata con i filtri selezionati.")
        else:
            # Metriche per i dati filtrati
            st.write(f"**Chiamate nella selezione**: {len(filtered_df)}")
            
            # Analisi pattern giornalieri
            daily_stats = filtered_df.groupby('DayOfWeek').agg({
                'Call ID': 'count',
                'Real_Conversation': 'sum',
                'Talking_sec': 'mean'
            }).round(2)
            daily_stats.columns = ['Totale_Chiamate', 'Conversazioni', 'Durata_Media']
            
            # Riordina i giorni della settimana
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            daily_stats = daily_stats.reindex([d for d in day_order if d in daily_stats.index])
            
            st.subheader("📊 Pattern Settimanali")
            st.dataframe(daily_stats)
            
            fig_weekly = px.bar(daily_stats.reset_index(), x='DayOfWeek', y='Totale_Chiamate',
                              title='Chiamate per giorno della settimana')
            st.plotly_chart(fig_weekly, use_container_width=True)
            
            # Concorrenza
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
            hourly_stats = filtered_df.groupby('Hour').agg({
                'Call ID': 'count',
                'Real_Conversation': 'sum',
                'Talking_sec': 'mean'
            }).round(2)
            
            fig2 = px.bar(hourly_stats.reset_index(), x='Hour', y='Call ID',
                         labels={'Hour': 'Ora del giorno', 'Call ID': 'Numero chiamate'},
                         title='Distribuzione chiamate per ora')
            st.plotly_chart(fig2, use_container_width=True)

            # Analisi durata chiamate dettagliata
            st.subheader("⏱️ Analisi Durata Chiamate Dettagliata")
            
            conversations_only = filtered_df[filtered_df['Real_Conversation']]
            if len(conversations_only) > 0:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Conversazioni totali", len(conversations_only))
                col2.metric("Durata media", f"{conversations_only['Talking_sec'].mean():.0f} sec")
                col3.metric("Durata mediana", f"{conversations_only['Talking_sec'].median():.0f} sec")
                col4.metric("Durata massima", f"{conversations_only['Talking_sec'].max():.0f} sec")
                
                # Distribuzione durate
                fig_talk_dist = px.histogram(conversations_only, x='Talking_sec',
                                           title='Distribuzione durata conversazioni',
                                           nbins=30,
                                           labels={'Talking_sec': 'Durata (secondi)'})
                st.plotly_chart(fig_talk_dist, use_container_width=True)

            # Top utenti DETTAGLIATO
            st.subheader("🏆 Top Utenti - Analisi Dettagliata")
            user_detailed_stats = filtered_df.groupby('User').agg({
                'Call ID': 'count',
                'Real_Conversation': 'sum',
                'Talking_sec': ['mean', 'sum'],
                'Ringing_sec': 'mean',
                'Is_Internal': 'sum',
                'Is_Inbound': 'sum',
                'Is_Outbound': 'sum'
            }).round(2)
            
            # Flatten column names
            user_detailed_stats.columns = [
                'Totale_Chiamate', 'Conversazioni_Reali', 'Durata_Media_Sec', 'Durata_Totale_Sec', 
                'Tempo_Risposta_Medio', 'Chiamate_Interne', 'Chiamate_In_Entrata', 'Chiamate_In_Uscita'
            ]
            
            user_detailed_stats['Tasso_Risposta_%'] = (
                user_detailed_stats['Conversazioni_Reali'] / user_detailed_stats['Totale_Chiamate'] * 100
            ).round(1)
            
            user_detailed_stats['Durata_Totale_Min'] = (user_detailed_stats['Durata_Totale_Sec'] / 60).round(1)
            
            user_detailed_stats = user_detailed_stats.sort_values('Totale_Chiamate', ascending=False).head(15)
            st.dataframe(user_detailed_stats)

            # CALL ACTIVITY DETAILS ANALYSIS
            if 'Call Activity Details' in df.columns:
                st.subheader("📝 Analisi Call Activity Details")
                activity_analysis = df['Call Activity Details'].value_counts().head(10)
                st.write("**Top 10 Activity Details:**")
                st.dataframe(activity_analysis)

            st.subheader("📋 Dati filtrati")
            with st.expander("Mostra tabella dettagliata"):
                display_columns = ['Call Time', 'From', 'To', 'Direction', 'Status', 'Ringing', 'Talking', 'Real_Conversation']
                if 'Call Activity Details' in filtered_df.columns:
                    display_columns.append('Call Activity Details')
                
                st.dataframe(filtered_df[display_columns])

            st.subheader("⬇️ Esporta i dati")
            
            col1, col2 = st.columns(2)
            with col1:
                csv_export = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Scarica CSV filtrato",
                    data=csv_export,
                    file_name=f"3cx_analisi_filtrati_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Export del breakdown dettagliato
                breakdown_export = breakdown_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Scarica Breakdown Dettagliato",
                    data=breakdown_export,
                    file_name=f"3cx_breakdown_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
            
    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione del file: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.write("**Suggerimenti per risolvere il problema:**")
        st.write("1. Verifica che il file CSV sia correttamente formattato")
        st.write("2. Controlla che la colonna 'Call Time' contenga date valide")
        st.write("3. Assicurati che il file non sia danneggiato")

else:
    st.info("📁 Carica un file CSV per iniziare l'analisi avanzata.")
    st.write("**🚀 Funzionalità di analisi corrette:**")
    st.write("✅ **Breakdown accurato**: Conversazioni reali vs abbandonate vs altri status")
    st.write("✅ **Nessuna supposizione**: Solo dati reali dal CSV")
    st.write("✅ **Tutte le durate valide**: 5 sec o 500 sec = conversazioni reali")
    st.write("✅ **Analisi status dettagliata**: Tutti gli status trovati nel tuo CSV")
    st.write("✅ **Metriche utente precise**: Basate sui dati reali")
    st.write("✅ **Filtri multipli**: Periodo, direzione, utente, ora")
    
    st.write("**📋 Formato CSV supportato:**")
    st.write("- **Call Time**: 2025-07-25T11:41:48")
    st.write("- **From/To**: Utenti con formato 'Nome (Numero)'") 
    st.write("- **Direction**: Internal/Inbound/Outbound")
    st.write("- **Status**: Answered/Missed/etc.")
    st.write("- **Talking/Ringing**: Durata HH:MM:SS")
    st.write("- **Call Activity Details**: Dettagli opzionali")
