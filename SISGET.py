# ============================================================
# IMPORTS
# ============================================================

import os
import psycopg2
import plotly.express as px
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

# ============================================================
# PRÓXIMO CÓDIGO DA ENTIDADE
#
# ÓRGÃO 001:
# 001.001
# 001.002
# 001.003
#
# SE EXCLUIR 001.002:
# PRÓXIMO VOLTA A SER 001.002
# ============================================================

def sisget_proximo_codigo_entidade(
    orgao_id
):

    # ========================================================
    # BUSCAR CÓDIGO DO ÓRGÃO
    # ========================================================

    orgao = _sisget_fetchone(
        """
        SELECT codigo
        FROM orgaos
        WHERE id = ?
        """,
        (
            orgao_id,
        )
    )

    if not orgao:

        return None

    codigo_orgao = str(
        orgao[0] or ""
    ).strip()

    if codigo_orgao.isdigit():

        codigo_orgao = (
            codigo_orgao.zfill(3)
        )

    # ========================================================
    # BUSCAR ENTIDADES DESSE ÓRGÃO
    # ========================================================

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM entidades
        WHERE orgao_id = ?
        ORDER BY codigo
        """,
        (
            orgao_id,
        )
    )

    numeros_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            parte_numerica = (
                codigo.split(".")[-1]
            )

            numeros_usados.add(
                int(parte_numerica)
            )

        except (ValueError, TypeError):

            pass

    # ========================================================
    # PRIMEIRO NÚMERO LIVRE
    # ========================================================

    proximo = 1

    while proximo in numeros_usados:

        proximo += 1

    numero_entidade = str(
        proximo
    ).zfill(3)

    return (
        f"{codigo_orgao}.{numero_entidade}"
    )


# ============================================================
# ENTIDADES - INCLUIR
# ============================================================

# ============================================================
# ENTIDADES - INCLUIR
# ============================================================

def entidade_incluir():

    st.subheader(
        "🏢 Dados da Entidade"
    )

    # ========================================================
    # BUSCAR ÓRGÃOS ATIVOS
    # ========================================================

    orgaos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM orgaos
        WHERE ativo = TRUE
        ORDER BY codigo, nome
        """
    )

    if not orgaos:

        st.warning(
            "⚠️ Nenhum órgão ativo cadastrado."
        )

        st.info(
            "Cadastre primeiro o órgão."
        )

        return

    # ========================================================
    # OPÇÕES DE ÓRGÃOS
    # ========================================================

    opcoes_orgaos = {

        f"{codigo} - {nome}": orgao_id

        for orgao_id, codigo, nome
        in orgaos
    }

    orgao_selecionado = st.selectbox(
        "Órgão *",
        list(
            opcoes_orgaos.keys()
        ),
        key="entidade_incluir_orgao"
    )

    orgao_id = (
        opcoes_orgaos[
            orgao_selecionado
        ]
    )

    # ========================================================
    # GERAR CÓDIGO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_entidade(
            orgao_id
        )
    )

    st.info(
        f"🔢 Código automático da entidade: {codigo}"
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
        # NOME OBRIGATÓRIO
        # ====================================================

        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return

        # ====================================================
        # NOME DUPLICADO NO MESMO ÓRGÃO
        # ====================================================

        nome_existente = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE orgao_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                orgao_id,
                nome
            )
        )

        if nome_existente:

            st.warning(
                "⚠️ Já existe uma entidade com esse nome neste órgão."
            )

            return

        # ====================================================
        # CNPJ
        # ====================================================

        if cnpj:

            if not validar_cnpj(
                cnpj
            ):

                st.warning(
                    "⚠️ CNPJ inválido."
                )

                return

            if cnpj_entidade_duplicado(
                cnpj
            ):

                st.warning(
                    "⚠️ Já existe uma entidade cadastrada com esse CNPJ."
                )

                return

            cnpj = "".join(
                caractere
                for caractere in cnpj
                if caractere.isdigit()
            )

        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_entidade(
                orgao_id
            )
        )

        if not codigo:

            st.error(
                "❌ Não foi possível gerar o código da entidade."
            )

            return

        # ====================================================
        # CÓDIGO DUPLICADO
        # ====================================================

        codigo_existente = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE codigo = ?
            """,
            (
                codigo,
            )
        )

        if codigo_existente:

            st.warning(
                "⚠️ Esse código de entidade já está cadastrado."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO entidades
            (
                orgao_id,
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
                ?,
                ?
            )
            """,
            (
                orgao_id,
                codigo,
                nome,
                cnpj if cnpj else None,
                tipo_entidade,
                ativo
            )
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            st.success(
                f"✅ Entidade cadastrada com sucesso! Código: {codigo}"
            )
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

# ============================================================
# ENTIDADES - ALTERAR
# COMPLETO
# ============================================================

