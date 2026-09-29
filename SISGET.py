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

# ============================================================
# TELA INICIAL DO SISGET - LAYOUT HORIZONTAL
# ============================================================

def tela_inicio():

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.title("🏛️ SISGET")

    st.subheader(
        "Sistema Integrado de Gestão Pública"
    )

    st.caption(
        "Gestão, treinamento, legislação e suporte em um único ambiente."
    )

    st.markdown("---")


    # ========================================================
    # ACESSOS PRINCIPAIS - HORIZONTAL
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)


    # ========================================================
    # SITE
    # ========================================================

    with col1:

        st.markdown(
            "### 🌐 Site"
        )

        st.caption(
            "Portal oficial do SISGET."
        )

        st.link_button(
            "🌐 Acessar",
            "https://SEU-SITE-AQUI.com.br",
            use_container_width=True
        )


    # ========================================================
    # YOUTUBE
    # ========================================================

    with col2:

        st.markdown(
            "### ▶️ Videoaulas"
        )

        st.caption(
            "Canal de treinamentos."
        )

        st.link_button(
            "▶️ YouTube",
            "https://www.youtube.com/@SEU_CANAL",
            use_container_width=True
        )


    # ========================================================
    # TREINAMENTO
    # ========================================================

    with col3:

        st.markdown(
            "### 🎓 Treinamento"
        )

        st.caption(
            "Aprenda a utilizar o SISGET."
        )

        if st.button(
            "🎓 Abrir Treinamento",
            use_container_width=True,
            key="btn_home_treinamento"
        ):

            st.session_state[
                "home_secao"
            ] = "treinamento"

            st.rerun()


    # ========================================================
    # CHATBOT
    # ========================================================

    with col4:

        st.markdown(
            "### 🤖 Assistente"
        )

        st.caption(
            "Suporte e dúvidas do sistema."
        )

        if st.button(
            "🤖 Abrir Chatbot",
            use_container_width=True,
            key="btn_home_chatbot"
        ):

            st.session_state[
                "home_secao"
            ] = "chatbot"

            st.rerun()


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
            "⬅️ Voltar",
            key="voltar_home_chatbot"
        ):

            st.session_state[
                "home_secao"
            ] = "inicio"

            st.rerun()


        modulo_assistente()

        return


    # ========================================================
    # TREINAMENTO
    # ========================================================

    if secao == "treinamento":

        if st.button(
            "⬅️ Voltar",
            key="voltar_home_treinamento"
        ):

            st.session_state[
                "home_secao"
            ] = "inicio"

            st.rerun()


        st.markdown("---")


        st.subheader(
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
            key="treinamento_home_modulo"
        )


        st.markdown("---")


        if treinamento == "Cadastro Básico":

            st.markdown(
                """
                ### 🏛️ Cadastro Básico

                Entidades • Órgãos • Unidades Orçamentárias •
                Unidades Administrativas • Setores • Exercícios • Organograma
                """
            )


        elif treinamento == "SISCOM - Licitações e Compras":

            st.markdown(
                """
                ### 🛒 SISCOM

                Solicitação • DFD • ETP • Termo de Referência •
                Pesquisa de Preços • Licitação • Contratação Direta • Homologação
                """
            )


        elif treinamento == "Contabilidade e Orçamento":

            st.markdown(
                """
                ### 📚 Contabilidade e Orçamento

                Dotação • Cota • Reserva • Empenho • Liquidação •
                Ordem de Pagamento • Pagamento • Restos a Pagar
                """
            )


        else:

            st.info(
                f"🎓 Conteúdo de treinamento de {treinamento}."
            )


        return


    # ========================================================
    # CENTRAL DE CONHECIMENTO - HORIZONTAL
    # ========================================================

    st.subheader(
        "📚 Central de Conhecimento"
    )


    col_lei, col_contab, col_guias = st.columns(3)


    # ========================================================
    # LICITAÇÕES
    # ========================================================

    with col_lei:

        st.markdown(
            "### ⚖️ Licitações e Contratos"
        )

        st.write(
            "Lei nº 14.133/2021"
        )

        st.caption(
            "Planejamento, licitações, contratação direta e contratos."
        )

        st.link_button(
            "📖 Lei 14.133/2021",
            "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
            use_container_width=True
        )

        st.link_button(
            "🏛️ Portal TCEMG",
            "https://www.tce.mg.gov.br/",
            use_container_width=True
        )


    # ========================================================
    # CONTABILIDADE
    # ========================================================

    with col_contab:

        st.markdown(
            "### 📊 Contabilidade Pública"
        )

        st.write(
            "Lei nº 4.320/1964"
        )

        st.caption(
            "Orçamento, empenho, liquidação, pagamento e balanços."
        )

        st.link_button(
            "📖 Lei 4.320/1964",
            "https://www.planalto.gov.br/ccivil_03/leis/l4320.htm",
            use_container_width=True
        )

        st.link_button(
            "📖 LRF - LC 101/2000",
            "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",
            use_container_width=True
        )


    # ========================================================
    # GUIAS
    # ========================================================

    with col_guias:

        st.markdown(
            "### 📘 Guias SISGET"
        )

        st.caption(
            "Acesso rápido aos principais fluxos do sistema."
        )

        st.markdown(
            """
            🏛️ Estrutura Administrativa  
            🛒 Compras e Licitações  
            📑 Contratos  
            💰 Execução Orçamentária  
            🏗️ Obras Públicas  
            🏙️ Problemas Urbanos
            """
        )


    st.markdown("---")


    # ========================================================
    # SEGUNDA FAIXA HORIZONTAL
    # ========================================================

    col5, col6, col7, col8 = st.columns(4)


    with col5:

        st.info(
            "🏛️ **Cadastro Básico**\n\n"
            "Entidades, órgãos, unidades e setores."
        )


    with col6:

        st.info(
            "🛒 **Compras e Licitações**\n\n"
            "Planejamento, processos e contratação."
        )


    with col7:

        st.info(
            "📚 **Contabilidade**\n\n"
            "Execução orçamentária e financeira."
        )


    with col8:

        st.info(
            "🏗️ **Gestão Pública**\n\n"
            "Obras, patrimônio, almoxarifado e SISPRO."
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

# ============================================================
# VALIDAR CNPJ
# ============================================================

# ============================================================
# VALIDAR CNPJ
# ============================================================

# ============================================================
# VALIDAR CNPJ
# ============================================================

def validar_cnpj(cnpj):

    cnpj = "".join(
        caractere
        for caractere in str(cnpj)
        if caractere.isdigit()
    )

    if len(cnpj) != 14:
        return False

    if cnpj == cnpj[0] * 14:
        return False

    pesos1 = [
        5, 4, 3, 2,
        9, 8, 7, 6,
        5, 4, 3, 2
    ]

    soma1 = sum(
        int(cnpj[i]) * pesos1[i]
        for i in range(12)
    )

    resto1 = soma1 % 11

    digito1 = (
        0
        if resto1 < 2
        else 11 - resto1
    )

    pesos2 = [
        6, 5, 4, 3, 2,
        9, 8, 7, 6,
        5, 4, 3, 2
    ]

    soma2 = sum(
        int(cnpj[i]) * pesos2[i]
        for i in range(13)
    )

    resto2 = soma2 % 11

    digito2 = (
        0
        if resto2 < 2
        else 11 - resto2
    )

    return (
        int(cnpj[12]) == digito1
        and
        int(cnpj[13]) == digito2
    )


# ============================================================
# VALIDAR CNPJ DUPLICADO
# ============================================================

def cnpj_entidade_duplicado(
    cnpj,
    entidade_id=None
):

    cnpj_limpo = "".join(
        caractere
        for caractere in str(cnpj)
        if caractere.isdigit()
    )

    if not cnpj_limpo:
        return False

    if entidade_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE REGEXP_REPLACE(
                COALESCE(cnpj, ''),
                '[^0-9]',
                '',
                'g'
            ) = ?
            """,
            (
                cnpj_limpo,
            )
        )

    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE REGEXP_REPLACE(
                COALESCE(cnpj, ''),
                '[^0-9]',
                '',
                'g'
            ) = ?
              AND id <> ?
            """,
            (
                cnpj_limpo,
                entidade_id
            )
        )

    return resultado is not None


