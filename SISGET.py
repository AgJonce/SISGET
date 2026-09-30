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
# ============================================================

def sisget_cabecalho_tela(
    titulo,
    voltar=None,
    chave=None
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

            if chave:

                chave_botao = (
                    f"sisget_btn_voltar_{chave}_{titulo}"
                )

            else:

                chave_botao = (
                    f"sisget_btn_voltar_padrao_{titulo}"
                )

            if st.button(
                "⬅️ Voltar",
                use_container_width=True,
                key=chave_botao
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

# ============================================================
# TELA PRINCIPAL PADRÃO DO SISGET
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
    # INICIALIZAÇÃO
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
                key=f"sisget_incluir_{chave}",
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
                key=f"sisget_localizar_{chave}",
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
                key=f"sisget_excluir_{chave}",
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
                key=f"sisget_imprimir_{chave}",
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
            ),
            chave=f"{chave}_incluir"
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
            ),
            chave=f"{chave}_localizar"
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
            ),
            chave=f"{chave}_alterar"
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
            ),
            chave=f"{chave}_excluir"
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
            ),
            chave=f"{chave}_imprimir"
        )

        if func_imprimir:

            func_imprimir()

        else:

            st.info(
                "Nenhum relatório configurado."
            )

    # ========================================================
    # SEGURANÇA
    # ========================================================

    else:

        st.session_state[
            chave_tela
        ] = "principal"

        st.session_state[
            chave_id
        ] = None

        st.rerun()
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


# ============================================================
# ORGANOGRAMA DO SISGET
# ============================================================

# ============================================================
# ORGANOGRAMA DO SISGET
# ============================================================

# ============================================================
# ORGANOGRAMA DO SISGET
# ============================================================

def organograma_sisget():

    st.title(
        "🌳 Organograma"
    )

    st.caption(
        "Visualização da estrutura administrativa cadastrada no SISGET."
    )

    st.markdown("---")

    # ========================================================
    # FILTROS
    # ========================================================

    col1, col2 = st.columns(
        [3, 1]
    )

    # ========================================================
    # BUSCAR ÓRGÃOS
    # ========================================================

    orgaos_filtro = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM orgaos
        ORDER BY
            codigo,
            nome
        """
    )

    opcoes_orgaos = {
        "Todos os Órgãos": None
    }

    for (
        orgao_id,
        codigo_orgao,
        nome_orgao
    ) in orgaos_filtro:

        opcoes_orgaos[
            f"{codigo_orgao} - {nome_orgao}"
        ] = orgao_id

    with col1:

        orgao_selecionado = st.selectbox(
            "Órgão",
            list(
                opcoes_orgaos.keys()
            ),
            key="organograma_filtro_orgao"
        )

    with col2:

        exibir_inativos = st.checkbox(
            "Exibir inativos",
            value=False,
            key="organograma_exibir_inativos"
        )

    orgao_id_filtro = (
        opcoes_orgaos[
            orgao_selecionado
        ]
    )

    st.markdown("---")

    # ========================================================
    # SQL DOS ÓRGÃOS
    # ========================================================

    sql_orgaos = """
        SELECT
            id,
            codigo,
            nome,
            COALESCE(
                sigla,
                ''
            ),
            ativo

        FROM orgaos

        WHERE 1 = 1
    """

    parametros_orgaos = []

    if orgao_id_filtro is not None:

        sql_orgaos += """
            AND id = ?
        """

        parametros_orgaos.append(
            orgao_id_filtro
        )

    if not exibir_inativos:

        sql_orgaos += """
            AND ativo = TRUE
        """

    sql_orgaos += """
        ORDER BY
            codigo,
            nome
    """

    orgaos = _sisget_fetch(
        sql_orgaos,
        tuple(
            parametros_orgaos
        )
    )

    if not orgaos:

        st.info(
            "Nenhum órgão encontrado."
        )

        return

    # ========================================================
    # CONTADORES
    # ========================================================

    total_orgaos = 0
    total_entidades = 0
    total_uos = 0
    total_uas = 0
    total_setores = 0
    total_subsetores = 0

    # ========================================================
    # FUNÇÃO INTERNA
    # MOSTRAR SETORES E SUBSETORES
    # ========================================================

    def mostrar_setores(
        setores,
        setor_pai_id=None,
        nivel=0
    ):

        nonlocal total_setores
        nonlocal total_subsetores

        encontrados = [
            registro
            for registro in setores
            if registro[1] == setor_pai_id
        ]

        for (
            setor_id,
            pai_id,
            codigo_setor,
            nome_setor,
            sigla_setor,
            ativo_setor
        ) in encontrados:

            # =================================================
            # IDENTIFICAR TIPO
            # =================================================

            if pai_id is None:

                total_setores += 1

                icone = "🧩"

            else:

                total_subsetores += 1

                icone = "↳"

            # =================================================
            # SIGLA
            # =================================================

            sigla_texto = (
                f" ({sigla_setor})"
                if sigla_setor
                else ""
            )

            # =================================================
            # SITUAÇÃO
            # =================================================

            situacao = (
                ""
                if ativo_setor
                else " 🔴"
            )

            # =================================================
            # INDENTAÇÃO
            # =================================================

            indentacao = (
                "&nbsp;&nbsp;&nbsp;&nbsp;"
                * (
                    nivel + 5
                )
            )

            # =================================================
            # EXIBIR SETOR
            # =================================================

            st.markdown(
                (
                    f"{indentacao}"
                    f"{icone} "
                    f"**{codigo_setor} - {nome_setor}**"
                    f"{sigla_texto}"
                    f"{situacao}"
                ),
                unsafe_allow_html=True
            )

            # =================================================
            # MOSTRAR FILHOS
            # =================================================

            mostrar_setores(
                setores,
                setor_pai_id=setor_id,
                nivel=nivel + 1
            )

    # ========================================================
    # PERCORRER ÓRGÃOS
    # ========================================================

    for (
        orgao_id,
        codigo_orgao,
        nome_orgao,
        sigla_orgao,
        ativo_orgao
    ) in orgaos:

        total_orgaos += 1

        situacao_orgao = (
            ""
            if ativo_orgao
            else " 🔴 INATIVO"
        )

        sigla_orgao_texto = (
            f" ({sigla_orgao})"
            if sigla_orgao
            else ""
        )

        # ====================================================
        # ENTIDADES DO ÓRGÃO
        # ====================================================

        sql_entidades = """
            SELECT
                id,
                codigo,
                nome,
                ativo

            FROM entidades

            WHERE orgao_id = ?
        """

        parametros_entidades = [
            orgao_id
        ]

        if not exibir_inativos:

            sql_entidades += """
                AND ativo = TRUE
            """

        sql_entidades += """
            ORDER BY
                codigo,
                nome
        """

        entidades = _sisget_fetch(
            sql_entidades,
            tuple(
                parametros_entidades
            )
        )

        # ====================================================
        # ÓRGÃO
        # ====================================================

        with st.expander(
            (
                f"🏛️ {codigo_orgao} - "
                f"{nome_orgao}"
                f"{sigla_orgao_texto}"
                f"{situacao_orgao}"
            ),
            expanded=True
        ):

            if not entidades:

                st.caption(
                    "Nenhuma entidade vinculada a este órgão."
                )

                continue

            # =================================================
            # ENTIDADES
            # =================================================

            for (
                entidade_id,
                codigo_entidade,
                nome_entidade,
                ativo_entidade
            ) in entidades:

                total_entidades += 1

                situacao_entidade = (
                    ""
                    if ativo_entidade
                    else " 🔴"
                )

                st.markdown(
                    (
                        "&nbsp;&nbsp;"
                        f"🏢 **{codigo_entidade} - {nome_entidade}**"
                        f"{situacao_entidade}"
                    ),
                    unsafe_allow_html=True
                )

                # =============================================
                # UNIDADES ORÇAMENTÁRIAS
                # =============================================

                sql_uos = """
                    SELECT
                        id,
                        codigo,
                        nome,
                        ativo

                    FROM unidades_orcamentarias

                    WHERE entidade_id = ?
                """

                parametros_uos = [
                    entidade_id
                ]

                if not exibir_inativos:

                    sql_uos += """
                        AND ativo = TRUE
                    """

                sql_uos += """
                    ORDER BY
                        codigo,
                        nome
                """

                unidades_orcamentarias = (
                    _sisget_fetch(
                        sql_uos,
                        tuple(
                            parametros_uos
                        )
                    )
                )

                if not unidades_orcamentarias:

                    st.markdown(
                        (
                            "&nbsp;&nbsp;&nbsp;&nbsp;"
                            "Nenhuma Unidade Orçamentária cadastrada."
                        ),
                        unsafe_allow_html=True
                    )

                    continue

                # =============================================
                # UNIDADES ORÇAMENTÁRIAS
                # =============================================

                for (
                    uo_id,
                    codigo_uo,
                    nome_uo,
                    ativo_uo
                ) in unidades_orcamentarias:

                    total_uos += 1

                    situacao_uo = (
                        ""
                        if ativo_uo
                        else " 🔴"
                    )

                    st.markdown(
                        (
                            "&nbsp;&nbsp;&nbsp;&nbsp;"
                            f"💼 **{codigo_uo} - {nome_uo}**"
                            f"{situacao_uo}"
                        ),
                        unsafe_allow_html=True
                    )

                    # =========================================
                    # UNIDADES ADMINISTRATIVAS
                    # =========================================

                    sql_uas = """
                        SELECT
                            id,
                            codigo,
                            nome,
                            COALESCE(
                                sigla,
                                ''
                            ),
                            ativo

                        FROM unidades_administrativas

                        WHERE unidade_orcamentaria_id = ?
                    """

                    parametros_uas = [
                        uo_id
                    ]

                    if not exibir_inativos:

                        sql_uas += """
                            AND ativo = TRUE
                        """

                    sql_uas += """
                        ORDER BY
                            codigo,
                            nome
                    """

                    unidades_administrativas = (
                        _sisget_fetch(
                            sql_uas,
                            tuple(
                                parametros_uas
                            )
                        )
                    )

                    if not unidades_administrativas:

                        st.markdown(
                            (
                                "&nbsp;&nbsp;&nbsp;&nbsp;"
                                "&nbsp;&nbsp;"
                                "Nenhuma Unidade Administrativa cadastrada."
                            ),
                            unsafe_allow_html=True
                        )

                        continue

                    # =========================================
                    # UNIDADES ADMINISTRATIVAS
                    # =========================================

                    for (
                        ua_id,
                        codigo_ua,
                        nome_ua,
                        sigla_ua,
                        ativo_ua
                    ) in unidades_administrativas:

                        total_uas += 1

                        situacao_ua = (
                            ""
                            if ativo_ua
                            else " 🔴"
                        )

                        sigla_ua_texto = (
                            f" ({sigla_ua})"
                            if sigla_ua
                            else ""
                        )

                        st.markdown(
                            (
                                "&nbsp;&nbsp;&nbsp;&nbsp;"
                                "&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"🏬 **{codigo_ua} - {nome_ua}**"
                                f"{sigla_ua_texto}"
                                f"{situacao_ua}"
                            ),
                            unsafe_allow_html=True
                        )

                        # =====================================
                        # SETORES
                        # =====================================

                        sql_setores = """
                            SELECT
                                id,
                                setor_pai_id,
                                codigo,
                                nome,
                                COALESCE(
                                    sigla,
                                    ''
                                ),
                                ativo

                            FROM setores

                            WHERE unidade_administrativa_id = ?
                        """

                        parametros_setores = [
                            ua_id
                        ]

                        if not exibir_inativos:

                            sql_setores += """
                                AND ativo = TRUE
                            """

                        sql_setores += """
                            ORDER BY
                                codigo,
                                nome
                        """

                        setores = _sisget_fetch(
                            sql_setores,
                            tuple(
                                parametros_setores
                            )
                        )

                        if not setores:

                            st.markdown(
                                (
                                    "&nbsp;&nbsp;&nbsp;&nbsp;"
                                    "&nbsp;&nbsp;&nbsp;&nbsp;"
                                    "&nbsp;&nbsp;"
                                    "Nenhum setor cadastrado."
                                ),
                                unsafe_allow_html=True
                            )

                            continue

                        # =====================================
                        # MOSTRAR SETORES
                        # =====================================

                        mostrar_setores(
                            setores,
                            setor_pai_id=None,
                            nivel=0
                        )

            st.markdown("---")

    # ========================================================
    # RESUMO
    # ========================================================

    st.subheader(
        "📊 Resumo da Estrutura"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "🏛️ Órgãos",
            total_orgaos
        )

        st.metric(
            "🏢 Entidades",
            total_entidades
        )

    with col2:

        st.metric(
            "💼 Unidades Orçamentárias",
            total_uos
        )

        st.metric(
            "🏬 Unidades Administrativas",
            total_uas
        )

    with col3:

        st.metric(
            "🧩 Setores",
            total_setores
        )

        st.metric(
            "↳ Subsetores",
            total_subsetores
        )
# ============================================================
# MÓDULO DE SOLICITAÇÕES
# ============================================================

def modulo_solicitacoes():

    sisget_tela_principal(
        titulo="Solicitações",
        chave="solicitacoes",
        func_incluir=solicitacao_incluir,
        func_localizar=solicitacao_localizar,
        func_alterar=solicitacao_alterar,
        func_excluir=solicitacao_excluir,
        func_imprimir=solicitacao_imprimir,
        icone="📝"
    )


# ============================================================
# PRÓXIMO NÚMERO DA SOLICITAÇÃO
# ============================================================

def sisget_proximo_numero_solicitacao():

    resultado = _sisget_fetchone(
        """
        SELECT COALESCE(
            MAX(numero),
            0
        )
        FROM solicitacoes
        """
    )

    if not resultado:

        return 1

    return int(
        resultado[0]
    ) + 1


# ============================================================
# SOLICITAÇÃO - INCLUIR
# ============================================================

def solicitacao_incluir():

    st.subheader(
        "📝 Nova Solicitação"
    )

    # ========================================================
    # NÚMERO
    # ========================================================

    numero = (
        sisget_proximo_numero_solicitacao()
    )

    st.info(
        f"🔢 Solicitação nº {str(numero).zfill(6)}"
    )

    # ========================================================
    # BUSCAR UNIDADES ADMINISTRATIVAS
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            a.id,
            a.codigo,
            a.nome,

            u.id,
            u.codigo,
            u.nome,

            e.id,
            e.codigo,
            e.nome,

            o.id,
            o.codigo,
            o.nome

        FROM unidades_administrativas a

        INNER JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        WHERE a.ativo = TRUE
          AND u.ativo = TRUE
          AND e.ativo = TRUE
          AND o.ativo = TRUE

        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            a.codigo
        """
    )

    if not unidades:

        st.warning(
            "⚠️ Nenhuma Unidade Administrativa ativa cadastrada."
        )

        return

    # ========================================================
    # OPÇÕES
    # ========================================================

    opcoes_unidades = {}

    for (
        ua_id,
        codigo_ua,
        nome_ua,

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
            f" → "
            f"{codigo_ua} - {nome_ua}"
        )

        opcoes_unidades[
            descricao
        ] = (
            orgao_id,
            entidade_id,
            uo_id,
            ua_id
        )

    unidade_selecionada = st.selectbox(
        "Unidade Administrativa *",
        list(
            opcoes_unidades.keys()
        ),
        key="solicitacao_incluir_unidade"
    )

    (
        orgao_id,
        entidade_id,
        unidade_orcamentaria_id,
        unidade_administrativa_id
    ) = opcoes_unidades[
        unidade_selecionada
    ]

    # ========================================================
    # SETORES
    # ========================================================

    setores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM setores
        WHERE unidade_administrativa_id = ?
          AND ativo = TRUE
        ORDER BY
            codigo,
            nome
        """,
        (
            unidade_administrativa_id,
        )
    )

    opcoes_setores = {
        "Sem setor específico": None
    }

    for (
        setor_id,
        codigo_setor,
        nome_setor
    ) in setores:

        opcoes_setores[
            f"{codigo_setor} - {nome_setor}"
        ] = setor_id

    setor_selecionado = st.selectbox(
        "Setor solicitante",
        list(
            opcoes_setores.keys()
        ),
        key="solicitacao_incluir_setor"
    )

    setor_id = (
        opcoes_setores[
            setor_selecionado
        ]
    )

    # ========================================================
    # SOLICITANTE
    # ========================================================

    usuario_logado = (
        st.session_state.get(
            "usuario_logado",
            ""
        )
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_solicitacao_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(2)

        with col1:

            tipo = st.selectbox(
                "Tipo de Solicitação *",
                [
                    "Aquisição de Material",
                    "Contratação de Serviço",
                    "Obra / Serviço de Engenharia",
                    "Tecnologia da Informação",
                    "Manutenção",
                    "Outros"
                ]
            )

        with col2:

            prioridade = st.selectbox(
                "Prioridade *",
                [
                    "Baixa",
                    "Normal",
                    "Alta",
                    "Urgente"
                ],
                index=1
            )

        titulo = st.text_input(
            "Objeto / Título da Solicitação *",
            max_chars=200,
            placeholder=(
                "Ex.: Aquisição de materiais de escritório"
            )
        )

        descricao = st.text_area(
            "Descrição",
            height=140,
            placeholder=(
                "Descreva o que está sendo solicitado."
            )
        )

        justificativa = st.text_area(
            "Justificativa *",
            height=140,
            placeholder=(
                "Informe a necessidade e o motivo da solicitação."
            )
        )

        solicitante = st.text_input(
            "Solicitante",
            value=usuario_logado,
            max_chars=200
        )

        data_solicitacao = st.date_input(
            "Data da Solicitação",
            value=datetime.now().date()
        )

        st.markdown("---")

        salvar = st.form_submit_button(
            "💾 Registrar Solicitação",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        titulo = titulo.strip()
        descricao = descricao.strip()
        justificativa = justificativa.strip()
        solicitante = solicitante.strip()

        if not titulo:

            st.warning(
                "⚠️ Informe o objeto da solicitação."
            )

            return

        if not justificativa:

            st.warning(
                "⚠️ Informe a justificativa."
            )

            return

        # ====================================================
        # RECALCULAR NÚMERO
        # ====================================================

        numero = (
            sisget_proximo_numero_solicitacao()
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO solicitacoes
            (
                numero,

                orgao_id,
                entidade_id,
                unidade_orcamentaria_id,
                unidade_administrativa_id,
                setor_id,

                tipo,
                prioridade,

                titulo,
                descricao,
                justificativa,

                solicitante,

                status,
                data_solicitacao
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
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                numero,

                orgao_id,
                entidade_id,
                unidade_orcamentaria_id,
                unidade_administrativa_id,
                setor_id,

                tipo,
                prioridade,

                titulo,
                descricao if descricao else None,
                justificativa,

                solicitante if solicitante else None,

                "Aberta",
                data_solicitacao
            )
        )

        if sucesso:

            st.success(
                "✅ Solicitação registrada com sucesso! "
                f"Nº {str(numero).zfill(6)}"
            )


# ============================================================
# SOLICITAÇÃO - LOCALIZAR
# ============================================================

def solicitacao_localizar():

    st.subheader(
        "🔎 Localizar Solicitações"
    )

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col1:

        filtro_numero = st.text_input(
            "Número",
            key="solicitacao_localizar_numero"
        )

    with col2:

        filtro_texto = st.text_input(
            "Objeto",
            key="solicitacao_localizar_texto"
        )

    with col3:

        filtro_status = st.selectbox(
            "Status",
            [
                "Todos",
                "Aberta",
                "Em análise",
                "Aprovada",
                "Rejeitada",
                "Em atendimento",
                "Concluída"
            ],
            key="solicitacao_localizar_status"
        )

    sql = """
        SELECT
            s.id,

            LPAD(
                s.numero::text,
                6,
                '0'
            ) AS "Número",

            s.data_solicitacao
                AS "Data",

            s.tipo
                AS "Tipo",

            s.titulo
                AS "Objeto",

            s.prioridade
                AS "Prioridade",

            COALESCE(
                se.nome,
                ''
            ) AS "Setor",

            s.solicitante
                AS "Solicitante",

            s.status
                AS "Status"

        FROM solicitacoes s

        LEFT JOIN setores se
            ON se.id = s.setor_id

        WHERE 1 = 1
    """

    parametros = []

    if filtro_numero.strip():

        try:

            numero = int(
                filtro_numero.strip()
            )

            sql += """
                AND s.numero = ?
            """

            parametros.append(
                numero
            )

        except ValueError:

            pass

    if filtro_texto.strip():

        sql += """
            AND s.titulo ILIKE ?
        """

        parametros.append(
            f"%{filtro_texto.strip()}%"
        )

    if filtro_status != "Todos":

        sql += """
            AND s.status = ?
        """

        parametros.append(
            filtro_status
        )

    sql += """
        ORDER BY
            s.numero DESC
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma solicitação encontrada."
        )

        return None

    st.caption(
        f"Solicitações encontradas: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes",
        coluna_id="id",
        altura=450
    )