def entidade_alterar(entidade_id):

    # ========================================================
    # FUNÇÕES INTERNAS
    # ========================================================

    def buscar_responsavel(tipo_responsavel):

        return _sisget_fetchone(
            """
            SELECT
                id,
                nome,
                cpf,
                cargo,
                data_inicio,
                data_fim,
                email,
                telefone
            FROM entidades_responsaveis
            WHERE entidade_id = ?
              AND tipo_responsavel = ?
              AND ativo = TRUE
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                entidade_id,
                tipo_responsavel
            )
        )


    def campos_responsavel(
        tipo_responsavel,
        chave
    ):

        registro = buscar_responsavel(
            tipo_responsavel
        )

        if registro:

            (
                responsavel_id,
                nome_atual,
                cpf_atual,
                cargo_atual,
                data_inicio_atual,
                data_fim_atual,
                email_atual,
                telefone_atual
            ) = registro

        else:

            responsavel_id = None
            nome_atual = ""
            cpf_atual = ""
            cargo_atual = ""
            data_inicio_atual = None
            data_fim_atual = None
            email_atual = ""
            telefone_atual = ""


        col1, col2 = st.columns(2)

        with col1:

            nome = st.text_input(
                "Nome",
                value=nome_atual or "",
                max_chars=200,
                key=f"{chave}_nome"
            )

        with col2:

            cpf = st.text_input(
                "CPF",
                value=cpf_atual or "",
                max_chars=14,
                placeholder="000.000.000-00",
                key=f"{chave}_cpf"
            )


        col1, col2 = st.columns(2)

        with col1:

            cargo = st.text_input(
                "Cargo / Função",
                value=cargo_atual or "",
                max_chars=150,
                key=f"{chave}_cargo"
            )

        with col2:

            telefone_responsavel = st.text_input(
                "Telefone",
                value=telefone_atual or "",
                max_chars=30,
                key=f"{chave}_telefone"
            )


        email_responsavel = st.text_input(
            "E-mail",
            value=email_atual or "",
            max_chars=200,
            key=f"{chave}_email"
        )


        col1, col2 = st.columns(2)

        with col1:

            data_inicio = st.date_input(
                "Data de início",
                value=data_inicio_atual,
                format="DD/MM/YYYY",
                key=f"{chave}_inicio"
            )

        with col2:

            data_fim = st.date_input(
                "Data de término",
                value=data_fim_atual,
                format="DD/MM/YYYY",
                key=f"{chave}_fim"
            )


        return {

            "id": responsavel_id,

            "tipo": tipo_responsavel,

            "nome": nome.strip(),

            "cpf": cpf.strip(),

            "cargo": cargo.strip(),

            "telefone":
                telefone_responsavel.strip(),

            "email":
                email_responsavel.strip(),

            "data_inicio": data_inicio,

            "data_fim": data_fim
        }


    def salvar_responsavel(dados):

        responsavel_id = dados["id"]

        nome_responsavel = dados["nome"]


        # Se não foi informado nome,
        # não cria responsável novo.

        if not nome_responsavel:

            return


        if responsavel_id:

            cursor.execute(
                """
                UPDATE entidades_responsaveis
                SET
                    nome = ?,
                    cpf = ?,
                    cargo = ?,
                    data_inicio = ?,
                    data_fim = ?,
                    email = ?,
                    telefone = ?
                WHERE id = ?
                """,
                (
                    nome_responsavel,

                    dados["cpf"]
                    if dados["cpf"]
                    else None,

                    dados["cargo"]
                    if dados["cargo"]
                    else None,

                    dados["data_inicio"],

                    dados["data_fim"],

                    dados["email"]
                    if dados["email"]
                    else None,

                    dados["telefone"]
                    if dados["telefone"]
                    else None,

                    responsavel_id
                )
            )

        else:

            # =================================================
            # SEGURANÇA
            # INATIVA OUTRO RESPONSÁVEL DO MESMO TIPO
            # =================================================

            cursor.execute(
                """
                UPDATE entidades_responsaveis
                SET
                    ativo = FALSE,
                    data_fim = COALESCE(
                        data_fim,
                        CURRENT_DATE
                    )
                WHERE entidade_id = ?
                  AND tipo_responsavel = ?
                  AND ativo = TRUE
                """,
                (
                    entidade_id,
                    dados["tipo"]
                )
            )


            cursor.execute(
                """
                INSERT INTO entidades_responsaveis
                (
                    entidade_id,
                    tipo_responsavel,
                    nome,
                    cpf,
                    cargo,
                    data_inicio,
                    data_fim,
                    email,
                    telefone,
                    ativo
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    TRUE
                )
                """,
                (
                    entidade_id,

                    dados["tipo"],

                    nome_responsavel,

                    dados["cpf"]
                    if dados["cpf"]
                    else None,

                    dados["cargo"]
                    if dados["cargo"]
                    else None,

                    dados["data_inicio"],

                    dados["data_fim"],

                    dados["email"]
                    if dados["email"]
                    else None,

                    dados["telefone"]
                    if dados["telefone"]
                    else None
                )
            )


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
            ativo,

            codigo_orgao_sicom,
            unidade_repasse,

            endereco,
            bairro,
            cep,
            telefone,
            fax,
            email,
            numero_habitantes,

            percentual_aquisicoes,
            percentual_estabelecido,

            orgao_padrao_id,
            unidade_orcamentaria_padrao_id,

            orgao_licitacao_id,
            unidade_licitacao_id,

            possui_assessoria_contabil,
            fornecedor_assessoria,

            conta_unica_tesouro,

            art20_numero_norma,
            art20_data_norma,
            art20_data_publicacao,
            art20_nome_arquivo

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
        ativo_atual,

        codigo_sicom_atual,
        unidade_repasse_atual,

        endereco_atual,
        bairro_atual,
        cep_atual,
        telefone_atual,
        fax_atual,
        email_atual,
        habitantes_atual,

        percentual_aquisicoes_atual,
        percentual_estabelecido_atual,

        orgao_padrao_atual,
        uo_padrao_atual,

        orgao_licitacao_atual,
        uo_licitacao_atual,

        assessoria_atual,
        fornecedor_assessoria_atual,

        conta_unica_atual,

        art20_numero_atual,
        art20_data_atual,
        art20_publicacao_atual,
        art20_nome_arquivo_atual

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
    # TIPOS DE ENTIDADE
    # ========================================================

    tipos = [
        "Prefeitura",
        "Câmara",
        "Autarquia",
        "Fundação",
        "Consórcio",
        "Outro"
    ]


    if not tipo_atual:

        tipo_atual = "Outro"


    if tipo_atual not in tipos:

        tipos.append(
            tipo_atual
        )


    indice_tipo = tipos.index(
        tipo_atual
    )


    # ========================================================
    # CARREGAR ÓRGÃOS
    # ========================================================

    orgaos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM orgaos
        WHERE entidade_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )


    opcoes_orgaos = {
        None: "Não informado"
    }


    for orgao_id, codigo_orgao, nome_orgao in orgaos:

        opcoes_orgaos[
            orgao_id
        ] = (
            f"{codigo_orgao} - "
            f"{nome_orgao}"
        )


    ids_orgaos = list(
        opcoes_orgaos.keys()
    )


    # ========================================================
    # CARREGAR UNIDADES ORÇAMENTÁRIAS
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM unidades_orcamentarias
        WHERE entidade_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )


    opcoes_unidades = {
        None: "Não informada"
    }


    for uo_id, codigo_uo, nome_uo in unidades:

        opcoes_unidades[
            uo_id
        ] = (
            f"{codigo_uo} - "
            f"{nome_uo}"
        )


    ids_unidades = list(
        opcoes_unidades.keys()
    )


    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_entidade_alterar_{entidade_id}"
    ):

        abas = st.tabs([

            "🏢 Dados da Entidade",

            "👤 Gestor",

            "⚖️ Autoridade",

            "📚 Contador",

            "💰 Tesoureiro",

            "✍️ Autorizador",

            "🏦 Secretário de Finanças"

        ])


        # ====================================================
        # ABA 1
        # DADOS DA ENTIDADE
        # ====================================================

        with abas[0]:

            st.markdown(
                "### 🏢 Identificação"
            )


            col1, col2 = st.columns(2)


            with col1:

                st.text_input(
                    "Código SISGET",
                    value=codigo_atual or "",
                    disabled=True
                )


            with col2:

                codigo_orgao_sicom = (
                    st.text_input(
                        "Código do Órgão no Portal SICOM",
                        value=(
                            codigo_sicom_atual
                            or ""
                        ),
                        max_chars=20
                    )
                )


            nome = st.text_input(
                "Nome da Entidade *",
                value=nome_atual or "",
                max_chars=200
            )


            col1, col2 = st.columns(2)


            with col1:

                cnpj = st.text_input(
                    "CNPJ",
                    value=cnpj_atual or "",
                    max_chars=18,
                    placeholder="00.000.000/0000-00"
                )


            with col2:

                tipo_entidade = (
                    st.selectbox(
                        "Tipo de Entidade",
                        tipos,
                        index=indice_tipo
                    )
                )


            unidade_repasse = st.text_input(
                "Unidade de Repasse",
                value=(
                    unidade_repasse_atual
                    or ""
                ),
                max_chars=30
            )


            st.markdown("---")


            # =================================================
            # ENDEREÇO
            # =================================================

            st.markdown(
                "### 📍 Endereço e Contato"
            )


            endereco = st.text_input(
                "Endereço",
                value=endereco_atual or "",
                max_chars=250
            )


            col1, col2, col3 = (
                st.columns(
                    [2, 1, 1]
                )
            )


            with col1:

                bairro = st.text_input(
                    "Bairro",
                    value=bairro_atual or "",
                    max_chars=120
                )


            with col2:

                cep = st.text_input(
                    "CEP",
                    value=cep_atual or "",
                    max_chars=10,
                    placeholder="00000-000"
                )


            with col3:

                numero_habitantes = (
                    st.number_input(
                        "Habitantes",
                        min_value=0,
                        step=1,
                        value=int(
                            habitantes_atual
                            or 0
                        )
                    )
                )


            col1, col2, col3 = (
                st.columns(3)
            )


            with col1:

                telefone = st.text_input(
                    "Telefone",
                    value=telefone_atual or "",
                    max_chars=30
                )


            with col2:

                fax = st.text_input(
                    "Fax",
                    value=fax_atual or "",
                    max_chars=30
                )


            with col3:

                email = st.text_input(
                    "E-mail",
                    value=email_atual or "",
                    max_chars=200
                )


            st.markdown("---")


            # =================================================
            # PERCENTUAIS
            # =================================================

            st.markdown(
                "### 📊 Percentuais"
            )


            col1, col2 = (
                st.columns(2)
            )


            with col1:

                percentual_aquisicoes = (
                    st.number_input(
                        (
                            "Percentual das aquisições "
                            "de bens/serviços licitáveis"
                        ),
                        min_value=0.0,
                        max_value=100.0,
                        step=0.01,
                        value=float(
                            percentual_aquisicoes_atual
                            or 0
                        )
                    )
                )


            with col2:

                percentual_estabelecido = (
                    st.number_input(
                        "Percentual estabelecido",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.01,
                        value=float(
                            percentual_estabelecido_atual
                            or 0
                        )
                    )
                )


            st.markdown("---")


            # =================================================
            # PADRÕES
            # =================================================

            st.markdown(
                "### 🏛️ Configuração Padrão"
            )


            if (
                orgao_padrao_atual
                in ids_orgaos
            ):

                indice = (
                    ids_orgaos.index(
                        orgao_padrao_atual
                    )
                )

            else:

                indice = 0


            orgao_padrao_id = (
                st.selectbox(
                    "Órgão Padrão",
                    ids_orgaos,
                    index=indice,
                    format_func=lambda x:
                        opcoes_orgaos[x]
                )
            )


            if (
                uo_padrao_atual
                in ids_unidades
            ):

                indice = (
                    ids_unidades.index(
                        uo_padrao_atual
                    )
                )

            else:

                indice = 0


            unidade_orcamentaria_padrao_id = (
                st.selectbox(
                    "Unidade Orçamentária Padrão",
                    ids_unidades,
                    index=indice,
                    format_func=lambda x:
                        opcoes_unidades[x]
                )
            )


            st.markdown("---")


            # =================================================
            # LICITAÇÃO
            # =================================================

            st.markdown(
                "### 🛒 Responsável por Licitações"
            )


            if (
                orgao_licitacao_atual
                in ids_orgaos
            ):

                indice = (
                    ids_orgaos.index(
                        orgao_licitacao_atual
                    )
                )

            else:

                indice = 0


            orgao_licitacao_id = (
                st.selectbox(
                    (
                        "Órgão responsável "
                        "pela Licitação"
                    ),
                    ids_orgaos,
                    index=indice,
                    format_func=lambda x:
                        opcoes_orgaos[x]
                )
            )


            if (
                uo_licitacao_atual
                in ids_unidades
            ):

                indice = (
                    ids_unidades.index(
                        uo_licitacao_atual
                    )
                )

            else:

                indice = 0


            unidade_licitacao_id = (
                st.selectbox(
                    (
                        "Unidade Orçamentária "
                        "responsável pela Licitação"
                    ),
                    ids_unidades,
                    index=indice,
                    format_func=lambda x:
                        opcoes_unidades[x]
                )
            )


            st.markdown("---")


            # =================================================
            # ASSESSORIA
            # =================================================

            st.markdown(
                "### 📚 Assessoria Contábil"
            )


            possui_assessoria = (
                st.radio(
                    "Possui Assessoria Contábil?",
                    [
                        True,
                        False
                    ],
                    index=(
                        0
                        if assessoria_atual
                        else 1
                    ),
                    format_func=lambda x:
                        "Sim"
                        if x
                        else "Não",
                    horizontal=True
                )
            )


            fornecedor_assessoria = (
                st.text_input(
                    "Fornecedor da Assessoria",
                    value=(
                        fornecedor_assessoria_atual
                        or ""
                    ),
                    max_chars=250,
                    disabled=(
                        not possui_assessoria
                    )
                )
            )


            st.markdown("---")


            # =================================================
            # CONTA ÚNICA
            # =================================================

            conta_unica = st.radio(
                "Utiliza Conta Única do Tesouro?",
                [
                    True,
                    False
                ],
                index=(
                    0
                    if conta_unica_atual
                    else 1
                ),
                format_func=lambda x:
                    "Sim"
                    if x
                    else "Não",
                horizontal=True
            )


            st.markdown("---")


            # =================================================
            # ARTIGO 20
            # =================================================

            st.markdown(
                "### ⚖️ Art. 20 - Lei 14.133/2021"
            )


            col1, col2, col3 = (
                st.columns(3)
            )


            with col1:

                art20_numero = (
                    st.text_input(
                        "Número da Norma",
                        value=(
                            art20_numero_atual
                            or ""
                        ),
                        max_chars=50
                    )
                )


            with col2:

                art20_data = (
                    st.date_input(
                        "Data da Norma",
                        value=art20_data_atual,
                        format="DD/MM/YYYY"
                    )
                )


            with col3:

                art20_publicacao = (
                    st.date_input(
                        "Data da Publicação",
                        value=(
                            art20_publicacao_atual
                        ),
                        format="DD/MM/YYYY"
                    )
                )


            if art20_nome_arquivo_atual:

                st.info(
                    (
                        "📎 Arquivo atual: "
                        f"{art20_nome_arquivo_atual}"
                    )
                )


            arquivo_art20 = (
                st.file_uploader(
                    "Arquivo PDF da Norma",
                    type=["pdf"],
                    key=(
                        "arquivo_art20_"
                        f"{entidade_id}"
                    )
                )
            )


        # ====================================================
        # ABA GESTOR
        # ====================================================

        with abas[1]:

            gestor = campos_responsavel(
                "GESTOR",
                f"gestor_{entidade_id}"
            )


        # ====================================================
        # ABA AUTORIDADE
        # ====================================================

        with abas[2]:

            autoridade = campos_responsavel(
                "AUTORIDADE",
                f"autoridade_{entidade_id}"
            )


        # ====================================================
        # ABA CONTADOR
        # ====================================================

        with abas[3]:

            contador = campos_responsavel(
                "CONTADOR",
                f"contador_{entidade_id}"
            )


        # ====================================================
        # ABA TESOUREIRO
        # ====================================================

        with abas[4]:

            tesoureiro = campos_responsavel(
                "TESOUREIRO",
                f"tesoureiro_{entidade_id}"
            )


        # ====================================================
        # ABA AUTORIZADOR
        # ====================================================

        with abas[5]:

            autorizador = campos_responsavel(
                "AUTORIZADOR_DESPESA",
                f"autorizador_{entidade_id}"
            )


        # ====================================================
        # ABA SECRETÁRIO
        # ====================================================

        with abas[6]:

            secretario = campos_responsavel(
                "SECRETARIO_FINANCAS",
                f"secretario_{entidade_id}"
            )


        # ====================================================
        # BOTÕES
        # ====================================================

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
                (
                    "❌ Não foi possível "
                    f"excluir a entidade: {erro}"
                )
            )


        return


    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()

        cnpj = cnpj.strip()


        # ====================================================
        # NOME
        # ====================================================

        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return


        # ====================================================
        # NOME DUPLICADO
        # ====================================================

        nome_existente = (
            _sisget_fetchone(
                """
                SELECT id
                FROM entidades
                WHERE LOWER(TRIM(nome))
                    = LOWER(TRIM(?))
                  AND id <> ?
                """,
                (
                    nome,
                    entidade_id
                )
            )
        )


        if nome_existente:

            st.warning(
                (
                    "⚠️ Já existe outra entidade "
                    "com esse nome."
                )
            )

            return


        # ====================================================
        # CNPJ
        # ====================================================

        if cnpj:

            if not validar_cnpj(
                cnpj
            ):

                st.warning(
                    "⚠️ CNPJ inválido."
                )

                return


            if cnpj_entidade_duplicado(
                cnpj,
                entidade_id
            ):

                st.warning(
                    (
                        "⚠️ Já existe outra entidade "
                        "com esse CNPJ."
                    )
                )

                return


            cnpj = "".join(
                caractere
                for caractere in cnpj
                if caractere.isdigit()
            )


        # ====================================================
        # SALVAR TUDO
        # ====================================================

        try:

            # =================================================
            # DADOS DA ENTIDADE
            # =================================================

            cursor.execute(
                """
                UPDATE entidades

                SET
                    nome = ?,
                    cnpj = ?,
                    tipo_entidade = ?,

                    codigo_orgao_sicom = ?,
                    unidade_repasse = ?,

                    endereco = ?,
                    bairro = ?,
                    cep = ?,
                    telefone = ?,
                    fax = ?,
                    email = ?,

                    numero_habitantes = ?,

                    percentual_aquisicoes = ?,
                    percentual_estabelecido = ?,

                    orgao_padrao_id = ?,

                    unidade_orcamentaria_padrao_id = ?,

                    orgao_licitacao_id = ?,

                    unidade_licitacao_id = ?,

                    possui_assessoria_contabil = ?,

                    fornecedor_assessoria = ?,

                    conta_unica_tesouro = ?,

                    art20_numero_norma = ?,

                    art20_data_norma = ?,

                    art20_data_publicacao = ?

                WHERE id = ?
                """,
                (
                    nome,

                    cnpj
                    if cnpj
                    else None,

                    tipo_entidade,

                    codigo_orgao_sicom.strip()
                    if codigo_orgao_sicom
                    else None,

                    unidade_repasse.strip()
                    if unidade_repasse
                    else None,

                    endereco.strip()
                    if endereco
                    else None,

                    bairro.strip()
                    if bairro
                    else None,

                    cep.strip()
                    if cep
                    else None,

                    telefone.strip()
                    if telefone
                    else None,

                    fax.strip()
                    if fax
                    else None,

                    email.strip()
                    if email
                    else None,

                    numero_habitantes
                    if numero_habitantes > 0
                    else None,

                    percentual_aquisicoes,

                    percentual_estabelecido,

                    orgao_padrao_id,

                    unidade_orcamentaria_padrao_id,

                    orgao_licitacao_id,

                    unidade_licitacao_id,

                    possui_assessoria,

                    fornecedor_assessoria.strip()
                    if (
                        possui_assessoria
                        and fornecedor_assessoria
                    )
                    else None,

                    conta_unica,

                    art20_numero.strip()
                    if art20_numero
                    else None,

                    art20_data,

                    art20_publicacao,

                    entidade_id
                )
            )


            # =================================================
            # ARQUIVO ARTIGO 20
            # =================================================

            if arquivo_art20:

                cursor.execute(
                    """
                    UPDATE entidades
                    SET
                        art20_arquivo = ?,
                        art20_nome_arquivo = ?
                    WHERE id = ?
                    """,
                    (
                        arquivo_art20.getvalue(),

                        arquivo_art20.name,

                        entidade_id
                    )
                )


            # =================================================
            # RESPONSÁVEIS
            # =================================================

            salvar_responsavel(
                gestor
            )

            salvar_responsavel(
                autoridade
            )

            salvar_responsavel(
                contador
            )

            salvar_responsavel(
                tesoureiro
            )

            salvar_responsavel(
                autorizador
            )

            salvar_responsavel(
                secretario
            )


            conn.commit()


            st.success(
                "✅ Entidade alterada com sucesso!"
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
                (
                    "❌ Não foi possível salvar "
                    f"a entidade: {erro}"
                )
            )
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
# PRÓXIMO CÓDIGO DO ÓRGÃO
#
# 001
# 002
# 003
#
# REUTILIZA PRIMEIRO CÓDIGO LIVRE
# ============================================================

def sisget_proximo_codigo_orgao():

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM orgaos
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
# VALIDAR NOME DUPLICADO DO ÓRGÃO
# ============================================================

def orgao_nome_duplicado(
    nome,
    orgao_id=None
):

    nome = nome.strip()

    if orgao_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                nome,
            )
        )

    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM orgaos
            WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                nome,
                orgao_id
            )
        )

    return resultado is not None


# ============================================================
# ÓRGÃOS - INCLUIR
# ============================================================

def orgao_incluir():

    st.subheader(
        "🏛️ Dados do Órgão"
    )

    codigo = (
        sisget_proximo_codigo_orgao()
    )

    st.info(
        f"🔢 Código automático do órgão: {codigo}"
    )

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

    if salvar:

        nome = nome.strip()
        sigla = sigla.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome do órgão."
            )

            return

        if orgao_nome_duplicado(
            nome
        ):

            st.warning(
                "⚠️ Já existe um órgão com esse nome."
            )

            return

        codigo = (
            sisget_proximo_codigo_orgao()
        )

        if orgao_codigo_duplicado(
            codigo
        ):

            st.warning(
                "⚠️ Esse código de órgão já está cadastrado."
            )

            return

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
                NULL,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
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

    col1, col2 = st.columns(2)

    with col1:

        filtro_nome = st.text_input(
            "Nome do Órgão",
            key="orgao_localizar_nome"
        )

    with col2:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todos",
                "Ativos",
                "Inativos"
            ],
            key="orgao_localizar_situacao"
        )

    sql = """
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

        WHERE 1 = 1
    """

    parametros = []

    if filtro_nome.strip():

        sql += """
            AND nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )

    if filtro_situacao == "Ativos":

        sql += """
            AND ativo = TRUE
        """

    elif filtro_situacao == "Inativos":

        sql += """
            AND ativo = FALSE
        """

    sql += """
        ORDER BY codigo
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

    orgao = _sisget_fetchone(
        """
        SELECT
            id,
            codigo,
            nome,
            sigla,
            ativo
        FROM orgaos
        WHERE id = ?
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
        codigo_atual,
        nome_atual,
        sigla_atual,
        ativo_atual
    ) = orgao

    if ativo_atual:

        st.success(
            "🟢 Situação: ATIVO"
        )

    else:

        st.warning(
            "🔴 Situação: INATIVO"
        )

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

    if cancelar:

        st.session_state[
            "sisget_id_orgaos"
        ] = None

        st.session_state[
            "sisget_tela_orgaos"
        ] = "localizar"

        st.rerun()

    if alterar_status:

        orgao_alterar_situacao(
            orgao_id,
            not ativo_atual
        )

        return

    if excluir:

        entidades_vinculadas = _sisget_fetchone(
            """
            SELECT COUNT(*)
            FROM entidades
            WHERE orgao_id = ?
            """,
            (
                orgao_id,
            )
        )

        quantidade = (
            entidades_vinculadas[0]
            if entidades_vinculadas
            else 0
        )

        if quantidade > 0:

            st.error(
                "❌ Não é possível excluir este órgão porque existem "
                f"{quantidade} entidade(s) vinculada(s) a ele."
            )

            return

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

    if salvar:

        nome = nome.strip()
        sigla = sigla.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome do órgão."
            )

            return

        if orgao_nome_duplicado(
            nome,
            orgao_id
        ):

            st.warning(
                "⚠️ Já existe outro órgão com esse nome."
            )

            return

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

    st.warning(
        "Selecione o órgão que deseja excluir."
    )

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

        ORDER BY codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhum órgão cadastrado."
        )

        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_orgaos",
        coluna_id="id",
        altura=420
    )

    if not registro_id:

        st.caption(
            "Dê duplo clique no órgão que deseja excluir."
        )

        return

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

    entidades_vinculadas = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM entidades
        WHERE orgao_id = ?
        """,
        (
            registro_id,
        )
    )

    quantidade = (
        entidades_vinculadas[0]
        if entidades_vinculadas
        else 0
    )

    st.markdown("---")

    st.error(
        f"⚠️ Você está prestes a excluir "
        f"**{codigo} - {nome}**."
    )

    if quantidade > 0:

        st.warning(
            "⚠️ Este órgão possui "
            f"{quantidade} entidade(s) vinculada(s). "
            "Ele não poderá ser excluído enquanto houver vínculos."
        )

        return

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


# ============================================================
# CADASTRO DE UNIDADES ORÇAMENTÁRIAS
# ============================================================

def cadastro_unidades_orcamentarias():

    sisget_tela_principal(
        titulo="Unidades Orçamentárias",
        chave="unidades_orcamentarias",
        func_incluir=unidade_orcamentaria_incluir,
        func_localizar=unidade_orcamentaria_localizar,
        func_alterar=unidade_orcamentaria_alterar,
        func_excluir=unidade_orcamentaria_excluir,
        func_imprimir=unidade_orcamentaria_imprimir,
        icone="💼"
    )

# ============================================================
# UNIDADE ORÇAMENTÁRIA - IMPRIMIR
# ============================================================

def unidade_orcamentaria_imprimir():

    st.subheader(
        "🖨️ Relatório de Unidades Orçamentárias"
    )

    # ========================================================
    # ENTIDADES PARA FILTRO
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            e.id,
            e.codigo,
            e.nome,
            o.codigo,
            o.nome

        FROM entidades e

        INNER JOIN orgaos o
            ON o.id = e.orgao_id

        ORDER BY
            o.codigo,
            e.codigo
        """
    )

    opcoes_entidades = {
        "Todas as Entidades": None
    }

    for (
        entidade_id,
        codigo_entidade,
        nome_entidade,
        codigo_orgao,
        nome_orgao
    ) in entidades:

        descricao = (
            f"{codigo_orgao} - {nome_orgao}"
            f" → "
            f"{codigo_entidade} - {nome_entidade}"
        )

        opcoes_entidades[
            descricao
        ] = entidade_id

    # ========================================================
    # FILTROS
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        entidade_selecionada = st.selectbox(
            "Entidade",
            list(
                opcoes_entidades.keys()
            ),
            key="uo_imprimir_entidade"
        )

    with col2:

        situacao = st.selectbox(
            "Situação",
            [
                "Todas",
                "Ativas",
                "Inativas"
            ],
            key="uo_imprimir_situacao"
        )

    entidade_id = (
        opcoes_entidades[
            entidade_selecionada
        ]
    )

    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            o.codigo,
            o.nome,

            e.codigo,
            e.nome,

            u.codigo,
            u.nome,

            COALESCE(
                u.codigo_tce,
                ''
            ),

            COALESCE(
                u.identificador_fundo,
                0
            ),

            u.data_envio_tce,

            u.ativo

        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        WHERE 1 = 1
    """

    parametros = []

    # ========================================================
    # FILTRO ENTIDADE
    # ========================================================

    if entidade_id is not None:

        sql += """
            AND u.entidade_id = ?
        """

        parametros.append(
            entidade_id
        )

    # ========================================================
    # FILTRO SITUAÇÃO
    # ========================================================

    if situacao == "Ativas":

        sql += """
            AND u.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND u.ativo = FALSE
        """

    # ========================================================
    # ORDENAÇÃO
    # ========================================================

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo
    """

    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )

    if not dados:

        st.info(
            "Nenhuma Unidade Orçamentária encontrada."
        )

        return

    # ========================================================
    # VISUALIZAÇÃO
    # ========================================================

    visualizacao = []

    for registro in dados:

        data_envio = ""

        if registro[8]:

            try:

                data_envio = (
                    registro[8].strftime(
                        "%d/%m/%Y"
                    )
                )

            except Exception:

                data_envio = str(
                    registro[8]
                )

        visualizacao.append({

            "Órgão":
                f"{registro[0]} - {registro[1]}",

            "Entidade":
                f"{registro[2]} - {registro[3]}",

            "Código":
                registro[4],

            "Unidade Orçamentária":
                registro[5],

            "Código TCE":
                registro[6],

            "Identificador":
                registro[7],

            "Envio TCE":
                data_envio,

            "Situação":
                (
                    "Ativa"
                    if registro[9]
                    else "Inativa"
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
        f"Total de Unidades Orçamentárias: {len(df)}"
    )

    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_unidades_orcamentarias"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8 * cm,
            leftMargin=0.8 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm
        )

        estilos = (
            getSampleStyleSheet()
        )

        titulo_style = ParagraphStyle(
            "TituloUO",
            parent=estilos["Heading1"],
            alignment=1,
            fontSize=15,
            spaceAfter=8
        )

        subtitulo_style = ParagraphStyle(
            "SubtituloUO",
            parent=estilos["Normal"],
            alignment=1,
            fontSize=9,
            spaceAfter=12
        )

        texto_tabela = ParagraphStyle(
            "TextoTabelaUO",
            parent=estilos["Normal"],
            fontSize=7,
            leading=8
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
                "Relatório de Unidades Orçamentárias",
                estilos["Heading2"]
            )
        )

        filtros_relatorio = (
            f"Entidade: {entidade_selecionada}"
            f" | Situação: {situacao}"
        )

        elementos.append(
            Paragraph(
                filtros_relatorio,
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
        # TABELA
        # ====================================================

        tabela_dados = [[
            "Órgão",
            "Entidade",
            "Código",
            "Unidade Orçamentária",
            "Cód. TCE",
            "Ident.",
            "Envio TCE",
            "Situação"
        ]]

        for registro in dados:

            data_envio = ""

            if registro[8]:

                try:

                    data_envio = (
                        registro[8].strftime(
                            "%d/%m/%Y"
                        )
                    )

                except Exception:

                    data_envio = str(
                        registro[8]
                    )

            tabela_dados.append([

                Paragraph(
                    f"{registro[0]} - {registro[1]}",
                    texto_tabela
                ),

                Paragraph(
                    f"{registro[2]} - {registro[3]}",
                    texto_tabela
                ),

                str(
                    registro[4] or ""
                ),

                Paragraph(
                    str(
                        registro[5] or ""
                    ),
                    texto_tabela
                ),

                str(
                    registro[6] or ""
                ),

                str(
                    registro[7]
                    if registro[7] is not None
                    else ""
                ),

                data_envio,

                (
                    "Ativa"
                    if registro[9]
                    else "Inativa"
                )
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                2.5 * cm,
                2.7 * cm,
                2.0 * cm,
                4.0 * cm,
                1.5 * cm,
                1.1 * cm,
                1.8 * cm,
                1.4 * cm
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
                    "FONTSIZE",
                    (0, 0),
                    (-1, 0),
                    7
                ),

                (
                    "FONTSIZE",
                    (0, 1),
                    (-1, -1),
                    7
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
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3
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

        # ====================================================
        # RODAPÉ
        # ====================================================

        elementos.append(
            Paragraph(
                f"Total de registros: {len(dados)}",
                estilos["Normal"]
            )
        )

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
            file_name="relatorio_unidades_orcamentarias.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_unidades_orcamentarias"
        )
def sisget_proximo_codigo_unidade_orcamentaria(
    entidade_id
):

    # ========================================================
    # BUSCAR ENTIDADE
    # ========================================================

    entidade = _sisget_fetchone(
        """
        SELECT
            codigo
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
        entidade[0] or ""
    ).strip()

    # ========================================================
    # BUSCAR CÓDIGOS UTILIZADOS NESSA ENTIDADE
    # ========================================================

    dados = _sisget_fetch(
        """
        SELECT
            codigo
        FROM unidades_orcamentarias
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

            parte = (
                codigo.split(".")[-1]
            )

            numeros_usados.add(
                int(parte)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    # ========================================================
    # PRIMEIRO NÚMERO LIVRE
    # ========================================================

    proximo = 1

    while proximo in numeros_usados:

        proximo += 1

    numero_uo = str(
        proximo
    ).zfill(3)

    return (
        f"{codigo_entidade}.{numero_uo}"
    )


# ============================================================
# VALIDAR NOME DUPLICADO
# ============================================================

def unidade_orcamentaria_nome_duplicado(
    entidade_id,
    nome,
    unidade_id=None
):

    nome = nome.strip()

    if unidade_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM unidades_orcamentarias
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
            FROM unidades_orcamentarias
            WHERE entidade_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                entidade_id,
                nome,
                unidade_id
            )
        )

    return resultado is not None


# ============================================================
# UNIDADE ORÇAMENTÁRIA - INCLUIR
# ============================================================

def unidade_orcamentaria_incluir():

    st.subheader(
        "💼 Dados da Unidade Orçamentária"
    )

    # ========================================================
    # ENTIDADES ATIVAS
    # COM SEU ÓRGÃO PAI
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            e.id,
            e.codigo,
            e.nome,
            o.id,
            o.codigo,
            o.nome

        FROM entidades e

        INNER JOIN orgaos o
            ON o.id = e.orgao_id

        WHERE e.ativo = TRUE
          AND o.ativo = TRUE

        ORDER BY
            o.codigo,
            e.codigo
        """
    )

    if not entidades:

        st.warning(
            "⚠️ Nenhuma entidade ativa vinculada a um órgão."
        )

        st.info(
            "Cadastre primeiro o órgão e depois a entidade."
        )

        return

    # ========================================================
    # OPÇÕES
    # ========================================================

    opcoes = {}

    for (
        entidade_id,
        codigo_entidade,
        nome_entidade,
        orgao_id,
        codigo_orgao,
        nome_orgao
    ) in entidades:

        descricao = (
            f"{codigo_orgao} - {nome_orgao}"
            f" → "
            f"{codigo_entidade} - {nome_entidade}"
        )

        opcoes[
            descricao
        ] = (
            entidade_id,
            orgao_id
        )

    entidade_selecionada = st.selectbox(
        "Entidade *",
        list(
            opcoes.keys()
        ),
        key="uo_incluir_entidade"
    )

    (
        entidade_id,
        orgao_id
    ) = opcoes[
        entidade_selecionada
    ]

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_unidade_orcamentaria(
            entidade_id
        )
    )

    st.info(
        f"🔢 Código automático: {codigo}"
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_unidade_orcamentaria_incluir",
        clear_on_submit=True
    ):

        nome = st.text_input(
            "Nome da Unidade Orçamentária *",
            max_chars=200
        )

        col1, col2 = st.columns(2)

        with col1:

            codigo_tce = st.text_input(
                "Código TCE",
                max_chars=20
            )

        with col2:

            identificador_fundo = st.selectbox(
                "Identificador",
                [
                    0,
                    1,
                    2,
                    3,
                    4,
                    99
                ],
                index=0
            )

        data_envio_tce = st.date_input(
            "Data de envio ao TCE",
            value=None
        )

        ativo = st.checkbox(
            "Unidade Orçamentária ativa",
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
        codigo_tce = codigo_tce.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome da Unidade Orçamentária."
            )

            return

        # ====================================================
        # NOME DUPLICADO
        # ====================================================

        if unidade_orcamentaria_nome_duplicado(
            entidade_id,
            nome
        ):

            st.warning(
                "⚠️ Já existe uma Unidade Orçamentária "
                "com esse nome nesta entidade."
            )

            return

        # ====================================================
        # CÓDIGO TCE DUPLICADO
        # ====================================================

        if codigo_tce:

            codigo_tce_existente = _sisget_fetchone(
                """
                SELECT id
                FROM unidades_orcamentarias
                WHERE entidade_id = ?
                  AND codigo_tce = ?
                """,
                (
                    entidade_id,
                    codigo_tce
                )
            )

            if codigo_tce_existente:

                st.warning(
                    "⚠️ Esse Código TCE já está cadastrado "
                    "nesta entidade."
                )

                return

        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_unidade_orcamentaria(
                entidade_id
            )
        )

        if not codigo:

            st.error(
                "❌ Não foi possível gerar o código."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO unidades_orcamentarias
            (
                entidade_id,
                orgao_id,
                codigo,
                nome,
                ativo,
                codigo_tce,
                identificador_fundo,
                data_envio_tce
            )
            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                entidade_id,
                orgao_id,
                codigo,
                nome,
                ativo,
                codigo_tce if codigo_tce else None,
                identificador_fundo,
                data_envio_tce
            )
        )

        if sucesso:

            st.success(
                "✅ Unidade Orçamentária cadastrada "
                f"com sucesso! Código: {codigo}"
            )


# ============================================================
# UNIDADE ORÇAMENTÁRIA - LOCALIZAR
# ============================================================

def unidade_orcamentaria_localizar():

    st.subheader(
        "🔎 Localizar Unidades Orçamentárias"
    )

    col1, col2 = st.columns(2)

    with col1:

        filtro_nome = st.text_input(
            "Nome",
            key="uo_localizar_nome"
        )

    with col2:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todas",
                "Ativas",
                "Inativas"
            ],
            key="uo_localizar_situacao"
        )

    sql = """
        SELECT
            u.id,

            o.codigo || ' - ' || o.nome
                AS "Órgão",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            u.codigo
                AS "Código",

            u.nome
                AS "Unidade Orçamentária",

            COALESCE(
                u.codigo_tce,
                ''
            ) AS "Código TCE",

            u.identificador_fundo
                AS "Identificador",

            u.data_envio_tce
                AS "Envio TCE",

            CASE
                WHEN u.ativo = TRUE
                    THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        WHERE 1 = 1
    """

    parametros = []

    if filtro_nome.strip():

        sql += """
            AND u.nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )

    if filtro_situacao == "Ativas":

        sql += """
            AND u.ativo = TRUE
        """

    elif filtro_situacao == "Inativas":

        sql += """
            AND u.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma Unidade Orçamentária encontrada."
        )

        return None

    st.caption(
        f"Registros encontrados: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="unidades_orcamentarias",
        coluna_id="id",
        altura=420
    )


# ============================================================
# UNIDADE ORÇAMENTÁRIA - ALTERAR
# ============================================================

def unidade_orcamentaria_alterar(
    unidade_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            u.id,
            u.entidade_id,
            u.orgao_id,
            u.codigo,
            u.nome,
            u.ativo,
            u.codigo_tce,
            u.identificador_fundo,
            u.data_envio_tce,
            e.codigo,
            e.nome,
            o.codigo,
            o.nome

        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        WHERE u.id = ?
        """,
        (
            unidade_id,
        )
    )

    if not registro:

        st.error(
            "❌ Unidade Orçamentária não encontrada."
        )

        return

    (
        id_unidade,
        entidade_id,
        orgao_id,
        codigo_atual,
        nome_atual,
        ativo_atual,
        codigo_tce_atual,
        identificador_atual,
        data_envio_atual,
        codigo_entidade,
        nome_entidade,
        codigo_orgao,
        nome_orgao
    ) = registro

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

    st.text_input(
        "Órgão",
        value=(
            f"{codigo_orgao} - {nome_orgao}"
        ),
        disabled=True
    )

    st.text_input(
        "Entidade",
        value=(
            f"{codigo_entidade} - {nome_entidade}"
        ),
        disabled=True
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_uo_alterar_{unidade_id}"
    ):

        st.text_input(
            "Código",
            value=codigo_atual or "",
            disabled=True
        )

        nome = st.text_input(
            "Nome da Unidade Orçamentária *",
            value=nome_atual or "",
            max_chars=200
        )

        col1, col2 = st.columns(2)

        with col1:

            codigo_tce = st.text_input(
                "Código TCE",
                value=codigo_tce_atual or "",
                max_chars=20
            )

        identificadores = [
            0,
            1,
            2,
            3,
            4,
            99
        ]

        try:

            indice_identificador = (
                identificadores.index(
                    int(
                        identificador_atual
                        if identificador_atual is not None
                        else 0
                    )
                )
            )

        except (
            ValueError,
            TypeError
        ):

            indice_identificador = 0

        with col2:

            identificador_fundo = st.selectbox(
                "Identificador",
                identificadores,
                index=indice_identificador
            )

        data_envio_tce = st.date_input(
            "Data de envio ao TCE",
            value=data_envio_atual
        )

        st.markdown("---")

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
            "sisget_id_unidades_orcamentarias"
        ] = None

        st.session_state[
            "sisget_tela_unidades_orcamentarias"
        ] = "localizar"

        st.rerun()

    # ========================================================
    # ATIVAR / INATIVAR
    # ========================================================

    if alterar_status:

        sucesso = _sisget_salvar(
            """
            UPDATE unidades_orcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo_atual,
                unidade_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_unidades_orcamentarias"
            ] = None

            st.session_state[
                "sisget_tela_unidades_orcamentarias"
            ] = "localizar"

            st.rerun()

        return

    # ========================================================
    # EXCLUIR
    # ========================================================

    if excluir:

        try:

            cursor.execute(
                """
                DELETE FROM unidades_orcamentarias
                WHERE id = ?
                """,
                (
                    unidade_id,
                )
            )

            conn.commit()

            st.session_state[
                "sisget_id_unidades_orcamentarias"
            ] = None

            st.session_state[
                "sisget_tela_unidades_orcamentarias"
            ] = "localizar"

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                "❌ Não foi possível excluir a Unidade "
                f"Orçamentária: {erro}"
            )

        return

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()
        codigo_tce = codigo_tce.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome da Unidade Orçamentária."
            )

            return

        if unidade_orcamentaria_nome_duplicado(
            entidade_id,
            nome,
            unidade_id
        ):

            st.warning(
                "⚠️ Já existe outra Unidade Orçamentária "
                "com esse nome nesta entidade."
            )

            return

        if codigo_tce:

            codigo_tce_existente = _sisget_fetchone(
                """
                SELECT id
                FROM unidades_orcamentarias
                WHERE entidade_id = ?
                  AND codigo_tce = ?
                  AND id <> ?
                """,
                (
                    entidade_id,
                    codigo_tce,
                    unidade_id
                )
            )

            if codigo_tce_existente:

                st.warning(
                    "⚠️ Esse Código TCE já está cadastrado "
                    "nesta entidade."
                )

                return

        sucesso = _sisget_salvar(
            """
            UPDATE unidades_orcamentarias
            SET
                nome = ?,
                codigo_tce = ?,
                identificador_fundo = ?,
                data_envio_tce = ?
            WHERE id = ?
            """,
            (
                nome,
                codigo_tce if codigo_tce else None,
                identificador_fundo,
                data_envio_tce,
                unidade_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_unidades_orcamentarias"
            ] = None

            st.session_state[
                "sisget_tela_unidades_orcamentarias"
            ] = "localizar"

            st.rerun()


# ============================================================
# UNIDADE ORÇAMENTÁRIA - EXCLUIR
# ============================================================

def unidade_orcamentaria_excluir():

    st.subheader(
        "🗑️ Excluir Unidade Orçamentária"
    )

    df = _sisget_dataframe(
        """
        SELECT
            u.id,

            o.codigo || ' - ' || o.nome
                AS "Órgão",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            u.codigo
                AS "Código",

            u.nome
                AS "Unidade Orçamentária",

            CASE
                WHEN u.ativo = TRUE
                    THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhuma Unidade Orçamentária cadastrada."
        )

        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_unidades_orcamentarias",
        coluna_id="id",
        altura=420
    )

    if not registro_id:

        st.caption(
            "Dê duplo clique na Unidade Orçamentária "
            "que deseja excluir."
        )

        return

    unidade = _sisget_fetchone(
        """
        SELECT
            codigo,
            nome
        FROM unidades_orcamentarias
        WHERE id = ?
        """,
        (
            registro_id,
        )
    )

    if not unidade:

        return

    codigo = unidade[0]
    nome = unidade[1]

    st.markdown("---")

    st.error(
        f"⚠️ Você está prestes a excluir "
        f"**{codigo} - {nome}**."
    )

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta Unidade Orçamentária.",
        key=f"confirmar_exclusao_uo_{registro_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"btn_excluir_uo_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação antes de excluir."
            )

            return

        try:

            cursor.execute(
                """
                DELETE FROM unidades_orcamentarias
                WHERE id = ?
                """,
                (
                    registro_id,
                )
            )

            conn.commit()

            st.success(
                "✅ Unidade Orçamentária excluída com sucesso!"
            )

            st.session_state[
                "sisget_tela_unidades_orcamentarias"
            ] = "principal"

            st.session_state[
                "sisget_id_unidades_orcamentarias"
            ] = None

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                "❌ Não foi possível excluir a Unidade "
                f"Orçamentária: {erro}"
            )

