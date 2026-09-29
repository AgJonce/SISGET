# ============================================================
# IMPORTS
# ============================================================

import os
import psycopg2
import plotly.express as pxDEF
import plotly.graph_objects as go
import sqlite3
import streamlit as st
import pandas as pd
import folium


from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.units import cm

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="SISGET - Sistema Integrado de Gestão Pública",
    page_icon="🏛️",
    layout="wide"
)


# ============================================================
# CURSOR COMPATÍVEL
# SQLITE -> POSTGRESQL
# ============================================================

class CursorSISGET:

    def __init__(
        self,
        cursor
    ):

        self._cursor = cursor
        self.lastrowid = None


    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(
        self,
        sql,
        parametros=None
    ):

        # SQLite:
        # WHERE id = ?
        #
        # PostgreSQL:
        # WHERE id = %s

        sql = sql.replace(
            "?",
            "%s"
        )


        sql_limpo = sql.strip()

        sql_upper = (
            sql_limpo.upper()
        )


        # ====================================================
        # IDENTIFICAR INSERT
        # ====================================================

        eh_insert = (
            sql_upper.startswith(
                "INSERT"
            )
        )


        # ====================================================
        # RESET
        # ====================================================

        self.lastrowid = None


        # ====================================================
        # EXECUTAR
        # ====================================================

        if parametros is None:

            self._cursor.execute(
                sql
            )

        else:

            self._cursor.execute(
                sql,
                parametros
            )


        return self


    # ========================================================
    # EXECUTEMANY
    # ========================================================

    def executemany(
        self,
        sql,
        parametros
    ):

        sql = sql.replace(
            "?",
            "%s"
        )

        return self._cursor.executemany(
            sql,
            parametros
        )


    # ========================================================
    # FETCHONE
    # ========================================================

    def fetchone(
        self
    ):

        return self._cursor.fetchone()


    # ========================================================
    # FETCHALL
    # ========================================================

    def fetchall(
        self
    ):

        return self._cursor.fetchall()


    # ========================================================
    # FETCHMANY
    # ========================================================

    def fetchmany(
        self,
        size=None
    ):

        if size is None:

            return self._cursor.fetchmany()

        return self._cursor.fetchmany(
            size
        )


    # ========================================================
    # ROWCOUNT
    # ========================================================

    @property
    def rowcount(
        self
    ):

        return self._cursor.rowcount


    # ========================================================
    # DESCRIPTION
    # ========================================================

    @property
    def description(
        self
    ):

        return self._cursor.description


    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self
    ):

        return self._cursor.close()


# ============================================================
# CONEXÃO COM POSTGRESQL / SUPABASE
# ============================================================

@st.cache_resource
def conectar_banco():

    return psycopg2.connect(

        host=st.secrets["postgres"]["host"],

        port=st.secrets["postgres"]["port"],

        dbname=st.secrets["postgres"]["dbname"],

        user=st.secrets["postgres"]["user"],

        password=st.secrets["postgres"]["password"],

        sslmode="require"
    )


conn = conectar_banco()

cursor = CursorSISGET(
    conn.cursor()
)


# ============================================================
# TESTAR CONEXÃO
# ============================================================

def testar_conexao():

    try:

        with conn.cursor() as cursor_teste:

            cursor_teste.execute(
                "SELECT 1"
            )

            resultado = (
                cursor_teste.fetchone()
            )


        return (
            resultado is not None
        )


    except Exception:

        return False


# ============================================================
# FETCH
# ============================================================

def _sisget_fetch(
    sql,
    params=()
):

    try:

        cursor.execute(
            sql,
            params
        )

        return cursor.fetchall()


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Erro ao consultar banco: {erro}"
        )

        return []


# ============================================================
# FETCH ONE
# ============================================================

def _sisget_fetchone(
    sql,
    params=()
):

    try:

        cursor.execute(
            sql,
            params
        )

        return cursor.fetchone()


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Erro ao consultar banco: {erro}"
        )

        return None


# ============================================================
# EXECUTAR / SALVAR
# ============================================================

def _sisget_salvar(
    sql,
    params=()
):

    try:

        cursor.execute(
            sql,
            params
        )

        conn.commit()

        return True


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Não foi possível salvar: {erro}"
        )

        return False


# ============================================================
# EXECUTAR COM RETORNO
# ============================================================

def _sisget_salvar_retorno(
    sql,
    params=()
):

    try:

        cursor.execute(
            sql,
            params
        )

        resultado = (
            cursor.fetchone()
        )

        conn.commit()

        return resultado


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Não foi possível salvar: {erro}"
        )

        return None


# ============================================================
# DATAFRAME
# ============================================================

def _sisget_dataframe(
    sql,
    params=()
):

    try:

        cursor.execute(
            sql,
            params
        )

        dados = (
            cursor.fetchall()
        )

        colunas = [

            descricao[0]

            for descricao
            in cursor.description

        ]


        return pd.DataFrame(
            dados,
            columns=colunas
        )


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Erro ao carregar dados: {erro}"
        )

        return pd.DataFrame()


# ============================================================
# LIMPAR ESTADO DE UM MÓDULO
# ============================================================

def sisget_limpar_estado(
    chave
):

    st.session_state[
        f"sisget_id_{chave}"
    ] = None


    st.session_state[
        f"sisget_tela_{chave}"
    ] = "principal"


# ============================================================
# VOLTAR PARA PRINCIPAL
# ============================================================

def sisget_voltar_principal(
    chave
):

    sisget_limpar_estado(
        chave
    )

    st.rerun()


# ============================================================
# VOLTAR PARA LOCALIZAR
# ============================================================

def sisget_voltar_localizar(
    chave
):

    st.session_state[
        f"sisget_id_{chave}"
    ] = None


    st.session_state[
        f"sisget_tela_{chave}"
    ] = "localizar"


    st.rerun()


# ============================================================
# CABEÇALHO PADRÃO DAS TELAS
# ============================================================

# ============================================================
# CABEÇALHO PADRÃO DAS TELAS
# BOTÃO VOLTAR
# ============================================================