# ============================================================
# SOLICITAÇÃO - ALTERAR
# ============================================================

def solicitacao_alterar(
    solicitacao_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            numero,
            tipo,
            prioridade,
            titulo,
            descricao,
            justificativa,
            solicitante,
            status,
            data_solicitacao,

            orgao_id,
            entidade_id,
            unidade_orcamentaria_id,
            unidade_administrativa_id,
            setor_id

        FROM solicitacoes

        WHERE id = ?
        """,
        (
            solicitacao_id,
        )
    )

    if not registro:

        st.error(
            "❌ Solicitação não encontrada."
        )

        return

    (
        numero,
        tipo_atual,
        prioridade_atual,
        titulo_atual,
        descricao_atual,
        justificativa_atual,
        solicitante_atual,
        status_atual,
        data_solicitacao,
        orgao_id,
        entidade_id,
        unidade_orcamentaria_id,
        unidade_administrativa_id,
        setor_id
    ) = registro

    st.info(
        f"📝 Solicitação nº {str(numero).zfill(6)}"
    )

    # ========================================================
    # ESTRUTURA
    # ========================================================

    estrutura = _sisget_fetchone(
        """
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
                se.codigo,
                ''
            ),

            COALESCE(
                se.nome,
                ''
            )

        FROM solicitacoes s

        LEFT JOIN orgaos o
            ON o.id = s.orgao_id

        LEFT JOIN entidades e
            ON e.id = s.entidade_id

        LEFT JOIN unidades_orcamentarias u
            ON u.id = s.unidade_orcamentaria_id

        LEFT JOIN unidades_administrativas a
            ON a.id = s.unidade_administrativa_id

        LEFT JOIN setores se
            ON se.id = s.setor_id

        WHERE s.id = ?
        """,
        (
            solicitacao_id,
        )
    )

    if estrutura:

        st.caption(
            (
                f"🏛️ {estrutura[0]} - {estrutura[1]}"
                f"  →  🏢 {estrutura[2]} - {estrutura[3]}"
                f"  →  💼 {estrutura[4]} - {estrutura[5]}"
                f"  →  🏬 {estrutura[6]} - {estrutura[7]}"
            )
        )

        if estrutura[8]:

            st.caption(
                f"🧩 {estrutura[8]} - {estrutura[9]}"
            )

    # ========================================================
    # FORM
    # ========================================================

    tipos = [
        "Aquisição de Material",
        "Contratação de Serviço",
        "Obra / Serviço de Engenharia",
        "Tecnologia da Informação",
        "Manutenção",
        "Outros"
    ]

    prioridades = [
        "Baixa",
        "Normal",
        "Alta",
        "Urgente"
    ]

    status_opcoes = [
        "Aberta",
        "Em análise",
        "Aprovada",
        "Rejeitada",
        "Em atendimento",
        "Concluída"
    ]

    with st.form(
        f"form_solicitacao_alterar_{solicitacao_id}"
    ):

        col1, col2, col3 = st.columns(3)

        with col1:

            tipo = st.selectbox(
                "Tipo",
                tipos,
                index=(
                    tipos.index(tipo_atual)
                    if tipo_atual in tipos
                    else 0
                )
            )

        with col2:

            prioridade = st.selectbox(
                "Prioridade",
                prioridades,
                index=(
                    prioridades.index(prioridade_atual)
                    if prioridade_atual in prioridades
                    else 1
                )
            )

        with col3:

            status = st.selectbox(
                "Status",
                status_opcoes,
                index=(
                    status_opcoes.index(status_atual)
                    if status_atual in status_opcoes
                    else 0
                )
            )

        titulo = st.text_input(
            "Objeto / Título *",
            value=titulo_atual or "",
            max_chars=200
        )

        descricao = st.text_area(
            "Descrição",
            value=descricao_atual or "",
            height=140
        )

        justificativa = st.text_area(
            "Justificativa *",
            value=justificativa_atual or "",
            height=140
        )

        solicitante = st.text_input(
            "Solicitante",
            value=solicitante_atual or "",
            max_chars=200
        )

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:

            salvar = st.form_submit_button(
                "💾 Salvar Alterações",
                type="primary",
                use_container_width=True
            )

        with col2:

            cancelar = st.form_submit_button(
                "❌ Cancelar",
                use_container_width=True
            )

    if cancelar:

        st.session_state[
            "sisget_id_solicitacoes"
        ] = None

        st.session_state[
            "sisget_tela_solicitacoes"
        ] = "localizar"

        st.rerun()

    if salvar:

        titulo = titulo.strip()
        descricao = descricao.strip()
        justificativa = justificativa.strip()
        solicitante = solicitante.strip()

        if not titulo:

            st.warning(
                "⚠️ Informe o objeto."
            )

            return

        if not justificativa:

            st.warning(
                "⚠️ Informe a justificativa."
            )

            return

        sucesso = _sisget_salvar(
            """
            UPDATE solicitacoes
            SET
                tipo = ?,
                prioridade = ?,
                titulo = ?,
                descricao = ?,
                justificativa = ?,
                solicitante = ?,
                status = ?
            WHERE id = ?
            """,
            (
                tipo,
                prioridade,
                titulo,
                descricao if descricao else None,
                justificativa,
                solicitante if solicitante else None,
                status,
                solicitacao_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_solicitacoes"
            ] = None

            st.session_state[
                "sisget_tela_solicitacoes"
            ] = "localizar"

            st.success(
                "✅ Solicitação alterada com sucesso!"
            )

            st.rerun()


# ============================================================
# SOLICITAÇÃO - EXCLUIR
# ============================================================

def solicitacao_excluir():

    st.subheader(
        "🗑️ Excluir Solicitação"
    )

    df = _sisget_dataframe(
        """
        SELECT
            id,

            LPAD(
                numero::text,
                6,
                '0'
            ) AS "Número",

            data_solicitacao
                AS "Data",

            titulo
                AS "Objeto",

            solicitante
                AS "Solicitante",

            status
                AS "Status"

        FROM solicitacoes

        ORDER BY
            numero DESC
        """
    )

    if df.empty:

        st.info(
            "Nenhuma solicitação cadastrada."
        )

        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_solicitacoes",
        coluna_id="id",
        altura=420
    )

    if not registro_id:

        st.caption(
            "Dê duplo clique na solicitação que deseja excluir."
        )

        return

    registro = _sisget_fetchone(
        """
        SELECT
            numero,
            titulo,
            status
        FROM solicitacoes
        WHERE id = ?
        """,
        (
            registro_id,
        )
    )

    if not registro:

        return

    numero = registro[0]
    titulo = registro[1]
    status = registro[2]

    st.markdown("---")

    st.error(
        (
            f"⚠️ Solicitação nº "
            f"**{str(numero).zfill(6)}**\n\n"
            f"**{titulo}**"
        )
    )

    if status == "Concluída":

        st.warning(
            "⚠️ Esta solicitação está concluída."
        )

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta solicitação.",
        key=f"confirmar_exclusao_solicitacao_{registro_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"btn_excluir_solicitacao_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação."
            )

            return

        sucesso = _sisget_salvar(
            """
            DELETE FROM solicitacoes
            WHERE id = ?
            """,
            (
                registro_id,
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_solicitacoes"
            ] = None

            st.session_state[
                "sisget_tela_solicitacoes"
            ] = "principal"

            st.success(
                "✅ Solicitação excluída."
            )

            st.rerun()


# ============================================================
# SOLICITAÇÕES - IMPRIMIR
# ============================================================

def solicitacao_imprimir():

    st.subheader(
        "🖨️ Relatório de Solicitações"
    )

    status = st.selectbox(
        "Status",
        [
            "Todos",
            "Aberta",
            "Em análise",
            "Aprovada",
            "Rejeitada",
            "Em atendimento",
            "Concluída"
        ],
        key="solicitacao_imprimir_status"
    )

    sql = """
        SELECT
            s.numero,
            s.data_solicitacao,
            s.tipo,
            s.titulo,
            s.prioridade,
            COALESCE(
                se.nome,
                ''
            ),
            COALESCE(
                s.solicitante,
                ''
            ),
            s.status

        FROM solicitacoes s

        LEFT JOIN setores se
            ON se.id = s.setor_id

        WHERE 1 = 1
    """

    parametros = []

    if status != "Todos":

        sql += """
            AND s.status = ?
        """

        parametros.append(
            status
        )

    sql += """
        ORDER BY
            s.numero
    """

    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )

    if not dados:

        st.info(
            "Nenhuma solicitação encontrada."
        )

        return

    visualizacao = []

    for registro in dados:

        visualizacao.append({

            "Número":
                str(registro[0]).zfill(6),

            "Data":
                (
                    registro[1].strftime(
                        "%d/%m/%Y"
                    )
                    if registro[1]
                    else ""
                ),

            "Tipo":
                registro[2],

            "Objeto":
                registro[3],

            "Prioridade":
                registro[4],

            "Setor":
                registro[5],

            "Solicitante":
                registro[6],

            "Status":
                registro[7]
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
        f"Total de solicitações: {len(df)}"
    )

    # ========================================================
    # PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_solicitacoes"
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
            "TextoSolicitacao",
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
                "Relatório de Solicitações",
                estilos["Heading2"]
            )
        )

        elementos.append(
            Paragraph(
                f"Status: {status}",
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
            "Nº",
            "Data",
            "Tipo",
            "Objeto",
            "Prioridade",
            "Setor",
            "Status"
        ]]

        for registro in dados:

            tabela_dados.append([

                str(
                    registro[0]
                ).zfill(6),

                (
                    registro[1].strftime(
                        "%d/%m/%Y"
                    )
                    if registro[1]
                    else ""
                ),

                Paragraph(
                    str(
                        registro[2] or ""
                    ),
                    texto_tabela
                ),

                Paragraph(
                    str(
                        registro[3] or ""
                    ),
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
                    registro[7] or ""
                )
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                1.2 * cm,
                1.8 * cm,
                2.8 * cm,
                5.5 * cm,
                1.7 * cm,
                3.0 * cm,
                2.0 * cm
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
            "⬇️ Baixar Relatório em PDF",
            data=buffer,
            file_name="relatorio_solicitacoes.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_solicitacoes"
        )
# ============================================================
# PLANEJAMENTO
# ============================================================
# ============================================================
# MÓDULO DE PLANEJAMENTO
# ============================================================

def modulo_planejamento():

    st.title(
        "📐 Planejamento"
    )

    st.caption(
        "Planejamento orçamentário e disponibilidade de recursos."
    )

    st.markdown("---")

    # ========================================================
    # CONTROLE DA TELA
    # ========================================================

    if "planejamento_tela" not in st.session_state:

        st.session_state[
            "planejamento_tela"
        ] = "principal"

    tela = st.session_state[
        "planejamento_tela"
    ]

    # ========================================================
    # TELA PRINCIPAL
    # ========================================================

    if tela == "principal":

        st.subheader(
            "💰 Planejamento Orçamentário"
        )

        st.caption(
            "Cadastre e acompanhe a estrutura orçamentária "
            "que será utilizada nas Solicitações."
        )

        st.markdown("---")

        # ====================================================
        # PRIMEIRA LINHA
        # ====================================================

        col1, col2, col3 = st.columns(3)

        # ====================================================
        # CLASSIFICAÇÕES
        # ====================================================

        with col1:

            st.markdown(
                "### 🧾 Classificações"
            )

            st.caption(
                "Função, Subfunção, Programa, "
                "Ação e Natureza da Despesa."
            )

            if st.button(
                "🧾 Abrir Classificações",
                use_container_width=True,
                key="btn_planejamento_classificacoes"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "classificacoes"

                st.rerun()

        # ====================================================
        # FONTES
        # ====================================================

        with col2:

            st.markdown(
                "### 💧 Fontes de Recursos"
            )

            st.caption(
                "Cadastro das fontes de recursos "
                "utilizadas nas fichas orçamentárias."
            )

            if st.button(
                "💧 Abrir Fontes",
                use_container_width=True,
                key="btn_planejamento_fontes"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "fontes"

                st.rerun()

        # ====================================================
        # FICHAS
        # ====================================================

        with col3:

            st.markdown(
                "### 📄 Fichas Orçamentárias"
            )

            st.caption(
                "Cadastro das fichas vinculadas às "
                "Unidades Orçamentárias do Cadastro Básico."
            )

            if st.button(
                "📄 Abrir Fichas",
                type="primary",
                use_container_width=True,
                key="btn_planejamento_fichas"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "fichas"

                st.rerun()

        st.markdown("---")

        # ====================================================
        # SEGUNDA LINHA
        # ====================================================

        col4, col5, col6 = st.columns(3)

        # ====================================================
        # SALDOS
        # ====================================================

        with col4:

            st.markdown(
                "### 💰 Saldos Orçamentários"
            )

            st.caption(
                "Consulta dos valores atuais, reservados "
                "e disponíveis por ficha."
            )

            if st.button(
                "💰 Consultar Saldos",
                use_container_width=True,
                key="btn_planejamento_saldos"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "saldos"

                st.rerun()

        # ====================================================
        # RESERVAS
        # ====================================================

        with col5:

            st.markdown(
                "### 🔒 Reservas Orçamentárias"
            )

            st.caption(
                "Controle dos valores reservados "
                "para futuras despesas."
            )

            if st.button(
                "🔒 Abrir Reservas",
                use_container_width=True,
                key="btn_planejamento_reservas"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "reservas"

                st.rerun()

        # ====================================================
        # CONSULTA
        # ====================================================

        with col6:

            st.markdown(
                "### 🔎 Consulta Orçamentária"
            )

            st.caption(
                "Consulta geral de fichas, fontes, "
                "classificações e disponibilidade."
            )

            if st.button(
                "🔎 Consultar Orçamento",
                use_container_width=True,
                key="btn_planejamento_consulta"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "consulta"

                st.rerun()

        st.markdown("---")

        # ====================================================
        # TERCEIRA LINHA
        # ====================================================

        col7, col8, col9 = st.columns(3)

        # ====================================================
        # RELATÓRIOS
        # ====================================================

        with col7:

            st.markdown(
                "### 🖨️ Relatórios"
            )

            st.caption(
                "Relatórios do planejamento e "
                "disponibilidade orçamentária."
            )

            if st.button(
                "🖨️ Abrir Relatórios",
                use_container_width=True,
                key="btn_planejamento_relatorios"
            ):

                st.session_state[
                    "planejamento_tela"
                ] = "relatorios"

                st.rerun()

        # ====================================================
        # ESPAÇOS RESERVADOS
        # ====================================================

        with col8:

            st.markdown(
                "### 📊 Planejamento"
            )

            st.caption(
                "Espaço reservado para futuras "
                "rotinas de planejamento."
            )

        with col9:

            st.markdown(
                "### 🔄 Integração"
            )

            st.caption(
                "Integração do orçamento com "
                "Solicitações e execução."
            )

        # ====================================================
        # FLUXO
        # ====================================================

        st.markdown("---")

        st.subheader(
            "🔄 Fluxo Orçamentário"
        )

        st.info(
            "🧾 Classificações"
            "  →  💧 Fontes"
            "  →  📄 Fichas Orçamentárias"
            "  →  💰 Saldo Disponível"
            "  →  📝 Solicitação"
            "  →  🔒 Reserva Orçamentária"
        )

        st.caption(
            "As Fichas Orçamentárias utilizam as Unidades "
            "Orçamentárias cadastradas no Cadastro Básico."
        )

        st.caption(
            "Depois, a Solicitação poderá selecionar a ficha "
            "e consultar o saldo disponível antes de seguir para "
            "DFD, ETP e Termo de Referência."
        )

    # ========================================================
    # CLASSIFICAÇÕES ORÇAMENTÁRIAS
    # ========================================================

    elif tela == "classificacoes":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_classificacoes"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_classificacoes()

    # ========================================================
    # FONTES DE RECURSOS
    # ========================================================

    elif tela == "fontes":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_fontes"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_fontes_recursos()

    # ========================================================
    # FICHAS ORÇAMENTÁRIAS
    # ========================================================

    elif tela == "fichas":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_fichas"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_fichas_orcamentarias()

    # ========================================================
    # SALDOS
    # ========================================================

    elif tela == "saldos":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_saldos"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_saldos()

    # ========================================================
    # RESERVAS
    # ========================================================

    elif tela == "reservas":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_reservas"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_reservas()

    # ========================================================
    # CONSULTA ORÇAMENTÁRIA
    # ========================================================

    elif tela == "consulta":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_consulta"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_consulta_orcamentaria()

    # ========================================================
    # RELATÓRIOS
    # ========================================================

    elif tela == "relatorios":

        if st.button(
            "⬅️ Voltar ao Planejamento",
            key="voltar_planejamento_relatorios"
        ):

            st.session_state[
                "planejamento_tela"
            ] = "principal"

            st.rerun()

        planejamento_relatorios()

    # ========================================================
    # SEGURANÇA
    # ========================================================

    else:

        st.session_state[
            "planejamento_tela"
        ] = "principal"

        st.rerun()

# ============================================================
# FICHAS ORÇAMENTÁRIAS - INCLUIR
# CAMPOS DE CLASSIFICAÇÃO COM SELECTBOX
# ============================================================

# ============================================================
# FICHAS ORÇAMENTÁRIAS - INCLUIR
# CLASSIFICAÇÃO POR SELECTBOX
# ============================================================

def ficha_orcamentaria_incluir():

    st.subheader("📄 Incluir Ficha Orçamentária")

    st.caption(
        "Selecione os dados cadastrados no SISGET. "
        "Os códigos da classificação serão preenchidos automaticamente."
    )

    # ========================================================
    # FUNÇÃO AUXILIAR LOCAL - SELECTBOX POR ID
    # ========================================================

    def selecionar_cadastro(
        titulo,
        registros,
        chave,
        mensagem,
        desabilitado=False
    ):

        opcoes = {}

        for registro in registros:

            registro_id = int(registro[0])
            codigo = str(registro[1] or "")
            nome = str(registro[2] or "")

            opcoes[registro_id] = {
                "codigo": codigo,
                "nome": nome
            }

        selecionado = st.selectbox(
            titulo,
            options=[None] + list(opcoes.keys()),
            format_func=lambda valor: (
                mensagem
                if valor is None
                else (
                    f"{opcoes[valor]['codigo']} - "
                    f"{opcoes[valor]['nome']}"
                )
            ),
            key=chave,
            disabled=desabilitado or not bool(registros)
        )

        if selecionado is None:
            return None, None

        return (
            selecionado,
            opcoes[selecionado]["codigo"]
        )

    # ========================================================
    # 1 - ÓRGÃO
    # ========================================================

    orgaos = _sisget_fetch(
        """
        SELECT id, codigo, nome
        FROM orgaos
        WHERE ativo = TRUE
        ORDER BY codigo, nome
        """
    )

    if not orgaos:

        st.warning("Nenhum Órgão ativo cadastrado.")
        return

    orgao_id, _ = selecionar_cadastro(
        "Órgão *",
        orgaos,
        "ficha_nova_orgao",
        "Selecione um Órgão"
    )

    if orgao_id is None:
        st.info("Selecione o Órgão para continuar.")
        return

    # ========================================================
    # 2 - ENTIDADE
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT id, codigo, nome
        FROM entidades
        WHERE orgao_id = ?
          AND ativo = TRUE
        ORDER BY codigo, nome
        """,
        (orgao_id,)
    )

    entidade_id, _ = selecionar_cadastro(
        "Entidade *",
        entidades,
        "ficha_nova_entidade",
        "Selecione uma Entidade"
    )

    if entidade_id is None:

        if not entidades:
            st.warning(
                "Nenhuma Entidade ativa vinculada ao Órgão."
            )

        return

    # ========================================================
    # 3 - UNIDADE ORÇAMENTÁRIA
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT id, codigo, nome
        FROM unidades_orcamentarias
        WHERE entidade_id = ?
          AND orgao_id = ?
          AND ativo = TRUE
        ORDER BY codigo, nome
        """,
        (
            entidade_id,
            orgao_id
        )
    )

    unidade_id, _ = selecionar_cadastro(
        "Unidade Orçamentária *",
        unidades,
        "ficha_nova_unidade",
        "Selecione a Unidade Orçamentária"
    )

    if unidade_id is None:

        if not unidades:
            st.warning(
                "Nenhuma Unidade Orçamentária ativa "
                "vinculada à Entidade."
            )

        return

    # ========================================================
    # 4 - EXERCÍCIO
    # ========================================================

    st.markdown("---")

    exercicios = _sisget_fetch(
        """
        SELECT
            id,
            ano,
            COALESCE(descricao, '')
        FROM exercicios
        WHERE entidade_id = ?
          AND ativo = TRUE
          AND encerrado = FALSE
        ORDER BY ano DESC
        """,
        (entidade_id,)
    )

    mapa_exercicios = {
        int(registro[0]): {
            "ano": int(registro[1]),
            "descricao": str(registro[2] or "")
        }
        for registro in exercicios
    }

    exercicio_id = st.selectbox(
        "Exercício *",
        options=[None] + list(mapa_exercicios.keys()),
        format_func=lambda valor: (
            "Selecione o Exercício"
            if valor is None
            else (
                f"{mapa_exercicios[valor]['ano']} - "
                f"{mapa_exercicios[valor]['descricao']}"
            )
        ),
        key="ficha_nova_exercicio",
        disabled=not bool(exercicios)
    )

    exercicio = (
        mapa_exercicios[exercicio_id]["ano"]
        if exercicio_id is not None
        else None
    )

    if not exercicios:

        st.warning(
            "Esta Entidade não possui Exercício ativo e aberto. "
            "Você ainda poderá visualizar as classificações "
            "cadastradas abaixo, mas não poderá salvar a Ficha "
            "até selecionar um Exercício válido."
        )

    # ========================================================
    # 5 - CLASSIFICAÇÃO ORÇAMENTÁRIA
    #
    # IMPORTANTE:
    # ESTE BLOCO FICA FORA DO st.form()
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 🧾 Classificação Orçamentária"
    )

    st.caption(
        "Os campos abaixo são carregados dos cadastros "
        "existentes no banco de dados."
    )

    # ========================================================
    # FUNÇÃO
    # ========================================================

    funcoes = _sisget_fetch(
        """
        SELECT id, codigo, descricao
        FROM funcoes_orcamentarias
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    funcao_id, funcao = selecionar_cadastro(
        "Função *",
        funcoes,
        "ficha_nova_funcao",
        "Selecione uma Função cadastrada"
    )

    if not funcoes:

        st.warning(
            "Nenhuma Função Orçamentária ativa cadastrada."
        )

    # ========================================================
    # SUBFUNÇÃO
    # FILTRADA PELA FUNÇÃO SELECIONADA
    # ========================================================

    subfuncoes = []

    if funcao_id is not None:

        subfuncoes = _sisget_fetch(
            """
            SELECT id, codigo, descricao
            FROM subfuncoes_orcamentarias
            WHERE funcao_id = ?
              AND ativo = TRUE
            ORDER BY codigo
            """,
            (funcao_id,)
        )

    subfuncao_id, subfuncao = selecionar_cadastro(
        "Subfunção *",
        subfuncoes,
        "ficha_nova_subfuncao",
        "Selecione uma Subfunção cadastrada",
        desabilitado=funcao_id is None
    )

    if funcao_id is not None and not subfuncoes:

        st.warning(
            "Não existem Subfunções ativas vinculadas "
            "à Função selecionada."
        )

    # ========================================================
    # PROGRAMA
    #
    # BUSCA NA TABELA programas
    # FILTRADO POR ENTIDADE E EXERCÍCIO
    # ========================================================

    programas = []

    if exercicio_id is not None:

        programas = _sisget_fetch(
            """
            SELECT id, codigo, nome
            FROM programas
            WHERE entidade_id = ?
              AND exercicio_id = ?
              AND ativo = TRUE
            ORDER BY codigo
            """,
            (
                entidade_id,
                exercicio_id
            )
        )

    programa_id, programa = selecionar_cadastro(
        "Programa *",
        programas,
        "ficha_nova_programa",
        "Selecione um Programa cadastrado",
        desabilitado=exercicio_id is None
    )

    if exercicio_id is not None and not programas:

        st.warning(
            "Nenhum Programa ativo cadastrado para "
            "esta Entidade e Exercício."
        )

    # ========================================================
    # AÇÃO
    # FILTRADA PELO PROGRAMA
    # ========================================================

    acoes = []

    if programa_id is not None:

        acoes = _sisget_fetch(
            """
            SELECT id, codigo, nome
            FROM acoes_orcamentarias
            WHERE entidade_id = ?
              AND exercicio_id = ?
              AND programa_id = ?
              AND ativo = TRUE
            ORDER BY codigo
            """,
            (
                entidade_id,
                exercicio_id,
                programa_id
            )
        )

    acao_id, acao = selecionar_cadastro(
        "Ação *",
        acoes,
        "ficha_nova_acao",
        "Selecione uma Ação cadastrada",
        desabilitado=programa_id is None
    )

    if programa_id is not None and not acoes:

        st.warning(
            "Nenhuma Ação ativa vinculada ao Programa."
        )

    # ========================================================
    # NATUREZA DA DESPESA
    # ========================================================

    naturezas = _sisget_fetch(
        """
        SELECT id, codigo, descricao
        FROM naturezas_despesa
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    natureza_id, natureza_despesa = selecionar_cadastro(
        "Natureza da Despesa *",
        naturezas,
        "ficha_nova_natureza",
        "Selecione uma Natureza da Despesa cadastrada"
    )

    if not naturezas:

        st.warning(
            "Nenhuma Natureza da Despesa ativa cadastrada."
        )

    # ========================================================
    # 6 - FONTE DE RECURSO
    # ========================================================

    st.markdown("---")

    fontes = []

    if exercicio is not None:

        fontes = _sisget_fetch(
            """
            SELECT id, codigo, descricao
            FROM fontes_recursos
            WHERE exercicio = ?
              AND ativo = TRUE
            ORDER BY codigo
            """,
            (exercicio,)
        )

    fonte_recurso_id, _ = selecionar_cadastro(
        "Fonte de Recurso *",
        fontes,
        "ficha_nova_fonte",
        "Selecione uma Fonte de Recurso cadastrada",
        desabilitado=exercicio is None
    )

    if exercicio is not None and not fontes:

        st.warning(
            f"Nenhuma Fonte de Recurso ativa "
            f"cadastrada para {exercicio}."
        )

    # ========================================================
    # 7 - CLASSIFICAÇÃO MONTADA AUTOMATICAMENTE
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 🔗 Classificação Selecionada"
    )

    classificacao = ".".join([
        funcao or "--",
        subfuncao or "---",
        programa or "----",
        acao or "----",
        natureza_despesa or "------"
    ])

    st.text_input(
        "Código da Classificação Orçamentária",
        value=classificacao,
        disabled=True,
        key="ficha_nova_classificacao_visual"
    )

    # ========================================================
    # 8 - NUMERAÇÃO AUTOMÁTICA DA FICHA
    # ========================================================

    def proximo_numero_ficha(ano, id_entidade):

        registros = _sisget_fetch(
            """
            SELECT numero_ficha
            FROM fichas_orcamentarias
            WHERE exercicio = ?
              AND entidade_id = ?
            """,
            (
                ano,
                id_entidade
            )
        )

        numeros = {
            int(registro[0])
            for registro in registros
            if registro[0] is not None
        }

        proximo = 1

        while proximo in numeros:
            proximo += 1

        return proximo

    numero_ficha = None

    if exercicio is not None:

        numero_ficha = proximo_numero_ficha(
            exercicio,
            entidade_id
        )

    st.text_input(
        "Número da Ficha",
        value=(
            str(numero_ficha)
            if numero_ficha is not None
            else "Aguardando Exercício"
        ),
        disabled=True,
        key="ficha_nova_numero_visual"
    )

    # ========================================================
    # 9 - FORMULÁRIO
    #
    # SOMENTE OS DADOS FINANCEIROS FICAM DENTRO DO FORM
    # OS SELECTBOX DE CLASSIFICAÇÃO JÁ FORAM CRIADOS ACIMA
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 💰 Dados Financeiros"
    )

    with st.form(
        "form_ficha_orcamentaria_incluir",
        clear_on_submit=True
    ):

        descricao = st.text_input(
            "Descrição da Ficha",
            max_chars=250,
            placeholder="Ex.: Material de Consumo"
        )

        valor_inicial = st.number_input(
            "Valor Inicial (R$)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f"
        )

        ativo = st.checkbox(
            "Ficha ativa",
            value=True
        )

        st.markdown("---")

        salvar = st.form_submit_button(
            "💾 Salvar Ficha Orçamentária",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # 10 - SALVAR
    # ========================================================

    if salvar:

        # ----------------------------------------------------
        # VALIDAÇÃO DO EXERCÍCIO
        # ----------------------------------------------------

        if exercicio_id is None:

            st.warning(
                "Selecione um Exercício ativo e aberto."
            )

            return

        # ----------------------------------------------------
        # VALIDAÇÃO DAS CLASSIFICAÇÕES
        # ----------------------------------------------------

        obrigatorios = {
            "Função": funcao_id,
            "Subfunção": subfuncao_id,
            "Programa": programa_id,
            "Ação": acao_id,
            "Natureza da Despesa": natureza_id,
            "Fonte de Recurso": fonte_recurso_id
        }

        faltantes = [
            nome
            for nome, valor in obrigatorios.items()
            if valor is None
        ]

        if faltantes:

            st.warning(
                "Selecione os seguintes campos: "
                + ", ".join(faltantes)
            )

            return

        # ----------------------------------------------------
        # REVALIDAR VÍNCULO DA SUBFUNÇÃO
        # ----------------------------------------------------

        subfuncao_valida = _sisget_fetchone(
            """
            SELECT id
            FROM subfuncoes_orcamentarias
            WHERE id = ?
              AND funcao_id = ?
              AND ativo = TRUE
            """,
            (
                subfuncao_id,
                funcao_id
            )
        )

        if not subfuncao_valida:

            st.warning(
                "A Subfunção selecionada não pertence "
                "à Função informada."
            )

            return

        # ----------------------------------------------------
        # REVALIDAR PROGRAMA E AÇÃO
        # ----------------------------------------------------

        vinculo_valido = _sisget_fetchone(
            """
            SELECT a.id
            FROM acoes_orcamentarias a

            INNER JOIN programas p
                ON p.id = a.programa_id

            WHERE a.id = ?
              AND a.programa_id = ?
              AND a.entidade_id = ?
              AND a.exercicio_id = ?

              AND p.entidade_id = ?
              AND p.exercicio_id = ?

              AND a.ativo = TRUE
              AND p.ativo = TRUE
            """,
            (
                acao_id,
                programa_id,
                entidade_id,
                exercicio_id,
                entidade_id,
                exercicio_id
            )
        )

        if not vinculo_valido:

            st.warning(
                "A Ação selecionada não está vinculada "
                "corretamente ao Programa e ao Exercício."
            )

            return

        # ----------------------------------------------------
        # RECALCULAR NÚMERO DA FICHA
        # ----------------------------------------------------

        numero_salvar = proximo_numero_ficha(
            exercicio,
            entidade_id
        )

        # ----------------------------------------------------
        # INSERT
        #
        # A TABELA ATUAL DE FICHAS POSSUI CAMPOS VARCHAR
        # PARA FUNÇÃO, SUBFUNÇÃO, PROGRAMA, AÇÃO E NATUREZA.
        #
        # POR ISSO, SELECIONAMOS PELO ID, MAS GRAVAMOS
        # O CÓDIGO CORRESPONDENTE.
        # ----------------------------------------------------

        sucesso = _sisget_salvar(
            """
            INSERT INTO fichas_orcamentarias
            (
                exercicio,
                numero_ficha,

                orgao_id,
                entidade_id,
                unidade_orcamentaria_id,

                funcao,
                subfuncao,
                programa,
                acao,
                natureza_despesa,

                fonte_recurso_id,

                descricao,

                valor_inicial,
                valor_atual,
                valor_reservado,

                ativo
            )
            VALUES
            (
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?,
                ?,
                ?, ?, ?,
                ?
            )
            """,
            (
                int(exercicio),
                numero_salvar,

                orgao_id,
                entidade_id,
                unidade_id,

                funcao,
                subfuncao,
                programa,
                acao,
                natureza_despesa,

                fonte_recurso_id,

                descricao.strip() or None,

                float(valor_inicial),
                float(valor_inicial),
                0.0,

                ativo
            )
        )

        if sucesso:

            st.success(
                f"✅ Ficha Orçamentária nº {numero_salvar} "
                "cadastrada com sucesso!"
            )

            st.rerun()
# ============================================================
# SISGET - FONTES DE RECURSOS
# ============================================================


# ============================================================
# TELA PRINCIPAL
# ============================================================

def planejamento_fontes_recursos():

    sisget_tela_principal(
        titulo="Fontes de Recursos",
        chave="fontes_recursos",
        func_incluir=fonte_recurso_incluir,
        func_localizar=fonte_recurso_localizar,
        func_alterar=fonte_recurso_alterar,
        func_excluir=fonte_recurso_excluir,
        func_imprimir=fonte_recurso_imprimir,
        icone="💧"
    )


# ============================================================
# FUNÇÃO AUXILIAR - EXERCÍCIOS CADASTRADOS
# ============================================================

def fonte_recurso_exercicios():

    dados = _sisget_fetch(
        """
        SELECT DISTINCT ano
        FROM exercicios
        WHERE ativo = TRUE
        ORDER BY ano DESC
        """
    )

    return [
        int(registro[0])
        for registro in dados
        if registro[0] is not None
    ]


# ============================================================
# INCLUIR
# ============================================================

# ============================================================
# FONTES DE RECURSOS - INCLUIR
# ENTIDADE + EXERCÍCIO VINCULADOS AUTOMATICAMENTE
# ============================================================

def fonte_recurso_incluir():

    st.subheader("💧 Incluir Fonte de Recurso")

    st.caption(
        "Selecione a estrutura administrativa e informe "
        "o código e a descrição da Fonte de Recurso."
    )

    # ========================================================
    # 1 - ÓRGÃO
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

        st.warning("Nenhum Órgão ativo cadastrado.")
        return

    mapa_orgaos = {
        int(r[0]): f"{r[1]} - {r[2]}"
        for r in orgaos
    }

    orgao_id = st.selectbox(
        "Órgão *",
        options=[None] + list(mapa_orgaos.keys()),
        format_func=lambda x: (
            "Selecione o Órgão"
            if x is None
            else mapa_orgaos[x]
        ),
        key="fonte_inc_orgao"
    )

    if orgao_id is None:
        st.info("Selecione o Órgão para continuar.")
        return

    # ========================================================
    # 2 - ENTIDADE VINCULADA AO ÓRGÃO
    # ========================================================

    entidades = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM entidades
        WHERE orgao_id = ?
          AND ativo = TRUE
        ORDER BY codigo, nome
        """,
        (orgao_id,)
    )

    if not entidades:

        st.warning(
            "Nenhuma Entidade ativa vinculada ao Órgão."
        )

        return

    mapa_entidades = {
        int(r[0]): f"{r[1]} - {r[2]}"
        for r in entidades
    }

    entidade_id = st.selectbox(
        "Entidade *",
        options=[None] + list(mapa_entidades.keys()),
        format_func=lambda x: (
            "Selecione a Entidade"
            if x is None
            else mapa_entidades[x]
        ),
        key="fonte_inc_entidade"
    )

    if entidade_id is None:
        return

    # ========================================================
    # 3 - EXERCÍCIO DA ENTIDADE
    # ========================================================

    exercicios = _sisget_fetch(
        """
        SELECT
            id,
            ano,
            descricao
        FROM exercicios
        WHERE entidade_id = ?
          AND ativo = TRUE
          AND encerrado = FALSE
        ORDER BY ano DESC
        """,
        (entidade_id,)
    )

    if not exercicios:

        st.warning(
            "Esta Entidade não possui Exercício ativo e aberto."
        )

        st.info(
            "É necessário ter um Exercício válido para "
            "vincular corretamente a Fonte de Recurso."
        )

        return

    mapa_exercicios = {}

    for registro in exercicios:

        exercicio_id = int(registro[0])
        ano = int(registro[1])
        descricao = str(registro[2] or "")

        mapa_exercicios[exercicio_id] = {
            "ano": ano,
            "texto": (
                f"{ano} - {descricao}"
                if descricao
                else str(ano)
            )
        }

    exercicio_id = st.selectbox(
        "Exercício *",
        options=[None] + list(mapa_exercicios.keys()),
        format_func=lambda x: (
            "Selecione o Exercício"
            if x is None
            else mapa_exercicios[x]["texto"]
        ),
        key="fonte_inc_exercicio"
    )

    if exercicio_id is None:
        return

    ano_exercicio = mapa_exercicios[
        exercicio_id
    ]["ano"]

    # ========================================================
    # 4 - DADOS VINCULADOS
    # ========================================================

    st.markdown("---")

    st.markdown("### 🔗 Vinculação da Fonte")

    col1, col2 = st.columns(2)

    with col1:

        st.text_input(
            "Entidade vinculada",
            value=mapa_entidades[entidade_id],
            disabled=True,
            key="fonte_inc_entidade_visual"
        )

    with col2:

        st.text_input(
            "Ano do Exercício",
            value=str(ano_exercicio),
            disabled=True,
            key="fonte_inc_ano_visual"
        )

    # ========================================================
    # 5 - FORMULÁRIO
    # ========================================================

    st.markdown("---")

    with st.form(
        "form_fonte_recurso_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns([1, 3])

        with col1:

            codigo = st.text_input(
                "Código da Fonte *",
                max_chars=20,
                placeholder="Ex.: 1500"
            )

        with col2:

            descricao = st.text_input(
                "Descrição da Fonte *",
                max_chars=200,
                placeholder="Ex.: Recursos não Vinculados de Impostos"
            )

        ativo = st.checkbox(
            "Fonte ativa",
            value=True
        )

        st.markdown("---")

        salvar = st.form_submit_button(
            "💾 Salvar Fonte de Recurso",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # 6 - SALVAR
    # ========================================================

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo:

            st.warning(
                "Informe o Código da Fonte de Recurso."
            )
            return

        if not descricao:

            st.warning(
                "Informe a Descrição da Fonte de Recurso."
            )
            return

        # ====================================================
        # REVALIDAR O EXERCÍCIO E A ENTIDADE
        # ====================================================

        exercicio_valido = _sisget_fetchone(
            """
            SELECT ano
            FROM exercicios
            WHERE id = ?
              AND entidade_id = ?
              AND ativo = TRUE
              AND encerrado = FALSE
            """,
            (
                exercicio_id,
                entidade_id
            )
        )

        if not exercicio_valido:

            st.warning(
                "O Exercício selecionado não está mais "
                "disponível para esta Entidade."
            )
            return

        ano_exercicio = int(exercicio_valido[0])

        # ====================================================
        # VERIFICAR DUPLICIDADE
        # ====================================================

        existe = _sisget_fetchone(
            """
            SELECT id
            FROM fontes_recursos
            WHERE entidade_id = ?
              AND exercicio_id = ?
              AND codigo = ?
            """,
            (
                entidade_id,
                exercicio_id,
                codigo
            )
        )

        if existe:

            st.warning(
                f"A Fonte {codigo} já está cadastrada "
                f"para esta Entidade no exercício "
                f"{ano_exercicio}."
            )

            return

        # ====================================================
        # INSERT COMPATÍVEL COM A TABELA REAL
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO fontes_recursos
            (
                entidade_id,
                exercicio_id,
                exercicio,
                codigo,
                descricao,
                ativo
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                entidade_id,
                exercicio_id,
                ano_exercicio,
                codigo,
                descricao,
                ativo
            )
        )

        if sucesso:

            st.session_state[
                "fonte_recurso_mensagem"
            ] = (
                f"✅ Fonte {codigo} - {descricao} "
                f"cadastrada com sucesso para {ano_exercicio}!"
            )

            st.rerun()

def fonte_recurso_alterar(registro_id):

    st.subheader("✏️ Alterar Fonte de Recurso")

    dados = _sisget_fetchone(
        """
        SELECT
            id,
            exercicio,
            codigo,
            descricao,
            ativo
        FROM fontes_recursos
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not dados:

        st.error(
            "Fonte de Recurso não encontrada."
        )

        return

    (
        fonte_id,
        exercicio_atual,
        codigo_atual,
        descricao_atual,
        ativo_atual
    ) = dados

    exercicios = fonte_recurso_exercicios()

    if exercicio_atual not in exercicios:

        exercicios.append(exercicio_atual)

        exercicios.sort(reverse=True)

    with st.form(
        f"form_alterar_fonte_{fonte_id}"
    ):

        exercicio = st.selectbox(
            "Exercício *",
            exercicios,
            index=exercicios.index(exercicio_atual)
        )

        col1, col2 = st.columns([1, 3])

        with col1:

            codigo = st.text_input(
                "Código *",
                value=str(codigo_atual),
                max_chars=20
            )

        with col2:

            descricao = st.text_input(
                "Descrição *",
                value=descricao_atual,
                max_chars=200
            )

        ativo = st.checkbox(
            "Fonte ativa",
            value=bool(ativo_atual)
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "Código e descrição são obrigatórios."
            )

            return

        duplicado = _sisget_fetchone(
            """
            SELECT id
            FROM fontes_recursos
            WHERE exercicio = ?
              AND codigo = ?
              AND id <> ?
            """,
            (
                exercicio,
                codigo,
                fonte_id
            )
        )

        if duplicado:

            st.warning(
                "Já existe outra Fonte com este código "
                "no exercício selecionado."
            )

            return

        sucesso = _sisget_salvar(
            """
            UPDATE fontes_recursos

            SET
                exercicio = ?,
                codigo = ?,
                descricao = ?,
                ativo = ?

            WHERE id = ?
            """,
            (
                exercicio,
                codigo,
                descricao,
                ativo,
                fonte_id
            )
        )

        if sucesso:

            st.session_state[
                "fonte_recurso_mensagem"
            ] = "Fonte de Recurso alterada com sucesso!"

            st.session_state[
                "sisget_id_fontes_recursos"
            ] = None

            st.session_state[
                "sisget_tela_fontes_recursos"
            ] = "localizar"

            st.rerun()


# ============================================================
# EXCLUIR / INATIVAR
#
# PRESERVA O HISTÓRICO DAS FICHAS VINCULADAS
# ============================================================

def fonte_recurso_excluir():

    st.subheader("🗑️ Excluir Fonte de Recurso")

    st.caption(
        "A exclusão será lógica (inativação), preservando "
        "os vínculos com fichas orçamentárias existentes."
    )

    fontes = _sisget_fetch(
        """
        SELECT
            id,
            exercicio,
            codigo,
            descricao

        FROM fontes_recursos

        WHERE ativo = TRUE

        ORDER BY exercicio DESC, codigo
        """
    )

    if not fontes:

        st.info(
            "Nenhuma Fonte ativa disponível."
        )

        return

    mapa = {
        int(r[0]): (
            f"{r[1]} | {r[2]} - {r[3]}"
        )
        for r in fontes
    }

    fonte_id = st.selectbox(
        "Selecione a Fonte",
        options=[None] + list(mapa.keys()),
        format_func=lambda valor: (
            "Selecione"
            if valor is None
            else mapa[valor]
        ),
        key="fonte_excluir_selecao"
    )

    if fonte_id is None:
        return

    vinculadas = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM fichas_orcamentarias
        WHERE fonte_recurso_id = ?
        """,
        (fonte_id,)
    )

    quantidade = (
        int(vinculadas[0])
        if vinculadas
        else 0
    )

    if quantidade:

        st.warning(
            f"Esta Fonte possui {quantidade} ficha(s) "
            "orçamentária(s) vinculada(s). "
            "O histórico será preservado."
        )

    confirmar = st.checkbox(
        "Confirmo que desejo inativar esta Fonte.",
        key="fonte_confirmar_exclusao"
    )

    if st.button(
        "🗑️ Confirmar Inativação",
        type="primary",
        disabled=not confirmar,
        key="fonte_botao_excluir"
    ):

        sucesso = _sisget_salvar(
            """
            UPDATE fontes_recursos
            SET ativo = FALSE
            WHERE id = ?
            """,
            (fonte_id,)
        )

        if sucesso:

            st.session_state[
                "fonte_recurso_mensagem"
            ] = "Fonte de Recurso inativada com sucesso!"

            st.rerun()


# ============================================================
# IMPRIMIR
# ============================================================

def fonte_recurso_imprimir():

    st.subheader("🖨️ Relatório de Fontes de Recursos")

    filtro_exercicio = st.selectbox(
        "Exercício",
        ["Todos"] + fonte_recurso_exercicios(),
        key="fonte_imprimir_exercicio"
    )

    sql = """
        SELECT
            exercicio AS "Exercício",
            codigo AS "Código",
            descricao AS "Descrição",

            CASE
                WHEN ativo = TRUE THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM fontes_recursos
        WHERE 1 = 1
    """

    parametros = []

    if filtro_exercicio != "Todos":

        sql += " AND exercicio = ?"

        parametros.append(filtro_exercicio)

    sql += """
        ORDER BY exercicio DESC, codigo
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma Fonte de Recurso para imprimir."
        )

        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar Relatório PDF",
        key="fonte_gerar_pdf"
    ):

        from xml.sax.saxutils import escape

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle
        )

        from io import BytesIO

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=25,
            leftMargin=25,
            topMargin=25,
            bottomMargin=25
        )

        estilos = getSampleStyleSheet()

        elementos = []

        elementos.append(
            Paragraph(
                "SISGET - Fontes de Recursos",
                estilos["Title"]
            )
        )

        elementos.append(Spacer(1, 12))

        tabela_dados = [
            [
                "Exercício",
                "Código",
                "Descrição",
                "Situação"
            ]
        ]

        for _, registro in df.iterrows():

            tabela_dados.append([
                str(registro["Exercício"]),
                str(registro["Código"]),
                Paragraph(
                    escape(str(registro["Descrição"])),
                    estilos["Normal"]
                ),
                str(registro["Situação"])
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                75,
                90,
                500,
                75
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
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.grey
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        elementos.append(tabela)

        documento.build(elementos)

        buffer.seek(0)

        st.session_state[
            "fonte_pdf"
        ] = buffer.getvalue()

    if st.session_state.get("fonte_pdf"):

        st.download_button(
            "⬇️ Baixar PDF",
            data=st.session_state["fonte_pdf"],
            file_name="fontes_recursos_sisget.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="fonte_baixar_pdf"
        )
def ficha_orcamentaria_imprimir():

    st.subheader(
        "🖨️ Relatório de Fichas Orçamentárias"
    )

    # ========================================================
    # FILTROS
    # ========================================================

    col1, col2 = st.columns(
        [1, 2]
    )

    with col1:

        exercicio = st.number_input(
            "Exercício",
            min_value=2000,
            max_value=2100,
            value=datetime.now().year,
            step=1,
            key="ficha_imprimir_exercicio"
        )

    with col2:

        situacao = st.selectbox(
            "Situação",
            [
                "Todas",
                "Ativas",
                "Inativas"
            ],
            key="ficha_imprimir_situacao"
        )

    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            f.numero_ficha,

            o.codigo || ' - ' || o.nome,

            e.codigo || ' - ' || e.nome,

            u.codigo || ' - ' || u.nome,

            COALESCE(
                f.funcao,
                ''
            ),

            COALESCE(
                f.subfuncao,
                ''
            ),

            COALESCE(
                f.programa,
                ''
            ),

            COALESCE(
                f.acao,
                ''
            ),

            COALESCE(
                f.natureza_despesa,
                ''
            ),

            COALESCE(
                fr.codigo,
                ''
            ),

            COALESCE(
                f.descricao,
                ''
            ),

            f.valor_inicial,

            f.valor_atual,

            f.valor_reservado,

            (
                f.valor_atual
                -
                f.valor_reservado
            ),

            f.ativo

        FROM fichas_orcamentarias f

        INNER JOIN orgaos o
            ON o.id = f.orgao_id

        INNER JOIN entidades e
            ON e.id = f.entidade_id

        INNER JOIN unidades_orcamentarias u
            ON u.id = f.unidade_orcamentaria_id

        LEFT JOIN fontes_recursos fr
            ON fr.id = f.fonte_recurso_id

        WHERE f.exercicio = ?
    """

    parametros = [
        int(exercicio)
    ]

    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if situacao == "Ativas":

        sql += """
            AND f.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND f.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            f.numero_ficha
    """

    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )

    # ========================================================
    # SEM REGISTROS
    # ========================================================

    if not dados:

        st.info(
            "Nenhuma ficha orçamentária encontrada."
        )

        return

    # ========================================================
    # DATAFRAME
    # ========================================================

    visualizacao = []

    for registro in dados:

        visualizacao.append({

            "Ficha":
                registro[0],

            "Órgão":
                registro[1],

            "Entidade":
                registro[2],

            "Unidade Orçamentária":
                registro[3],

            "Função":
                registro[4],

            "Subfunção":
                registro[5],

            "Programa":
                registro[6],

            "Ação":
                registro[7],

            "Natureza":
                registro[8],

            "Fonte":
                registro[9],

            "Descrição":
                registro[10],

            "Valor Inicial":
                float(
                    registro[11] or 0
                ),

            "Valor Atual":
                float(
                    registro[12] or 0
                ),

            "Reservado":
                float(
                    registro[13] or 0
                ),

            "Disponível":
                float(
                    registro[14] or 0
                ),

            "Situação":
                (
                    "Ativa"
                    if registro[15]
                    else "Inativa"
                )
        })

    df = pd.DataFrame(
        visualizacao
    )

    # ========================================================
    # EXIBIR
    # ========================================================

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"Total de fichas: {len(df)}"
    )

    # ========================================================
    # TOTAIS
    # ========================================================

    total_inicial = sum(
        float(
            registro[11] or 0
        )
        for registro in dados
    )

    total_atual = sum(
        float(
            registro[12] or 0
        )
        for registro in dados
    )

    total_reservado = sum(
        float(
            registro[13] or 0
        )
        for registro in dados
    )

    total_disponivel = sum(
        float(
            registro[14] or 0
        )
        for registro in dados
    )

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Dotação Inicial",
            f"R$ {total_inicial:,.2f}"
        )

    with col2:

        st.metric(
            "Dotação Atual",
            f"R$ {total_atual:,.2f}"
        )

    with col3:

        st.metric(
            "Reservado",
            f"R$ {total_reservado:,.2f}"
        )

    with col4:

        st.metric(
            "Disponível",
            f"R$ {total_disponivel:,.2f}"
        )

    # ========================================================
    # GERAR PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_fichas_orcamentarias"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.7 * cm,
            leftMargin=0.7 * cm,
            topMargin=0.8 * cm,
            bottomMargin=0.8 * cm
        )

        estilos = (
            getSampleStyleSheet()
        )

        estilo_tabela = ParagraphStyle(
            "TextoFicha",
            parent=estilos["Normal"],
            fontSize=6,
            leading=7
        )

        elementos = []

        # ====================================================
        # CABEÇALHO PDF
        # ====================================================

        elementos.append(
            Paragraph(
                "SISGET - Sistema Integrado de Gestão Pública",
                estilos["Heading1"]
            )
        )

        elementos.append(
            Paragraph(
                f"Fichas Orçamentárias - Exercício {int(exercicio)}",
                estilos["Heading2"]
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
            "Ficha",
            "Unidade Orçamentária",
            "Natureza",
            "Fonte",
            "Descrição",
            "Atual",
            "Reservado",
            "Disponível"
        ]]

        for registro in dados:

            tabela_dados.append([

                str(
                    registro[0] or ""
                ),

                Paragraph(
                    str(
                        registro[3] or ""
                    ),
                    estilo_tabela
                ),

                Paragraph(
                    str(
                        registro[8] or ""
                    ),
                    estilo_tabela
                ),

                str(
                    registro[9] or ""
                ),

                Paragraph(
                    str(
                        registro[10] or ""
                    ),
                    estilo_tabela
                ),

                (
                    f"{float(registro[12] or 0):,.2f}"
                ),

                (
                    f"{float(registro[13] or 0):,.2f}"
                ),

                (
                    f"{float(registro[14] or 0):,.2f}"
                )
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                1.2 * cm,
                4.2 * cm,
                2.2 * cm,
                1.5 * cm,
                4.0 * cm,
                2.0 * cm,
                2.0 * cm,
                2.0 * cm
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
                    0.4,
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
                    6
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
        # TOTAIS PDF
        # ====================================================

        elementos.append(
            Paragraph(
                (
                    f"Dotação Atual: "
                    f"R$ {total_atual:,.2f}"
                ),
                estilos["Normal"]
            )
        )

        elementos.append(
            Paragraph(
                (
                    f"Total Reservado: "
                    f"R$ {total_reservado:,.2f}"
                ),
                estilos["Normal"]
            )
        )

        elementos.append(
            Paragraph(
                (
                    f"Total Disponível: "
                    f"R$ {total_disponivel:,.2f}"
                ),
                estilos["Normal"]
            )
        )

        elementos.append(
            Spacer(
                1,
                0.3 * cm
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
        # GERAR
        # ====================================================

        documento.build(
            elementos
        )

        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar Relatório em PDF",
            data=buffer,
            file_name=(
                f"fichas_orcamentarias_{int(exercicio)}.pdf"
            ),
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_fichas_orcamentarias"
        )

def ficha_orcamentaria_localizar():

    st.subheader(
        "🔎 Localizar Fichas Orçamentárias"
    )

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col1:

        exercicio = st.number_input(
            "Exercício",
            min_value=2000,
            max_value=2100,
            value=datetime.now().year,
            step=1,
            key="ficha_localizar_exercicio"
        )

    with col2:

        pesquisa = st.text_input(
            "Ficha / descrição / unidade",
            key="ficha_localizar_pesquisa"
        )

    with col3:

        situacao = st.selectbox(
            "Situação",
            [
                "Todas",
                "Ativas",
                "Inativas"
            ],
            key="ficha_localizar_situacao"
        )

    sql = """
        SELECT
            f.id,

            f.numero_ficha
                AS "Ficha",

            o.codigo || ' - ' || o.nome
                AS "Órgão",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            u.codigo || ' - ' || u.nome
                AS "Unidade Orçamentária",

            COALESCE(
                f.funcao,
                ''
            ) AS "Função",

            COALESCE(
                f.subfuncao,
                ''
            ) AS "Subfunção",

            COALESCE(
                f.programa,
                ''
            ) AS "Programa",

            COALESCE(
                f.acao,
                ''
            ) AS "Ação",

            COALESCE(
                f.natureza_despesa,
                ''
            ) AS "Natureza",

            COALESCE(
                fr.codigo,
                ''
            ) AS "Fonte",

            COALESCE(
                f.descricao,
                ''
            ) AS "Descrição",

            f.valor_atual
                AS "Valor Atual",

            f.valor_reservado
                AS "Reservado",

            (
                f.valor_atual
                -
                f.valor_reservado
            ) AS "Disponível",

            CASE
                WHEN f.ativo = TRUE
                    THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM fichas_orcamentarias f

        INNER JOIN orgaos o
            ON o.id = f.orgao_id

        INNER JOIN entidades e
            ON e.id = f.entidade_id

        INNER JOIN unidades_orcamentarias u
            ON u.id = f.unidade_orcamentaria_id

        LEFT JOIN fontes_recursos fr
            ON fr.id = f.fonte_recurso_id

        WHERE f.exercicio = ?
    """

    parametros = [
        int(exercicio)
    ]

    if pesquisa.strip():

        termo = (
            f"%{pesquisa.strip()}%"
        )

        sql += """
            AND
            (
                CAST(
                    f.numero_ficha AS TEXT
                ) ILIKE ?

                OR COALESCE(
                    f.descricao,
                    ''
                ) ILIKE ?

                OR u.nome ILIKE ?

                OR u.codigo ILIKE ?
            )
        """

        parametros.extend([
            termo,
            termo,
            termo,
            termo
        ])

    if situacao == "Ativas":

        sql += """
            AND f.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND f.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            f.numero_ficha
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma ficha encontrada."
        )

        return None

    st.caption(
        f"Total encontrado: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="fichas_orcamentarias",
        coluna_id="id",
        altura=470
    )


# ============================================================
# FICHAS ORÇAMENTÁRIAS - ALTERAR
# ============================================================

def ficha_orcamentaria_alterar(
    ficha_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            f.exercicio,
            f.numero_ficha,

            f.funcao,
            f.subfuncao,
            f.programa,
            f.acao,

            f.natureza_despesa,
            f.fonte_recurso_id,
            f.descricao,

            f.valor_inicial,
            f.valor_atual,
            f.valor_reservado,

            f.ativo,

            o.codigo,
            o.nome,

            e.codigo,
            e.nome,

            u.codigo,
            u.nome

        FROM fichas_orcamentarias f

        INNER JOIN orgaos o
            ON o.id = f.orgao_id

        INNER JOIN entidades e
            ON e.id = f.entidade_id

        INNER JOIN unidades_orcamentarias u
            ON u.id = f.unidade_orcamentaria_id

        WHERE f.id = ?
        """,
        (
            ficha_id,
        )
    )

    if not registro:

        st.error(
            "❌ Ficha Orçamentária não encontrada."
        )

        return

    (
        exercicio,
        numero_ficha,

        funcao_atual,
        subfuncao_atual,
        programa_atual,
        acao_atual,

        natureza_atual,
        fonte_atual_id,
        descricao_atual,

        valor_inicial,
        valor_atual,
        valor_reservado,

        ativo,

        codigo_orgao,
        nome_orgao,

        codigo_entidade,
        nome_entidade,

        codigo_uo,
        nome_uo

    ) = registro

    # ========================================================
    # ESTRUTURA
    # ========================================================

    st.info(
        f"""
🏛️ **{codigo_orgao} - {nome_orgao}**

🏢 **{codigo_entidade} - {nome_entidade}**

💼 **{codigo_uo} - {nome_uo}**
        """
    )

    # ========================================================
    # VALORES
    # ========================================================

    saldo = (
        float(valor_atual or 0)
        -
        float(valor_reservado or 0)
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Dotação Inicial",
        f"R$ {float(valor_inicial or 0):,.2f}"
    )

    col2.metric(
        "Dotação Atual",
        f"R$ {float(valor_atual or 0):,.2f}"
    )

    col3.metric(
        "Reservado",
        f"R$ {float(valor_reservado or 0):,.2f}"
    )

    col4.metric(
        "Disponível",
        f"R$ {saldo:,.2f}"
    )

    # ========================================================
    # FONTES
    # ========================================================

    fontes = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM fontes_recursos
        WHERE exercicio = ?
        ORDER BY codigo
        """,
        (
            int(exercicio),
        )
    )

    mapa_fontes = {
        "Sem fonte definida": None
    }

    for fonte_id, codigo, descricao in fontes:

        mapa_fontes[
            f"{codigo} - {descricao}"
        ] = fonte_id

    lista_fontes = list(
        mapa_fontes.keys()
    )

    indice_fonte = 0

    for indice, nome in enumerate(
        lista_fontes
    ):

        if mapa_fontes[nome] == fonte_atual_id:

            indice_fonte = indice

            break

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_alterar_ficha_{ficha_id}"
    ):

        col1, col2 = st.columns(2)

        with col1:

            st.number_input(
                "Exercício",
                value=int(exercicio),
                disabled=True
            )

        with col2:

            st.number_input(
                "Número da Ficha",
                value=int(numero_ficha),
                disabled=True
            )

        fonte_nome = st.selectbox(
            "Fonte de Recursos",
            lista_fontes,
            index=indice_fonte
        )

        st.markdown(
            "### 🧾 Classificação"
        )

        col1, col2 = st.columns(2)

        with col1:

            funcao = st.text_input(
                "Função",
                value=funcao_atual or "",
                max_chars=2
            )

        with col2:

            subfuncao = st.text_input(
                "Subfunção",
                value=subfuncao_atual or "",
                max_chars=3
            )

        col1, col2 = st.columns(2)

        with col1:

            programa = st.text_input(
                "Programa",
                value=programa_atual or "",
                max_chars=20
            )

        with col2:

            acao = st.text_input(
                "Ação",
                value=acao_atual or "",
                max_chars=20
            )

        natureza = st.text_input(
            "Natureza da Despesa",
            value=natureza_atual or "",
            max_chars=30
        )

        descricao = st.text_input(
            "Descrição",
            value=descricao_atual or "",
            max_chars=250
        )

        novo_valor_atual = st.number_input(
            "Valor Atual",
            min_value=0.0,
            value=float(
                valor_atual or 0
            ),
            step=100.00,
            format="%.2f"
        )

        st.caption(
            f"Valor atualmente reservado: "
            f"R$ {float(valor_reservado or 0):,.2f}"
        )

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:

            salvar = st.form_submit_button(
                "💾 Salvar Alterações",
                type="primary",
                use_container_width=True
            )

        with col2:

            mudar_situacao = st.form_submit_button(
                (
                    "🚫 Inativar Ficha"
                    if ativo
                    else "✅ Ativar Ficha"
                ),
                use_container_width=True
            )

    # ========================================================
    # SITUAÇÃO
    # ========================================================

    if mudar_situacao:

        sucesso = _sisget_salvar(
            """
            UPDATE fichas_orcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                ficha_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_fichas_orcamentarias"
            ] = None

            st.session_state[
                "sisget_tela_fichas_orcamentarias"
            ] = "localizar"

            st.rerun()

        return

    # ========================================================
    # ALTERAR
    # ========================================================

    if salvar:

        if (
            float(novo_valor_atual)
            <
            float(valor_reservado or 0)
        ):

            st.warning(
                "⚠️ O valor atual não pode ser menor "
                "que o valor já reservado."
            )

            return

        fonte_recurso_id = mapa_fontes[
            fonte_nome
        ]

        sucesso = _sisget_salvar(
            """
            UPDATE fichas_orcamentarias
            SET
                funcao = ?,
                subfuncao = ?,
                programa = ?,
                acao = ?,
                natureza_despesa = ?,
                fonte_recurso_id = ?,
                descricao = ?,
                valor_atual = ?
            WHERE id = ?
            """,
            (
                funcao.strip() or None,
                subfuncao.strip() or None,
                programa.strip() or None,
                acao.strip() or None,
                natureza.strip() or None,
                fonte_recurso_id,
                descricao.strip() or None,
                float(novo_valor_atual),
                ficha_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_id_fichas_orcamentarias"
            ] = None

            st.session_state[
                "sisget_tela_fichas_orcamentarias"
            ] = "localizar"

            st.rerun()


# ============================================================
# FICHAS ORÇAMENTÁRIAS - EXCLUIR
# ============================================================

def ficha_orcamentaria_excluir():

    st.subheader(
        "🗑️ Excluir Ficha Orçamentária"
    )

    exercicio = st.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="ficha_excluir_exercicio"
    )

    df = _sisget_dataframe(
        """
        SELECT
            f.id,

            f.numero_ficha
                AS "Ficha",

            e.codigo || ' - ' || e.nome
                AS "Entidade",

            u.codigo || ' - ' || u.nome
                AS "Unidade Orçamentária",

            COALESCE(
                f.descricao,
                ''
            ) AS "Descrição",

            f.valor_atual
                AS "Valor Atual",

            f.valor_reservado
                AS "Reservado"

        FROM fichas_orcamentarias f

        INNER JOIN entidades e
            ON e.id = f.entidade_id

        INNER JOIN unidades_orcamentarias u
            ON u.id = f.unidade_orcamentaria_id

        WHERE f.exercicio = ?

        ORDER BY
            f.numero_ficha
        """,
        (
            int(exercicio),
        )
    )

    if df.empty:

        st.info(
            "Nenhuma ficha cadastrada."
        )

        return

    ficha_id = sisget_grid_localizar(
        df=df,
        chave="excluir_fichas_orcamentarias",
        coluna_id="id",
        altura=430
    )

    if not ficha_id:

        st.caption(
            "Dê duplo clique na ficha que deseja excluir."
        )

        return

    registro = _sisget_fetchone(
        """
        SELECT
            numero_ficha,
            descricao,
            valor_reservado
        FROM fichas_orcamentarias
        WHERE id = ?
        """,
        (
            ficha_id,
        )
    )

    if not registro:

        return

    numero_ficha = registro[0]
    descricao = registro[1] or ""
    reservado = float(
        registro[2] or 0
    )

    st.markdown("---")

    st.error(
        f"⚠️ Ficha **{numero_ficha} - {descricao}**"
    )

    if reservado > 0:

        st.warning(
            "🔒 Esta ficha possui valor reservado "
            "e não pode ser excluída."
        )

        return

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta ficha.",
        key=f"confirmar_excluir_ficha_{ficha_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_ficha_{ficha_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação."
            )

            return

        sucesso = _sisget_salvar(
            """
            DELETE FROM fichas_orcamentarias
            WHERE id = ?
            """,
            (
                ficha_id,
            )
        )

        if sucesso:

            st.session_state[
                "sisget_tela_fichas_orcamentarias"
            ] = "principal"

            st.rerun()