# ============================================================
# PRÓXIMO CÓDIGO DISPONÍVEL
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


# ============================================================
# ALTERAR SITUAÇÃO DA ENTIDADE
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
            f"❌ Não foi possível alterar a situação: {erro}"
        )


# ============================================================
# ENTIDADES - INCLUIR
# ============================================================

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

        # ====================================================
        # VALIDAR NOME
        # ====================================================

        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return

        # ====================================================
        # VALIDAR NOME DUPLICADO
        # ====================================================

        nome_existente = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                nome,
            )
        )

        if nome_existente:

            st.warning(
                "⚠️ Já existe uma entidade cadastrada com esse nome."
            )

            return

        # ====================================================
        # VALIDAR CNPJ
        # ====================================================

        if cnpj:

            if not validar_cnpj(cnpj):

                st.warning(
                    "⚠️ CNPJ inválido."
                )

                return

            # =================================================
            # VALIDAR CNPJ DUPLICADO
            # =================================================

            if cnpj_entidade_duplicado(cnpj):

                st.warning(
                    "⚠️ Já existe uma entidade cadastrada com esse CNPJ."
                )

                return

            # =================================================
            # LIMPAR CNPJ
            # =================================================

            cnpj = "".join(
                caractere
                for caractere in cnpj
                if caractere.isdigit()
            )

        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_entidade()
        )

        # ====================================================
        # INSERT
        # ====================================================

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
                max_chars=18,
                placeholder="00.000.000/0000-00"
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

        with col2:

            if ativo_atual:

                alterar_status = st.form_submit_button(
                    "🚫 Inativar",
                    use_container_width=True
                )

            else:

                alterar_status = st.form_submit_button(
                    "✅ Ativar",
                    use_container_width=True
                )

        with col3:

            excluir = st.form_submit_button(
                "🗑️ Excluir",
                use_container_width=True
            )

        with col4:

            cancelar = st.form_submit_button(
                "❌ Cancelar",
                use_container_width=True
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

        # ====================================================
        # VALIDAR NOME
        # ====================================================

        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return

        # ====================================================
        # VALIDAR NOME DUPLICADO
        # IGNORA A PRÓPRIA ENTIDADE
        # ====================================================

        nome_existente = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                nome,
                entidade_id
            )
        )

        if nome_existente:

            st.warning(
                "⚠️ Já existe outra entidade cadastrada com esse nome."
            )

            return

        # ====================================================
        # VALIDAR CNPJ
        # ====================================================

        if cnpj:

            if not validar_cnpj(cnpj):

                st.warning(
                    "⚠️ CNPJ inválido."
                )

                return

            # =================================================
            # VALIDAR CNPJ DUPLICADO
            # IGNORA A PRÓPRIA ENTIDADE
            # =================================================

            if cnpj_entidade_duplicado(
                cnpj,
                entidade_id
            ):

                st.warning(
                    "⚠️ Já existe outra entidade cadastrada com esse CNPJ."
                )

                return

            # =================================================
            # LIMPAR CNPJ
            # =================================================

            cnpj = "".join(
                caractere
                for caractere in cnpj
                if caractere.isdigit()
            )

        # ====================================================
        # UPDATE
        # ====================================================

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

            st.rerun()
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