def sisget_cabecalho_tela(
    titulo,
    voltar=None
):

    col1, col2 = st.columns(
        [6, 1]
    )

    # ========================================================
    # TÍTULO
    # ========================================================

    with col1:

        st.subheader(
            titulo
        )

    # ========================================================
    # BOTÃO VOLTAR
    # ========================================================

    with col2:

        if voltar is not None:

            if st.button(
                "⬅️ Voltar",
                use_container_width=True,
                key=f"btn_voltar_{titulo}"
            ):

                voltar()

    st.markdown("---")
def sisget_grid_localizar(
    df,
    chave,
    coluna_id="id",
    altura=420
):

    if df is None:

        return None


    if df.empty:

        st.info(
            "Nenhum registro encontrado."
        )

        return None


    # ========================================================
    # GRID
    # ========================================================

    gb = (
        GridOptionsBuilder
        .from_dataframe(
            df
        )
    )


    gb.configure_default_column(

        sortable=True,

        filter=True,

        resizable=True,

        floatingFilter=True
    )


    # ========================================================
    # SELEÇÃO
    # ========================================================

    gb.configure_selection(

        selection_mode="single",

        use_checkbox=False
    )


    # ========================================================
    # OCULTAR ID
    # ========================================================

    if coluna_id in df.columns:

        gb.configure_column(

            coluna_id,

            hide=True
        )


    grid_options = (
        gb.build()
    )


    # ========================================================
    # DUPLO CLIQUE
    # ========================================================

    js_duplo_clique = JsCode(
        """
        function(event) {

            event.api.deselectAll();

            event.node.setSelected(true);

        }
        """
    )


    grid_options[
        "suppressRowClickSelection"
    ] = True


    grid_options[
        "onRowDoubleClicked"
    ] = js_duplo_clique


    # ========================================================
    # EXIBIR
    # ========================================================

    resposta = AgGrid(

        df,

        gridOptions=grid_options,

        height=altura,

        fit_columns_on_grid_load=True,

        update_mode=(
            GridUpdateMode.SELECTION_CHANGED
        ),

        allow_unsafe_jscode=True,

        theme="streamlit",

        key=f"grid_{chave}"
    )


    # ========================================================
    # PEGAR SELEÇÃO
    # ========================================================

    selecionados = resposta.get(
        "selected_rows",
        []
    )


    if selecionados is None:

        return None


    # ========================================================
    # DATAFRAME
    # ========================================================

    if isinstance(
        selecionados,
        pd.DataFrame
    ):

        if selecionados.empty:

            return None


        if coluna_id not in (
            selecionados.columns
        ):

            return None


        return int(
            selecionados.iloc[
                0
            ][coluna_id]
        )


    # ========================================================
    # LIST
    # ========================================================

    if isinstance(
        selecionados,
        list
    ):

        if len(
            selecionados
        ) == 0:

            return None


        registro = (
            selecionados[0]
        )


        if isinstance(
            registro,
            dict
        ):

            valor = registro.get(
                coluna_id
            )


            if valor is not None:

                return int(
                    valor
                )


    return None


# ============================================================
# DEF PRINCIPAL PADRÃO
#
# TODOS OS MÓDULOS DO SISGET USARÃO ESSA BASE
#
# INCLUIR
# LOCALIZAR
# IMPRIMIR
#
# DUPLO CLIQUE EM LOCALIZAR -> ALTERAR
# ============================================================

# ============================================================
# DEF PRINCIPAL PADRÃO
#
# INCLUIR
# LOCALIZAR
# EXCLUIR
# IMPRIMIR
#
# DUPLO CLIQUE EM LOCALIZAR -> ALTERAR
# ============================================================

def sisget_tela_principal(

    titulo,

    chave,

    func_incluir,

    func_localizar,

    func_alterar,

    func_excluir=None,

    func_imprimir=None,

    icone="📋"
):

    chave_tela = (
        f"sisget_tela_{chave}"
    )


    chave_id = (
        f"sisget_id_{chave}"
    )


    # ========================================================
    # INICIALIZAR
    # ========================================================

    if chave_tela not in st.session_state:

        st.session_state[
            chave_tela
        ] = "principal"


    if chave_id not in st.session_state:

        st.session_state[
            chave_id
        ] = None


    tela = st.session_state[
        chave_tela
    ]


    # ========================================================
    # TÍTULO
    # ========================================================

    st.title(
        f"{icone} {titulo}"
    )


    # ========================================================
    # TELA PRINCIPAL
    # ========================================================

    if tela == "principal":

        st.markdown("---")


        col1, col2, col3, col4 = st.columns(4)


        # ====================================================
        # INCLUIR
        # ====================================================

        with col1:

            if st.button(
                "➕ Incluir",
                key=f"incluir_{chave}",
                use_container_width=True,
                type="primary"
            ):

                st.session_state[
                    chave_id
                ] = None

                st.session_state[
                    chave_tela
                ] = "incluir"

                st.rerun()


        # ====================================================
        # LOCALIZAR
        # ====================================================

        with col2:

            if st.button(
                "🔎 Localizar",
                key=f"localizar_{chave}",
                use_container_width=True
            ):

                st.session_state[
                    chave_id
                ] = None

                st.session_state[
                    chave_tela
                ] = "localizar"

                st.rerun()


        # ====================================================
        # EXCLUIR
        # ====================================================

        with col3:

            if st.button(
                "🗑️ Excluir",
                key=f"excluir_{chave}",
                use_container_width=True
            ):

                st.session_state[
                    chave_id
                ] = None

                st.session_state[
                    chave_tela
                ] = "excluir"

                st.rerun()


        # ====================================================
        # IMPRIMIR
        # ====================================================

        with col4:

            if st.button(
                "🖨️ Imprimir",
                key=f"imprimir_{chave}",
                use_container_width=True
            ):

                st.session_state[
                    chave_id
                ] = None

                st.session_state[
                    chave_tela
                ] = "imprimir"

                st.rerun()


        st.markdown("---")


    # ========================================================
    # INCLUIR
    # ========================================================

    elif tela == "incluir":

        sisget_cabecalho_tela(
            "➕ Incluir",
            voltar=lambda: sisget_voltar_principal(
                chave
            )
        )

        func_incluir()


    # ========================================================
    # LOCALIZAR
    # ========================================================

    elif tela == "localizar":

        sisget_cabecalho_tela(
            "🔎 Localizar",
            voltar=lambda: sisget_voltar_principal(
                chave
            )
        )

        st.caption(
            "Dê duplo clique em um registro para alterar."
        )


        registro_id = func_localizar()


        if registro_id:

            st.session_state[
                chave_id
            ] = registro_id

            st.session_state[
                chave_tela
            ] = "alterar"

            st.rerun()


    # ========================================================
    # ALTERAR
    # ========================================================

    elif tela == "alterar":

        registro_id = st.session_state.get(
            chave_id
        )


        if not registro_id:

            st.session_state[
                chave_tela
            ] = "localizar"

            st.rerun()


        sisget_cabecalho_tela(
            "✏️ Alterar",
            voltar=lambda: sisget_voltar_localizar(
                chave
            )
        )


        func_alterar(
            registro_id
        )


    # ========================================================
    # EXCLUIR
    # ========================================================

    elif tela == "excluir":

        sisget_cabecalho_tela(
            "🗑️ Excluir",
            voltar=lambda: sisget_voltar_principal(
                chave
            )
        )


        if func_excluir:

            func_excluir()

        else:

            st.info(
                "Nenhuma rotina de exclusão configurada."
            )


    # ========================================================
    # IMPRIMIR
    # ========================================================

    elif tela == "imprimir":

        sisget_cabecalho_tela(
            "🖨️ Imprimir",
            voltar=lambda: sisget_voltar_principal(
                chave
            )
        )


        if func_imprimir:

            func_imprimir()

        else:

            st.info(
                "Nenhum relatório configurado."
            )