# ============================================================
# FICHAS ORÇAMENTÁRIAS - IMPRIMIR
# ============================================================

def ficha_orcamentaria_imprimir():

    st.subheader(
        "🖨️ Relatório de Fichas Orçamentárias"
    )

    exercicio = st.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="ficha_imprimir_exercicio"
    )

    dados = _sisget_fetch(
        """
        SELECT
            f.numero_ficha,

            u.codigo,
            u.nome,

            COALESCE(
                f.natureza_despesa,
                ''
            ),

            COALESCE(
                fr.codigo,
                ''
            ),

            COALESCE(
                f.descricao,
                ''
            ),

            f.valor_inicial,
            f.valor_atual,
            f.valor_reservado,

            (
                f.valor_atual
                -
                f.valor_reservado
            ),

            f.ativo

        FROM fichas_orcamentarias f

        INNER JOIN unidades_orcamentarias u
            ON u.id = f.unidade_orcamentaria_id

        LEFT JOIN fontes_recursos fr
            ON fr.id = f.fonte_recurso_id

        WHERE f.exercicio = ?

        ORDER BY
            u.codigo,
            f.numero_ficha
        """,
        (
            int(exercicio),
        )
    )

    if not dados:

        st.info(
            "Nenhuma ficha encontrada."
        )

        return

    visualizacao = []

    for registro in dados:

        visualizacao.append({

            "Ficha":
                registro[0],

            "Unidade Orçamentária":
                f"{registro[1]} - {registro[2]}",

            "Natureza":
                registro[3],

            "Fonte":
                registro[4],

            "Descrição":
                registro[5],

            "Inicial":
                float(registro[6] or 0),

            "Atual":
                float(registro[7] or 0),

            "Reservado":
                float(registro[8] or 0),

            "Disponível":
                float(registro[9] or 0),

            "Situação":
                (
                    "Ativa"
                    if registro[10]
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

    # ========================================================
    # TOTAIS
    # ========================================================

    total_atual = sum(
        float(r[7] or 0)
        for r in dados
    )

    total_reservado = sum(
        float(r[8] or 0)
        for r in dados
    )

    total_disponivel = sum(
        float(r[9] or 0)
        for r in dados
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Dotação Atual",
        f"R$ {total_atual:,.2f}"
    )

    col2.metric(
        "Reservado",
        f"R$ {total_reservado:,.2f}"
    )

    col3.metric(
        "Disponível",
        f"R$ {total_disponivel:,.2f}"
    )

    # ========================================================
    # PDF
    # ========================================================

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key="gerar_pdf_fichas"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.7 * cm,
            leftMargin=0.7 * cm,
            topMargin=0.8 * cm,
            bottomMargin=0.8 * cm
        )

        estilos = getSampleStyleSheet()

        estilo_pequeno = ParagraphStyle(
            "FichaTexto",
            parent=estilos["Normal"],
            fontSize=6,
            leading=7
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
                f"Fichas Orçamentárias - Exercício {int(exercicio)}",
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
            "Ficha",
            "Unidade Orçamentária",
            "Natureza",
            "Fonte",
            "Descrição",
            "Atual",
            "Reservado",
            "Disponível"
        ]]

        for registro in dados:

            tabela_dados.append([

                str(
                    registro[0]
                ),

                Paragraph(
                    f"{registro[1]} - {registro[2]}",
                    estilo_pequeno
                ),

                str(
                    registro[3] or ""
                ),

                str(
                    registro[4] or ""
                ),

                Paragraph(
                    str(
                        registro[5] or ""
                    ),
                    estilo_pequeno
                ),

                f"{float(registro[7] or 0):,.2f}",

                f"{float(registro[8] or 0):,.2f}",

                f"{float(registro[9] or 0):,.2f}"
            ])

        tabela = Table(
            tabela_dados,
            colWidths=[
                1.1 * cm,
                4.1 * cm,
                2.2 * cm,
                1.4 * cm,
                4.0 * cm,
                2.0 * cm,
                2.0 * cm,
                2.0 * cm
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
                    0.4,
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
                    6
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
                f"Dotação Atual: R$ {total_atual:,.2f}",
                estilos["Normal"]
            )
        )

        elementos.append(
            Paragraph(
                f"Reservado: R$ {total_reservado:,.2f}",
                estilos["Normal"]
            )
        )

        elementos.append(
            Paragraph(
                f"Disponível: R$ {total_disponivel:,.2f}",
                estilos["Normal"]
            )
        )

        documento.build(
            elementos
        )

        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar PDF",
            data=buffer,
            file_name=(
                f"fichas_orcamentarias_{int(exercicio)}.pdf"
            ),
            mime="application/pdf",
            use_container_width=True,
            key="baixar_pdf_fichas"
        )


