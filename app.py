import streamlit as st
from supabase import create_client, Client
import os
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Compta Sénégal", page_icon="🇸🇳", layout="wide")

# --- 🔐 AUTHENTIFICATION PAR MOT DE PASSE ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 Compta Sénégal - Accès Sécurisé")
        st.markdown("### Veuillez entrer le mot de passe pour accéder à l'application.")
        password = st.text_input("Mot de passe", type="password")
        if st.button("🔓 Se connecter", type="primary"):
            # ⚠️ CHANGEZ CE MOT DE PASSE par celui que vous voulez
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.success("✅ Connexion réussie !")
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect")
        st.stop()  # Bloque le reste de l'app tant que non connecté
    
    # Bouton de déconnexion dans la barre latérale
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.authenticated = False
        st.rerun()

# Appeler la vérification AU TOUT DÉBUT
check_password()

# --- Connexion à Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- MAPPING COMPTABLE OHADA ---
PAIEMENTS = {
    "Espèces (Caisse)": "530000",
    "Virement Bancaire": "512000",
    "Mobile Money (Wave/OM)": "512500"
}

MOTIFS_RECETTE = {
    "Vente de marchandises": "701000",
    "Prestation de service": "706000",
    "Remboursement / Avance client": "411000"
}

MOTIFS_DEPENSE = {
    "Achat de marchandises": "601000",
    "Loyer / Factures": "613000",
    "Transport / Livraison": "624000",
    "Autre dépense": "658000"
}

# --- TITRE ---
st.title("📱 Ma Comptabilité")
st.sidebar.success(f"✅ Connecté en tant qu'administrateur")
st.markdown("Saisissez vos opérations simplement. La comptabilité en partie double est gérée automatiquement.")

# --- FORMULAIRE DE SAISIE ---
with st.form("saisie_operation"):
    col1, col2 = st.columns(2)
    with col1:
        type_op = st.radio("Type d'opération", ["💰 J'ai REÇU (Recette)", "💸 J'ai DÉPENSÉ (Dépense)"])
    with col2:
        montant = st.number_input("Montant (FCFA)", min_value=0, step=100, format="%d")
    
    if "REÇU" in type_op:
        motif_dict = MOTIFS_RECETTE
        options_motif = list(motif_dict.keys())
    else:
        motif_dict = MOTIFS_DEPENSE
        options_motif = list(motif_dict.keys())
        
    motif_choisi = st.selectbox("Motif de l'opération", options_motif)
    paiement_choisi = st.selectbox("Mode de paiement / Encaissement", list(PAIEMENTS.keys()))
    
    soumis = st.form_submit_button("✅ ENREGISTRER L'OPÉRATION", use_container_width=True, type="primary")

    if soumis:
        if montant <= 0:
            st.error("Le montant doit être supérieur à 0.")
        else:
            try:
                if "REÇU" in type_op:
                    cpt_debit = PAIEMENTS[paiement_choisi]
                    cpt_credit = motif_dict[motif_choisi]
                else:
                    cpt_debit = motif_dict[motif_choisi]
                    cpt_credit = PAIEMENTS[paiement_choisi]

                data = {
                    "type_operation": "Recette" if "REÇU" in type_op else "Depense",
                    "motif": motif_choisi,
                    "mode_paiement": paiement_choisi,
                    "montant": int(montant),
                    "compte_debit": cpt_debit,
                    "compte_credit": cpt_credit
                }
                
                response = supabase.table("transactions").insert(data).execute()
                
                if response.data:
                    st.success(f"✅ Opération de {montant:,.0f} FCFA enregistrée avec succès !")
                    st.rerun()
                else:
                    st.error("Erreur lors de la sauvegarde.")
            except Exception as e:
                st.error(f"Une erreur est survenue : {e}")