def modulo_em_desenvolvimento(
    nome,
    icone="🚧"
):

    st.title(
        f"{icone} {nome}"
    )


    st.info(
        "Módulo preparado na estrutura do SISGET."
    )


# ============================================================
# TELA INICIAL DO SISGET
# ============================================================

def tela_inicio():

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.title(
        "🏛️ SISGET"
    )

    st.subheader(
        "Sistema Integrado de Gestão Pública"
    )

    st.caption(
        "Gestão, treinamento, legislação e suporte em um único ambiente."
    )

    st.markdown("---")


    # ========================================================
    # CONTROLE DE SEÇÃO
    # ========================================================

    if "home_secao" not in st.session_state:

        st.session_state[
            "home_secao"
        ] = "inicio"


    secao = st.session_state[
        "home_secao"
    ]


    # ========================================================
    # CHATBOT
    # ========================================================

    if secao == "chatbot":

        if st.button(
            "⬅️ Voltar para Início",
            key="voltar_home_chatbot"
        ):

            st.session_state[
                "home_secao"
            ] = "inicio"

            st.rerun()


        st.markdown("---")

        modulo_assistente()

        return


    # ========================================================
    # TREINAMENTO
    # ========================================================

    if secao == "treinamento":

        if st.button(
            "⬅️ Voltar para Início",
            key="voltar_home_treinamento"
        ):

            st.session_state[
                "home_secao"
            ] = "inicio"

            st.rerun()


        st.markdown("---")


        st.header(
            "🎓 Central de Treinamento"
        )


        treinamento = st.selectbox(
            "Selecione o módulo",
            [
                "Cadastro Básico",
                "Solicitações",
                "Planejamento",
                "SISCOM - Licitações e Compras",
                "SISCON - Contratos",
                "Contabilidade e Orçamento",
                "Almoxarifado",
                "Patrimônio",
                "SISOPB - Obras Públicas",
                "SISPRO - Problemas Urbanos",
                "SICOM / TCEMG"
            ],
            key="home_treinamento_modulo"
        )


        st.markdown("---")


        if treinamento == "Cadastro Básico":

            st.subheader(
                "🏛️ Cadastro Básico"
            )

            st.markdown(
                """
                Entidades • Órgãos • Unidades Orçamentárias •
                Unidades Administrativas • Setores • Exercícios • Organograma
                """
            )


        elif treinamento == "SISCOM - Licitações e Compras":

            st.subheader(
                "🛒 SISCOM - Licitações e Compras"
            )

            st.markdown(
                """
                Solicitações • DFD • ETP • Termo de Referência •
                Pesquisa de Preços • Licitação • Contratação Direta • Homologação
                """
            )


        elif treinamento == "Contabilidade e Orçamento":

            st.subheader(
                "📚 Contabilidade e Orçamento"
            )

            st.markdown(
                """
                Dotação • Cota • Reserva • Empenho • Liquidação •
                Ordem de Pagamento • Pagamento • Restos a Pagar
                """
            )


        else:

            st.info(
                f"🎓 O treinamento de {treinamento} será disponibilizado nesta área."
            )


        return


    # ========================================================
    # ACESSOS PRINCIPAIS
    # ========================================================

    st.subheader(
        "🚀 Acessos"
    )


    col1, col2, col3, col4 = st.columns(4)


    # ========================================================
    # SITE
    # ========================================================

    with col1:

        linha1, linha2 = st.columns(
            [1.1, 1]
        )

        with linha1:

            st.markdown(
                "### 🌐 Site"
            )

        with linha2:

            st.link_button(
                "Acessar Site",
                "https://SEU-SITE-AQUI.com.br",
                use_container_width=True
            )


        st.write(
            "Portal oficial do SISGET."
        )


    # ========================================================
    # VIDEOAULAS
    # ========================================================

    with col2:

        linha1, linha2 = st.columns(
            [1.2, 1]
        )

        with linha1:

            st.markdown(
                "### ▶️ Videoaulas"
            )

        with linha2:

            st.link_button(
                "Abrir YouTube",
                "https://www.youtube.com/@SEU_CANAL",
                use_container_width=True
            )


        st.write(
            "Canal de treinamentos."
        )


    # ========================================================
    # TREINAMENTO
    # ========================================================

    with col3:

        linha1, linha2 = st.columns(
            [1.2, 1.2]
        )

        with linha1:

            st.markdown(
                "### 🎓 Treinamento"
            )

        with linha2:

            if st.button(
                "Abrir Treinamento",
                use_container_width=True,
                key="btn_home_treinamento"
            ):

                st.session_state[
                    "home_secao"
                ] = "treinamento"

                st.rerun()


        st.write(
            "Aprenda a utilizar o SISGET."
        )


    # ========================================================
    # ASSISTENTE
    # ========================================================

    with col4:

        linha1, linha2 = st.columns(
            [1.1, 1.1]
        )

        with linha1:

            st.markdown(
                "### 🤖 Assistente"
            )

        with linha2:

            if st.button(
                "Abrir Assistente",
                use_container_width=True,
                key="btn_home_chatbot"
            ):

                st.session_state[
                    "home_secao"
                ] = "chatbot"

                st.rerun()


        st.write(
            "Suporte e dúvidas do sistema."
        )


    st.markdown("---")


    # ========================================================
    # CENTRAL DE CONHECIMENTO
    # ========================================================

    st.subheader(
        "📚 Central de Conhecimento"
    )


    aba1, aba2, aba3 = st.tabs(
        [
            "⚖️ Licitações e Contratos",
            "📊 Contabilidade Pública",
            "📘 Guias SISGET"
        ]
    )


    # ========================================================
    # LICITAÇÕES E CONTRATOS
    # ========================================================

    with aba1:

        col_lei1, col_lei2 = st.columns(2)


        with col_lei1:

            st.markdown(
                "### ⚖️ Lei nº 14.133/2021"
            )

            st.write(
                "Lei de Licitações e Contratos Administrativos."
            )

            st.link_button(
                "📖 Consultar Lei 14.133/2021",
                "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
                use_container_width=True
            )


        with col_lei2:

            st.markdown(
                "### 🏛️ TCEMG / SICOM"
            )

            st.write(
                "Informações e orientações do Tribunal de Contas."
            )

            st.link_button(
                "🏛️ Acessar TCEMG",
                "https://www.tce.mg.gov.br/",
                use_container_width=True
            )


    # ========================================================
    # CONTABILIDADE PÚBLICA
    # ========================================================

    with aba2:

        col_cont1, col_cont2, col_cont3 = st.columns(3)


        with col_cont1:

            st.markdown(
                "### 📖 Lei 4.320/1964"
            )

            st.write(
                "Normas gerais de Direito Financeiro."
            )

            st.link_button(
                "Consultar Lei 4.320",
                "https://www.planalto.gov.br/ccivil_03/leis/l4320.htm",
                use_container_width=True
            )


        with col_cont2:

            st.markdown(
                "### 📊 LRF"
            )

            st.write(
                "Lei de Responsabilidade Fiscal."
            )

            st.link_button(
                "Consultar LC 101/2000",
                "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",
                use_container_width=True
            )


        with col_cont3:

            st.markdown(
                "### 📚 MCASP"
            )

            st.write(
                "Manual de Contabilidade Aplicada ao Setor Público."
            )


    # ========================================================
    # GUIAS SISGET
    # ========================================================

    with aba3:

        col_guia1, col_guia2, col_guia3, col_guia4 = st.columns(4)


        with col_guia1:

            st.info(
                """
                🏛️ **Cadastro Básico**

                Entidades  
                Órgãos  
                Unidades  
                Setores
                """
            )


        with col_guia2:

            st.info(
                """
                🛒 **Licitações**

                Solicitações  
                Planejamento  
                Compras  
                Licitação
                """
            )


        with col_guia3:

            st.info(
                """
                📑 **Contratos**

                Contratos  
                Aditivos  
                Responsáveis  
                Execução
                """
            )


        with col_guia4:

            st.info(
                """
                💰 **Contabilidade**

                Reserva  
                Empenho  
                Liquidação  
                Pagamento
                """
            )


    # ========================================================
    # RODAPÉ
    # ========================================================

    st.markdown("---")

    st.caption(
        "SISGET - Sistema Integrado de Gestão Pública"
    )