# ============================================================
# FICHAS ORÇAMENTÁRIAS - TELA PRINCIPAL
# ============================================================

def planejamento_fichas_orcamentarias():

    sisget_tela_principal(
        titulo="Fichas Orçamentárias",
        chave="fichas_orcamentarias",

        func_incluir=ficha_orcamentaria_incluir,
        func_localizar=ficha_orcamentaria_localizar,
        func_alterar=ficha_orcamentaria_alterar,
        func_excluir=ficha_orcamentaria_excluir,
        func_imprimir=ficha_orcamentaria_imprimir,

        icone="📄"
    )

# ============================================================
# CLASSIFICAÇÕES ORÇAMENTÁRIAS
# ============================================================

# ============================================================
# CLASSIFICAÇÕES ORÇAMENTÁRIAS
# ============================================================

def planejamento_classificacoes():

    st.subheader("🧾 Classificações Orçamentárias")

    abas = st.tabs([
        "🏷️ Funções",
        "🔹 Subfunções",
        "📘 Programas",
        "🎯 Ações",
        "💵 Naturezas da Despesa"
    ])

    with abas[0]:
        planejamento_funcoes()

    with abas[1]:
        planejamento_subfuncoes()

    with abas[2]:
        planejamento_programas()

    with abas[3]:
        planejamento_acoes()

    with abas[4]:
        planejamento_naturezas()