# ============================================================
# CADASTRO DE ÓRGÃOS
# ============================================================

def cadastro_orgaos():

    sisget_tela_principal(
        titulo="Cadastro de Órgãos",
        chave="orgaos",
        func_incluir=orgao_incluir,
        func_localizar=orgao_localizar,
        func_alterar=orgao_alterar,
        func_excluir=orgao_excluir,
        func_imprimir=orgao_imprimir,
        icone="🏛️"
    )


# ============================================================
# PRÓXIMO CÓDIGO DO ÓRGÃO
#
# ENTIDADE 001:
# 001.001
# 001.002
# 001.003
#
# SE EXCLUIR 001.002:
# PRÓXIMO VOLTA A SER 001.002
# ============================================================

def sisget_proximo_codigo_orgao(
    entidade_id
):

    # ========================================================
    # BUSCAR CÓDIGO DA ENTIDADE
    # ========================================================

    entidade = _sisget_fetchone(
        """
        SELECT codigo
        FROM entidades
        WHERE id = ?
        """,
        (
            entidade_id,
        )
    )


    if not entidade:

        return None


    codigo_entidade = str(
        entidade[0]
    ).strip()


    # ========================================================
    # GARANTIR 3 DÍGITOS NA ENTIDADE
    # ========================================================

    if codigo_entidade.isdigit():

        codigo_entidade = (
            codigo_entidade.zfill(3)
        )


    # ========================================================
    # BUSCAR CÓDIGOS JÁ UTILIZADOS
    # ========================================================

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM orgaos
        WHERE entidade_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )


    numeros_usados = set()


    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()


        try:

            # Exemplo:
            # 001.003 -> pega 003

            parte_numerica = (
                codigo.split(".")[-1]
            )


            numeros_usados.add(
                int(parte_numerica)
            )


        except (ValueError, TypeError):

            pass


    # ========================================================
    # PROCURAR PRIMEIRO NÚMERO LIVRE
    # ========================================================

    proximo = 1


    while proximo in numeros_usados:

        proximo += 1


    numero_orgao = str(
        proximo
    ).zfill(3)


    return (
        f"{codigo_entidade}.{numero_orgao}"
    )