def cadastro_basico():

    st.title(
        "🏛️ Cadastro Básico"
    )

    st.caption(
        "Estrutura administrativa e organizacional do SISGET."
    )

    st.markdown("---")


    # ========================================================
    # CONTROLE DO SUBMÓDULO
    # ========================================================

    if "cadastro_basico_modulo" not in st.session_state:

        st.session_state[
            "cadastro_basico_modulo"
        ] = "principal"


    modulo = st.session_state[
        "cadastro_basico_modulo"
    ]


    # ========================================================
    # TELA PRINCIPAL
    # ========================================================

    if modulo == "principal":

        st.subheader(
            "📋 Selecione o cadastro"
        )

        st.write("")


        # ====================================================
        # PRIMEIRA LINHA
        # ====================================================

        col1, col2, col3 = st.columns(3)


        with col1:

            if st.button(
                "🏢 Entidades",
                use_container_width=True,
                key="btn_cb_entidades"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "entidades"

                st.rerun()


        with col2:

            if st.button(
                "🏛️ Órgãos",
                use_container_width=True,
                key="btn_cb_orgaos"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "orgaos"

                st.rerun()


        with col3:

            if st.button(
                "💼 Unidades Orçamentárias",
                use_container_width=True,
                key="btn_cb_uo"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "unidades_orcamentarias"

                st.rerun()


        # ====================================================
        # SEGUNDA LINHA
        # ====================================================

        col4, col5, col6 = st.columns(3)


        with col4:

            if st.button(
                "🏬 Unidades Administrativas",
                use_container_width=True,
                key="btn_cb_ua"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "unidades_administrativas"

                st.rerun()


        with col5:

            if st.button(
                "🧩 Setores",
                use_container_width=True,
                key="btn_cb_setores"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "setores"

                st.rerun()


        with col6:

            if st.button(
                "📅 Exercícios",
                use_container_width=True,
                key="btn_cb_exercicios"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "exercicios"

                st.rerun()


        # ====================================================
        # TERCEIRA LINHA
        # ====================================================

        col7, col8, col9 = st.columns(3)


        with col7:

            if st.button(
                "🌳 Organograma",
                use_container_width=True,
                key="btn_cb_organograma"
            ):

                st.session_state[
                    "cadastro_basico_modulo"
                ] = "organograma"

                st.rerun()


        with col8:

            st.empty()


        with col9:

            st.empty()


        st.markdown("---")


        st.info(
            "Selecione uma opção para acessar o cadastro."
        )


    # ========================================================
    # ENTIDADES
    # ========================================================

    elif modulo == "entidades":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_entidades"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_entidades()


    # ========================================================
    # ÓRGÃOS
    # ========================================================

    elif modulo == "orgaos":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_orgaos"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_orgaos()


    # ========================================================
    # UNIDADES ORÇAMENTÁRIAS
    # ========================================================

    elif modulo == "unidades_orcamentarias":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_uo"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_unidades_orcamentarias()


    # ========================================================
    # UNIDADES ADMINISTRATIVAS
    # ========================================================

    elif modulo == "unidades_administrativas":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_ua"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_unidades_administrativas()


    # ========================================================
    # SETORES
    # ========================================================

    elif modulo == "setores":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_setores"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_setores()


    # ========================================================
    # EXERCÍCIOS
    # ========================================================

    elif modulo == "exercicios":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_exercicios"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        cadastro_exercicios()


    # ========================================================
    # ORGANOGRAMA
    # ========================================================

    elif modulo == "organograma":

        if st.button(
            "⬅️ Voltar ao Cadastro Básico",
            key="voltar_cb_organograma"
        ):

            st.session_state[
                "cadastro_basico_modulo"
            ] = "principal"

            st.rerun()


        organograma_sisget()

# ============================================================
# CADASTRO DE ENTIDADES
# ============================================================

def cadastro_entidades():

    sisget_tela_principal(
        titulo="Cadastro de Entidades",
        chave="entidades",
        func_incluir=entidade_incluir,
        func_localizar=entidade_localizar,
        func_alterar=entidade_alterar,
        func_excluir=entidade_excluir,
        func_imprimir=entidade_imprimir,
        icone="🏢"
    )


# ============================================================
# ENTIDADES - EXCLUIR
# ============================================================

def entidade_excluir():

    st.subheader(
        "🗑️ Excluir Entidade"
    )

    st.warning(
        "Selecione a entidade que deseja excluir."
    )


    # ========================================================
    # CARREGAR ENTIDADES
    # ========================================================

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            nome AS "Nome",
            cnpj AS "CNPJ",
            tipo_entidade AS "Tipo",
            CASE
                WHEN ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM entidades
        ORDER BY nome
        """
    )


    if df.empty:

        st.info(
            "Nenhuma entidade cadastrada."
        )

        return


    # ========================================================
    # GRID
    # ========================================================

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_entidades",
        coluna_id="id",
        altura=420
    )


    # ========================================================
    # REGISTRO SELECIONADO
    # ========================================================

    if registro_id:

        entidade = _sisget_fetchone(
            """
            SELECT
                codigo,
                nome
            FROM entidades
            WHERE id = ?
            """,
            (
                registro_id,
            )
        )


        if not entidade:

            st.error(
                "❌ Entidade não encontrada."
            )

            return


        codigo = entidade[0]
        nome = entidade[1]


        st.markdown("---")


        st.error(
            f"⚠️ Você está prestes a excluir: "
            f"**{codigo} - {nome}**"
        )


        confirmar = st.checkbox(
            "Confirmo que desejo excluir esta entidade.",
            key=f"confirmar_exclusao_entidade_{registro_id}"
        )


        if st.button(
            "🗑️ Confirmar Exclusão",
            type="primary",
            use_container_width=True,
            key=f"confirmar_excluir_entidade_{registro_id}"
        ):

            if not confirmar:

                st.warning(
                    "⚠️ Marque a confirmação antes de excluir."
                )

                return


            try:

                cursor.execute(
                    """
                    DELETE FROM entidades
                    WHERE id = ?
                    """,
                    (
                        registro_id,
                    )
                )


                conn.commit()


                st.success(
                    "✅ Entidade excluída com sucesso!"
                )


                st.session_state[
                    "sisget_tela_entidades"
                ] = "principal"


                st.session_state[
                    "sisget_id_entidades"
                ] = None


                st.rerun()


            except Exception as erro:

                conn.rollback()

                st.error(
                    f"❌ Não foi possível excluir a entidade: {erro}"
                )

# ============================================================
# PRÓXIMO CÓDIGO DISPONÍVEL DA ENTIDADE
# ============================================================

def sisget_proximo_codigo_entidade():

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM entidades
        WHERE codigo ~ '^[0-9]+$'
        ORDER BY CAST(codigo AS INTEGER)
        """
    )

    codigos_usados = set()

    for registro in dados:

        try:

            codigos_usados.add(
                int(registro[0])
            )

        except (ValueError, TypeError):

            pass

    proximo = 1

    while proximo in codigos_usados:

        proximo += 1

    return str(proximo).zfill(3)

def entidade_incluir():

    st.subheader(
        "🏢 Dados da Entidade"
    )


    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_entidade()
    )


    st.info(
        f"🔢 Código automático: {codigo}"
    )


    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_entidade_incluir",
        clear_on_submit=True
    ):

        nome = st.text_input(
            "Nome da Entidade *",
            max_chars=200
        )


        col1, col2 = st.columns(2)


        with col1:

            cnpj = st.text_input(
                "CNPJ",
                max_chars=18,
                placeholder="00.000.000/0000-00"
            )


        with col2:

            tipo_entidade = st.selectbox(
                "Tipo de Entidade",
                [
                    "Prefeitura",
                    "Câmara",
                    "Autarquia",
                    "Fundação",
                    "Consórcio",
                    "Outro"
                ]
            )


        ativo = st.checkbox(
            "Entidade ativa",
            value=True
        )


        st.markdown("---")


        salvar = st.form_submit_button(
            "💾 Salvar",
            type="primary",
            use_container_width=True
        )


    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()

        cnpj = cnpj.strip()


        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return


        # ====================================================
        # RECALCULAR CÓDIGO NA HORA DO INSERT
        # ====================================================

        codigo = (
            sisget_proximo_codigo_entidade()
        )


        sucesso = _sisget_salvar(
            """
            INSERT INTO entidades
            (
                codigo,
                nome,
                cnpj,
                tipo_entidade,
                ativo
            )
            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                codigo,
                nome,
                cnpj if cnpj else None,
                tipo_entidade,
                ativo
            )
        )


        if sucesso:

            st.success(
                f"✅ Entidade cadastrada com sucesso! Código: {codigo}"
            )

def entidade_localizar():

    st.subheader(
        "🔎 Localizar Entidades"
    )


    # ========================================================
    # FILTROS
    # ========================================================

    col1, col2, col3 = st.columns(
        [1, 3, 1]
    )


    with col1:

        filtro_codigo = st.text_input(
            "Código",
            key="entidade_filtro_codigo"
        )


    with col2:

        filtro_nome = st.text_input(
            "Nome",
            key="entidade_filtro_nome"
        )


    with col3:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todos",
                "Ativos",
                "Inativos"
            ],
            key="entidade_filtro_situacao"
        )


    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            id,
            codigo AS "Código",
            nome AS "Nome",
            cnpj AS "CNPJ",
            tipo_entidade AS "Tipo",
            CASE
                WHEN ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM entidades
        WHERE 1 = 1
    """


    parametros = []


    # ========================================================
    # CÓDIGO
    # ========================================================

    if filtro_codigo.strip():

        sql += """
            AND codigo ILIKE ?
        """

        parametros.append(
            f"%{filtro_codigo.strip()}%"
        )


    # ========================================================
    # NOME
    # ========================================================

    if filtro_nome.strip():

        sql += """
            AND nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )


    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if filtro_situacao == "Ativos":

        sql += """
            AND ativo = TRUE
        """


    elif filtro_situacao == "Inativos":

        sql += """
            AND ativo = FALSE
        """


    sql += """
        ORDER BY nome
    """


    # ========================================================
    # DATAFRAME
    # ========================================================

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )


    if df.empty:

        st.info(
            "Nenhuma entidade encontrada."
        )

        return None


    st.caption(
        f"Registros encontrados: {len(df)}"
    )


    # ========================================================
    # GRID
    #
    # DUPLO CLIQUE -> ALTERAR
    # ========================================================

    registro_id = sisget_grid_localizar(
        df=df,
        chave="entidades",
        coluna_id="id",
        altura=420
    )


    return registro_id


# ============================================================
# ATIVAR / INATIVAR ENTIDADE
# ============================================================

def entidade_alterar_situacao(
    entidade_id,
    novo_status
):

    try:

        cursor.execute(
            """
            UPDATE entidades
            SET ativo = ?
            WHERE id = ?
            """,
            (
                novo_status,
                entidade_id
            )
        )


        conn.commit()


        if novo_status:

            st.success(
                "✅ Entidade ativada com sucesso!"
            )

        else:

            st.success(
                "✅ Entidade inativada com sucesso!"
            )


        st.session_state[
            "sisget_id_entidades"
        ] = None


        st.session_state[
            "sisget_tela_entidades"
        ] = "localizar"


        st.rerun()


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Não foi possível alterar a situação da entidade: {erro}"
        )

# ============================================================
# ENTIDADES - ALTERAR
# ============================================================

def entidade_alterar(
    entidade_id
):

    # ========================================================
    # BUSCAR ENTIDADE
    # ========================================================

    entidade = _sisget_fetchone(
        """
        SELECT
            id,
            codigo,
            nome,
            cnpj,
            tipo_entidade,
            ativo
        FROM entidades
        WHERE id = ?
        """,
        (
            entidade_id,
        )
    )


    if not entidade:

        st.error(
            "❌ Entidade não encontrada."
        )

        return


    (
        id_entidade,
        codigo_atual,
        nome_atual,
        cnpj_atual,
        tipo_atual,
        ativo_atual
    ) = entidade


    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if ativo_atual:

        st.success(
            "🟢 Situação: ATIVA"
        )

    else:

        st.warning(
            "🔴 Situação: INATIVA"
        )


    # ========================================================
    # TIPOS
    # ========================================================

    tipos = [
        "Prefeitura",
        "Câmara",
        "Autarquia",
        "Fundação",
        "Consórcio",
        "Outro"
    ]


    if tipo_atual not in tipos:

        tipos.append(
            tipo_atual
        )


    indice_tipo = tipos.index(
        tipo_atual
    )


    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_entidade_alterar_{entidade_id}"
    ):

        # ====================================================
        # CÓDIGO
        # ====================================================

        st.text_input(
            "Código",
            value=codigo_atual or "",
            disabled=True
        )


        # ====================================================
        # NOME
        # ====================================================

        nome = st.text_input(
            "Nome da Entidade *",
            value=nome_atual or "",
            max_chars=200
        )


        # ====================================================
        # CNPJ / TIPO
        # ====================================================

        col1, col2 = st.columns(2)


        with col1:

            cnpj = st.text_input(
                "CNPJ",
                value=cnpj_atual or "",
                max_chars=18
            )


        with col2:

            tipo_entidade = st.selectbox(
                "Tipo de Entidade",
                tipos,
                index=indice_tipo
            )


        st.markdown("---")


        # ====================================================
        # BOTÕES
        # ====================================================

        col1, col2, col3, col4 = st.columns(4)


        with col1:

            salvar = st.form_submit_button(
                "💾 Salvar",
                type="primary",
                use_container_width=True
            )


        # ====================================================
        # ATIVAR / INATIVAR
        # ====================================================

        with col2:

            if ativo_atual:

                alterar_status = (
                    st.form_submit_button(
                        "🚫 Inativar",
                        use_container_width=True
                    )
                )

            else:

                alterar_status = (
                    st.form_submit_button(
                        "✅ Ativar",
                        use_container_width=True
                    )
                )


        # ====================================================
        # EXCLUIR
        # ====================================================

        with col3:

            excluir = st.form_submit_button(
                "🗑️ Excluir",
                use_container_width=True
            )


        # ====================================================
        # CANCELAR
        # ====================================================

        with col4:

            cancelar = (
                st.form_submit_button(
                    "❌ Cancelar",
                    use_container_width=True
                )
            )


    # ========================================================
    # CANCELAR
    # ========================================================

    if cancelar:

        st.session_state[
            "sisget_id_entidades"
        ] = None


        st.session_state[
            "sisget_tela_entidades"
        ] = "localizar"


        st.rerun()


    # ========================================================
    # ATIVAR / INATIVAR
    # ========================================================

    if alterar_status:

        entidade_alterar_situacao(
            entidade_id,
            not ativo_atual
        )

        return


    # ========================================================
    # EXCLUIR
    # ========================================================

    if excluir:

        try:

            cursor.execute(
                """
                DELETE FROM entidades
                WHERE id = ?
                """,
                (
                    entidade_id,
                )
            )


            conn.commit()


            st.session_state[
                "sisget_id_entidades"
            ] = None


            st.session_state[
                "sisget_tela_entidades"
            ] = "localizar"


            st.success(
                "✅ Entidade excluída com sucesso!"
            )


            st.rerun()


        except Exception as erro:

            conn.rollback()

            st.error(
                f"❌ Não foi possível excluir a entidade: {erro}"
            )


        return


    # ========================================================
    # SALVAR ALTERAÇÕES
    # ========================================================

    if salvar:

        nome = nome.strip()

        cnpj = cnpj.strip()


        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return


        sucesso = _sisget_salvar(
            """
            UPDATE entidades
            SET
                nome = ?,
                cnpj = ?,
                tipo_entidade = ?
            WHERE id = ?
            """,
            (
                nome,
                cnpj if cnpj else None,
                tipo_entidade,
                entidade_id
            )
        )


        if sucesso:

            st.session_state[
                "sisget_id_entidades"
            ] = None


            st.session_state[
                "sisget_tela_entidades"
            ] = "localizar"


            st.success(
                "✅ Entidade alterada com sucesso!"
            )


            st.rerun()

def entidade_imprimir():

    st.subheader(
        "🖨️ Relatório de Entidades"
    )


    # ========================================================
    # FILTRO
    # ========================================================

    filtro = st.selectbox(
        "Situação",
        [
            "Todas",
            "Ativas",
            "Inativas"
        ],
        key="entidade_imprimir_situacao"
    )


    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            codigo,
            nome,
            cnpj,
            tipo_entidade,
            ativo
        FROM entidades
        WHERE 1 = 1
    """


    if filtro == "Ativas":

        sql += """
            AND ativo = TRUE
        """


    elif filtro == "Inativas":

        sql += """
            AND ativo = FALSE
        """


    sql += """
        ORDER BY nome
    """


    dados = _sisget_fetch(
        sql
    )


    if not dados:

        st.info(
            "Nenhuma entidade encontrada para impressão."
        )

        return


    # ========================================================
    # VISUALIZAÇÃO
    # ========================================================

    dados_visualizacao = []


    for registro in dados:

        dados_visualizacao.append({

            "Código":
                registro[0],

            "Nome":
                registro[1],

            "CNPJ":
                registro[2] or "",

            "Tipo":
                registro[3] or "",

            "Situação":
                "Ativo"
                if registro[4]
                else "Inativo"
        })


    df = pd.DataFrame(
        dados_visualizacao
    )


    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


    st.caption(
        f"Total de entidades: {len(df)}"
    )


    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="btn_pdf_entidades"
    ):

        buffer = BytesIO()


        documento = SimpleDocTemplate(

            buffer,

            pagesize=A4,

            rightMargin=1.2 * cm,

            leftMargin=1.2 * cm,

            topMargin=1.2 * cm,

            bottomMargin=1.2 * cm
        )


        estilos = getSampleStyleSheet()


        titulo_style = ParagraphStyle(

            "TituloSISGET",

            parent=estilos[
                "Heading1"
            ],

            alignment=1,

            fontSize=16,

            spaceAfter=10
        )


        subtitulo_style = ParagraphStyle(

            "SubtituloSISGET",

            parent=estilos[
                "Normal"
            ],

            alignment=1,

            fontSize=9,

            spaceAfter=15
        )


        elementos = []


        # ====================================================
        # TÍTULO
        # ====================================================

        elementos.append(

            Paragraph(
                "SISGET - Sistema Integrado de Gestão Pública",
                titulo_style
            )
        )


        elementos.append(

            Paragraph(
                "Relatório de Entidades",
                estilos["Heading2"]
            )
        )


        elementos.append(

            Paragraph(
                f"Situação: {filtro}",
                subtitulo_style
            )
        )


        elementos.append(
            Spacer(
                1,
                0.3 * cm
            )
        )


        # ====================================================
        # CABEÇALHO DA TABELA
        # ====================================================

        tabela_dados = [[

            "Código",
            "Nome",
            "CNPJ",
            "Tipo",
            "Situação"

        ]]


        # ====================================================
        # DADOS
        # ====================================================

        for registro in dados:

            tabela_dados.append([

                str(
                    registro[0] or ""
                ),

                Paragraph(
                    str(
                        registro[1] or ""
                    ),
                    estilos["Normal"]
                ),

                str(
                    registro[2] or ""
                ),

                str(
                    registro[3] or ""
                ),

                (
                    "Ativo"
                    if registro[4]
                    else "Inativo"
                )
            ])


        # ====================================================
        # TABELA
        # ====================================================

        tabela = Table(

            tabela_dados,

            colWidths=[
                2 * cm,
                6 * cm,
                4 * cm,
                3 * cm,
                2 * cm
            ],

            repeatRows=1
        )


        tabela.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.black
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, 0),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                )
            ])
        )


        elementos.append(
            tabela
        )


        elementos.append(
            Spacer(
                1,
                0.5 * cm
            )
        )


        elementos.append(

            Paragraph(
                f"Total de registros: {len(dados)}",
                estilos["Normal"]
            )
        )


        # ====================================================
        # DATA
        # ====================================================

        elementos.append(

            Paragraph(
                (
                    "Emitido em: "
                    + datetime.now().strftime(
                        "%d/%m/%Y %H:%M"
                    )
                ),
                estilos["Normal"]
            )
        )


        # ====================================================
        # CONSTRUIR PDF
        # ====================================================

        documento.build(
            elementos
        )


        buffer.seek(0)


        st.download_button(

            label="⬇️ Baixar Relatório em PDF",

            data=buffer,

            file_name="relatorio_entidades.pdf",

            mime="application/pdf",

            use_container_width=True,

            key="download_pdf_entidades"
        )