# ============================================================
# FUNÇÕES - TELA PRINCIPAL
# ============================================================

def planejamento_funcoes():

    sisget_tela_principal(
        titulo="Funções Orçamentárias",
        chave="funcoes_orcamentarias",
        func_incluir=funcao_orcamentaria_incluir,
        func_localizar=funcao_orcamentaria_localizar,
        func_alterar=funcao_orcamentaria_alterar,
        func_excluir=funcao_orcamentaria_excluir,
        func_imprimir=funcao_orcamentaria_imprimir,
        icone="🏷️"
    )


# ============================================================
# FUNÇÃO - INCLUIR
# ============================================================

def funcao_orcamentaria_incluir():

    with st.form(
        "form_funcao_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns([1, 4])

        codigo = col1.text_input(
            "Código *",
            max_chars=10
        )

        descricao = col2.text_input(
            "Descrição *",
            max_chars=200
        )

        salvar = st.form_submit_button(
            "💾 Salvar",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:
            st.warning("⚠️ Informe código e descrição.")
            return

        existe = _sisget_fetchone(
            """
            SELECT id
            FROM funcoes_orcamentarias
            WHERE codigo = ?
            """,
            (codigo,)
        )

        if existe:
            st.warning("⚠️ Esta Função já está cadastrada.")
            return

        if _sisget_salvar(
            """
            INSERT INTO funcoes_orcamentarias
            (
                codigo,
                descricao,
                ativo
            )
            VALUES (?, ?, TRUE)
            """,
            (
                codigo,
                descricao
            )
        ):

            st.success("✅ Função cadastrada com sucesso!")
            st.rerun()


# ============================================================
# FUNÇÃO - LOCALIZAR
# ============================================================

def funcao_orcamentaria_localizar():

    pesquisa = st.text_input(
        "🔎 Código ou descrição",
        key="buscar_funcao_orc"
    )

    sql = """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM funcoes_orcamentarias
        WHERE 1 = 1
    """

    parametros = []

    if pesquisa.strip():

        termo = f"%{pesquisa.strip()}%"

        sql += """
            AND
            (
                codigo ILIKE ?
                OR descricao ILIKE ?
            )
        """

        parametros.extend([
            termo,
            termo
        ])

    sql += " ORDER BY codigo"

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:
        st.info("Nenhuma Função encontrada.")
        return None

    return sisget_grid_localizar(
        df=df,
        chave="funcoes_orcamentarias",
        coluna_id="id",
        altura=420
    )


# ============================================================
# FUNÇÃO - ALTERAR
# ============================================================

def funcao_orcamentaria_alterar(funcao_id):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            descricao,
            ativo
        FROM funcoes_orcamentarias
        WHERE id = ?
        """,
        (funcao_id,)
    )

    if not registro:
        st.error("❌ Função não encontrada.")
        return

    codigo_atual, descricao_atual, ativo = registro

    with st.form(
        f"form_funcao_alterar_{funcao_id}"
    ):

        codigo = st.text_input(
            "Código *",
            value=codigo_atual or ""
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if status:

        if _sisget_salvar(
            """
            UPDATE funcoes_orcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                funcao_id
            )
        ):

            st.session_state[
                "sisget_tela_funcoes_orcamentarias"
            ] = "localizar"

            st.rerun()

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:
            st.warning("⚠️ Informe código e descrição.")
            return

        duplicado = _sisget_fetchone(
            """
            SELECT id
            FROM funcoes_orcamentarias
            WHERE codigo = ?
              AND id <> ?
            """,
            (
                codigo,
                funcao_id
            )
        )

        if duplicado:
            st.warning("⚠️ Já existe outra Função com este código.")
            return

        if _sisget_salvar(
            """
            UPDATE funcoes_orcamentarias
            SET
                codigo = ?,
                descricao = ?
            WHERE id = ?
            """,
            (
                codigo,
                descricao,
                funcao_id
            )
        ):

            st.session_state[
                "sisget_tela_funcoes_orcamentarias"
            ] = "localizar"

            st.rerun()