# ============================================================
# VALIDAR NOME DUPLICADO DO ÓRGÃO
# ============================================================

def orgao_nome_duplicado(
    entidade_id,
    nome,
    orgao_id=None
):

    nome = nome.strip()


    if orgao_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE entidade_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                entidade_id,
                nome
            )
        )


    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE entidade_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                entidade_id,
                nome,
                orgao_id
            )
        )


    return resultado is not None


# ============================================================
# VALIDAR CÓDIGO DUPLICADO
# ============================================================

def orgao_codigo_duplicado(
    codigo,
    orgao_id=None
):

    if orgao_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE codigo = ?
            """,
            (
                codigo,
            )
        )


    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE codigo = ?
              AND id <> ?
            """,
            (
                codigo,
                orgao_id
            )
        )


    return resultado is not None


# ============================================================
# ALTERAR SITUAÇÃO DO ÓRGÃO
# ============================================================

def orgao_alterar_situacao(
    orgao_id,
    novo_status
):

    try:

        cursor.execute(
            """
            UPDATE orgaos
            SET ativo = ?
            WHERE id = ?
            """,
            (
                novo_status,
                orgao_id
            )
        )


        conn.commit()


        st.session_state[
            "sisget_id_orgaos"
        ] = None


        st.session_state[
            "sisget_tela_orgaos"
        ] = "localizar"


        st.rerun()


    except Exception as erro:

        conn.rollback()

        st.error(
            f"❌ Não foi possível alterar a situação do órgão: {erro}"
        )


# ============================================================
# ÓRGÃOS - INCLUIR
# ============================================================