def cadastro_orgaos():

    modulo_em_desenvolvimento(
        "Cadastro de Órgãos",
        "🏛️"
    )


def cadastro_unidades_orcamentarias():

    modulo_em_desenvolvimento(
        "Unidades Orçamentárias",
        "💼"
    )


def cadastro_unidades_administrativas():

    modulo_em_desenvolvimento(
        "Unidades Administrativas",
        "🏬"
    )


def cadastro_setores():

    modulo_em_desenvolvimento(
        "Cadastro de Setores",
        "🧩"
    )


def cadastro_exercicios():

    modulo_em_desenvolvimento(
        "Exercícios",
        "📅"
    )


def organograma_sisget():

    modulo_em_desenvolvimento(
        "Organograma",
        "🌳"
    )


# ============================================================
# SOLICITAÇÕES
# ============================================================

def modulo_solicitacoes():

    modulo_em_desenvolvimento(
        "Solicitações",
        "📝"
    )


# ============================================================
# PLANEJAMENTO
# ============================================================

def modulo_planejamento():

    modulo_em_desenvolvimento(
        "Planejamento",
        "📐"
    )


# ============================================================
# SISCOM
# ============================================================

def modulo_siscom():

    modulo_em_desenvolvimento(
        "SISCOM - Licitações e Compras",
        "🛒"
    )