# --- RÉCUPÉRATION DES DONNÉES ---
try:
    response = supabase.table("transactions").select("*").order("date_creation", desc=True).execute()
    all_data = response.data
    
    if all_data:
        df = pd.DataFrame(all_data)
        df['date_creation'] = pd.to_datetime(df['date_creation'])
        
        # --- GRAPHIQUE DE TRÉSORERIE ---
        st.markdown("---")
        st.subheader("📈 Évolution de la Trésorerie")
        
        mode_affichage = st.radio(
            "Afficher par :",
            ["📊 Chaque opération (détaillé)", "📅 Par jour (synthétique)"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        if mode_affichage == "📊 Chaque opération (détaillé)":
            df_detail = df.sort_values('date_creation').copy()
            df_detail['Flux'] = df_detail.apply(
                lambda row: row['montant'] if row['type_operation'] == 'Recette' else -row['montant'],
                axis=1
            )
            df_detail['Trésorerie cumulée'] = df_detail['Flux'].cumsum()
            
            chart_data = df_detail.set_index('date_creation')[['Trésorerie cumulée']]
            st.line_chart(chart_data, color="#0068c9", height=350, use_container_width=True)
            
            with st.expander("📋 Voir le détail de chaque opération"):
                for _, row in df_detail.iterrows():
                    flux = row['montant'] if row['type_operation'] == 'Recette' else -row['montant']
                    emoji = "💰" if flux > 0 else "💸"
                    st.write(
                        f"{emoji} **{row['date_creation'].strftime('%d/%m/%Y %H:%M')}** | "
                        f"{row['motif']} | {flux:+,.0f} FCFA | "
                        f"**Solde: {row['Trésorerie cumulée']:,.0f} FCFA**".replace(",", " ")
                    )
        else:
            df['date_jour'] = df['date_creation'].dt.date
            tresorerie_jour = df.groupby('date_jour').apply(
                lambda x: x[x['type_operation'] == 'Recette']['montant'].sum() - 
                          x[x['type_operation'] == 'Depense']['montant'].sum()
            ).reset_index()
            tresorerie_jour.columns = ['Date', 'Flux du jour']
            tresorerie_jour['Trésorerie cumulée'] = tresorerie_jour['Flux du jour'].cumsum()
            st.line_chart(tresorerie_jour.set_index('Date')['Trésorerie cumulée'], color="#0068c9", height=350, use_container_width=True)
        
        # KPIs
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        total_recettes = df[df['type_operation'] == 'Recette']['montant'].sum()
        total_depenses = df[df['type_operation'] == 'Depense']['montant'].sum()
        solde_actuel = total_recettes - total_depenses
        
        with col1:
            st.metric("💰 Recettes totales", f"{total_recettes:,.0f} FCFA".replace(",", " "))
        with col2:
            st.metric("💸 Dépenses totales", f"{total_depenses:,.0f} FCFA".replace(",", " "))
        with col3:
            st.metric("📊 Solde actuel", f"{solde_actuel:,.0f} FCFA".replace(",", " "))
        
        # Historique
        st.markdown("---")
        st.subheader("📊 Historique des opérations")
        for _, row in df.head(20).iterrows():
            date_str = row['date_creation'].strftime("%d/%m/%Y %H:%M")
            st.markdown(
                f"**{date_str}** | {row['type_operation']} | **{row['motif']}** ({row['mode_paiement']}) | "
                f"**{row['montant']:,.0f} FCFA** | *(D: {row['compte_debit']} / C: {row['compte_credit']})*"
            )
        
        # Export CSV
        st.markdown("---")
        st.subheader("📥 Export des données")
        df_export = df.copy()
        df_export['date_creation'] = df_export['date_creation'].dt.strftime("%d/%m/%Y %H:%M")
        df_export = df_export.rename(columns={
            'date_creation': 'Date', 'type_operation': 'Type', 'motif': 'Motif',
            'mode_paiement': 'Mode de paiement', 'montant': 'Montant (FCFA)',
            'compte_debit': 'Compte Débit', 'compte_credit': 'Compte Crédit'
        })
        df_export = df_export[['Date', 'Type', 'Motif', 'Mode de paiement', 'Montant (FCFA)', 'Compte Débit', 'Compte Crédit']]
        csv = df_export.to_csv(index=False, sep=';', encoding='utf-8-sig')
        
        st.download_button(
            label=f"📥 Télécharger l'historique complet ({len(df)} opérations)",
            data=csv,
            file_name=f"compta_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("Aucune opération enregistrée pour le moment.")
        
except Exception as e:
    st.warning(f"Impossible de charger les données : {e}")