# ============================================================
# FUNÇÃO - EXCLUIR
# ============================================================

def funcao_orcamentaria_excluir():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição"
        FROM funcoes_orcamentarias
        ORDER BY codigo
        """
    )

    if df.empty:
        st.info("Nenhuma Função cadastrada.")
        return

    funcao_id = sisget_grid_localizar(
        df=df,
        chave="excluir_funcoes_orcamentarias",
        coluna_id="id",
        altura=420
    )

    if not funcao_id:
        st.caption("Dê duplo clique na Função que deseja excluir.")
        return

    dependencias = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM subfuncoes_orcamentarias
        WHERE funcao_id = ?
        """,
        (funcao_id,)
    )

    if dependencias and dependencias[0] > 0:

        st.warning(
            "⚠️ Esta Função possui Subfunções vinculadas "
            "e não pode ser excluída."
        )
        return

    confirmar = st.checkbox(
        "Confirmo a exclusão desta Função.",
        key=f"confirmar_funcao_{funcao_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_funcao_{funcao_id}"
    ):

        if not confirmar:
            st.warning("⚠️ Marque a confirmação.")
            return

        if _sisget_salvar(
            """
            DELETE FROM funcoes_orcamentarias
            WHERE id = ?
            """,
            (funcao_id,)
        ):

            st.rerun()


# ============================================================
# FUNÇÃO - IMPRIMIR
# ============================================================

def funcao_orcamentaria_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM funcoes_orcamentarias
        ORDER BY codigo
        """
    )

    sisget_relatorio_classificacao(
        "Funções Orçamentárias",
        df,
        "funcoes_orcamentarias.pdf"
    )

# ============================================================
# SUBFUNÇÕES - TELA PRINCIPAL
# ============================================================

def planejamento_subfuncoes():

    sisget_tela_principal(
        titulo="Subfunções Orçamentárias",
        chave="subfuncoes_orcamentarias",
        func_incluir=subfuncao_orcamentaria_incluir,
        func_localizar=subfuncao_orcamentaria_localizar,
        func_alterar=subfuncao_orcamentaria_alterar,
        func_excluir=subfuncao_orcamentaria_excluir,
        func_imprimir=subfuncao_orcamentaria_imprimir,
        icone="🔹"
    )


def subfuncao_orcamentaria_incluir():

    funcoes = _sisget_fetch(
        """
        SELECT id, codigo, descricao
        FROM funcoes_orcamentarias
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    if not funcoes:
        st.warning("⚠️ Cadastre uma Função primeiro.")
        return

    mapa = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in funcoes
    }

    with st.form(
        "form_subfuncao_incluir",
        clear_on_submit=True
    ):

        funcao_nome = st.selectbox(
            "Função *",
            list(mapa.keys())
        )

        col1, col2 = st.columns([1, 4])

        codigo = col1.text_input("Código *")
        descricao = col2.text_input("Descrição *")

        salvar = st.form_submit_button(
            "💾 Salvar",
            type="primary",
            use_container_width=True
        )

    if salvar:

        funcao_id = mapa[funcao_nome]

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:
            st.warning("⚠️ Informe código e descrição.")
            return

        existe = _sisget_fetchone(
            """
            SELECT id
            FROM subfuncoes_orcamentarias
            WHERE funcao_id = ?
              AND codigo = ?
            """,
            (
                funcao_id,
                codigo
            )
        )

        if existe:
            st.warning("⚠️ Subfunção já cadastrada.")
            return

        if _sisget_salvar(
            """
            INSERT INTO subfuncoes_orcamentarias
            (
                funcao_id,
                codigo,
                descricao,
                ativo
            )
            VALUES (?, ?, ?, TRUE)
            """,
            (
                funcao_id,
                codigo,
                descricao
            )
        ):

            st.success("✅ Subfunção cadastrada.")
            st.rerun()


def subfuncao_orcamentaria_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            s.id,
            f.codigo || ' - ' || f.descricao
                AS "Função",
            s.codigo AS "Código",
            s.descricao AS "Descrição",
            CASE
                WHEN s.ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM subfuncoes_orcamentarias s

        INNER JOIN funcoes_orcamentarias f
            ON f.id = s.funcao_id

        ORDER BY
            f.codigo,
            s.codigo
        """
    )

    if df.empty:
        st.info("Nenhuma Subfunção encontrada.")
        return None

    return sisget_grid_localizar(
        df=df,
        chave="subfuncoes_orcamentarias",
        coluna_id="id",
        altura=420
    )


def subfuncao_orcamentaria_alterar(subfuncao_id):

    registro = _sisget_fetchone(
        """
        SELECT
            funcao_id,
            codigo,
            descricao,
            ativo
        FROM subfuncoes_orcamentarias
        WHERE id = ?
        """,
        (subfuncao_id,)
    )

    if not registro:
        st.error("❌ Subfunção não encontrada.")
        return

    funcao_atual, codigo_atual, descricao_atual, ativo = registro

    funcoes = _sisget_fetch(
        """
        SELECT id, codigo, descricao
        FROM funcoes_orcamentarias
        ORDER BY codigo
        """
    )

    mapa = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in funcoes
    }

    nomes = list(mapa.keys())

    indice = 0

    for i, nome in enumerate(nomes):
        if mapa[nome] == funcao_atual:
            indice = i
            break

    with st.form(
        f"form_subfuncao_alterar_{subfuncao_id}"
    ):

        funcao_nome = st.selectbox(
            "Função *",
            nomes,
            index=indice
        )

        codigo = st.text_input(
            "Código *",
            value=codigo_atual or ""
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if status:

        if _sisget_salvar(
            """
            UPDATE subfuncoes_orcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                subfuncao_id
            )
        ):

            st.session_state[
                "sisget_tela_subfuncoes_orcamentarias"
            ] = "localizar"

            st.rerun()

    if salvar:

        if _sisget_salvar(
            """
            UPDATE subfuncoes_orcamentarias
            SET
                funcao_id = ?,
                codigo = ?,
                descricao = ?
            WHERE id = ?
            """,
            (
                mapa[funcao_nome],
                codigo.strip(),
                descricao.strip(),
                subfuncao_id
            )
        ):

            st.session_state[
                "sisget_tela_subfuncoes_orcamentarias"
            ] = "localizar"

            st.rerun()


def subfuncao_orcamentaria_excluir():

    df = _sisget_dataframe(
        """
        SELECT
            s.id,
            f.codigo AS "Função",
            s.codigo AS "Código",
            s.descricao AS "Descrição"
        FROM subfuncoes_orcamentarias s
        INNER JOIN funcoes_orcamentarias f
            ON f.id = s.funcao_id
        ORDER BY f.codigo, s.codigo
        """
    )

    if df.empty:
        st.info("Nenhuma Subfunção cadastrada.")
        return

    registro_id = sisget_grid_localizar(
        df=df,
        chave="excluir_subfuncoes",
        coluna_id="id",
        altura=420
    )

    if not registro_id:
        st.caption("Dê duplo clique na Subfunção.")
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_subfuncao_{registro_id}"
    ):

        if _sisget_salvar(
            """
            DELETE FROM subfuncoes_orcamentarias
            WHERE id = ?
            """,
            (registro_id,)
        ):

            st.rerun()

# ============================================================
# PROGRAMAS
# ============================================================

def planejamento_programas():

    sisget_tela_principal(
        titulo="Programas Orçamentários",
        chave="programas_orcamentarios",
        func_incluir=programa_orcamentario_incluir,
        func_localizar=programa_orcamentario_localizar,
        func_alterar=programa_orcamentario_alterar,
        func_excluir=programa_orcamentario_excluir,
        func_imprimir=programa_orcamentario_imprimir,
        icone="📘"
    )


# ============================================================
# PROGRAMA ORÇAMENTÁRIO - INCLUIR
# ============================================================

# ============================================================
# PROGRAMA ORÇAMENTÁRIO - INCLUIR
# ============================================================

# ============================================================
# PROGRAMA ORÇAMENTÁRIO - INCLUIR
# ============================================================