# ============================================================
# SISCON
# ============================================================

def modulo_siscon():

    modulo_em_desenvolvimento(
        "SISCON - Contratos",
        "📑"
    )


# ============================================================
# CONTABILIDADE / ORÇAMENTO
# ============================================================

def modulo_contabilidade():

    modulo_em_desenvolvimento(
        "Contabilidade e Orçamento",
        "📚"
    )


# ============================================================
# ALMOXARIFADO
# ============================================================

def modulo_almoxarifado():

    modulo_em_desenvolvimento(
        "Almoxarifado",
        "📦"
    )


# ============================================================
# PATRIMÔNIO
# ============================================================

def modulo_patrimonio():

    modulo_em_desenvolvimento(
        "Patrimônio",
        "🏷️"
    )


# ============================================================
# SISOPB
# ============================================================

def modulo_sisopb():

    modulo_em_desenvolvimento(
        "SISOPB - Obras Públicas",
        "🏗️"
    )


# ============================================================
# SISPRO
# ============================================================

def modulo_sispro():

    modulo_em_desenvolvimento(
        "SISPRO - Problemas Urbanos",
        "🏙️"
    )


# ============================================================
# SICOM
# ============================================================

def modulo_sicom():

    modulo_em_desenvolvimento(
        "SICOM / TCEMG",
        "📤"
    )