def orgao_incluir():

    st.subheader(
        "🏛️ Dados do Órgão"
    )


    # ========================================================
    # ENTIDADES ATIVAS
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM entidades
        WHERE ativo = TRUE
        ORDER BY codigo, nome
        """
    )


    if not entidades:

        st.warning(
            "⚠️ Nenhuma entidade ativa cadastrada."
        )

        st.info(
            "Cadastre uma entidade antes de cadastrar órgãos."
        )

        return


    # ========================================================
    # OPÇÕES DAS ENTIDADES
    # ========================================================

    opcoes_entidades = {

        f"{codigo} - {nome}": entidade_id

        for entidade_id, codigo, nome
        in entidades
    }


    entidade_selecionada = st.selectbox(
        "Entidade *",
        list(
            opcoes_entidades.keys()
        ),
        key="orgao_incluir_entidade"
    )


    entidade_id = (
        opcoes_entidades[
            entidade_selecionada
        ]
    )


    # ========================================================
    # GERAR CÓDIGO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_orgao(
            entidade_id
        )
    )


    st.info(
        f"🔢 Código automático do órgão: {codigo}"
    )


    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_orgao_incluir",
        clear_on_submit=True
    ):

        nome = st.text_input(
            "Nome do Órgão *",
            max_chars=200
        )


        sigla = st.text_input(
            "Sigla",
            max_chars=30
        )


        ativo = st.checkbox(
            "Órgão ativo",
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
        sigla = sigla.strip()


        # ====================================================
        # NOME OBRIGATÓRIO
        # ====================================================

        if not nome:

            st.warning(
                "⚠️ Informe o nome do órgão."
            )

            return


        # ====================================================
        # NOME DUPLICADO
        # ====================================================

        if orgao_nome_duplicado(
            entidade_id,
            nome
        ):

            st.warning(
                "⚠️ Já existe um órgão com esse nome nesta entidade."
            )

            return


        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_orgao(
                entidade_id
            )
        )


        if not codigo:

            st.error(
                "❌ Não foi possível gerar o código do órgão."
            )

            return


        # ====================================================
        # CÓDIGO DUPLICADO
        # ====================================================

        if orgao_codigo_duplicado(
            codigo
        ):

            st.warning(
                "⚠️ Esse código de órgão já está cadastrado."
            )

            return


        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO orgaos
            (
                entidade_id,
                codigo,
                nome,
                sigla,
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
                entidade_id,
                codigo,
                nome,
                sigla if sigla else None,
                ativo
            )
        )


        if sucesso:

            st.success(
                f"✅ Órgão cadastrado com sucesso! Código: {codigo}"
            )


# ============================================================
# ÓRGÃOS - LOCALIZAR
# ============================================================

def orgao_localizar():

    st.subheader(
        "🔎 Localizar Órgãos"
    )


    # ========================================================
    # FILTROS
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM entidades
        ORDER BY codigo, nome
        """
    )


    entidade_opcoes = {
        "Todas": None
    }


    for entidade_id, codigo, nome in entidades:

        entidade_opcoes[
            f"{codigo} - {nome}"
        ] = entidade_id


    col1, col2, col3 = st.columns(3)


    with col1:

        filtro_entidade = st.selectbox(
            "Entidade",
            list(
                entidade_opcoes.keys()
            ),
            key="orgao_localizar_entidade"
        )


    with col2:

        filtro_nome = st.text_input(
            "Nome do Órgão",
            key="orgao_localizar_nome"
        )


    with col3:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todos",
                "Ativos",
                "Inativos"
            ],
            key="orgao_localizar_situacao"
        )


    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            o.id,

            e.codigo AS "Entidade",

            o.codigo AS "Código",

            o.nome AS "Órgão",

            COALESCE(
                o.sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN o.ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM orgaos o

        INNER JOIN entidades e
            ON e.id = o.entidade_id

        WHERE 1 = 1
    """


    parametros = []


    # ========================================================
    # ENTIDADE
    # ========================================================

    entidade_id = (
        entidade_opcoes[
            filtro_entidade
        ]
    )


    if entidade_id is not None:

        sql += """
            AND o.entidade_id = ?
        """

        parametros.append(
            entidade_id
        )


    # ========================================================
    # NOME
    # ========================================================

    if filtro_nome.strip():

        sql += """
            AND o.nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )


    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if filtro_situacao == "Ativos":

        sql += """
            AND o.ativo = TRUE
        """


    elif filtro_situacao == "Inativos":

        sql += """
            AND o.ativo = FALSE
        """


    sql += """
        ORDER BY
            e.codigo,
            o.codigo
    """


    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )


    if df.empty:

        st.info(
            "Nenhum órgão encontrado."
        )

        return None


    st.caption(
        f"Registros encontrados: {len(df)}"
    )


    # ========================================================
    # DUPLO CLIQUE -> ALTERAR
    # ========================================================

    return sisget_grid_localizar(
        df=df,
        chave="orgaos",
        coluna_id="id",
        altura=420
    )


# ============================================================
# ÓRGÃOS - ALTERAR
# ============================================================

