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
# CABEÇALHO DE TELA
# ============================================================

def sisget_cabecalho_tela(
    titulo,
    voltar=None
):

    c1, c2 = st.columns(
        [6, 1]
    )


    with c1:

        st.subheader(
            titulo
        )


    if voltar is not None:

        with c2:

            if st.button(
                "⬅️ Voltar",
                use_container_width=True,
                key=f"voltar_{titulo}_{voltar}"
            ):

                voltar()


    st.markdown("---")


# ============================================================
# GRID PADRÃO DO SISGET
#
# DUPLO CLIQUE = ABRIR PARA ALTERAÇÃO
# ============================================================

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

def sisget_tela_principal(

    titulo,

    chave,

    func_incluir,

    func_localizar,

    func_alterar,

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

    if chave_tela not in (
        st.session_state
    ):

        st.session_state[
            chave_tela
        ] = "principal"


    if chave_id not in (
        st.session_state
    ):

        st.session_state[
            chave_id
        ] = None


    tela = (
        st.session_state[
            chave_tela
        ]
    )


    # ========================================================
    # TÍTULO
    # ========================================================

    st.title(
        f"{icone} {titulo}"
    )


    # ========================================================
    # PRINCIPAL
    # ========================================================

    if tela == "principal":

        st.markdown("---")


        col1, col2, col3 = (
            st.columns(3)
        )


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
        # IMPRIMIR
        # ====================================================

        with col3:

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

            voltar=lambda:
                sisget_voltar_principal(
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

            voltar=lambda:
                sisget_voltar_principal(
                    chave
                )
        )


        st.caption(
            "Dê duplo clique em um registro para alterar."
        )


        registro_id = (
            func_localizar()
        )


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

        registro_id = (
            st.session_state.get(
                chave_id
            )
        )


        if not registro_id:

            st.session_state[
                chave_tela
            ] = "localizar"

            st.rerun()


        sisget_cabecalho_tela(

            "✏️ Alterar",

            voltar=lambda:
                sisget_voltar_localizar(
                    chave
                )
        )


        func_alterar(
            registro_id
        )


    # ========================================================
    # IMPRIMIR
    # ========================================================

    elif tela == "imprimir":

        sisget_cabecalho_tela(

            "🖨️ Imprimir",

            voltar=lambda:
                sisget_voltar_principal(
                    chave
                )
        )


        if func_imprimir:

            func_imprimir()

        else:

            st.info(
                "Nenhum relatório configurado."
            )


# ============================================================
# MÓDULO AINDA NÃO DESENVOLVIDO
# ============================================================

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
# INÍCIO
# ============================================================

def tela_inicio():

    st.title(
        "🏛️ SISGET"
    )


    st.subheader(
        "Sistema Integrado de Gestão Pública"
    )


    st.markdown("---")


    c1, c2, c3, c4 = (
        st.columns(4)
    )


    c1.metric(
        "Sistema",
        "SISGET"
    )


    c2.metric(
        "Banco",
        "PostgreSQL"
    )


    c3.metric(
        "Servidor",
        "Supabase"
    )


    c4.metric(
        "Situação",
        "Online"
        if testar_conexao()
        else "Offline"
    )


    st.markdown("---")


    st.info(
        "Selecione um módulo no menu lateral."
    )


# ============================================================
# CADASTRO BÁSICO
# ============================================================

def cadastro_basico():

    st.title(
        "🏛️ Cadastro Básico"
    )


    opcao = st.sidebar.radio(

        "Cadastro Básico",

        [
            "🏢 Entidades",
            "🏛️ Órgãos",
            "💼 Unidades Orçamentárias",
            "🏬 Unidades Administrativas",
            "🧩 Setores",
            "📅 Exercícios",
            "🌳 Organograma"
        ],

        key="menu_cadastro_basico"
    )


    if opcao == "🏢 Entidades":

        cadastro_entidades()


    elif opcao == "🏛️ Órgãos":

        cadastro_orgaos()


    elif opcao == "💼 Unidades Orçamentárias":

        cadastro_unidades_orcamentarias()


    elif opcao == "🏬 Unidades Administrativas":

        cadastro_unidades_administrativas()


    elif opcao == "🧩 Setores":

        cadastro_setores()


    elif opcao == "📅 Exercícios":

        cadastro_exercicios()


    elif opcao == "🌳 Organograma":

        organograma_sisget()


# ============================================================
# PLACEHOLDERS TEMPORÁRIOS
#
# VAMOS SUBSTITUIR UM POR UM
# ============================================================

def cadastro_entidades():

    modulo_em_desenvolvimento(
        "Cadastro de Entidades",
        "🏢"
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

def modulo_assistente():

    modulo_em_desenvolvimento(
        "Assistente SISGET",
        "🤖"
    )


# ============================================================
# LOGIN
# TEMPORÁRIO
#
# SE VOCÊ JÁ TEM SEU LOGIN,
# MANTENHA O SEU.
# ============================================================

def login():

    st.title(
        "🏛️ SISGET"
    )


    st.subheader(
        "Acesso ao Sistema"
    )


    usuario = st.text_input(
        "Usuário"
    )


    senha = st.text_input(
        "Senha",
        type="password"
    )


    if st.button(
        "🔐 Entrar",
        type="primary",
        use_container_width=True
    ):

        linha = _sisget_fetchone(
            """
            SELECT
                id,
                usuario,
                funcao
            FROM usuarios
            WHERE usuario = ?
              AND senha = ?
              AND ativo = TRUE
            """,
            (
                usuario,
                senha
            )
        )


        if linha:

            st.session_state[
                "usuario_id"
            ] = linha[0]


            st.session_state[
                "usuario_logado"
            ] = linha[1]


            st.session_state[
                "funcao_usuario"
            ] = linha[2]


            st.rerun()


        else:

            st.error(
                "Usuário ou senha inválidos."
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