# ============================================================
# DASHBOARD
# ============================================================

def modulo_dashboard():

    modulo_em_desenvolvimento(
        "Gestão / Dashboard",
        "📊"
    )


# ============================================================
# USUÁRIOS
# ============================================================

def modulo_usuarios():

    modulo_em_desenvolvimento(
        "Pessoas e Usuários",
        "👥"
    )


# ============================================================
# ASSISTENTE
# ============================================================

# ============================================================
# ASSISTENTE
# ============================================================

def modulo_assistente():

    modulo_em_desenvolvimento(
        "Assistente SISGET",
        "🤖"
    )


# ============================================================
# LOGIN
# ============================================================

def login():

    st.title("🏛️ SISGET")
    st.subheader("🔐 Login no Sistema")

    with st.form("form_login"):

        usuario = st.text_input("👤 Usuário")

        senha = st.text_input(
            "🔑 Senha",
            type="password"
        )

        entrar = st.form_submit_button(
            "Entrar",
            type="primary",
            use_container_width=True
        )

    if entrar:

        if usuario == "admin" and senha == "123":

            st.session_state["usuario_logado"] = "admin"
            st.session_state["usuario_id"] = 1
            st.session_state["funcao_usuario"] = "Administrador"

            st.success(
                "✅ Login realizado com sucesso!"
            )

            st.rerun()

        else:

            st.error(
                "🚫 Usuário ou senha inválidos."
            )