def orgao_alterar(
    orgao_id
):

    # ========================================================
    # BUSCAR ÓRGÃO
    # ========================================================

    orgao = _sisget_fetchone(
        """
        SELECT
            o.id,
            o.entidade_id,
            e.codigo,
            e.nome,
            o.codigo,
            o.nome,
            o.sigla,
            o.ativo

        FROM orgaos o

        INNER JOIN entidades e
            ON e.id = o.entidade_id

        WHERE o.id = ?
        """,
        (
            orgao_id,
        )
    )


    if not orgao:

        st.error(
            "❌ Órgão não encontrado."
        )

        return


    (
        id_orgao,
        entidade_id,
        codigo_entidade,
        nome_entidade,
        codigo_atual,
        nome_atual,
        sigla_atual,
        ativo_atual
    ) = orgao


    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if ativo_atual:

        st.success(
            "🟢 Situação: ATIVO"
        )

    else:

        st.warning(
            "🔴 Situação: INATIVO"
        )


    # ========================================================
    # ENTIDADE
    # ========================================================

    st.text_input(
        "Entidade",
        value=(
            f"{codigo_entidade} - "
            f"{nome_entidade}"
        ),
        disabled=True
    )


    # ========================================================
    # FORM
    # ========================================================

    with st.form(
        f"form_orgao_alterar_{orgao_id}"
    ):

        st.text_input(
            "Código",
            value=codigo_atual or "",
            disabled=True
        )


        nome = st.text_input(
            "Nome do Órgão *",
            value=nome_atual or "",
            max_chars=200
        )


        sigla = st.text_input(
            "Sigla",
            value=sigla_atual or "",
            max_chars=30
        )


        st.markdown("---")


        col1, col2, col3, col4 = (
            st.columns(4)
        )


        with col1:

            salvar = (
                st.form_submit_button(
                    "💾 Salvar",
                    type="primary",
                    use_container_width=True
                )
            )


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


        with col3:

            excluir = (
                st.form_submit_button(
                    "🗑️ Excluir",
                    use_container_width=True
                )
            )


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
            "sisget_id_orgaos"
        ] = None


        st.session_state[
            "sisget_tela_orgaos"
        ] = "localizar"


        st.rerun()


    # ========================================================
    # ATIVAR / INATIVAR
    # ========================================================

    if alterar_status:

        orgao_alterar_situacao(
            orgao_id,
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
                DELETE FROM orgaos
                WHERE id = ?
                """,
                (
                    orgao_id,
                )
            )


            conn.commit()


            st.session_state[
                "sisget_id_orgaos"
            ] = None


            st.session_state[
                "sisget_tela_orgaos"
            ] = "localizar"


            st.rerun()


        except Exception as erro:

            conn.rollback()

            st.error(
                f"❌ Não foi possível excluir o órgão: {erro}"
            )


        return


    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()
        sigla = sigla.strip()


        if not nome:

            st.warning(
                "⚠️ Informe o nome do órgão."
            )

            return


        # ====================================================
        # NOME DUPLICADO
        # ====================================================

        if orgao_nome_duplicado(
            entidade_id,
            nome,
            orgao_id
        ):

            st.warning(
                "⚠️ Já existe outro órgão com esse nome nesta entidade."
            )

            return


        # ====================================================
        # UPDATE
        # ====================================================

        sucesso = _sisget_salvar(
            """
            UPDATE orgaos
            SET
                nome = ?,
                sigla = ?
            WHERE id = ?
            """,
            (
                nome,
                sigla if sigla else None,
                orgao_id
            )
        )


        if sucesso:

            st.session_state[
                "sisget_id_orgaos"
            ] = None


            st.session_state[
                "sisget_tela_orgaos"
            ] = "localizar"


            st.rerun()


# ============================================================
# ÓRGÃOS - EXCLUIR
# ============================================================

def orgao_excluir():

    st.subheader(
        "🗑️ Excluir Órgão"
    )


    # ========================================================
    # FILTRO POR ENTIDADE
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM entidades
        ORDER BY codigo, nome
        """
    )


    if not entidades:

        st.info(
            "Nenhuma entidade cadastrada."
        )

        return


    opcoes = {

        f"{codigo} - {nome}": entidade_id

        for entidade_id, codigo, nome
        in entidades
    }


    entidade_selecionada = st.selectbox(
        "Entidade",
        list(
            opcoes.keys()
        ),
        key="excluir_orgao_entidade"
    )


    entidade_id = (
        opcoes[
            entidade_selecionada
        ]
    )


    # ========================================================
    # CARREGAR ÓRGÃOS
    # ========================================================

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            nome AS "Órgão",
            COALESCE(
                sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM orgaos

        WHERE entidade_id = ?

        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )


    if df.empty:

        st.info(
            "Nenhum órgão cadastrado nesta entidade."
        )

        return


    # ========================================================
    # GRID
    # ========================================================

    registro_id = (
        sisget_grid_localizar(
            df=df,
            chave="excluir_orgaos",
            coluna_id="id",
            altura=420
        )
    )


    if not registro_id:

        st.caption(
            "Dê duplo clique no órgão que deseja excluir."
        )

        return


    # ========================================================
    # ÓRGÃO SELECIONADO
    # ========================================================

    orgao = _sisget_fetchone(
        """
        SELECT
            codigo,
            nome
        FROM orgaos
        WHERE id = ?
        """,
        (
            registro_id,
        )
    )


    if not orgao:

        return


    codigo = orgao[0]
    nome = orgao[1]


    st.markdown("---")


    st.error(
        f"⚠️ Você está prestes a excluir "
        f"**{codigo} - {nome}**."
    )


    confirmar = st.checkbox(
        "Confirmo que desejo excluir este órgão.",
        key=f"confirmar_orgao_{registro_id}"
    )


    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"btn_excluir_orgao_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação antes de excluir."
            )

            return


        try:

            cursor.execute(
                """
                DELETE FROM orgaos
                WHERE id = ?
                """,
                (
                    registro_id,
                )
            )


            conn.commit()


            st.success(
                "✅ Órgão excluído com sucesso!"
            )


            st.session_state[
                "sisget_tela_orgaos"
            ] = "principal"


            st.session_state[
                "sisget_id_orgaos"
            ] = None


            st.rerun()


        except Exception as erro:

            conn.rollback()

            st.error(
                f"❌ Não foi possível excluir o órgão: {erro}"
            )