def programa_orcamentario_incluir():

    st.subheader(
        "📘 Incluir Programa Orçamentário"
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
        WHERE ativo = TRUE
        ORDER BY codigo, nome
        """
    )

    if not entidades:

        st.warning(
            "⚠️ Nenhuma Entidade ativa cadastrada."
        )

        return

    mapa_entidades = {
        f"{codigo} - {nome}": entidade_id
        for entidade_id, codigo, nome in entidades
    }

    entidade_nome = st.selectbox(
        "Entidade *",
        list(mapa_entidades.keys()),
        key="programa_entidade"
    )

    entidade_id = mapa_entidades[
        entidade_nome
    ]

    # ========================================================
    # EXERCÍCIOS DA ENTIDADE
    # ========================================================

    exercicios = _sisget_fetch(
        """
        SELECT
            id,
            ano,
            descricao
        FROM exercicios
        WHERE entidade_id = ?
          AND ativo = TRUE
          AND encerrado = FALSE
        ORDER BY ano DESC
        """,
        (
            entidade_id,
        )
    )

    # ========================================================
    # CRIAR EXERCÍCIO AUTOMATICAMENTE SE NÃO EXISTIR
    # ========================================================

    if not exercicios:

        ano_atual = datetime.now().year

        exercicio_existente = _sisget_fetchone(
            """
            SELECT
                id
            FROM exercicios
            WHERE entidade_id = ?
              AND ano = ?
            """,
            (
                entidade_id,
                ano_atual
            )
        )

        if exercicio_existente:

            exercicio_id_existente = exercicio_existente[0]

            sucesso = _sisget_salvar(
                """
                UPDATE exercicios
                SET
                    ativo = TRUE,
                    encerrado = FALSE,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    exercicio_id_existente,
                )
            )

            if not sucesso:

                st.error(
                    "❌ Não foi possível reabrir o exercício existente."
                )

                return

        else:

            resultado = _sisget_salvar_retorno(
                """
                INSERT INTO exercicios
                (
                    entidade_id,
                    ano,
                    descricao,
                    data_inicio,
                    data_fim,
                    encerrado,
                    ativo,
                    criado_em,
                    atualizado_em
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    FALSE,
                    TRUE,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
                """,
                (
                    entidade_id,
                    ano_atual,
                    f"Exercício {ano_atual}",
                    f"{ano_atual}-01-01",
                    f"{ano_atual}-12-31"
                )
            )

            if not resultado:

                st.error(
                    "❌ Não foi possível criar o exercício automaticamente."
                )

                return

        # ====================================================
        # RECARREGAR EXERCÍCIOS
        # ====================================================

        exercicios = _sisget_fetch(
            """
            SELECT
                id,
                ano,
                descricao
            FROM exercicios
            WHERE entidade_id = ?
              AND ativo = TRUE
              AND encerrado = FALSE
            ORDER BY ano DESC
            """,
            (
                entidade_id,
            )
        )

    # ========================================================
    # GARANTIA
    # ========================================================

    if not exercicios:

        st.error(
            "❌ Nenhum exercício ativo e aberto foi encontrado."
        )

        return

    # ========================================================
    # MAPA DOS EXERCÍCIOS
    # ========================================================

    mapa_exercicios = {}

    for exercicio_id, ano, descricao in exercicios:

        texto = str(ano)

        if descricao:

            texto += f" - {descricao}"

        mapa_exercicios[
            texto
        ] = (
            exercicio_id,
            ano
        )

    exercicio_nome = st.selectbox(
        "Exercício *",
        list(mapa_exercicios.keys()),
        key="programa_exercicio"
    )

    (
        exercicio_id,
        ano_exercicio
    ) = mapa_exercicios[
        exercicio_nome
    ]

    # ========================================================
    # PRÓXIMO CÓDIGO AUTOMÁTICO DO PROGRAMA
    # ========================================================

    codigos = _sisget_fetch(
        """
        SELECT
            codigo
        FROM programas
        WHERE entidade_id = ?
          AND exercicio_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
            exercicio_id
        )
    )

    usados = set()

    for registro in codigos:

        try:

            usados.add(
                int(
                    str(
                        registro[0]
                    ).strip()
                )
            )

        except (ValueError, TypeError):

            pass

    proximo = 1

    while proximo in usados:

        proximo += 1

    codigo_automatico = str(
        proximo
    ).zfill(4)

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_programa_orcamentario_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            st.text_input(
                "Código",
                value=codigo_automatico,
                disabled=True
            )

        with col2:

            nome = st.text_input(
                "Nome do Programa *",
                max_chars=250,
                placeholder="Ex.: Gestão Administrativa"
            )

        descricao = st.text_area(
            "Descrição",
            height=100
        )

        ativo = st.checkbox(
            "Programa ativo",
            value=True
        )

        salvar = st.form_submit_button(
            "💾 Salvar Programa",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()
        descricao = descricao.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome do Programa."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO NO MOMENTO DE SALVAR
        # ====================================================

        codigos = _sisget_fetch(
            """
            SELECT
                codigo
            FROM programas
            WHERE entidade_id = ?
              AND exercicio_id = ?
            """,
            (
                entidade_id,
                exercicio_id
            )
        )

        usados = set()

        for registro in codigos:

            try:

                usados.add(
                    int(
                        str(
                            registro[0]
                        ).strip()
                    )
                )

            except (ValueError, TypeError):

                pass

        proximo = 1

        while proximo in usados:

            proximo += 1

        codigo = str(
            proximo
        ).zfill(4)

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO programas
            (
                entidade_id,
                exercicio_id,
                codigo,
                nome,
                descricao,
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
                entidade_id,
                exercicio_id,
                codigo,
                nome,
                descricao or None,
                ativo
            )
        )

        if sucesso:

            st.success(
                f"✅ Programa {codigo} - {nome} "
                f"cadastrado para {ano_exercicio}."
            )

            st.rerun()

def programa_orcamentario_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            exercicio AS "Exercício",
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM programas_orcamentarios
        ORDER BY exercicio DESC, codigo
        """
    )

    if df.empty:
        st.info("Nenhum Programa encontrado.")
        return None

    return sisget_grid_localizar(
        df=df,
        chave="programas_orcamentarios",
        coluna_id="id",
        altura=420
    )


def programa_orcamentario_alterar(programa_id):

    registro = _sisget_fetchone(
        """
        SELECT
            exercicio,
            codigo,
            descricao,
            ativo
        FROM programas_orcamentarios
        WHERE id = ?
        """,
        (programa_id,)
    )

    if not registro:
        return

    exercicio, codigo_atual, descricao_atual, ativo = registro

    with st.form(
        f"form_programa_alterar_{programa_id}"
    ):

        st.number_input(
            "Exercício",
            value=int(exercicio),
            disabled=True
        )

        codigo = st.text_input(
            "Código *",
            value=codigo_atual or ""
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if status:

        _sisget_salvar(
            """
            UPDATE programas_orcamentarios
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                programa_id
            )
        )

        st.rerun()

    if salvar:

        if _sisget_salvar(
            """
            UPDATE programas_orcamentarios
            SET
                codigo = ?,
                descricao = ?
            WHERE id = ?
            """,
            (
                codigo.strip(),
                descricao.strip(),
                programa_id
            )
        ):

            st.rerun()


def programa_orcamentario_excluir():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            exercicio AS "Exercício",
            codigo AS "Código",
            descricao AS "Descrição"
        FROM programas_orcamentarios
        ORDER BY exercicio DESC, codigo
        """
    )

    if df.empty:
        return

    programa_id = sisget_grid_localizar(
        df=df,
        chave="excluir_programa",
        coluna_id="id",
        altura=420
    )

    if not programa_id:
        return

    filhos = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM acoes_orcamentarias
        WHERE programa_id = ?
        """,
        (programa_id,)
    )

    if filhos and filhos[0] > 0:

        st.warning(
            "⚠️ Este Programa possui Ações vinculadas."
        )
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_programa_{programa_id}"
    ):

        if _sisget_salvar(
            """
            DELETE FROM programas_orcamentarios
            WHERE id = ?
            """,
            (programa_id,)
        ):

            st.rerun()

# ============================================================
# AÇÕES
# ============================================================

def planejamento_acoes():

    sisget_tela_principal(
        titulo="Ações Orçamentárias",
        chave="acoes_orcamentarias",
        func_incluir=acao_orcamentaria_incluir,
        func_localizar=acao_orcamentaria_localizar,
        func_alterar=acao_orcamentaria_alterar,
        func_excluir=acao_orcamentaria_excluir,
        func_imprimir=acao_orcamentaria_imprimir,
        icone="🎯"
    )


# ============================================================
# AÇÃO ORÇAMENTÁRIA - INCLUIR
# ============================================================

# ============================================================
# AÇÃO ORÇAMENTÁRIA - INCLUIR
# ============================================================

def acao_orcamentaria_incluir():

    st.subheader(
        "🎯 Incluir Ação Orçamentária"
    )

    # ========================================================
    # BUSCAR PROGRAMAS CADASTRADOS
    # ========================================================

    programas = _sisget_fetch(
        """
        SELECT
            p.id,
            p.entidade_id,
            p.exercicio_id,

            p.codigo,
            p.nome,

            e.codigo,
            e.nome,

            ex.ano

        FROM programas p

        INNER JOIN entidades e
            ON e.id = p.entidade_id

        INNER JOIN exercicios ex
            ON ex.id = p.exercicio_id

        WHERE p.ativo = TRUE
          AND e.ativo = TRUE
          AND ex.ativo = TRUE

        ORDER BY
            ex.ano DESC,
            e.codigo,
            p.codigo
        """
    )

    # ========================================================
    # NENHUM PROGRAMA
    # ========================================================

    if not programas:

        st.warning(
            "⚠️ Nenhum Programa ativo foi encontrado "
            "para vincular à Ação."
        )

        return

    # ========================================================
    # MAPA DOS PROGRAMAS
    # ========================================================

    mapa_programas = {}

    for (
        programa_id,
        entidade_id,
        exercicio_id,

        codigo_programa,
        nome_programa,

        codigo_entidade,
        nome_entidade,

        ano_exercicio

    ) in programas:

        texto = (
            f"{ano_exercicio}"
            f" | "
            f"{codigo_entidade} - {nome_entidade}"
            f" | "
            f"{codigo_programa} - {nome_programa}"
        )

        mapa_programas[
            texto
        ] = {
            "programa_id": programa_id,
            "entidade_id": entidade_id,
            "exercicio_id": exercicio_id,

            "codigo_programa": codigo_programa,
            "nome_programa": nome_programa,

            "codigo_entidade": codigo_entidade,
            "nome_entidade": nome_entidade,

            "ano": ano_exercicio
        }

    # ========================================================
    # SELEÇÃO DO PROGRAMA
    # ========================================================

    programa_nome = st.selectbox(
        "Programa *",
        list(
            mapa_programas.keys()
        ),
        key="acao_programa_selecionado"
    )

    dados_programa = mapa_programas[
        programa_nome
    ]

    programa_id = dados_programa[
        "programa_id"
    ]

    entidade_id = dados_programa[
        "entidade_id"
    ]

    exercicio_id = dados_programa[
        "exercicio_id"
    ]

    # ========================================================
    # MOSTRAR VÍNCULOS AUTOMÁTICOS
    # ========================================================

    st.markdown(
        "### 🔗 Vinculação automática"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.text_input(
            "Entidade",
            value=(
                f"{dados_programa['codigo_entidade']} - "
                f"{dados_programa['nome_entidade']}"
            ),
            disabled=True,
            key="acao_entidade_vinculada"
        )

    with col2:

        st.text_input(
            "Exercício",
            value=str(
                dados_programa[
                    "ano"
                ]
            ),
            disabled=True,
            key="acao_exercicio_vinculado"
        )

    st.text_input(
        "Programa Vinculado",
        value=(
            f"{dados_programa['codigo_programa']} - "
            f"{dados_programa['nome_programa']}"
        ),
        disabled=True,
        key="acao_programa_vinculado"
    )

    # ========================================================
    # PRÓXIMO CÓDIGO AUTOMÁTICO DA AÇÃO
    # ========================================================

    codigos = _sisget_fetch(
        """
        SELECT codigo
        FROM acoes_orcamentarias
        WHERE entidade_id = ?
          AND exercicio_id = ?
          AND programa_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
            exercicio_id,
            programa_id
        )
    )

    usados = set()

    for registro in codigos:

        try:

            usados.add(
                int(
                    str(
                        registro[0]
                    ).strip()
                )
            )

        except (ValueError, TypeError):

            pass

    proximo = 1

    while proximo in usados:

        proximo += 1

    codigo_automatico = str(
        proximo
    ).zfill(4)

    st.markdown("---")

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_acao_orcamentaria_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            st.text_input(
                "Código da Ação",
                value=codigo_automatico,
                disabled=True
            )

        with col2:

            nome = st.text_input(
                "Nome da Ação *",
                max_chars=250,
                placeholder=(
                    "Ex.: Manutenção das "
                    "Atividades Administrativas"
                )
            )

        tipo = st.selectbox(
            "Tipo da Ação *",
            [
                "Atividade",
                "Projeto",
                "Operação Especial"
            ]
        )

        descricao = st.text_area(
            "Descrição",
            height=120
        )

        ativo = st.checkbox(
            "Ação ativa",
            value=True
        )

        salvar = st.form_submit_button(
            "💾 Salvar Ação",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        nome = nome.strip()
        descricao = descricao.strip()

        if not nome:

            st.warning(
                "⚠️ Informe o nome da Ação."
            )

            return

        # ====================================================
        # RECALCULAR O CÓDIGO
        # ====================================================

        codigos = _sisget_fetch(
            """
            SELECT codigo
            FROM acoes_orcamentarias
            WHERE entidade_id = ?
              AND exercicio_id = ?
              AND programa_id = ?
            """,
            (
                entidade_id,
                exercicio_id,
                programa_id
            )
        )

        usados = set()

        for registro in codigos:

            try:

                usados.add(
                    int(
                        str(
                            registro[0]
                        ).strip()
                    )
                )

            except (ValueError, TypeError):

                pass

        proximo = 1

        while proximo in usados:

            proximo += 1

        codigo = str(
            proximo
        ).zfill(4)

        # ====================================================
        # INSERT CORRETO
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO acoes_orcamentarias
            (
                entidade_id,
                exercicio_id,
                programa_id,

                codigo,
                nome,
                tipo,
                descricao,
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
                ?
            )
            """,
            (
                entidade_id,
                exercicio_id,
                programa_id,

                codigo,
                nome,
                tipo,
                descricao or None,
                ativo
            )
        )

        if sucesso:

            st.success(
                f"✅ Ação {codigo} - {nome} "
                "cadastrada com sucesso!"
            )

            st.rerun()

def acao_orcamentaria_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            a.id,
            p.exercicio AS "Exercício",
            p.codigo || ' - ' || p.descricao
                AS "Programa",
            a.codigo AS "Código",
            a.descricao AS "Descrição",
            CASE
                WHEN a.ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM acoes_orcamentarias a

        INNER JOIN programas_orcamentarios p
            ON p.id = a.programa_id

        ORDER BY
            p.exercicio DESC,
            p.codigo,
            a.codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="acoes_orcamentarias",
        coluna_id="id",
        altura=420
    )


def acao_orcamentaria_alterar(acao_id):

    registro = _sisget_fetchone(
        """
        SELECT
            programa_id,
            codigo,
            descricao,
            ativo
        FROM acoes_orcamentarias
        WHERE id = ?
        """,
        (acao_id,)
    )

    if not registro:
        return

    programa_id, codigo_atual, descricao_atual, ativo = registro

    programas = _sisget_fetch(
        """
        SELECT id, exercicio, codigo, descricao
        FROM programas_orcamentarios
        ORDER BY exercicio DESC, codigo
        """
    )

    mapa = {
        f"{exercicio} - {codigo} - {descricao}": id_
        for id_, exercicio, codigo, descricao in programas
    }

    nomes = list(mapa.keys())

    indice = 0

    for i, nome in enumerate(nomes):
        if mapa[nome] == programa_id:
            indice = i
            break

    with st.form(
        f"form_acao_alterar_{acao_id}"
    ):

        programa = st.selectbox(
            "Programa *",
            nomes,
            index=indice
        )

        codigo = st.text_input(
            "Código *",
            value=codigo_atual or ""
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if status:

        _sisget_salvar(
            """
            UPDATE acoes_orcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                acao_id
            )
        )

        st.rerun()

    if salvar:

        if _sisget_salvar(
            """
            UPDATE acoes_orcamentarias
            SET
                programa_id = ?,
                codigo = ?,
                descricao = ?
            WHERE id = ?
            """,
            (
                mapa[programa],
                codigo.strip(),
                descricao.strip(),
                acao_id
            )
        ):

            st.rerun()


def acao_orcamentaria_excluir():

    df = _sisget_dataframe(
        """
        SELECT
            a.id,
            p.codigo AS "Programa",
            a.codigo AS "Código",
            a.descricao AS "Descrição"
        FROM acoes_orcamentarias a
        INNER JOIN programas_orcamentarios p
            ON p.id = a.programa_id
        ORDER BY p.codigo, a.codigo
        """
    )

    if df.empty:
        return

    acao_id = sisget_grid_localizar(
        df=df,
        chave="excluir_acao",
        coluna_id="id",
        altura=420
    )

    if not acao_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_acao_{acao_id}"
    ):

        if _sisget_salvar(
            """
            DELETE FROM acoes_orcamentarias
            WHERE id = ?
            """,
            (acao_id,)
        ):

            st.rerun()

# ============================================================
# NATUREZAS DA DESPESA
# ============================================================