# ============================================================
# LOGOUT
# ============================================================

def logout():

    chaves = list(
        st.session_state.keys()
    )

    for chave in chaves:

        del st.session_state[
            chave
        ]

    st.rerun()
def logout():

    chaves = list(
        st.session_state.keys()
    )


    for chave in chaves:

        del st.session_state[
            chave
        ]


    st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # LOGIN
    # ========================================================

    if "usuario_logado" not in (
        st.session_state
    ):

        login()

        return


    # ========================================================
    # USUÁRIO
    # ========================================================

    usuario = (
        st.session_state.get(
            "usuario_logado",
            ""
        )
    )


    funcao = (
        st.session_state.get(
            "funcao_usuario",
            ""
        )
    )


    st.sidebar.title(
        "🏛️ SISGET"
    )


    st.sidebar.success(
        f"👤 {usuario}"
    )


    st.sidebar.info(
        f"🔐 {funcao}"
    )


    st.sidebar.markdown("---")


    # ========================================================
    # MENU
    # ========================================================

    menu = [

        "🏠 Início",

        "🏛️ Cadastro Básico",

        "📝 Solicitações",

        "📐 Planejamento",

        "🛒 SISCOM - Licitações e Compras",

        "📑 SISCON - Contratos",

        "📚 Contabilidade / Orçamento",

        "📦 Almoxarifado",

        "🏷️ Patrimônio",

        "🏗️ SISOPB - Obras Públicas",

        "🏙️ SISPRO - Problemas Urbanos",

        "📤 SICOM / TCEMG",

        "📊 Gestão / Dashboard",

        "👥 Pessoas e Usuários",

        "🤖 Assistente SISGET",

        "🔓 Logout"
    ]


    escolha = (
        st.sidebar.selectbox(
            "📋 Módulo",
            menu
        )
    )


    # ========================================================
    # ROTEAMENTO
    # ========================================================

    if escolha == "🏠 Início":

        tela_inicio()


    elif escolha == "🏛️ Cadastro Básico":

        cadastro_basico()


    elif escolha == "📝 Solicitações":

        modulo_solicitacoes()


    elif escolha == "📐 Planejamento":

        modulo_planejamento()


    elif escolha == "🛒 SISCOM - Licitações e Compras":

        modulo_siscom()


    elif escolha == "📑 SISCON - Contratos":

        modulo_siscon()


    elif escolha == "📚 Contabilidade / Orçamento":

        modulo_contabilidade()


    elif escolha == "📦 Almoxarifado":

        modulo_almoxarifado()


    elif escolha == "🏷️ Patrimônio":

        modulo_patrimonio()


    elif escolha == "🏗️ SISOPB - Obras Públicas":

        modulo_sisopb()


    elif escolha == "🏙️ SISPRO - Problemas Urbanos":

        modulo_sispro()


    elif escolha == "📤 SICOM / TCEMG":

        modulo_sicom()


    elif escolha == "📊 Gestão / Dashboard":

        modulo_dashboard()


    elif escolha == "👥 Pessoas e Usuários":

        modulo_usuarios()


    elif escolha == "🤖 Assistente SISGET":

        modulo_assistente()


    elif escolha == "🔓 Logout":

        logout()


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":

    main()