# ============================================================
# CADASTRO DE UNIDADES ADMINISTRATIVAS
# ============================================================

def cadastro_unidades_administrativas():

    sisget_tela_principal(
        titulo="Unidades Administrativas",
        chave="unidades_administrativas",
        func_incluir=unidade_administrativa_incluir,
        func_localizar=unidade_administrativa_localizar,
        func_alterar=unidade_administrativa_alterar,
        func_excluir=unidade_administrativa_excluir,
        func_imprimir=unidade_administrativa_imprimir,
        icone="🏬"
    )


# ============================================================
# PRÓXIMO CÓDIGO DA UNIDADE ADMINISTRATIVA
#
# UO:
# 001.001.001
#
# UA:
# 001.001.001.001
# 001.001.001.002
#
# REUTILIZA O PRIMEIRO CÓDIGO LIVRE
# ============================================================

def sisget_proximo_codigo_unidade_administrativa(
    unidade_orcamentaria_id
):

    # ========================================================
    # BUSCAR CÓDIGO DA UO
    # ========================================================

    unidade = _sisget_fetchone(
        """
        SELECT codigo
        FROM unidades_orcamentarias
        WHERE id = ?
        """,
        (
            unidade_orcamentaria_id,
        )
    )

    if not unidade:

        return None

    codigo_uo = str(
        unidade[0] or ""
    ).strip()

    # ========================================================
    # BUSCAR CÓDIGOS JÁ UTILIZADOS
    # ========================================================

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM unidades_administrativas
        WHERE unidade_orcamentaria_id = ?
        ORDER BY codigo
        """,
        (
            unidade_orcamentaria_id,
        )
    )

    numeros_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            parte = (
                codigo.split(".")[-1]
            )

            numeros_usados.add(
                int(parte)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    # ========================================================
    # PRIMEIRO NÚMERO LIVRE
    # ========================================================

    proximo = 1

    while proximo in numeros_usados:

        proximo += 1

    numero_ua = str(
        proximo
    ).zfill(3)

    return (
        f"{codigo_uo}.{numero_ua}"
    )


# ============================================================
# VALIDAR NOME DUPLICADO
# ============================================================

def unidade_administrativa_nome_duplicado(
    unidade_orcamentaria_id,
    nome,
    unidade_id=None
):

    nome = nome.strip()

    if unidade_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM unidades_administrativas
            WHERE unidade_orcamentaria_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                unidade_orcamentaria_id,
                nome
            )
        )

    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM unidades_administrativas
            WHERE unidade_orcamentaria_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                unidade_orcamentaria_id,
                nome,
                unidade_id
            )
        )

    return resultado is not None


# ============================================================
# UNIDADE ADMINISTRATIVA - INCLUIR
# ============================================================

def unidade_administrativa_incluir():

    st.subheader(
        "🏬 Dados da Unidade Administrativa"
    )

    # ========================================================
    # BUSCAR UNIDADES ORÇAMENTÁRIAS ATIVAS
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            u.id,
            u.codigo,
            u.nome,

            e.id,
            e.codigo,
            e.nome,

            o.id,
            o.codigo,
            o.nome

        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        WHERE u.ativo = TRUE
          AND e.ativo = TRUE
          AND o.ativo = TRUE

        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo
        """
    )

    if not unidades:

        st.warning(
            "⚠️ Nenhuma Unidade Orçamentária ativa cadastrada."
        )

        st.info(
            "Cadastre primeiro a Unidade Orçamentária."
        )

        return

    # ========================================================
    # OPÇÕES
    # ========================================================

    opcoes = {}

    for (
        uo_id,
        codigo_uo,
        nome_uo,
        entidade_id,
        codigo_entidade,
        nome_entidade,
        orgao_id,
        codigo_orgao,
        nome_orgao
    ) in unidades:

        descricao = (
            f"{codigo_orgao} - {nome_orgao}"
            f" → "
            f"{codigo_entidade} - {nome_entidade}"
            f" → "
            f"{codigo_uo} - {nome_uo}"
        )

        opcoes[
            descricao
        ] = (
            uo_id,
            entidade_id,
            orgao_id
        )

    unidade_selecionada = st.selectbox(
        "Unidade Orçamentária *",
        list(
            opcoes.keys()
        ),
        key="ua_incluir_uo"
    )

    (
        unidade_orcamentaria_id,
        entidade_id,
        orgao_id
    ) = opcoes[
        unidade_selecionada
    ]

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_unidade_administrativa(
            unidade_orcamentaria_id
        )
    )

    st.info(
        f"🔢 Código automático: {codigo}"
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_unidade_administrativa_incluir",
        clear_on_submit=True
    ):

        nome = st.text_input(
            "Nome da Unidade Administrativa *",
            max_chars=200
        )

        sigla = st.text_input(
            "Sigla",
            max_chars=30
        )

        ativo = st.checkbox(
            "Unidade Administrativa ativa",
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

        if not nome:

            st.warning(
                "⚠️ Informe o nome da Unidade Administrativa."
            )

            return

        # ====================================================
        # NOME DUPLICADO
        # ====================================================

        if unidade_administrativa_nome_duplicado(
            unidade_orcamentaria_id,
            nome
        ):

            st.warning(
                "⚠️ Já existe uma Unidade Administrativa "
                "com esse nome nesta Unidade Orçamentária."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_unidade_administrativa(
                unidade_orcamentaria_id
            )
        )

        if not codigo:

            st.error(
                "❌ Não foi possível gerar o código."
            )

            return

        # ====================================================
        # VALIDAR CÓDIGO
        # ====================================================

        codigo_existente = _sisget_fetchone(
            """
            SELECT id
            FROM unidades_administrativas
            WHERE entidade_id = ?
              AND codigo = ?
            """,
            (
                entidade_id,
                codigo
            )
        )

        if codigo_existente:

            st.warning(
                "⚠️ Esse código já está cadastrado."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO unidades_administrativas
            (
                entidade_id,
                orgao_id,
                unidade_orcamentaria_id,
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
                ?,
                ?,
                ?
            )
            """,
            (
                entidade_id,
                orgao_id,
                unidade_orcamentaria_id,
                codigo,
                nome,
                sigla if sigla else None,
                ativo
            )
        )

        if sucesso:

            st.success(
                "✅ Unidade Administrativa cadastrada "
                f"com sucesso! Código: {codigo}"
            )


# ============================================================
# UNIDADE ADMINISTRATIVA - LOCALIZAR
# ============================================================

def unidade_administrativa_localizar():

    st.subheader(
        "🔎 Localizar Unidades Administrativas"
    )

    col1, col2 = st.columns(2)

    with col1:

        filtro_nome = st.text_input(
            "Nome",
            key="ua_localizar_nome"
        )

    with col2:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todas",
                "Ativas",
                "Inativas"
            ],
            key="ua_localizar_situacao"
        )

    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            a.id,

            o.codigo || ' - ' || o.nome
                AS "Órgão",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            u.codigo || ' - ' || u.nome
                AS "Unidade Orçamentária",

            a.codigo
                AS "Código",

            a.nome
                AS "Unidade Administrativa",

            COALESCE(
                a.sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN a.ativo = TRUE
                    THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        LEFT JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        WHERE 1 = 1
    """

    parametros = []

    # ========================================================
    # FILTRO NOME
    # ========================================================

    if filtro_nome.strip():

        sql += """
            AND a.nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )

    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if filtro_situacao == "Ativas":

        sql += """
            AND a.ativo = TRUE
        """

    elif filtro_situacao == "Inativas":

        sql += """
            AND a.ativo = FALSE
        """

    # ========================================================
    # ORDENAR
    # ========================================================

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            a.codigo
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma Unidade Administrativa encontrada."
        )

        return None

    st.caption(
        f"Registros encontrados: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="unidades_administrativas",
        coluna_id="id",
        altura=420
    )


# ============================================================
# UNIDADE ADMINISTRATIVA - ALTERAR
# ============================================================

def unidade_administrativa_alterar(
    unidade_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            a.id,
            a.entidade_id,
            a.orgao_id,
            a.unidade_orcamentaria_id,
            a.codigo,
            a.nome,
            a.sigla,
            a.ativo,

            u.codigo,
            u.nome,

            e.codigo,
            e.nome,

            o.codigo,
            o.nome

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        LEFT JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        WHERE a.id = ?
        """,
        (
            unidade_id,
        )
    )

    if not registro:

        st.error(
            "❌ Unidade Administrativa não encontrada."
        )

        return

    (
        id_unidade,
        entidade_id,
        orgao_id,
        unidade_orcamentaria_id,
        codigo_atual,
        nome_atual,
        sigla_atual,
        ativo_atual,
        codigo_uo,
        nome_uo,
        codigo_entidade,
        nome_entidade,
        codigo_orgao,
        nome_orgao
    ) = registro

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
    # HIERARQUIA
    # ========================================================

    st.text_input(
        "Órgão",
        value=(
            f"{codigo_orgao} - {nome_orgao}"
        ),
        disabled=True
    )

    st.text_input(
        "Entidade",
        value=(
            f"{codigo_entidade} - {nome_entidade}"
        ),
        disabled=True
    )

    st.text_input(
        "Unidade Orçamentária",
        value=(
            f"{codigo_uo or ''} - {nome_uo or ''}"
        ),
        disabled=True
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_ua_alterar_{unidade_id}"
    ):

        st.text_input(
            "Código",
            value=codigo_atual or "",
            disabled=True
        )

        nome = st.text_input(
            "Nome da Unidade Administrativa *",
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
            "sisget_id_unidades_administrativas"
        ] = None

        st.session_state[
            "sisget_tela_unidades_administrativas"
        ] = "localizar"

        st.rerun()

    # ========================================================
    # ALTERAR SITUAÇÃO
    # ========================================================

    if alterar_status:

        sucesso = _sisget_salvar(
            """
            UPDATE unidades_administrativas
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo_atual,
                unidade_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_unidades_administrativas"
            ] = None

            st.session_state[
                "sisget_tela_unidades_administrativas"
            ] = "localizar"

            st.rerun()

        return

    # ========================================================
    # EXCLUIR
    # ========================================================

    if excluir:

        try:

            cursor.execute(
                """
                DELETE FROM unidades_administrativas
                WHERE id = ?
                """,
                (
                    unidade_id,
                )
            )

            conn.commit()

            st.session_state[
                "sisget_id_unidades_administrativas"
            ] = None

            st.session_state[
                "sisget_tela_unidades_administrativas"
            ] = "localizar"

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                "❌ Não foi possível excluir a Unidade "
                f"Administrativa: {erro}"
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
                "⚠️ Informe o nome da Unidade Administrativa."
            )

            return

        if unidade_administrativa_nome_duplicado(
            unidade_orcamentaria_id,
            nome,
            unidade_id
        ):

            st.warning(
                "⚠️ Já existe outra Unidade Administrativa "
                "com esse nome nesta Unidade Orçamentária."
            )

            return

        sucesso = _sisget_salvar(
            """
            UPDATE unidades_administrativas
            SET
                nome = ?,
                sigla = ?
            WHERE id = ?
            """,
            (
                nome,
                sigla if sigla else None,
                unidade_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_unidades_administrativas"
            ] = None

            st.session_state[
                "sisget_tela_unidades_administrativas"
            ] = "localizar"

            st.rerun()


# ============================================================
# UNIDADE ADMINISTRATIVA - EXCLUIR
# ============================================================

def unidade_administrativa_excluir():

    st.subheader(
        "🗑️ Excluir Unidade Administrativa"
    )

    df = _sisget_dataframe(
        """
        SELECT
            a.id,

            o.codigo || ' - ' || o.nome
                AS "Órgão",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            COALESCE(
                u.codigo || ' - ' || u.nome,
                ''
            ) AS "Unidade Orçamentária",

            a.codigo
                AS "Código",

            a.nome
                AS "Unidade Administrativa",

            COALESCE(
                a.sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN a.ativo = TRUE
                    THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        LEFT JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            a.codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhuma Unidade Administrativa cadastrada."
        )

        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_unidades_administrativas",
        coluna_id="id",
        altura=420
    )

    if not registro_id:

        st.caption(
            "Dê duplo clique na Unidade Administrativa "
            "que deseja excluir."
        )

        return

    unidade = _sisget_fetchone(
        """
        SELECT
            codigo,
            nome
        FROM unidades_administrativas
        WHERE id = ?
        """,
        (
            registro_id,
        )
    )

    if not unidade:

        return

    codigo = unidade[0]
    nome = unidade[1]

    # ========================================================
    # VERIFICAR SETORES VINCULADOS
    # ========================================================

    setores = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM setores
        WHERE unidade_administrativa_id = ?
        """,
        (
            registro_id,
        )
    )

    quantidade_setores = (
        setores[0]
        if setores
        else 0
    )

    st.markdown("---")

    st.error(
        f"⚠️ Você está prestes a excluir "
        f"**{codigo} - {nome}**."
    )

    if quantidade_setores > 0:

        st.warning(
            "⚠️ Esta Unidade Administrativa possui "
            f"{quantidade_setores} setor(es) vinculado(s). "
            "Remova os vínculos antes de excluir."
        )

        return

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta Unidade Administrativa.",
        key=f"confirmar_exclusao_ua_{registro_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"btn_excluir_ua_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação antes de excluir."
            )

            return

        try:

            cursor.execute(
                """
                DELETE FROM unidades_administrativas
                WHERE id = ?
                """,
                (
                    registro_id,
                )
            )

            conn.commit()

            st.success(
                "✅ Unidade Administrativa excluída com sucesso!"
            )

            st.session_state[
                "sisget_tela_unidades_administrativas"
            ] = "principal"

            st.session_state[
                "sisget_id_unidades_administrativas"
            ] = None

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                "❌ Não foi possível excluir a Unidade "
                f"Administrativa: {erro}"
            )


# ============================================================
# UNIDADE ADMINISTRATIVA - IMPRIMIR
# ============================================================

def unidade_administrativa_imprimir():

    st.subheader(
        "🖨️ Relatório de Unidades Administrativas"
    )

    # ========================================================
    # FILTRO
    # ========================================================

    situacao = st.selectbox(
        "Situação",
        [
            "Todas",
            "Ativas",
            "Inativas"
        ],
        key="ua_imprimir_situacao"
    )

    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            o.codigo,
            o.nome,

            e.codigo,
            e.nome,

            u.codigo,
            u.nome,

            a.codigo,
            a.nome,

            COALESCE(
                a.sigla,
                ''
            ),

            a.ativo

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        LEFT JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        WHERE 1 = 1
    """

    if situacao == "Ativas":

        sql += """
            AND a.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND a.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            a.codigo
    """

    dados = _sisget_fetch(
        sql
    )

    if not dados:

        st.info(
            "Nenhuma Unidade Administrativa encontrada."
        )

        return

    # ========================================================
    # DATAFRAME
    # ========================================================

    visualizacao = []

    for registro in dados:

        visualizacao.append({

            "Órgão":
                f"{registro[0]} - {registro[1]}",

            "Entidade":
                f"{registro[2]} - {registro[3]}",

            "Unidade Orçamentária":
                (
                    f"{registro[4]} - {registro[5]}"
                    if registro[4]
                    else ""
                ),

            "Código":
                registro[6],

            "Unidade Administrativa":
                registro[7],

            "Sigla":
                registro[8],

            "Situação":
                (
                    "Ativa"
                    if registro[9]
                    else "Inativa"
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
        f"Total de Unidades Administrativas: {len(df)}"
    )

    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_unidades_administrativas"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8 * cm,
            leftMargin=0.8 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm
        )

        estilos = (
            getSampleStyleSheet()
        )

        texto_tabela = ParagraphStyle(
            "TextoTabelaUA",
            parent=estilos["Normal"],
            fontSize=7,
            leading=8
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
                "Relatório de Unidades Administrativas",
                estilos["Heading2"]
            )
        )

        elementos.append(
            Paragraph(
                f"Situação: {situacao}",
                estilos["Normal"]
            )
        )

        elementos.append(
            Spacer(
                1,
                0.4 * cm
            )
        )

        # ====================================================
        # TABELA
        # ====================================================

        tabela_dados = [[
            "Órgão",
            "Entidade",
            "UO",
            "Código",
            "Unidade Administrativa",
            "Sigla",
            "Situação"
        ]]

        for registro in dados:

            tabela_dados.append([

                Paragraph(
                    f"{registro[0]} - {registro[1]}",
                    texto_tabela
                ),

                Paragraph(
                    f"{registro[2]} - {registro[3]}",
                    texto_tabela
                ),

                Paragraph(
                    (
                        f"{registro[4]} - {registro[5]}"
                        if registro[4]
                        else ""
                    ),
                    texto_tabela
                ),

                str(
                    registro[6] or ""
                ),

                Paragraph(
                    str(
                        registro[7] or ""
                    ),
                    texto_tabela
                ),

                str(
                    registro[8] or ""
                ),

                (
                    "Ativa"
                    if registro[9]
                    else "Inativa"
                )
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                2.5 * cm,
                2.7 * cm,
                3.0 * cm,
                2.2 * cm,
                4.0 * cm,
                1.5 * cm,
                1.5 * cm
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
                    7
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3
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

        documento.build(
            elementos
        )

        buffer.seek(0)

        st.download_button(
            label="⬇️ Baixar Relatório em PDF",
            data=buffer,
            file_name="relatorio_unidades_administrativas.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_unidades_administrativas"
        )


# ============================================================
# CADASTRO DE SETORES
# ============================================================

def cadastro_setores():

    sisget_tela_principal(
        titulo="Cadastro de Setores",
        chave="setores",
        func_incluir=setor_incluir,
        func_localizar=setor_localizar,
        func_alterar=setor_alterar,
        func_excluir=setor_excluir,
        func_imprimir=setor_imprimir,
        icone="🧩"
    )


# ============================================================
# PRÓXIMO CÓDIGO DO SETOR
#
# UA:
# 001.001.001.001
#
# SETOR:
# 001.001.001.001.001
# 001.001.001.001.002
#
# ============================================================

def sisget_proximo_codigo_setor(
    unidade_administrativa_id
):

    unidade = _sisget_fetchone(
        """
        SELECT codigo
        FROM unidades_administrativas
        WHERE id = ?
        """,
        (
            unidade_administrativa_id,
        )
    )

    if not unidade:

        return None

    codigo_unidade = str(
        unidade[0] or ""
    ).strip()

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM setores
        WHERE unidade_administrativa_id = ?
        ORDER BY codigo
        """,
        (
            unidade_administrativa_id,
        )
    )

    numeros_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            parte = (
                codigo.split(".")[-1]
            )

            numeros_usados.add(
                int(parte)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    proximo = 1

    while proximo in numeros_usados:

        proximo += 1

    numero_setor = str(
        proximo
    ).zfill(3)

    return (
        f"{codigo_unidade}.{numero_setor}"
    )


# ============================================================
# VALIDAR NOME DUPLICADO
# ============================================================

def setor_nome_duplicado(
    unidade_administrativa_id,
    nome,
    setor_id=None
):

    nome = nome.strip()

    if setor_id is None:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM setores
            WHERE unidade_administrativa_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
            """,
            (
                unidade_administrativa_id,
                nome
            )
        )

    else:

        resultado = _sisget_fetchone(
            """
            SELECT id
            FROM setores
            WHERE unidade_administrativa_id = ?
              AND LOWER(TRIM(nome)) = LOWER(TRIM(?))
              AND id <> ?
            """,
            (
                unidade_administrativa_id,
                nome,
                setor_id
            )
        )

    return resultado is not None


# ============================================================
# SETOR - INCLUIR
# ============================================================

# ============================================================
# SETOR - INCLUIR
# ============================================================

# ============================================================
# SETOR - INCLUIR
# ============================================================

def setor_incluir():

    st.subheader(
        "🧩 Dados do Setor"
    )

    # ========================================================
    # BUSCAR UNIDADES ADMINISTRATIVAS ATIVAS
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            a.id,
            a.codigo,
            a.nome,

            e.id,
            e.codigo,
            e.nome,

            o.codigo,
            o.nome

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        WHERE a.ativo = TRUE
          AND e.ativo = TRUE
          AND o.ativo = TRUE

        ORDER BY
            o.codigo,
            e.codigo,
            a.codigo
        """
    )

    if not unidades:

        st.warning(
            "⚠️ Nenhuma Unidade Administrativa ativa cadastrada."
        )

        st.info(
            "Cadastre primeiro uma Unidade Administrativa."
        )

        return

    # ========================================================
    # OPÇÕES DAS UNIDADES ADMINISTRATIVAS
    # ========================================================

    opcoes_unidades = {}

    for (
        ua_id,
        codigo_ua,
        nome_ua,
        entidade_id,
        codigo_entidade,
        nome_entidade,
        codigo_orgao,
        nome_orgao
    ) in unidades:

        descricao = (
            f"{codigo_orgao} - {nome_orgao}"
            f" → "
            f"{codigo_entidade} - {nome_entidade}"
            f" → "
            f"{codigo_ua} - {nome_ua}"
        )

        opcoes_unidades[
            descricao
        ] = (
            ua_id,
            entidade_id
        )

    # ========================================================
    # UNIDADE ADMINISTRATIVA
    # ========================================================

    unidade_selecionada = st.selectbox(
        "Unidade Administrativa *",
        list(
            opcoes_unidades.keys()
        ),
        key="setor_incluir_ua"
    )

    (
        unidade_administrativa_id,
        entidade_id
    ) = opcoes_unidades[
        unidade_selecionada
    ]

    # ========================================================
    # GERAR CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_setor(
            unidade_administrativa_id
        )
    )

    st.info(
        f"🔢 Código automático: {codigo}"
    )

    # ========================================================
    # TIPO DE ESTRUTURA
    # ========================================================

    st.markdown(
        "### 🏗️ Tipo de Estrutura"
    )

    chave_tipo = (
        "setor_incluir_tipo_estrutura"
    )

    if chave_tipo not in st.session_state:

        st.session_state[
            chave_tipo
        ] = "principal"

    col1, col2 = st.columns(2)

    # ========================================================
    # BOTÃO SETOR PRINCIPAL
    # ========================================================

    with col1:

        if st.button(
            "🏢 Setor Principal",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state[
                    chave_tipo
                ] == "principal"
                else "secondary"
            ),
            key="btn_setor_principal"
        ):

            st.session_state[
                chave_tipo
            ] = "principal"

            st.rerun()

    # ========================================================
    # BOTÃO SUBSETOR
    # ========================================================

    with col2:

        if st.button(
            "↳ Subsetor",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state[
                    chave_tipo
                ] == "subsetor"
                else "secondary"
            ),
            key="btn_setor_subsetor"
        ):

            st.session_state[
                chave_tipo
            ] = "subsetor"

            st.rerun()

    tipo_estrutura = (
        st.session_state[
            chave_tipo
        ]
    )

    # ========================================================
    # DEFINIR SETOR PAI
    # ========================================================

    setor_pai_id = None
    setor_superior = None
    opcoes_setores_principais = {}

    # ========================================================
    # SE FOR SUBSETOR
    # ========================================================

    if tipo_estrutura == "subsetor":

        st.markdown("---")

        st.markdown(
            "### ↳ Vincular ao Setor Principal"
        )

        # ====================================================
        # BUSCAR SOMENTE SETORES PRINCIPAIS
        # ====================================================

        setores_principais = _sisget_fetch(
            """
            SELECT
                id,
                codigo,
                nome

            FROM setores

            WHERE unidade_administrativa_id = ?
              AND setor_pai_id IS NULL
              AND ativo = TRUE

            ORDER BY
                codigo,
                nome
            """,
            (
                unidade_administrativa_id,
            )
        )

        if not setores_principais:

            st.warning(
                "⚠️ Nenhum setor principal cadastrado "
                "nesta Unidade Administrativa."
            )

            st.info(
                "Cadastre primeiro um Setor Principal "
                "para depois cadastrar um Subsetor."
            )

        else:

            for (
                setor_id,
                codigo_setor,
                nome_setor
            ) in setores_principais:

                opcoes_setores_principais[
                    f"{codigo_setor} - {nome_setor}"
                ] = setor_id

            setor_superior = st.selectbox(
                "Setor Principal *",
                list(
                    opcoes_setores_principais.keys()
                ),
                key="setor_incluir_setor_superior"
            )

            setor_pai_id = (
                opcoes_setores_principais[
                    setor_superior
                ]
            )

    # ========================================================
    # IDENTIFICAÇÃO VISUAL
    # ========================================================

    st.markdown("---")

    if tipo_estrutura == "principal":

        st.success(
            "🏢 Você está cadastrando um Setor Principal."
        )

    else:

        st.info(
            "↳ Você está cadastrando um Subsetor."
        )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_setor_incluir",
        clear_on_submit=True
    ):

        # ====================================================
        # NOME
        # ====================================================

        if tipo_estrutura == "principal":

            nome = st.text_input(
                "Nome do Setor *",
                max_chars=200,
                placeholder="Ex.: Departamento de Compras"
            )

        else:

            nome = st.text_input(
                "Nome do Subsetor *",
                max_chars=200,
                placeholder="Ex.: Licitações"
            )

        # ====================================================
        # SIGLA
        # ====================================================

        sigla = st.text_input(
            "Sigla",
            max_chars=30,
            placeholder="Ex.: COMPRAS"
        )

        # ====================================================
        # SITUAÇÃO
        # ====================================================

        ativo = st.checkbox(
            (
                "Setor ativo"
                if tipo_estrutura == "principal"
                else "Subsetor ativo"
            ),
            value=True
        )

        st.markdown("---")

        # ====================================================
        # SALVAR
        # ====================================================

        salvar = st.form_submit_button(
            (
                "💾 Salvar Setor"
                if tipo_estrutura == "principal"
                else "💾 Salvar Subsetor"
            ),
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
        # VALIDAR NOME
        # ====================================================

        if not nome:

            if tipo_estrutura == "principal":

                st.warning(
                    "⚠️ Informe o nome do setor."
                )

            else:

                st.warning(
                    "⚠️ Informe o nome do subsetor."
                )

            return

        # ====================================================
        # VALIDAR SUBSETOR
        # ====================================================

        if tipo_estrutura == "subsetor":

            if not opcoes_setores_principais:

                st.warning(
                    "⚠️ Não existe Setor Principal disponível."
                )

                return

            if setor_pai_id is None:

                st.warning(
                    "⚠️ Selecione o Setor Principal "
                    "ao qual o Subsetor pertence."
                )

                return

        else:

            setor_pai_id = None

        # ====================================================
        # VALIDAR NOME DUPLICADO
        # ====================================================

        if setor_nome_duplicado(
            unidade_administrativa_id,
            nome
        ):

            st.warning(
                "⚠️ Já existe um setor com esse nome "
                "nesta Unidade Administrativa."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_setor(
                unidade_administrativa_id
            )
        )

        if not codigo:

            st.error(
                "❌ Não foi possível gerar o código do setor."
            )

            return

        # ====================================================
        # VALIDAR CÓDIGO DUPLICADO
        # ====================================================

        codigo_existente = _sisget_fetchone(
            """
            SELECT id
            FROM setores
            WHERE entidade_id = ?
              AND codigo = ?
            """,
            (
                entidade_id,
                codigo
            )
        )

        if codigo_existente:

            st.warning(
                "⚠️ Esse código já está cadastrado."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO setores
            (
                entidade_id,
                unidade_administrativa_id,
                setor_pai_id,
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
                ?,
                ?,
                ?
            )
            """,
            (
                entidade_id,
                unidade_administrativa_id,
                setor_pai_id,
                codigo,
                nome,
                sigla if sigla else None,
                ativo
            )
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            if tipo_estrutura == "principal":

                st.success(
                    f"✅ Setor Principal cadastrado com sucesso! "
                    f"Código: {codigo}"
                )

            else:

                st.success(
                    f"✅ Subsetor cadastrado com sucesso! "
                    f"Código: {codigo}"
                )
def setor_localizar():

    st.subheader(
        "🔎 Localizar Setores"
    )

    col1, col2 = st.columns(2)

    with col1:

        filtro_nome = st.text_input(
            "Nome do Setor",
            key="setor_localizar_nome"
        )

    with col2:

        filtro_situacao = st.selectbox(
            "Situação",
            [
                "Todos",
                "Ativos",
                "Inativos"
            ],
            key="setor_localizar_situacao"
        )

    sql = """
        SELECT
            s.id,

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            a.codigo || ' - ' || a.nome
                AS "Unidade Administrativa",

            COALESCE(
                p.codigo || ' - ' || p.nome,
                ''
            ) AS "Setor Superior",

            s.codigo
                AS "Código",

            s.nome
                AS "Setor",

            COALESCE(
                s.sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN s.ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM setores s

        INNER JOIN entidades e
            ON e.id = s.entidade_id

        INNER JOIN unidades_administrativas a
            ON a.id = s.unidade_administrativa_id

        LEFT JOIN setores p
            ON p.id = s.setor_pai_id

        WHERE 1 = 1
    """

    parametros = []

    if filtro_nome.strip():

        sql += """
            AND s.nome ILIKE ?
        """

        parametros.append(
            f"%{filtro_nome.strip()}%"
        )

    if filtro_situacao == "Ativos":

        sql += """
            AND s.ativo = TRUE
        """

    elif filtro_situacao == "Inativos":

        sql += """
            AND s.ativo = FALSE
        """

    sql += """
        ORDER BY
            e.codigo,
            a.codigo,
            s.codigo
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhum setor encontrado."
        )

        return None

    st.caption(
        f"Registros encontrados: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="setores",
        coluna_id="id",
        altura=420
    )


# ============================================================
# SETOR - ALTERAR
# ============================================================

def setor_alterar(
    setor_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            s.id,
            s.entidade_id,
            s.unidade_administrativa_id,
            s.setor_pai_id,
            s.codigo,
            s.nome,
            s.sigla,
            s.ativo,

            a.codigo,
            a.nome,

            e.codigo,
            e.nome

        FROM setores s

        INNER JOIN entidades e
            ON e.id = s.entidade_id

        INNER JOIN unidades_administrativas a
            ON a.id = s.unidade_administrativa_id

        WHERE s.id = ?
        """,
        (
            setor_id,
        )
    )

    if not registro:

        st.error(
            "❌ Setor não encontrado."
        )

        return

    (
        id_setor,
        entidade_id,
        unidade_administrativa_id,
        setor_pai_id,
        codigo_atual,
        nome_atual,
        sigla_atual,
        ativo_atual,
        codigo_ua,
        nome_ua,
        codigo_entidade,
        nome_entidade
    ) = registro

    if ativo_atual:

        st.success(
            "🟢 Situação: ATIVO"
        )

    else:

        st.warning(
            "🔴 Situação: INATIVO"
        )

    st.text_input(
        "Entidade",
        value=(
            f"{codigo_entidade} - {nome_entidade}"
        ),
        disabled=True
    )

    st.text_input(
        "Unidade Administrativa",
        value=(
            f"{codigo_ua} - {nome_ua}"
        ),
        disabled=True
    )

    setores_superiores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM setores
        WHERE unidade_administrativa_id = ?
          AND id <> ?
        ORDER BY codigo
        """,
        (
            unidade_administrativa_id,
            setor_id
        )
    )

    opcoes_superiores = {
        "Sem setor superior": None
    }

    indice_atual = 0

    for sid, codigo, nome in setores_superiores:

        descricao = (
            f"{codigo} - {nome}"
        )

        opcoes_superiores[
            descricao
        ] = sid

    lista_superiores = list(
        opcoes_superiores.keys()
    )

    if setor_pai_id is not None:

        for i, descricao in enumerate(
            lista_superiores
        ):

            if (
                opcoes_superiores[
                    descricao
                ] == setor_pai_id
            ):

                indice_atual = i

                break

    with st.form(
        f"form_setor_alterar_{setor_id}"
    ):

        st.text_input(
            "Código",
            value=codigo_atual or "",
            disabled=True
        )

        setor_superior = st.selectbox(
            "Setor superior",
            lista_superiores,
            index=indice_atual
        )

        nome = st.text_input(
            "Nome do Setor *",
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

    if cancelar:

        st.session_state[
            "sisget_id_setores"
        ] = None

        st.session_state[
            "sisget_tela_setores"
        ] = "localizar"

        st.rerun()

    if alterar_status:

        sucesso = _sisget_salvar(
            """
            UPDATE setores
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo_atual,
                setor_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_setores"
            ] = None

            st.session_state[
                "sisget_tela_setores"
            ] = "localizar"

            st.rerun()

        return

    if excluir:

        filhos = _sisget_fetchone(
            """
            SELECT COUNT(*)
            FROM setores
            WHERE setor_pai_id = ?
            """,
            (
                setor_id,
            )
        )

        quantidade_filhos = (
            filhos[0]
            if filhos
            else 0
        )

        if quantidade_filhos > 0:

            st.error(
                "❌ Não é possível excluir este setor porque "
                f"existem {quantidade_filhos} subsetor(es) vinculados."
            )

            return

        try:

            cursor.execute(
                """
                DELETE FROM setores
                WHERE id = ?
                """,
                (
                    setor_id,
                )
            )

            conn.commit()

            st.session_state[
                "sisget_id_setores"
            ] = None

            st.session_state[
                "sisget_tela_setores"
            ] = "localizar"

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                f"❌ Não foi possível excluir o setor: {erro}"
            )

        return

    if salvar:

        nome = nome.strip()
        sigla = sigla.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome do setor."
            )

            return

        if setor_nome_duplicado(
            unidade_administrativa_id,
            nome,
            setor_id
        ):

            st.warning(
                "⚠️ Já existe outro setor com esse nome "
                "nesta Unidade Administrativa."
            )

            return

        novo_setor_pai_id = (
            opcoes_superiores[
                setor_superior
            ]
        )

        sucesso = _sisget_salvar(
            """
            UPDATE setores
            SET
                setor_pai_id = ?,
                nome = ?,
                sigla = ?
            WHERE id = ?
            """,
            (
                novo_setor_pai_id,
                nome,
                sigla if sigla else None,
                setor_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_setores"
            ] = None

            st.session_state[
                "sisget_tela_setores"
            ] = "localizar"

            st.rerun()


# ============================================================
# SETOR - EXCLUIR
# ============================================================

def setor_excluir():

    st.subheader(
        "🗑️ Excluir Setor"
    )

    df = _sisget_dataframe(
        """
        SELECT
            s.id,

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            a.codigo || ' - ' || a.nome
                AS "Unidade Administrativa",

            s.codigo
                AS "Código",

            s.nome
                AS "Setor",

            COALESCE(
                s.sigla,
                ''
            ) AS "Sigla",

            CASE
                WHEN s.ativo = TRUE
                    THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM setores s

        INNER JOIN entidades e
            ON e.id = s.entidade_id

        INNER JOIN unidades_administrativas a
            ON a.id = s.unidade_administrativa_id

        ORDER BY
            e.codigo,
            a.codigo,
            s.codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhum setor cadastrado."
        )

        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_setores",
        coluna_id="id",
        altura=420
    )

    if not registro_id:

        st.caption(
            "Dê duplo clique no setor que deseja excluir."
        )

        return

    setor = _sisget_fetchone(
        """
        SELECT
            codigo,
            nome
        FROM setores
        WHERE id = ?
        """,
        (
            registro_id,
        )
    )

    if not setor:

        return

    codigo = setor[0]
    nome = setor[1]

    filhos = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM setores
        WHERE setor_pai_id = ?
        """,
        (
            registro_id,
        )
    )

    quantidade_filhos = (
        filhos[0]
        if filhos
        else 0
    )

    st.markdown("---")

    st.error(
        f"⚠️ Você está prestes a excluir "
        f"**{codigo} - {nome}**."
    )

    if quantidade_filhos > 0:

        st.warning(
            "⚠️ Este setor possui "
            f"{quantidade_filhos} subsetor(es) vinculado(s)."
        )

        return

    confirmar = st.checkbox(
        "Confirmo que desejo excluir este setor.",
        key=f"confirmar_setor_{registro_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"btn_excluir_setor_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação antes de excluir."
            )

            return

        try:

            cursor.execute(
                """
                DELETE FROM setores
                WHERE id = ?
                """,
                (
                    registro_id,
                )
            )

            conn.commit()

            st.success(
                "✅ Setor excluído com sucesso!"
            )

            st.session_state[
                "sisget_tela_setores"
            ] = "principal"

            st.session_state[
                "sisget_id_setores"
            ] = None

            st.rerun()

        except Exception as erro:

            conn.rollback()

            st.error(
                f"❌ Não foi possível excluir o setor: {erro}"
            )


# ============================================================
# SETOR - IMPRIMIR
# ============================================================

def setor_imprimir():

    st.subheader(
        "🖨️ Relatório de Setores"
    )

    situacao = st.selectbox(
        "Situação",
        [
            "Todos",
            "Ativos",
            "Inativos"
        ],
        key="setor_imprimir_situacao"
    )

    sql = """
        SELECT
            e.codigo,
            e.nome,

            a.codigo,
            a.nome,

            s.codigo,
            s.nome,

            COALESCE(
                s.sigla,
                ''
            ),

            COALESCE(
                p.codigo || ' - ' || p.nome,
                ''
            ),

            s.ativo

        FROM setores s

        INNER JOIN entidades e
            ON e.id = s.entidade_id

        INNER JOIN unidades_administrativas a
            ON a.id = s.unidade_administrativa_id

        LEFT JOIN setores p
            ON p.id = s.setor_pai_id

        WHERE 1 = 1
    """

    if situacao == "Ativos":

        sql += """
            AND s.ativo = TRUE
        """

    elif situacao == "Inativos":

        sql += """
            AND s.ativo = FALSE
        """

    sql += """
        ORDER BY
            e.codigo,
            a.codigo,
            s.codigo
    """

    dados = _sisget_fetch(
        sql
    )

    if not dados:

        st.info(
            "Nenhum setor encontrado."
        )

        return

    visualizacao = []

    for registro in dados:

        visualizacao.append({

            "Entidade":
                f"{registro[0]} - {registro[1]}",

            "Unidade Administrativa":
                f"{registro[2]} - {registro[3]}",

            "Código":
                registro[4],

            "Setor":
                registro[5],

            "Sigla":
                registro[6],

            "Setor Superior":
                registro[7],

            "Situação":
                (
                    "Ativo"
                    if registro[8]
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
        f"Total de setores: {len(df)}"
    )

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_setores"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8 * cm,
            leftMargin=0.8 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm
        )

        estilos = (
            getSampleStyleSheet()
        )

        texto_tabela = ParagraphStyle(
            "TextoTabelaSetores",
            parent=estilos["Normal"],
            fontSize=7,
            leading=8
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
                "Relatório de Setores",
                estilos["Heading2"]
            )
        )

        elementos.append(
            Paragraph(
                f"Situação: {situacao}",
                estilos["Normal"]
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
            "Unidade",
            "Código",
            "Setor",
            "Sigla",
            "Superior",
            "Situação"
        ]]

        for registro in dados:

            tabela_dados.append([

                Paragraph(
                    f"{registro[0]} - {registro[1]}",
                    texto_tabela
                ),

                Paragraph(
                    f"{registro[2]} - {registro[3]}",
                    texto_tabela
                ),

                str(
                    registro[4] or ""
                ),

                Paragraph(
                    str(
                        registro[5] or ""
                    ),
                    texto_tabela
                ),

                str(
                    registro[6] or ""
                ),

                Paragraph(
                    str(
                        registro[7] or ""
                    ),
                    texto_tabela
                ),

                (
                    "Ativo"
                    if registro[8]
                    else "Inativo"
                )
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                2.7 * cm,
                3.0 * cm,
                2.4 * cm,
                3.5 * cm,
                1.3 * cm,
                3.0 * cm,
                1.5 * cm
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
                    7
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3
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

        documento.build(
            elementos
        )

        buffer.seek(0)

        st.download_button(
            label="⬇️ Baixar Relatório em PDF",
            data=buffer,
            file_name="relatorio_setores.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_setores"
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