# ============================================================
# ÓRGÃOS - IMPRIMIR
# ============================================================

def orgao_imprimir():

    st.subheader(
        "🖨️ Relatório de Órgãos"
    )


    # ========================================================
    # ENTIDADES
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM entidades
        ORDER BY codigo, nome
        """
    )


    opcoes = {
        "Todas as Entidades": None
    }


    for entidade_id, codigo, nome in entidades:

        opcoes[
            f"{codigo} - {nome}"
        ] = entidade_id


    entidade_selecionada = st.selectbox(
        "Entidade",
        list(
            opcoes.keys()
        ),
        key="imprimir_orgao_entidade"
    )


    situacao = st.selectbox(
        "Situação",
        [
            "Todos",
            "Ativos",
            "Inativos"
        ],
        key="imprimir_orgao_situacao"
    )


    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            e.codigo,
            e.nome,
            o.codigo,
            o.nome,
            COALESCE(
                o.sigla,
                ''
            ),
            o.ativo

        FROM orgaos o

        INNER JOIN entidades e
            ON e.id = o.entidade_id

        WHERE 1 = 1
    """


    parametros = []


    entidade_id = (
        opcoes[
            entidade_selecionada
        ]
    )


    if entidade_id is not None:

        sql += """
            AND o.entidade_id = ?
        """

        parametros.append(
            entidade_id
        )


    if situacao == "Ativos":

        sql += """
            AND o.ativo = TRUE
        """


    elif situacao == "Inativos":

        sql += """
            AND o.ativo = FALSE
        """


    sql += """
        ORDER BY
            e.codigo,
            o.codigo
    """


    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )


    if not dados:

        st.info(
            "Nenhum órgão encontrado."
        )

        return


    # ========================================================
    # DATAFRAME
    # ========================================================

    visualizacao = []


    for registro in dados:

        visualizacao.append({

            "Entidade":
                f"{registro[0]} - {registro[1]}",

            "Código":
                registro[2],

            "Órgão":
                registro[3],

            "Sigla":
                registro[4],

            "Situação":
                (
                    "Ativo"
                    if registro[5]
                    else "Inativo"
                )
        })


    df = pd.DataFrame(
        visualizacao
    )


    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


    st.caption(
        f"Total de órgãos: {len(df)}"
    )


    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_orgaos"
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


        estilos = (
            getSampleStyleSheet()
        )


        elementos = []


        elementos.append(
            Paragraph(
                "SISGET - Sistema Integrado de Gestão Pública",
                estilos["Heading1"]
            )
        )


        elementos.append(
            Paragraph(
                "Relatório de Órgãos",
                estilos["Heading2"]
            )
        )


        elementos.append(
            Spacer(
                1,
                0.4 * cm
            )
        )


        tabela_dados = [[
            "Entidade",
            "Código",
            "Órgão",
            "Sigla",
            "Situação"
        ]]


        for registro in dados:

            tabela_dados.append([

                str(
                    registro[0] or ""
                ),

                str(
                    registro[2] or ""
                ),

                Paragraph(
                    str(
                        registro[3] or ""
                    ),
                    estilos["Normal"]
                ),

                str(
                    registro[4] or ""
                ),

                (
                    "Ativo"
                    if registro[5]
                    else "Inativo"
                )
            ])


        tabela = Table(
            tabela_dados,
            colWidths=[
                2.5 * cm,
                2.5 * cm,
                7 * cm,
                2.5 * cm,
                2.5 * cm
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
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                )
            ])
        )


        elementos.append(
            tabela
        )


        documento.build(
            elementos
        )


        buffer.seek(0)


        st.download_button(
            "⬇️ Baixar Relatório em PDF",
            data=buffer,
            file_name="relatorio_orgaos.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_orgaos"
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