def planejamento_naturezas():

    sisget_tela_principal(
        titulo="Naturezas da Despesa",
        chave="naturezas_despesa",
        func_incluir=natureza_despesa_incluir,
        func_localizar=natureza_despesa_localizar,
        func_alterar=natureza_despesa_alterar,
        func_excluir=natureza_despesa_excluir,
        func_imprimir=natureza_despesa_imprimir,
        icone="💵"
    )


def natureza_despesa_incluir():

    with st.form(
        "form_natureza_incluir",
        clear_on_submit=True
    ):

        codigo = st.text_input(
            "Código *",
            placeholder="Ex.: 3.3.90.30.00"
        )

        descricao = st.text_input(
            "Descrição *",
            placeholder="Ex.: Material de Consumo"
        )

        salvar = st.form_submit_button(
            "💾 Salvar",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:
            st.warning("⚠️ Informe código e descrição.")
            return

        if _sisget_salvar(
            """
            INSERT INTO naturezas_despesa
            (
                codigo,
                descricao,
                ativo
            )
            VALUES (?, ?, TRUE)
            """,
            (
                codigo,
                descricao
            )
        ):

            st.success("✅ Natureza cadastrada.")
            st.rerun()


def natureza_despesa_localizar():

    pesquisa = st.text_input(
        "🔎 Código ou descrição",
        key="buscar_natureza"
    )

    sql = """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM naturezas_despesa
        WHERE 1 = 1
    """

    parametros = []

    if pesquisa.strip():

        termo = f"%{pesquisa.strip()}%"

        sql += """
            AND
            (
                codigo ILIKE ?
                OR descricao ILIKE ?
            )
        """

        parametros.extend([
            termo,
            termo
        ])

    sql += " ORDER BY codigo"

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="naturezas_despesa",
        coluna_id="id",
        altura=420
    )


def natureza_despesa_alterar(natureza_id):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            descricao,
            ativo
        FROM naturezas_despesa
        WHERE id = ?
        """,
        (natureza_id,)
    )

    if not registro:
        return

    codigo_atual, descricao_atual, ativo = registro

    with st.form(
        f"form_natureza_alterar_{natureza_id}"
    ):

        codigo = st.text_input(
            "Código *",
            value=codigo_atual or ""
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if status:

        _sisget_salvar(
            """
            UPDATE naturezas_despesa
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                natureza_id
            )
        )

        st.rerun()

    if salvar:

        if _sisget_salvar(
            """
            UPDATE naturezas_despesa
            SET
                codigo = ?,
                descricao = ?
            WHERE id = ?
            """,
            (
                codigo.strip(),
                descricao.strip(),
                natureza_id
            )
        ):

            st.rerun()


def natureza_despesa_excluir():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição"
        FROM naturezas_despesa
        ORDER BY codigo
        """
    )

    if df.empty:
        return

    natureza_id = sisget_grid_localizar(
        df=df,
        chave="excluir_natureza",
        coluna_id="id",
        altura=420
    )

    if not natureza_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_natureza_{natureza_id}"
    ):

        if _sisget_salvar(
            """
            DELETE FROM naturezas_despesa
            WHERE id = ?
            """,
            (natureza_id,)
        ):

            st.rerun()

# ============================================================
# RELATÓRIO GENÉRICO DAS CLASSIFICAÇÕES
# ============================================================

def sisget_relatorio_classificacao(
    titulo,
    df,
    nome_arquivo
):

    if df.empty:

        st.info(
            "Nenhum registro encontrado."
        )

        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"Total de registros: {len(df)}"
    )

    if st.button(
        "📄 Gerar PDF",
        type="primary",
        use_container_width=True,
        key=f"pdf_{nome_arquivo}"
    ):

        buffer = BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1 * cm,
            bottomMargin=1 * cm
        )

        estilos = getSampleStyleSheet()

        estilo_celula = ParagraphStyle(
            "celula_classificacao",
            parent=estilos["Normal"],
            fontSize=7,
            leading=9
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
                titulo,
                estilos["Heading2"]
            )
        )

        elementos.append(
            Spacer(
                1,
                0.4 * cm
            )
        )

        cabecalho = list(
            df.columns
        )

        dados_tabela = [
            [
                Paragraph(
                    str(coluna),
                    estilo_celula
                )
                for coluna in cabecalho
            ]
        ]

        for _, linha in df.iterrows():

            dados_tabela.append([
                Paragraph(
                    str(
                        linha[coluna]
                        if pd.notna(linha[coluna])
                        else ""
                    ),
                    estilo_celula
                )
                for coluna in cabecalho
            ])

        largura_total = (
            19 * cm
        )

        largura_coluna = (
            largura_total
            /
            len(cabecalho)
        )

        tabela = Table(
            dados_tabela,
            colWidths=[
                largura_coluna
                for _ in cabecalho
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
                    0.4,
                    colors.grey
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
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
            "⬇️ Baixar PDF",
            data=buffer,
            file_name=nome_arquivo,
            mime="application/pdf",
            use_container_width=True,
            key=f"download_{nome_arquivo}"
        )
def natureza_despesa_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM naturezas_despesa
        ORDER BY codigo
        """
    )

    sisget_relatorio_classificacao(
        "Naturezas da Despesa",
        df,
        "naturezas_despesa.pdf"
    )
def acao_orcamentaria_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            p.exercicio AS "Exercício",
            p.codigo || ' - ' || p.descricao AS "Programa",
            a.codigo AS "Código",
            a.descricao AS "Descrição"
        FROM acoes_orcamentarias a
        INNER JOIN programas_orcamentarios p
            ON p.id = a.programa_id
        ORDER BY p.exercicio DESC, p.codigo, a.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Ações Orçamentárias",
        df,
        "acoes_orcamentarias.pdf"
    )
def programa_orcamentario_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            exercicio AS "Exercício",
            codigo AS "Código",
            descricao AS "Descrição"
        FROM programas_orcamentarios
        ORDER BY exercicio DESC, codigo
        """
    )

    sisget_relatorio_classificacao(
        "Programas Orçamentários",
        df,
        "programas_orcamentarios.pdf"
    )
def subfuncao_orcamentaria_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            f.codigo || ' - ' || f.descricao AS "Função",
            s.codigo AS "Código",
            s.descricao AS "Descrição"
        FROM subfuncoes_orcamentarias s
        INNER JOIN funcoes_orcamentarias f
            ON f.id = s.funcao_id
        ORDER BY f.codigo, s.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Subfunções Orçamentárias",
        df,
        "subfuncoes_orcamentarias.pdf"
    )
def cadastro_funcoes_orcamentarias():

    st.markdown(
        "### 🏷️ Funções"
    )

    with st.form(
        "form_funcao_orcamentaria",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            codigo = st.text_input(
                "Código *",
                max_chars=10
            )

        with col2:

            descricao = st.text_input(
                "Descrição *",
                max_chars=200
            )

        salvar = st.form_submit_button(
            "💾 Cadastrar Função",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "⚠️ Informe código e descrição."
            )

        else:

            existe = _sisget_fetchone(
                """
                SELECT id
                FROM funcoes_orcamentarias
                WHERE codigo = ?
                """,
                (
                    codigo,
                )
            )

            if existe:

                st.warning(
                    "⚠️ Esta função já está cadastrada."
                )

            else:

                if _sisget_salvar(
                    """
                    INSERT INTO funcoes_orcamentarias
                    (
                        codigo,
                        descricao,
                        ativo
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        TRUE
                    )
                    """,
                    (
                        codigo,
                        descricao
                    )
                ):

                    st.success(
                        "✅ Função cadastrada."
                    )

                    st.rerun()

    dados = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM funcoes_orcamentarias
        ORDER BY codigo
        """
    )

    if not dados.empty:

        st.dataframe(
            dados,
            use_container_width=True,
            hide_index=True
        )
# ============================================================
# SUBFUNÇÕES ORÇAMENTÁRIAS
# ============================================================

def cadastro_subfuncoes_orcamentarias():

    st.markdown(
        "### 🔹 Subfunções"
    )

    funcoes = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM funcoes_orcamentarias
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    if not funcoes:

        st.warning(
            "⚠️ Cadastre primeiro uma Função."
        )

        return

    mapa_funcoes = {
        f"{codigo} - {descricao}": funcao_id
        for funcao_id, codigo, descricao in funcoes
    }

    with st.form(
        "form_subfuncao_orcamentaria",
        clear_on_submit=True
    ):

        funcao_nome = st.selectbox(
            "Função *",
            list(mapa_funcoes.keys())
        )

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            codigo = st.text_input(
                "Código *",
                max_chars=10
            )

        with col2:

            descricao = st.text_input(
                "Descrição *",
                max_chars=200
            )

        salvar = st.form_submit_button(
            "💾 Cadastrar Subfunção",
            type="primary",
            use_container_width=True
        )

    if salvar:

        funcao_id = mapa_funcoes[
            funcao_nome
        ]

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "⚠️ Informe código e descrição."
            )

        else:

            existe = _sisget_fetchone(
                """
                SELECT id
                FROM subfuncoes_orcamentarias
                WHERE funcao_id = ?
                  AND codigo = ?
                """,
                (
                    funcao_id,
                    codigo
                )
            )

            if existe:

                st.warning(
                    "⚠️ Esta Subfunção já está cadastrada."
                )

            else:

                if _sisget_salvar(
                    """
                    INSERT INTO subfuncoes_orcamentarias
                    (
                        funcao_id,
                        codigo,
                        descricao,
                        ativo
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        ?,
                        TRUE
                    )
                    """,
                    (
                        funcao_id,
                        codigo,
                        descricao
                    )
                ):

                    st.success(
                        "✅ Subfunção cadastrada."
                    )

                    st.rerun()

    dados = _sisget_dataframe(
        """
        SELECT
            s.id,
            f.codigo || ' - ' || f.descricao
                AS "Função",
            s.codigo AS "Código",
            s.descricao AS "Descrição",
            CASE
                WHEN s.ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM subfuncoes_orcamentarias s

        INNER JOIN funcoes_orcamentarias f
            ON f.id = s.funcao_id

        ORDER BY
            f.codigo,
            s.codigo
        """
    )

    if not dados.empty:

        st.dataframe(
            dados,
            use_container_width=True,
            hide_index=True
        )
# ============================================================
# PROGRAMAS ORÇAMENTÁRIOS
# ============================================================

def cadastro_programas_orcamentarios():

    st.markdown(
        "### 📘 Programas"
    )

    with st.form(
        "form_programa_orcamentario",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 1]
        )

        with col1:

            exercicio = st.number_input(
                "Exercício *",
                min_value=2000,
                max_value=2100,
                value=datetime.now().year,
                step=1
            )

        with col2:

            codigo = st.text_input(
                "Código *",
                max_chars=20
            )

        descricao = st.text_input(
            "Descrição *",
            max_chars=250
        )

        salvar = st.form_submit_button(
            "💾 Cadastrar Programa",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "⚠️ Informe código e descrição."
            )

        else:

            existe = _sisget_fetchone(
                """
                SELECT id
                FROM programas_orcamentarios
                WHERE exercicio = ?
                  AND codigo = ?
                """,
                (
                    int(exercicio),
                    codigo
                )
            )

            if existe:

                st.warning(
                    "⚠️ Este Programa já está cadastrado."
                )

            else:

                if _sisget_salvar(
                    """
                    INSERT INTO programas_orcamentarios
                    (
                        exercicio,
                        codigo,
                        descricao,
                        ativo
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        ?,
                        TRUE
                    )
                    """,
                    (
                        int(exercicio),
                        codigo,
                        descricao
                    )
                ):

                    st.success(
                        "✅ Programa cadastrado."
                    )

                    st.rerun()

    dados = _sisget_dataframe(
        """
        SELECT
            id,
            exercicio AS "Exercício",
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM programas_orcamentarios
        ORDER BY
            exercicio DESC,
            codigo
        """
    )

    if not dados.empty:

        st.dataframe(
            dados,
            use_container_width=True,
            hide_index=True
        )
# ============================================================
# AÇÕES ORÇAMENTÁRIAS
# ============================================================

def cadastro_acoes_orcamentarias():

    st.markdown(
        "### 🎯 Ações"
    )

    programas = _sisget_fetch(
        """
        SELECT
            id,
            exercicio,
            codigo,
            descricao
        FROM programas_orcamentarios
        WHERE ativo = TRUE
        ORDER BY
            exercicio DESC,
            codigo
        """
    )

    if not programas:

        st.warning(
            "⚠️ Cadastre primeiro um Programa."
        )

        return

    mapa_programas = {
        (
            f"{exercicio} - "
            f"{codigo} - "
            f"{descricao}"
        ): programa_id
        for (
            programa_id,
            exercicio,
            codigo,
            descricao
        ) in programas
    }

    with st.form(
        "form_acao_orcamentaria",
        clear_on_submit=True
    ):

        programa_nome = st.selectbox(
            "Programa *",
            list(mapa_programas.keys())
        )

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            codigo = st.text_input(
                "Código *",
                max_chars=20
            )

        with col2:

            descricao = st.text_input(
                "Descrição *",
                max_chars=250
            )

        salvar = st.form_submit_button(
            "💾 Cadastrar Ação",
            type="primary",
            use_container_width=True
        )

    if salvar:

        programa_id = mapa_programas[
            programa_nome
        ]

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "⚠️ Informe código e descrição."
            )

        else:

            existe = _sisget_fetchone(
                """
                SELECT id
                FROM acoes_orcamentarias
                WHERE programa_id = ?
                  AND codigo = ?
                """,
                (
                    programa_id,
                    codigo
                )
            )

            if existe:

                st.warning(
                    "⚠️ Esta Ação já está cadastrada."
                )

            else:

                if _sisget_salvar(
                    """
                    INSERT INTO acoes_orcamentarias
                    (
                        programa_id,
                        codigo,
                        descricao,
                        ativo
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        ?,
                        TRUE
                    )
                    """,
                    (
                        programa_id,
                        codigo,
                        descricao
                    )
                ):

                    st.success(
                        "✅ Ação cadastrada."
                    )

                    st.rerun()

    dados = _sisget_dataframe(
        """
        SELECT
            a.id,

            p.exercicio
                AS "Exercício",

            p.codigo || ' - ' || p.descricao
                AS "Programa",

            a.codigo
                AS "Código",

            a.descricao
                AS "Descrição",

            CASE
                WHEN a.ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"

        FROM acoes_orcamentarias a

        INNER JOIN programas_orcamentarios p
            ON p.id = a.programa_id

        ORDER BY
            p.exercicio DESC,
            p.codigo,
            a.codigo
        """
    )

    if not dados.empty:

        st.dataframe(
            dados,
            use_container_width=True,
            hide_index=True
        )
# ============================================================
# NATUREZAS DA DESPESA
# ============================================================

def cadastro_naturezas_despesa():

    st.markdown(
        "### 💵 Naturezas da Despesa"
    )

    with st.form(
        "form_natureza_despesa",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        with col1:

            codigo = st.text_input(
                "Código *",
                max_chars=30
            )

        with col2:

            descricao = st.text_input(
                "Descrição *",
                max_chars=250
            )

        salvar = st.form_submit_button(
            "💾 Cadastrar Natureza",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo or not descricao:

            st.warning(
                "⚠️ Informe código e descrição."
            )

        else:

            existe = _sisget_fetchone(
                """
                SELECT id
                FROM naturezas_despesa
                WHERE codigo = ?
                """,
                (
                    codigo,
                )
            )

            if existe:

                st.warning(
                    "⚠️ Esta Natureza já está cadastrada."
                )

            else:

                if _sisget_salvar(
                    """
                    INSERT INTO naturezas_despesa
                    (
                        codigo,
                        descricao,
                        ativo
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        TRUE
                    )
                    """,
                    (
                        codigo,
                        descricao
                    )
                ):

                    st.success(
                        "✅ Natureza da Despesa cadastrada."
                    )

                    st.rerun()

    dados = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM naturezas_despesa
        ORDER BY codigo
        """
    )

    if not dados.empty:

        st.dataframe(
            dados,
            use_container_width=True,
            hide_index=True
        )
# ============================================================
# PRÓXIMO CÓDIGO DO PROGRAMA
# ============================================================

def sisget_proximo_codigo_programa(exercicio):

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM programas_orcamentarios
        WHERE exercicio = ?
        ORDER BY codigo
        """,
        (
            int(exercicio),
        )
    )

    numeros_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            numeros_usados.add(
                int(codigo)
            )

        except (ValueError, TypeError):

            pass

    proximo = 1

    while proximo in numeros_usados:

        proximo += 1

    return str(proximo)

def planejamento_saldos():

    st.subheader(
        "💰 Saldos Orçamentários"
    )

    st.info(
        "Aqui será exibido o saldo disponível de cada "
        "Ficha Orçamentária."
    )


# ============================================================
# RESERVAS ORÇAMENTÁRIAS
# ============================================================

def planejamento_reservas():

    st.subheader(
        "🔒 Reservas Orçamentárias"
    )

    st.info(
        "Aqui serão controladas as reservas realizadas "
        "a partir das Solicitações."
    )


# ============================================================
# CONSULTA ORÇAMENTÁRIA
# ============================================================

def planejamento_consulta_orcamentaria():

    st.subheader(
        "🔎 Consulta Orçamentária"
    )

    st.info(
        "Aqui será possível consultar fichas, fontes, "
        "valores e saldo disponível."
    )


# ============================================================
# RELATÓRIOS
# ============================================================

def planejamento_relatorios():

    st.subheader(
        "🖨️ Relatórios do Planejamento"
    )

    st.info(
        "Aqui serão gerados os relatórios orçamentários."
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
