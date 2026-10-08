# ============================================================
# IMPORTS
# ============================================================
import requests
import re
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
        sslmode="require",

        # Evita conexão morta ficar presa por muito tempo
        connect_timeout=10,

        # Mantém conexão viva
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )


# ============================================================
# PEGAR / RENOVAR CONEXÃO
# ============================================================

def sisget_obter_conexao():

    global conn
    global cursor

    precisa_reconectar = False

    try:

        if conn is None:

            precisa_reconectar = True

        elif conn.closed != 0:

            precisa_reconectar = True

        else:

            with conn.cursor() as cursor_teste:

                cursor_teste.execute(
                    "SELECT 1"
                )

                cursor_teste.fetchone()

    except Exception:

        precisa_reconectar = True


    if precisa_reconectar:

        try:

            conectar_banco.clear()

        except Exception:

            pass


        conn = conectar_banco()

        cursor = CursorSISGET(
            conn.cursor()
        )


    return conn, cursor


# ============================================================
# INICIALIZAR CONEXÃO
# ============================================================

conn = None
cursor = None


sisget_obter_conexao()


# ============================================================
# ROLLBACK SEGURO
# ============================================================

def sisget_rollback_seguro():

    global conn

    try:

        if (
            conn is not None
            and conn.closed == 0
        ):

            conn.rollback()

    except Exception:

        pass


# ============================================================
# RECONEXÃO FORÇADA
# ============================================================

def sisget_reconectar():

    global conn
    global cursor

    try:

        if cursor is not None:

            cursor.close()

    except Exception:

        pass


    try:

        if (
            conn is not None
            and conn.closed == 0
        ):

            conn.close()

    except Exception:

        pass


    try:

        conectar_banco.clear()

    except Exception:

        pass


    conn = conectar_banco()

    cursor = CursorSISGET(
        conn.cursor()
    )


# ============================================================
# TESTAR CONEXÃO
# ============================================================

def testar_conexao():

    try:

        conexao, _ = sisget_obter_conexao()

        with conexao.cursor() as cursor_teste:

            cursor_teste.execute(
                "SELECT 1"
            )

            resultado = cursor_teste.fetchone()


        return resultado is not None


    except Exception:

        return False


# ============================================================
# FETCH
# ============================================================

def _sisget_fetch(
    sql,
    params=()
):

    global conn
    global cursor

    # ========================================================
    # PRIMEIRA TENTATIVA
    # ========================================================

    try:

        sisget_obter_conexao()

        cursor.execute(
            sql,
            params
        )

        return cursor.fetchall()


    except (
        psycopg2.InterfaceError,
        psycopg2.OperationalError
    ):

        # ====================================================
        # CONEXÃO CAIU
        # RECONECTA E TENTA MAIS UMA VEZ
        # ====================================================

        try:

            sisget_reconectar()

            cursor.execute(
                sql,
                params
            )

            return cursor.fetchall()

        except Exception as erro:

            sisget_rollback_seguro()

            st.error(
                f"❌ Erro ao consultar banco: {erro}"
            )

            return []


    except Exception as erro:

        sisget_rollback_seguro()

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

    global conn
    global cursor

    try:

        sisget_obter_conexao()

        cursor.execute(
            sql,
            params
        )

        return cursor.fetchone()


    except (
        psycopg2.InterfaceError,
        psycopg2.OperationalError
    ):

        try:

            sisget_reconectar()

            cursor.execute(
                sql,
                params
            )

            return cursor.fetchone()

        except Exception as erro:

            sisget_rollback_seguro()

            st.error(
                f"❌ Erro ao consultar banco: {erro}"
            )

            return None


    except Exception as erro:

        sisget_rollback_seguro()

        st.error(
            f"❌ Erro ao consultar banco: {erro}"
        )

        return None


# ============================================================
# SALVAR
# ============================================================

def _sisget_salvar(
    sql,
    params=()
):

    global conn
    global cursor

    try:

        sisget_obter_conexao()

        cursor.execute(
            sql,
            params
        )

        conn.commit()

        return True


    except (
        psycopg2.InterfaceError,
        psycopg2.OperationalError
    ):

        try:

            sisget_reconectar()

            cursor.execute(
                sql,
                params
            )

            conn.commit()

            return True

        except Exception as erro:

            sisget_rollback_seguro()

            st.error(
                f"❌ Não foi possível salvar: {erro}"
            )

            return False


    except Exception as erro:

        sisget_rollback_seguro()

        st.error(
            f"❌ Não foi possível salvar: {erro}"
        )

        return False


# ============================================================
# SALVAR COM RETORNO
# ============================================================

def _sisget_salvar_retorno(
    sql,
    params=()
):

    global conn
    global cursor

    try:

        sisget_obter_conexao()

        cursor.execute(
            sql,
            params
        )

        resultado = cursor.fetchone()

        conn.commit()

        if resultado:

            # Para RETURNING id
            if len(resultado) == 1:

                return resultado[0]

        return resultado


    except (
        psycopg2.InterfaceError,
        psycopg2.OperationalError
    ):

        try:

            sisget_reconectar()

            cursor.execute(
                sql,
                params
            )

            resultado = cursor.fetchone()

            conn.commit()

            if resultado:

                if len(resultado) == 1:

                    return resultado[0]

            return resultado

        except Exception as erro:

            sisget_rollback_seguro()

            st.error(
                f"❌ Não foi possível salvar: {erro}"
            )

            return None


    except Exception as erro:

        sisget_rollback_seguro()

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

    global conn
    global cursor

    try:

        sisget_obter_conexao()

        cursor.execute(
            sql,
            params
        )

        dados = cursor.fetchall()

        colunas = [
            descricao[0]
            for descricao
            in cursor.description
        ]

        return pd.DataFrame(
            dados,
            columns=colunas
        )


    except (
        psycopg2.InterfaceError,
        psycopg2.OperationalError
    ):

        try:

            sisget_reconectar()

            cursor.execute(
                sql,
                params
            )

            dados = cursor.fetchall()

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

            sisget_rollback_seguro()

            st.error(
                f"❌ Erro ao carregar dados: {erro}"
            )

            return pd.DataFrame()


    except Exception as erro:

        sisget_rollback_seguro()

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

def sisget_tela_principal(
    titulo,
    chave,
    func_incluir,
    func_localizar,
    func_alterar,
    func_excluir=None,
    func_imprimir=None,
    icone="📋",
    botoes_extras=None
):

    chave_tela = (
        f"sisget_tela_{chave}"
    )

    chave_id = (
        f"sisget_id_{chave}"
    )

    # ========================================================
    # ESTADO INICIAL
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
    # TELA PRINCIPAL
    # ========================================================

    if tela == "principal":

        st.title(
            f"{icone} {titulo}"
        )

        st.markdown("---")

        # ====================================================
        # BOTÕES PADRÃO
        # ====================================================

        botoes = [
            (
                "➕ Incluir",
                "incluir"
            ),
            (
                "🔎 Localizar",
                "localizar"
            )
        ]

        # ====================================================
        # BOTÕES EXTRAS
        # ====================================================

        if botoes_extras:

            for botao in botoes_extras:

                botoes.append(
                    (
                        botao["titulo"],
                        botao["tela"]
                    )
                )

        # ====================================================
        # EXCLUIR
        # ====================================================

        if func_excluir:

            botoes.append(
                (
                    "🗑️ Excluir",
                    "excluir"
                )
            )

        # ====================================================
        # IMPRIMIR
        # ====================================================

        if func_imprimir:

            botoes.append(
                (
                    "🖨️ Imprimir",
                    "imprimir"
                )
            )

        # ====================================================
        # EXIBIR BOTÕES
        # 3 POR LINHA
        # ====================================================

        quantidade = len(
            botoes
        )

        indice = 0

        while indice < quantidade:

            linha = botoes[
                indice:
                indice + 3
            ]

            colunas = st.columns(
                len(linha)
            )

            for posicao, (
                titulo_botao,
                tela_botao
            ) in enumerate(linha):

                with colunas[
                    posicao
                ]:

                    if st.button(
                        titulo_botao,
                        use_container_width=True,
                        key=(
                            f"sisget_"
                            f"{chave}_"
                            f"{tela_botao}"
                        ),
                        type=(
                            "primary"
                            if tela_botao == "incluir"
                            else "secondary"
                        )
                    ):

                        st.session_state[
                            chave_id
                        ] = None

                        st.session_state[
                            chave_tela
                        ] = tela_botao

                        st.rerun()

            indice += 3

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
    # TELAS EXTRAS
    # ========================================================

    elif botoes_extras:

        encontrou = False

        for botao in botoes_extras:

            if tela == botao[
                "tela"
            ]:

                encontrou = True

                sisget_cabecalho_tela(
                    botao["titulo"],
                    voltar=lambda: sisget_voltar_principal(
                        chave
                    ),
                    chave=(
                        f"{chave}_"
                        f"{botao['tela']}"
                    )
                )

                botao[
                    "funcao"
                ]()

                break

        if not encontrou:

            st.session_state[
                chave_tela
            ] = "principal"

            st.rerun()

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

def sisget_proximo_numero_solicitacao(
    tipo_solicitacao=None,
    exercicio=None
):

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    if exercicio is None:

        exercicio = datetime.now().year

    # ========================================================
    # CONSULTA
    # ========================================================

    sql = """
        SELECT
            COALESCE(
                MAX(
                    CAST(numero AS BIGINT)
                ),
                0
            )
        FROM solicitacoes
        WHERE numero IS NOT NULL
          AND TRIM(numero::TEXT) ~ '^[0-9]+$'
    """

    parametros = []

    # ========================================================
    # FILTRO POR TIPO
    # ========================================================

    if tipo_solicitacao is not None:

        sql += """
            AND tipo_solicitacao = ?
        """

        parametros.append(
            tipo_solicitacao
        )

        sql += """
            AND exercicio = ?
        """

        parametros.append(
            exercicio
        )

    # ========================================================
    # EXECUTAR CONSULTA
    # ========================================================

    registro = _sisget_fetchone(
        sql,
        tuple(parametros)
    )

    # ========================================================
    # VALIDAR RESULTADO
    # ========================================================

    if registro is None:

        st.error(
            "❌ Não foi possível consultar "
            "o próximo número da solicitação."
        )

        return None

    # ========================================================
    # RETORNAR PRÓXIMO NÚMERO
    # ========================================================

    return int(
        registro[0] or 0
    ) + 1

def solicitacao_incluir():

    from datetime import datetime

    st.subheader("📝 Nova Solicitação")

    entidade_sessao = st.session_state.get("entidade_id")

    if entidade_sessao is None:
        st.error("❌ Entidade não identificada no usuário logado.")
        return

    reset = st.session_state.setdefault("sisget_solicitacao_reset", 0)
    chave_itens = f"sisget_sol_itens_{reset}"
    st.session_state.setdefault(chave_itens, [])

    numero = sisget_proximo_numero_solicitacao()

    if numero is None:

        return

    st.info(f"🔢 Solicitação nº {str(numero).zfill(6)}")

    # ========================================================
    # UNIDADE ADMINISTRATIVA + VÍNCULOS DO PLANEJAMENTO
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            a.id, a.codigo, a.nome,
            u.id, u.codigo, u.nome,
            e.id, e.codigo, e.nome,
            o.id, o.codigo, o.nome
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
          AND a.entidade_id = ?
        ORDER BY o.codigo, u.codigo, a.codigo
        """,
        (entidade_sessao,)
    )

    if not unidades:
        st.warning("⚠️ Nenhuma Unidade Administrativa ativa para esta entidade.")
        return

    mapa_unidades = {}

    for (ua_id, ua_cod, ua_nome,
         uo_id, uo_cod, uo_nome,
         ent_id, ent_cod, ent_nome,
         org_id, org_cod, org_nome) in unidades:

        rotulo = (
            f"{org_cod} - {org_nome} → "
            f"{ent_cod} - {ent_nome} → "
            f"{uo_cod} - {uo_nome} → "
            f"{ua_cod} - {ua_nome}"
        )
        mapa_unidades[rotulo] = (org_id, ent_id, uo_id, ua_id)

    unidade_nome = st.selectbox(
        "Unidade Administrativa *",
        list(mapa_unidades),
        key=f"sisget_sol_unidade_{reset}"
    )
    orgao_id, entidade_id, uo_id, ua_id = mapa_unidades[unidade_nome]

    # Ao mudar a unidade, o combo de setores e as fichas são atualizados.

    # ========================================================
    # SETORES DO PLANEJAMENTO / CADASTRO BÁSICO
    # ========================================================

    setores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            nome
        FROM setores
        WHERE entidade_id = ?
          AND unidade_administrativa_id = ?
          AND ativo = TRUE
        ORDER BY codigo, nome
        """,
        (
            entidade_id,
            ua_id
        )
    )

    if not setores:

        st.warning(
            "⚠️ Cadastre um Setor ativo vinculado à "
            "Unidade Administrativa selecionada antes "
            "de registrar a solicitação."
        )

        return

    mapa_setores = {
        f"{codigo} - {nome}": setor_id
        for setor_id, codigo, nome in setores
    }

    setor_nome = st.selectbox(
        "Setor solicitante *",
        list(mapa_setores.keys()),
        key=f"sisget_sol_setor_{reset}_{ua_id}"
    )

    setor_id = mapa_setores[
        setor_nome
    ]

    # ========================================================
    # DOTAÇÕES = FICHAS ORÇAMENTÁRIAS DO PLANEJAMENTO
    # ========================================================

    ano = datetime.now().year

    fichas = _sisget_fetch(
        """
        SELECT
            id, numero_ficha, descricao, natureza_despesa,
            valor_atual, valor_reservado
        FROM fichas_orcamentarias
        WHERE entidade_id = ?
          AND unidade_orcamentaria_id = ?
          AND exercicio = ?
          AND ativo = TRUE
        ORDER BY numero_ficha
        """,
        (entidade_id, uo_id, ano)
    )

    mapa_fichas = {}

    for ficha_id, numero_ficha, descricao_ficha, natureza, atual, reservado in fichas:
        # O número da dotação é o número da ficha orçamentária.
        rotulo = (
            f"Ficha {numero_ficha} | "
            f"{descricao_ficha or 'Sem descrição'} | "
            f"Natureza: {natureza or '-'}"
        )
        mapa_fichas[rotulo] = ficha_id

    st.markdown("### 💰 Dotações Orçamentárias")

    if not mapa_fichas:
        st.warning(
            "⚠️ Não há fichas orçamentárias ativas para esta Unidade "
            f"Orçamentária no exercício {ano}."
        )

    fichas_escolhidas = st.multiselect(
        "Números das Dotações / Fichas",
        options=list(mapa_fichas),
        key=f"sisget_sol_fichas_{reset}_{uo_id}"
    )

    # ========================================================
    # DADOS DA SOLICITAÇÃO
    # ========================================================

    st.markdown("### 📝 Dados da Solicitação")

    col1, col2 = st.columns(2)
    tipo = col1.selectbox(
        "Tipo de Solicitação *",
        ["Aquisição de Material", "Contratação de Serviço",
         "Obra / Serviço de Engenharia", "Tecnologia da Informação",
         "Manutenção", "Outros"],
        key=f"sisget_sol_tipo_{reset}"
    )
    prioridade = col2.selectbox(
        "Prioridade *",
        ["Baixa", "Normal", "Alta", "Urgente"],
        index=1,
        key=f"sisget_sol_prioridade_{reset}"
    )

    titulo = st.text_input(
        "Objeto / Título da Solicitação *",
        max_chars=200,
        key=f"sisget_sol_titulo_{reset}"
    )
    descricao = st.text_area(
        "Descrição",
        height=120,
        key=f"sisget_sol_descricao_{reset}"
    )
    justificativa = st.text_area(
        "Justificativa *",
        height=120,
        key=f"sisget_sol_justificativa_{reset}"
    )
    solicitante = st.text_input(
        "Solicitante",
        value=st.session_state.get("usuario_logado", ""),
        key=f"sisget_sol_solicitante_{reset}"
    )
    data_solicitacao = st.date_input(
        "Data da Solicitação",
        value=datetime.now().date(),
        key=f"sisget_sol_data_{reset}"
    )

    # ========================================================
    # PRODUTOS CADASTRADOS + CARRINHO DE ITENS
    # ========================================================

    st.markdown("### 📦 Itens da Solicitação")

    produtos = _sisget_fetch(
        """
        SELECT id, codigo, COALESCE(NULLIF(produto, ''), descricao)
        FROM produtos
        WHERE entidade_id = ?
          AND ativo = TRUE
        ORDER BY codigo
        """,
        (entidade_id,)
    )

    mapa_produtos = {
        f"{codigo} - {nome}": produto_id
        for produto_id, codigo, nome in produtos
    }

    if not mapa_produtos:
        st.warning("⚠️ Cadastre produtos ativos antes de adicionar itens.")
    else:
        with st.form(f"sisget_sol_form_item_{reset}", clear_on_submit=True):
            produto_nome = st.selectbox("Produto *", list(mapa_produtos))
            ic1, ic2 = st.columns(2)
            quantidade = ic1.number_input(
                "Quantidade *", min_value=0.000001,
                value=1.0, format="%.6f"
            )
            valor_unitario = ic2.number_input(
                "Valor estimado unitário (R$)", min_value=0.0,
                value=0.0, format="%.2f"
            )
            observacao_item = st.text_input("Observação do item")
            adicionar = st.form_submit_button(
                "➕ Adicionar Item", use_container_width=True
            )

        if adicionar:
            st.session_state[chave_itens].append({
                "produto_id": mapa_produtos[produto_nome],
                "produto": produto_nome,
                "quantidade": float(quantidade),
                "valor_unitario": float(valor_unitario),
                "observacao": observacao_item.strip() or None
            })
            st.rerun()

    itens = st.session_state[chave_itens]

    if itens:
        for indice, item in enumerate(itens):
            col_i, col_q, col_x = st.columns([6, 2, 1])
            col_i.write(item["produto"])
            col_q.write(
                f'{item["quantidade"]:,.2f} × R$ {item["valor_unitario"]:,.2f}'
            )
            if col_x.button("🗑️", key=f"sisget_sol_remover_{reset}_{indice}"):
                itens.pop(indice)
                st.rerun()

        total = sum(
            item["quantidade"] * item["valor_unitario"]
            for item in itens
        )
        st.metric("Valor estimado total", f"R$ {total:,.2f}")
    else:
        st.info("Adicione pelo menos um item à solicitação.")

    st.markdown("---")

    salvar = st.button(
        "💾 Registrar Solicitação",
        type="primary",
        use_container_width=True,
        key=f"sisget_sol_salvar_{reset}"
    )

    # ========================================================
    # GRAVAÇÃO ATÔMICA DA SOLICITAÇÃO / FICHAS / ITENS
    # ========================================================
    # IMPORTANTE: usamos cursor/conn diretamente aqui para que
    # tudo seja confirmado em um único commit. Não chame
    # _sisget_salvar() para cada item: ela confirma separadamente.

    if salvar:
        if not titulo.strip():
            st.warning("⚠️ Informe o objeto da solicitação.")
            return

        if not justificativa.strip():
            st.warning("⚠️ Informe a justificativa.")
            return

        if not itens:
            st.warning("⚠️ Adicione pelo menos um item.")
            return

        if not fichas_escolhidas:
            st.warning("⚠️ Selecione pelo menos uma dotação/ficha orçamentária.")
            return

        numero = sisget_proximo_numero_solicitacao()

        if numero is None:

            return

        try:
            cursor.execute(
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
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                RETURNING id
                """,
                (
                    numero,
                    orgao_id,
                    entidade_id,
                    uo_id,
                    ua_id,
                    setor_id,
                    tipo,
                    prioridade,
                    titulo.strip(),
                    descricao.strip() or None,
                    justificativa.strip(),
                    solicitante.strip() or None,
                    "Aberta",
                    data_solicitacao
                )
            )

            solicitacao_id = cursor.fetchone()[0]

            for ficha_nome in fichas_escolhidas:
                cursor.execute(
                    """
                    INSERT INTO solicitacoes_fichas_orcamentarias
                    (
                        solicitacao_id,
                        ficha_orcamentaria_id
                    )
                    VALUES (?, ?)
                    """,
                    (solicitacao_id, mapa_fichas[ficha_nome])
                )

            for item in itens:
                valor_total = (
                    item["quantidade"] * item["valor_unitario"]
                )
                cursor.execute(
                    """
                    INSERT INTO solicitacoes_itens
                    (
                        solicitacao_id,
                        produto_id,
                        quantidade_solicitada,
                        valor_estimado_unitario,
                        valor_estimado_total,
                        observacao,
                        ativo
                    )
                    VALUES (?, ?, ?, ?, ?, ?, TRUE)
                    """,
                    (
                        solicitacao_id,
                        item["produto_id"],
                        item["quantidade"],
                        item["valor_unitario"],
                        valor_total,
                        item["observacao"]
                    )
                )

            conn.commit()

        except Exception as erro:
            try:
                conn.rollback()
            except Exception:
                pass
            st.error(f"❌ Não foi possível salvar a solicitação: {erro}")
            return

        st.session_state["sisget_mensagem_solicitacao"] = (
            f"✅ Solicitação nº {str(numero).zfill(6)} "
            "registrada com sucesso!"
        )
        st.session_state.pop(chave_itens, None)
        st.session_state["sisget_solicitacao_reset"] += 1
        st.rerun()

    # ========================================================
    # MENSAGEM ABAIXO DO FORMULÁRIO, APÓS RERUN
    # ========================================================

    if "sisget_mensagem_solicitacao" in st.session_state:
        st.success(st.session_state.pop("sisget_mensagem_solicitacao"))

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
def modulo_planejamento():

    st.title("📐 Planejamento Orçamentário")

    st.caption(
        "Selecione o módulo de Planejamento Orçamentário "
        "que deseja acessar."
    )

    st.divider()

    modulo = st.selectbox(
        "Módulo *",
        options=[
            "Selecione...",
            "🧾 Funções Orçamentárias",
            "🧾 Subfunções Orçamentárias",
            "📘 Programas",
            "🎯 Ações",
            "💰 Naturezas da Despesa",
            "💧 Fontes de Recursos",
            "📄 Fichas Orçamentárias"
        ],
        key="sisget_planejamento_modulo"
    )

    st.divider()

    if modulo == "Selecione...":

        st.info(
            "Selecione um módulo acima para continuar."
        )

        return

    elif modulo == "🧾 Funções Orçamentárias":

        planejamento_funcoes()

    elif modulo == "🧾 Subfunções Orçamentárias":

        planejamento_subfuncoes_orcamentarias()

    elif modulo == "📘 Programas":

        planejamento_programas_orcamentarios()

    elif modulo == "🎯 Ações":

        planejamento_acoes_orcamentarias()

    elif modulo == "💰 Naturezas da Despesa":

        planejamento_naturezas()

    elif modulo == "💧 Fontes de Recursos":

        planejamento_fontes_recursos()

    elif modulo == "📄 Fichas Orçamentárias":

        planejamento_fichas_orcamentarias()

def sisget_proximo_codigo_ficha_extra(
    exercicio,
    entidade_id
):

    registros = _sisget_fetch(
        """
        SELECT codigo
        FROM fichas_extraorcamentarias
        WHERE exercicio = ?
          AND entidade_id = ?
        ORDER BY codigo
        """,
        (
            int(exercicio),
            entidade_id
        )
    )

    numeros_utilizados = set()

    for registro in registros:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            numeros_utilizados.add(
                int(codigo)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    proximo = 1

    while proximo in numeros_utilizados:

        proximo += 1

    return str(
        proximo
    ).zfill(3)
def ficha_orcamentaria_incluir():

  # ========================================================
    # CONTROLE DE RESET DA TELA
    # ========================================================

    if "sisget_ficha_reset" not in st.session_state:
        st.session_state["sisget_ficha_reset"] = 0

    reset_ficha = st.session_state["sisget_ficha_reset"]

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.subheader(
        "📄 Cadastro de Ficha de Despesa"
    )

    st.caption(
        "Selecione a estrutura orçamentária "
        "e informe os dados da ficha."
    )

    # ========================================================
    # FUNÇÃO AUXILIAR DOS SELECTBOX
    # ========================================================

    def selecionar(
        titulo,
        registros,
        chave,
        mensagem="Selecione",
        desabilitado=False
    ):

        mapa = {}

        for registro in registros:

            registro_id = int(
                registro[0]
            )

            codigo = str(
                registro[1]
                if registro[1] is not None
                else ""
            )

            descricao = str(
                registro[2]
                if registro[2] is not None
                else ""
            )

            mapa[registro_id] = {
                "codigo": codigo,
                "descricao": descricao,
                "texto": (
                    f"{codigo} | {descricao}"
                )
            }

        selecionado = st.selectbox(
            titulo,
            options=[
                None
            ] + list(
                mapa.keys()
            ),
            format_func=lambda valor: (
                mensagem
                if valor is None
                else mapa[valor]["texto"]
            ),
            key=chave,
            disabled=(
                desabilitado
                or not bool(mapa)
            )
        )

        if selecionado is None:

            return (
                None,
                None,
                None
            )

        return (
            selecionado,
            mapa[selecionado]["codigo"],
            mapa[selecionado]["texto"]
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
        WHERE ativo = TRUE
        ORDER BY codigo, nome
        """
    )

    if not orgaos:

        st.warning(
            "Nenhum Órgão ativo cadastrado."
        )

        return

    # ========================================================
    # ESTRUTURA ADMINISTRATIVA
    # ========================================================

    with st.container(
        border=True
    ):

        st.markdown(
            "### 🏛️ Estrutura Administrativa"
        )

        col1, col2, col3 = st.columns(
            3
        )

        # ====================================================
        # ÓRGÃO
        # ====================================================

        with col1:

            (
                orgao_id,
                _,
                orgao_texto
            ) = selecionar(
                "Órgão *",
                orgaos,
                (
                    f"sisget_ficha_orgao_"
                    f"{reset_ficha}"
                ),
                "Selecione o Órgão"
            )

        # ====================================================
        # ENTIDADE
        # ====================================================

        entidades = []

        if orgao_id is not None:

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
                (
                    orgao_id,
                )
            )

        with col2:

            (
                entidade_id,
                _,
                entidade_texto
            ) = selecionar(
                "Entidade *",
                entidades,
                (
                    f"sisget_ficha_entidade_"
                    f"{reset_ficha}_"
                    f"{orgao_id}"
                ),
                "Selecione a Entidade",
                desabilitado=(
                    orgao_id is None
                )
            )

        # ====================================================
        # UNIDADE ORÇAMENTÁRIA
        # ====================================================

        unidades = []

        if entidade_id is not None:

            unidades = _sisget_fetch(
                """
                SELECT
                    id,
                    codigo,
                    nome
                FROM unidades_orcamentarias
                WHERE orgao_id = ?
                  AND entidade_id = ?
                  AND ativo = TRUE
                ORDER BY codigo, nome
                """,
                (
                    orgao_id,
                    entidade_id
                )
            )

        with col3:

            (
                unidade_id,
                _,
                unidade_texto
            ) = selecionar(
                "Unidade Orçamentária *",
                unidades,
                (
                    f"sisget_ficha_unidade_"
                    f"{reset_ficha}_"
                    f"{entidade_id}"
                ),
                "Selecione a Unidade Orçamentária",
                desabilitado=(
                    entidade_id is None
                )
            )

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    exercicios = []

    if entidade_id is not None:

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

    mapa_exercicios = {}

    for registro in exercicios:

        registro_id = int(
            registro[0]
        )

        ano = int(
            registro[1]
        )

        descricao_exercicio = str(
            registro[2] or ""
        )

        mapa_exercicios[
            registro_id
        ] = {
            "ano": ano,
            "descricao": descricao_exercicio,
            "texto": (
                f"{ano} | {descricao_exercicio}"
                if descricao_exercicio
                else str(ano)
            )
        }

    with st.container(
        border=True
    ):

        st.markdown(
            "### 📅 Dados Orçamentários"
        )

        exercicio_id = st.selectbox(
            "Exercício *",
            options=[
                None
            ] + list(
                mapa_exercicios.keys()
            ),
            format_func=lambda valor: (
                "Selecione o Exercício"
                if valor is None
                else mapa_exercicios[
                    valor
                ]["texto"]
            ),
            key=(
                f"sisget_ficha_exercicio_"
                f"{reset_ficha}_"
                f"{entidade_id}"
            ),
            disabled=not bool(
                mapa_exercicios
            )
        )

        exercicio = (
            mapa_exercicios[
                exercicio_id
            ]["ano"]
            if exercicio_id is not None
            else None
        )

        if (
            entidade_id is not None
            and not exercicios
        ):

            st.warning(
                "Esta Entidade não possui "
                "Exercício ativo e aberto."
            )

    # ========================================================
    # FUNCIONAL PROGRAMÁTICA
    # ========================================================

    with st.container(
        border=True
    ):

        st.markdown(
            "### 📊 Funcional Programática"
        )

        col1, col2 = st.columns(
            2
        )

        # ====================================================
        # FUNÇÃO
        # ====================================================

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

        with col1:

            (
                funcao_id,
                funcao,
                funcao_texto
            ) = selecionar(
                "Função *",
                funcoes,
                (
                    f"sisget_ficha_funcao_"
                    f"{reset_ficha}"
                ),
                "Selecione a Função"
            )

        # ====================================================
        # SUBFUNÇÃO
        # ====================================================

        subfuncoes = []

        if funcao_id is not None:

            subfuncoes = _sisget_fetch(
                """
                SELECT
                    id,
                    codigo,
                    descricao
                FROM subfuncoes_orcamentarias
                WHERE funcao_id = ?
                  AND ativo = TRUE
                ORDER BY codigo
                """,
                (
                    funcao_id,
                )
            )

        with col2:

            (
                subfuncao_id,
                subfuncao,
                subfuncao_texto
            ) = selecionar(
                "Subfunção *",
                subfuncoes,
                (
                    f"sisget_ficha_subfuncao_"
                    f"{reset_ficha}_"
                    f"{funcao_id}"
                ),
                "Selecione a Subfunção",
                desabilitado=(
                    funcao_id is None
                )
            )

        # ====================================================
        # PROGRAMA
        # ====================================================

        programas = []

        if (
            entidade_id is not None
            and exercicio_id is not None
        ):

            programas = _sisget_fetch(
                """
                SELECT
                    id,
                    codigo,
                    nome
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

        col1, col2 = st.columns(
            2
        )

        with col1:

            (
                programa_id,
                programa,
                programa_texto
            ) = selecionar(
                "Programa *",
                programas,
                (
                    f"sisget_ficha_programa_"
                    f"{reset_ficha}_"
                    f"{entidade_id}_"
                    f"{exercicio_id}"
                ),
                "Selecione o Programa",
                desabilitado=(
                    exercicio_id is None
                )
            )

        # ====================================================
        # AÇÃO
        # ====================================================

        acoes = []

        if programa_id is not None:

            acoes = _sisget_fetch(
                """
                SELECT
                    id,
                    codigo,
                    nome
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

        with col2:

            (
                acao_id,
                acao,
                acao_texto
            ) = selecionar(
                "Projeto / Atividade / Ação *",
                acoes,
                (
                    f"sisget_ficha_acao_"
                    f"{reset_ficha}_"
                    f"{programa_id}"
                ),
                "Selecione a Ação",
                desabilitado=(
                    programa_id is None
                )
            )

    # ========================================================
    # NATUREZA + FONTE
    # ========================================================

    with st.container(
        border=True
    ):

        st.markdown(
            "### 💰 Classificação da Despesa"
        )

        col1, col2 = st.columns(
            2
        )

        # ====================================================
        # NATUREZA DA DESPESA
        # ====================================================

        naturezas = _sisget_fetch(
            """
            SELECT
                id,
                codigo,
                descricao
            FROM naturezas_despesa
            WHERE ativo = TRUE
            ORDER BY codigo
            """
        )

        with col1:

            (
                natureza_id,
                natureza_despesa,
                natureza_texto
            ) = selecionar(
                "Natureza da Despesa *",
                naturezas,
                (
                    f"sisget_ficha_natureza_"
                    f"{reset_ficha}"
                ),
                "Selecione a Natureza da Despesa"
            )

        # ====================================================
        # FONTE DE RECURSO
        # ====================================================

        fontes = []

        if (
            entidade_id is not None
            and exercicio_id is not None
        ):

            fontes = _sisget_fetch(
                """
                SELECT
                    id,
                    codigo,
                    descricao
                FROM fontes_recursos
                WHERE entidade_id = ?
                  AND exercicio_id = ?
                  AND ativo = TRUE
                ORDER BY codigo, descricao
                """,
                (
                    entidade_id,
                    exercicio_id
                )
            )

        with col2:

            (
                fonte_recurso_id,
                fonte_codigo,
                fonte_texto
            ) = selecionar(
                "Fonte de Recurso *",
                fontes,
                (
                    f"sisget_ficha_fonte_"
                    f"{reset_ficha}_"
                    f"{entidade_id}_"
                    f"{exercicio_id}"
                ),
                "Selecione a Fonte de Recurso",
                desabilitado=(
                    exercicio_id is None
                )
            )

    # ========================================================
    # CLASSIFICAÇÃO SELECIONADA
    # ========================================================

    st.divider()

    st.markdown(
        "### 🔗 Classificação Selecionada"
    )

    classificacoes = [
        {
            "Classificação": "Órgão",
            "Código e descrição": (
                orgao_texto
                or "Não selecionado"
            )
        },
        {
            "Classificação": "Entidade",
            "Código e descrição": (
                entidade_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Unidade Orçamentária",
            "Código e descrição": (
                unidade_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Função",
            "Código e descrição": (
                funcao_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Subfunção",
            "Código e descrição": (
                subfuncao_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Programa",
            "Código e descrição": (
                programa_texto
                or "Não selecionado"
            )
        },
        {
            "Classificação": "Ação",
            "Código e descrição": (
                acao_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Natureza da Despesa",
            "Código e descrição": (
                natureza_texto
                or "Não selecionada"
            )
        },
        {
            "Classificação": "Fonte de Recurso",
            "Código e descrição": (
                fonte_texto
                or "Não selecionada"
            )
        }
    ]

    st.dataframe(
        classificacoes,
        use_container_width=True,
        hide_index=True,
        key=(
            f"sisget_ficha_resumo_"
            f"{reset_ficha}"
        )
    )

    # ========================================================
    # IDENTIFICAÇÃO E ORÇAMENTO
    # ========================================================

    st.divider()

    with st.container(
        border=True
    ):

        st.markdown(
            "### 📄 Identificação e Orçamento"
        )

        with st.form(
            (
                f"sisget_form_ficha_"
                f"{reset_ficha}"
            ),
            clear_on_submit=False
        ):

            col1, col2 = st.columns(
                [1, 3]
            )

            # =================================================
            # NÚMERO DA FICHA
            # =================================================

            with col1:

                numero_ficha_texto = st.text_input(
                    "Número da Ficha *",
                    placeholder="Ex.: 125",
                    max_chars=10,
                    key=(
                        f"sisget_ficha_numero_"
                        f"{reset_ficha}"
                    )
                )

            # =================================================
            # DESCRIÇÃO
            # =================================================

            with col2:

                descricao = st.text_input(
                    "Descrição da Ficha",
                    max_chars=250,
                    placeholder=(
                        "Ex.: Manutenção das "
                        "Atividades do Gabinete"
                    ),
                    key=(
                        f"sisget_ficha_descricao_"
                        f"{reset_ficha}"
                    )
                )

            # =================================================
            # VALOR
            # =================================================

            valor_inicial = st.number_input(
                "R$ Valor Inicial / Total Orçado",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                key=(
                    f"sisget_ficha_valor_"
                    f"{reset_ficha}"
                )
            )

            valor_formatado = (
                f"{valor_inicial:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

            st.caption(
                f"💰 R$ {valor_formatado}"
            )

            # =================================================
            # ATIVO
            # =================================================

            ativo = st.checkbox(
                "Ficha ativa",
                value=True,
                key=(
                    f"sisget_ficha_ativo_"
                    f"{reset_ficha}"
                )
            )

            st.divider()

            # =================================================
            # BOTÃO SALVAR
            # =================================================

            salvar = st.form_submit_button(
                "💾 Salvar Ficha",
                type="primary",
                use_container_width=True
            )

    # ========================================================
    # MENSAGEM DE SUCESSO - EMBAIXO
    # ========================================================

    mensagem = st.session_state.pop(
        "sisget_mensagem_ficha_incluir",
        None
    )

    if mensagem:

        st.success(
            mensagem
        )

    # ========================================================
    # SE NÃO CLICOU EM SALVAR, PARA AQUI
    # ========================================================

    if not salvar:
        return

    # ========================================================
    # VALIDAR NÚMERO DA FICHA
    # ========================================================

    numero_ficha_texto = (
        numero_ficha_texto.strip()
    )

    if not numero_ficha_texto:

        st.warning(
            "Informe o número da Ficha."
        )

        return

    if not numero_ficha_texto.isdigit():

        st.warning(
            "O número da Ficha deve conter "
            "somente números."
        )

        return

    numero_ficha = int(
        numero_ficha_texto
    )

    if numero_ficha <= 0:

        st.warning(
            "O número da Ficha deve ser "
            "maior que zero."
        )

        return

    # ========================================================
    # CAMPOS OBRIGATÓRIOS
    # ========================================================

    obrigatorios = {
        "Órgão": orgao_id,
        "Entidade": entidade_id,
        "Unidade Orçamentária": unidade_id,
        "Exercício": exercicio_id,
        "Função": funcao_id,
        "Subfunção": subfuncao_id,
        "Programa": programa_id,
        "Ação": acao_id,
        "Natureza da Despesa": natureza_id,
        "Fonte de Recurso": fonte_recurso_id
    }

    faltantes = [
        nome
        for nome, valor
        in obrigatorios.items()
        if valor is None
    ]

    if faltantes:

        st.warning(
            "Preencha os seguintes campos: "
            + ", ".join(faltantes)
        )

        return

    # ========================================================
    # VALIDAR EXERCÍCIO
    # ========================================================

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
            "O Exercício selecionado "
            "não está disponível."
        )

        return

    exercicio = int(
        exercicio_valido[0]
    )

    # ========================================================
    # VALIDAR ESTRUTURA ADMINISTRATIVA
    # ========================================================

    estrutura_valida = _sisget_fetchone(
        """
        SELECT u.id
        FROM unidades_orcamentarias u

        INNER JOIN entidades e
            ON e.id = u.entidade_id

        INNER JOIN orgaos o
            ON o.id = u.orgao_id

        WHERE u.id = ?
          AND u.entidade_id = ?
          AND u.orgao_id = ?
          AND e.orgao_id = ?
          AND u.ativo = TRUE
          AND e.ativo = TRUE
          AND o.ativo = TRUE
        """,
        (
            unidade_id,
            entidade_id,
            orgao_id,
            orgao_id
        )
    )

    if not estrutura_valida:

        st.warning(
            "O vínculo entre Órgão, Entidade "
            "e Unidade Orçamentária não é válido."
        )

        return

    # ========================================================
    # VALIDAR SUBFUNÇÃO
    # ========================================================

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
            "A Subfunção selecionada "
            "não pertence à Função."
        )

        return

    # ========================================================
    # VALIDAR PROGRAMA
    # ========================================================

    programa_valido = _sisget_fetchone(
        """
        SELECT id
        FROM programas
        WHERE id = ?
          AND entidade_id = ?
          AND exercicio_id = ?
          AND ativo = TRUE
        """,
        (
            programa_id,
            entidade_id,
            exercicio_id
        )
    )

    if not programa_valido:

        st.warning(
            "O Programa selecionado não pertence "
            "à Entidade e ao Exercício."
        )

        return

    # ========================================================
    # VALIDAR AÇÃO
    # ========================================================

    acao_valida = _sisget_fetchone(
        """
        SELECT id
        FROM acoes_orcamentarias
        WHERE id = ?
          AND entidade_id = ?
          AND exercicio_id = ?
          AND programa_id = ?
          AND ativo = TRUE
        """,
        (
            acao_id,
            entidade_id,
            exercicio_id,
            programa_id
        )
    )

    if not acao_valida:

        st.warning(
            "A Ação selecionada não pertence "
            "ao Programa informado."
        )

        return

    # ========================================================
    # VALIDAR FONTE
    # ========================================================

    fonte_valida = _sisget_fetchone(
        """
        SELECT id
        FROM fontes_recursos
        WHERE id = ?
          AND entidade_id = ?
          AND exercicio_id = ?
          AND ativo = TRUE
        """,
        (
            fonte_recurso_id,
            entidade_id,
            exercicio_id
        )
    )

    if not fonte_valida:

        st.warning(
            "A Fonte de Recurso não pertence "
            "à Entidade e ao Exercício."
        )

        return

    # ========================================================
    # VERIFICAR FICHA DUPLICADA
    # ========================================================

    ficha_existente = _sisget_fetchone(
        """
        SELECT id
        FROM fichas_orcamentarias
        WHERE exercicio = ?
          AND entidade_id = ?
          AND numero_ficha = ?
        """,
        (
            exercicio,
            entidade_id,
            numero_ficha
        )
    )

    if ficha_existente:

        st.warning(
            f"Já existe uma Ficha nº "
            f"{numero_ficha} cadastrada "
            f"para esta Entidade em "
            f"{exercicio}."
        )

        return

    # ========================================================
    # SALVAR
    # ÚNICO INSERT DA FUNÇÃO
    # ========================================================

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
            exercicio,
            numero_ficha,

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

    # ========================================================
    # SALVOU COM SUCESSO
    # ========================================================

    if sucesso:

        st.session_state[
            "sisget_mensagem_ficha_incluir"
        ] = (
            f"✅ Ficha nº {numero_ficha} "
            "cadastrada com sucesso!"
        )

        # ====================================================
        # MUDA A VERSÃO DOS WIDGETS
        #
        # ISSO FAZ TODOS NASCEREM NOVOS E LIMPOS
        # ====================================================

        st.session_state[
            "sisget_ficha_reset"
        ] += 1

        # ====================================================
        # RECARREGAR A TELA
        # ====================================================

        st.rerun()

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

        numeros_utilizados = {
            int(registro[0])
            for registro in registros
            if registro[0] is not None
        }

        proximo = 1

        while proximo in numeros_utilizados:
            proximo += 1

        return proximo

    numero_ficha = None

    if exercicio is not None:

        numero_ficha = proximo_numero_ficha(
            exercicio,
            entidade_id
        )

        campos = {
            "Função": funcao_id,
            "Subfunção": subfuncao_id,
            "Programa": programa_id,
            "Ação": acao_id,
            "Natureza da Despesa": natureza_id,
            "Fonte de Recurso": fonte_recurso_id
        }

        faltantes = [
            nome
            for nome, valor in campos.items()
            if valor is None
        ]

        if faltantes:

            st.warning(
                "Selecione os seguintes campos: "
                + ", ".join(faltantes)
            )

            return

        # ====================================================
        # VALIDAR EXERCÍCIO
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

        exercicio = int(exercicio_valido[0])

        # ====================================================
        # VALIDAR SUBFUNÇÃO
        # ====================================================

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
                "A Subfunção não pertence à Função selecionada."
            )

            return

        # ====================================================
        # VALIDAR PROGRAMA E AÇÃO
        # ====================================================

        acao_valida = _sisget_fetchone(
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

        if not acao_valida:

            st.warning(
                "A Ação selecionada não possui vínculo "
                "válido com o Programa e o Exercício."
            )

            return

        # ====================================================
        # VALIDAR FONTE DE RECURSO
        # ====================================================

        fonte_valida = _sisget_fetchone(
            """
            SELECT id
            FROM fontes_recursos
            WHERE id = ?
              AND entidade_id = ?
              AND exercicio_id = ?
              AND ativo = TRUE
            """,
            (
                fonte_recurso_id,
                entidade_id,
                exercicio_id
            )
        )

        if not fonte_valida:

            st.warning(
                "A Fonte de Recurso não está vinculada "
                "corretamente à Entidade e ao Exercício."
            )

            return

        # ====================================================
        # RECALCULAR NÚMERO
        # ====================================================

        numero_salvar = proximo_numero_ficha(
            exercicio,
            entidade_id
        )

        # ====================================================
        # INSERT
        # ====================================================

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
                exercicio,
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

        numeros_utilizados = {
            int(registro[0])
            for registro in registros
            if registro[0] is not None
        }

        proximo = 1

        while proximo in numeros_utilizados:
            proximo += 1

        return proximo

    numero_ficha = None

    if exercicio is not None:

        numero_ficha = proximo_numero_ficha(
            exercicio,
            entidade_id
        )


    if salvar:

        if exercicio_id is None:

            st.warning(
                "Selecione um Exercício ativo e aberto."
            )

            return

        # ====================================================
        # VALIDAR CAMPOS OBRIGATÓRIOS
        # ====================================================

        campos = {
            "Função": funcao_id,
            "Subfunção": subfuncao_id,
            "Programa": programa_id,
            "Ação": acao_id,
            "Natureza da Despesa": natureza_id,
            "Fonte de Recurso": fonte_recurso_id
        }

        faltantes = [
            nome
            for nome, valor in campos.items()
            if valor is None
        ]

        if faltantes:

            st.warning(
                "Selecione os seguintes campos: "
                + ", ".join(faltantes)
            )

            return

        # ====================================================
        # VALIDAR EXERCÍCIO
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

        exercicio = int(exercicio_valido[0])

        # ====================================================
        # VALIDAR SUBFUNÇÃO
        # ====================================================

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
                "A Subfunção não pertence à Função selecionada."
            )

            return

        # ====================================================
        # VALIDAR PROGRAMA E AÇÃO
        # ====================================================

        acao_valida = _sisget_fetchone(
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

        if not acao_valida:

            st.warning(
                "A Ação selecionada não possui vínculo "
                "válido com o Programa e o Exercício."
            )

            return

        # ====================================================
        # VALIDAR FONTE DE RECURSO
        # ====================================================

        fonte_valida = _sisget_fetchone(
            """
            SELECT id
            FROM fontes_recursos
            WHERE id = ?
              AND entidade_id = ?
              AND exercicio_id = ?
              AND ativo = TRUE
            """,
            (
                fonte_recurso_id,
                entidade_id,
                exercicio_id
            )
        )

        if not fonte_valida:

            st.warning(
                "A Fonte de Recurso não está vinculada "
                "corretamente à Entidade e ao Exercício."
            )

            return

        # ====================================================
        # RECALCULAR O NÚMERO AUTOMÁTICO
        # ====================================================

        numero_salvar = proximo_numero_ficha(
            exercicio,
            entidade_id
        )

        # ====================================================
        # SALVAR
        #
        # OS IDs SÃO UTILIZADOS NAS SELEÇÕES.
        # OS CÓDIGOS SÃO GRAVADOS NOS CAMPOS VARCHAR
        # DA TABELA fichas_orcamentarias.
        # ====================================================

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
                exercicio,
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


    st.markdown("---")


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
# FONTES DE RECURSOS - LOCALIZAR
# ============================================================

def fonte_recurso_localizar():

    st.subheader("🔎 Localizar Fontes de Recursos")

    col1, col2 = st.columns(2)

    with col1:

        pesquisa = st.text_input(
            "Pesquisar Código ou Descrição",
            key="fonte_localizar_pesquisa"
        )

    with col2:

        situacao = st.selectbox(
            "Situação",
            ["Todos", "Ativos", "Inativos"],
            key="fonte_localizar_situacao"
        )

    sql = """
        SELECT
            f.id,
            f.exercicio AS "Exercício",
            e.nome AS "Entidade",
            f.codigo AS "Código",
            f.descricao AS "Descrição",

            CASE
                WHEN f.ativo = TRUE THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM fontes_recursos f

        LEFT JOIN entidades e
            ON e.id = f.entidade_id

        WHERE 1 = 1
    """

    parametros = []

    if pesquisa.strip():

        sql += """
            AND (
                f.codigo ILIKE ?
                OR f.descricao ILIKE ?
            )
        """

        termo = f"%{pesquisa.strip()}%"

        parametros.extend([termo, termo])

    if situacao == "Ativos":

        sql += " AND f.ativo = TRUE"

    elif situacao == "Inativos":

        sql += " AND f.ativo = FALSE"

    sql += """
        ORDER BY f.exercicio DESC, f.codigo
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info("Nenhuma Fonte de Recurso encontrada.")
        return None

    st.caption(
        "Dê duplo clique em uma Fonte para alterar."
    )

    return sisget_grid_localizar(
        df=df,
        chave="localizar_fontes_recursos",
        coluna_id="id",
        altura=420
    )
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

    st.title("📄 Fichas Orçamentárias")

    st.caption(
        "Selecione o tipo de ficha que deseja acessar."
    )

    st.divider()

    tipo_ficha = st.selectbox(
        "Tipo de Ficha *",
        options=[
            "Selecione...",
            "💸 Fichas de Despesa",
            "💰 Fichas de Receita",
            "🔄 Fichas Extraorçamentárias"
        ],
        key="sisget_tipo_ficha_orcamentaria"
    )

    st.divider()

    if tipo_ficha == "Selecione...":

        st.info(
            "Selecione um tipo de ficha acima para continuar."
        )

        return

    elif tipo_ficha == "💸 Fichas de Despesa":

        planejamento_fichas_despesa()

    elif tipo_ficha == "💰 Fichas de Receita":

        planejamento_fichas_receita()

    elif tipo_ficha == "🔄 Fichas Extraorçamentárias":

        planejamento_fichas_extraorcamentarias()
def planejamento_fichas_despesa():

    sisget_tela_principal(
        titulo="Fichas de Despesa",
        chave="fichas_orcamentarias",

        func_incluir=ficha_orcamentaria_incluir,
        func_localizar=ficha_orcamentaria_localizar,
        func_alterar=ficha_orcamentaria_alterar,
        func_excluir=ficha_orcamentaria_excluir,
        func_imprimir=ficha_orcamentaria_imprimir,

        icone="💸"
    )


# ============================================================
# AUXILIAR - PRÓXIMO NÚMERO DA FICHA
# ============================================================

def sisget_proximo_numero_ficha_nova(
    tabela,
    exercicio,
    entidade_id
):

    tabelas_permitidas = [
        "fichas_receitas",
        "fichas_extraorcamentarias"
    ]

    if tabela not in tabelas_permitidas:

        raise ValueError(
            "Tabela de ficha não permitida."
        )

    registros = _sisget_fetch(
        f"""
        SELECT numero_ficha
        FROM {tabela}
        WHERE exercicio = ?
          AND entidade_id = ?
        """,
        (
            int(exercicio),
            entidade_id
        )
    )

    numeros_utilizados = {
        int(registro[0])
        for registro in registros
        if registro[0] is not None
    }

    proximo = 1

    while proximo in numeros_utilizados:
        proximo += 1

    return proximo


# ============================================================
# AUXILIAR - SELECTBOX
# ============================================================

def sisget_ficha_selectbox(
    titulo,
    registros,
    chave,
    mensagem="Selecione",
    disabled=False
):

    mapa = {}

    for registro in registros:

        registro_id = int(
            registro[0]
        )

        codigo = str(
            registro[1] or ""
        )

        descricao = str(
            registro[2] or ""
        )

        mapa[registro_id] = {
            "codigo": codigo,
            "descricao": descricao,
            "texto": f"{codigo} | {descricao}"
        }

    selecionado = st.selectbox(
        titulo,
        options=[None] + list(mapa.keys()),
        format_func=lambda valor: (
            mensagem
            if valor is None
            else mapa[valor]["texto"]
        ),
        key=chave,
        disabled=(
            disabled
            or not bool(mapa)
        )
    )

    if selecionado is None:

        return (
            None,
            None,
            None
        )

    return (
        selecionado,
        mapa[selecionado]["codigo"],
        mapa[selecionado]["texto"]
    )


# ============================================================
# AUXILIAR - ESTRUTURA ADMINISTRATIVA
# ============================================================

def sisget_ficha_estrutura_administrativa(
    prefixo
):

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
            "⚠️ Nenhum Órgão ativo cadastrado."
        )

        return (
            None,
            None,
            None,
            None,
            None,
            None
        )

    col1, col2, col3 = st.columns(3)

    with col1:

        (
            orgao_id,
            _,
            orgao_texto
        ) = sisget_ficha_selectbox(
            "Órgão *",
            orgaos,
            f"{prefixo}_orgao",
            "Selecione o Órgão"
        )

    entidades = []

    if orgao_id is not None:

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
            (
                orgao_id,
            )
        )

    with col2:

        (
            entidade_id,
            _,
            entidade_texto
        ) = sisget_ficha_selectbox(
            "Entidade *",
            entidades,
            f"{prefixo}_entidade_{orgao_id}",
            "Selecione a Entidade",
            disabled=(
                orgao_id is None
            )
        )

    unidades = []

    if (
        orgao_id is not None
        and entidade_id is not None
    ):

        unidades = _sisget_fetch(
            """
            SELECT
                id,
                codigo,
                nome
            FROM unidades_orcamentarias
            WHERE orgao_id = ?
              AND entidade_id = ?
              AND ativo = TRUE
            ORDER BY codigo, nome
            """,
            (
                orgao_id,
                entidade_id
            )
        )

    with col3:

        (
            unidade_id,
            _,
            unidade_texto
        ) = sisget_ficha_selectbox(
            "Unidade Orçamentária *",
            unidades,
            f"{prefixo}_unidade_{entidade_id}",
            "Selecione a Unidade Orçamentária",
            disabled=(
                entidade_id is None
            )
        )

    return (
        orgao_id,
        entidade_id,
        unidade_id,
        orgao_texto,
        entidade_texto,
        unidade_texto
    )


# ============================================================
# AUXILIAR - FONTES DE RECURSOS
# ============================================================

def sisget_mapa_fontes_fichas():

    fontes = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM fontes_recursos
        WHERE ativo = TRUE
        ORDER BY codigo, descricao
        """
    )

    mapa = {
        "Sem fonte vinculada": None
    }

    for (
        fonte_id,
        codigo,
        descricao
    ) in fontes:

        mapa[
            f"{codigo} - {descricao}"
        ] = fonte_id

    return mapa


# ============================================================
# FICHAS DE RECEITA - PRINCIPAL
# ============================================================

def planejamento_fichas_receita():

    sisget_tela_principal(
        titulo="Fichas de Receita",
        chave="fichas_receitas",
        func_incluir=ficha_receita_incluir,
        func_localizar=ficha_receita_localizar,
        func_alterar=ficha_receita_alterar,
        func_excluir=ficha_receita_excluir,
        func_imprimir=ficha_receita_imprimir,
        icone="💰"
    )


# ============================================================
# FICHA DE RECEITA - INCLUIR
# ============================================================

def ficha_receita_incluir():

    # ========================================================
    # CONTROLE DE RESET
    # ========================================================

    if "sisget_receita_reset" not in st.session_state:

        st.session_state[
            "sisget_receita_reset"
        ] = 0

    reset_receita = st.session_state[
        "sisget_receita_reset"
    ]

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.subheader(
        "💰 Cadastro de Ficha de Receita"
    )

    st.caption(
        "Informe a estrutura administrativa "
        "e os dados da receita."
    )

    # ========================================================
    # MENSAGEM DE SUCESSO
    # ========================================================

    if (
        "sisget_mensagem_receita_incluir"
        in st.session_state
    ):

        st.success(
            st.session_state.pop(
                "sisget_mensagem_receita_incluir"
            )
        )

    # ========================================================
    # ESTRUTURA ADMINISTRATIVA
    # ========================================================

    with st.container(
        border=True
    ):

        st.markdown(
            "### 🏛️ Estrutura Administrativa"
        )

        (
            orgao_id,
            entidade_id,
            unidade_id,
            _,
            _,
            _
        ) = sisget_ficha_estrutura_administrativa(
            f"receita_incluir_{reset_receita}"
        )

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    col_ex1, col_ex2 = st.columns(
        [1, 2]
    )

    exercicio = col_ex1.number_input(
        "Exercício *",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key=(
            f"receita_incluir_exercicio_"
            f"{reset_receita}"
        )
    )

    # ========================================================
    # PRÓXIMO NÚMERO DA FICHA
    # ========================================================

    numero_ficha = None

    if entidade_id is not None:

        numero_ficha = (
            sisget_proximo_numero_ficha_nova(
                "fichas_receitas",
                exercicio,
                entidade_id
            )
        )

    elif (
        "sisget_proxima_ficha_receita"
        in st.session_state
    ):

        numero_ficha = (
            st.session_state[
                "sisget_proxima_ficha_receita"
            ]
        )

    else:

        numero_ficha = 1

    # ========================================================
    # NÚMERO DA FICHA EDITÁVEL
    # ========================================================

    numero_ficha_digitado = (
        col_ex2.number_input(
            "Número da Ficha *",
            min_value=1,
            value=int(
                numero_ficha
            ),
            step=1,
            key=(
                f"receita_numero_ficha_"
                f"{reset_receita}_"
                f"{entidade_id}"
            )
        )
    )

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo_automatico = ""

    if entidade_id is not None:

        codigo_automatico = (
            sisget_proximo_codigo_ficha_receita(
                exercicio,
                entidade_id
            )
        )

    # ========================================================
    # FONTES DE RECURSOS
    # ========================================================

    fontes = (
        sisget_mapa_fontes_fichas()
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        (
            f"form_ficha_receita_incluir_"
            f"{reset_receita}_"
            f"{entidade_id}"
        )
    ):

        st.markdown(
            "### 💰 Classificação da Receita"
        )

        col1, col2 = st.columns(
            [1, 3]
        )

        codigo_receita = (
            col1.text_input(
                "Código",
                value=codigo_automatico,
                disabled=True
            )
        )

        descricao = (
            col2.text_input(
                "Descrição da Receita *",
                max_chars=300
            )
        )

        fonte_nome = (
            st.selectbox(
                "Fonte de Recurso",
                list(
                    fontes.keys()
                )
            )
        )

        st.markdown("---")

        # ====================================================
        # VALORES
        # ====================================================

        st.markdown(
            "### 💵 Valores"
        )

        col3, col4, col5 = (
            st.columns(3)
        )

        valor_inicial = (
            col3.number_input(
                "Previsão Inicial",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f"
            )
        )

        valor_atual = (
            col4.number_input(
                "Previsão Atualizada",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f"
            )
        )

        valor_arrecadado = (
            col5.number_input(
                "Valor Arrecadado",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f"
            )
        )

        salvar = (
            st.form_submit_button(
                "💾 Salvar Ficha de Receita",
                type="primary",
                use_container_width=True
            )
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        # ====================================================
        # VALIDAR ESTRUTURA
        # ====================================================

        if (
            orgao_id is None
            or entidade_id is None
            or unidade_id is None
        ):

            st.warning(
                "⚠️ Selecione Órgão, Entidade "
                "e Unidade Orçamentária."
            )

            return

        # ====================================================
        # DESCRIÇÃO
        # ====================================================

        descricao = (
            descricao.strip()
        )

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição da Receita."
            )

            return

        # ====================================================
        # NÚMERO DA FICHA
        # ====================================================

        numero_ficha = int(
            numero_ficha_digitado
        )

        # ====================================================
        # VALIDAR FICHA DUPLICADA
        # ====================================================

        ficha_existente = (
            _sisget_fetchone(
                """
                SELECT id
                FROM fichas_receitas
                WHERE exercicio = ?
                  AND entidade_id = ?
                  AND numero_ficha = ?
                """,
                (
                    int(exercicio),
                    entidade_id,
                    numero_ficha
                )
            )
        )

        if ficha_existente:

            st.warning(
                f"⚠️ Já existe a Ficha nº "
                f"{numero_ficha} cadastrada "
                f"para esta Entidade no exercício "
                f"{int(exercicio)}."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO AUTOMÁTICO
        # ====================================================

        codigo_receita = (
            sisget_proximo_codigo_ficha_receita(
                exercicio,
                entidade_id
            )
        )

        # ====================================================
        # VALIDAR CÓDIGO DUPLICADO
        # ====================================================

        codigo_existente = (
            _sisget_fetchone(
                """
                SELECT id
                FROM fichas_receitas
                WHERE exercicio = ?
                  AND entidade_id = ?
                  AND codigo_receita = ?
                """,
                (
                    int(exercicio),
                    entidade_id,
                    codigo_receita
                )
            )
        )

        if codigo_existente:

            st.warning(
                f"⚠️ O código "
                f"{codigo_receita} "
                f"já está cadastrado."
            )

            return

        # ====================================================
        # FONTE DE RECURSO
        # ====================================================

        fonte_id = fontes[
            fonte_nome
        ]

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO fichas_receitas
            (
                exercicio,
                numero_ficha,

                orgao_id,
                entidade_id,
                unidade_orcamentaria_id,

                codigo_receita,
                descricao,

                fonte_recurso_id,

                valor_previsto_inicial,
                valor_previsto_atual,
                valor_arrecadado,

                ativo
            )
            VALUES
            (
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?,
                ?, ?, ?,
                TRUE
            )
            """,
            (
                int(exercicio),
                numero_ficha,

                orgao_id,
                entidade_id,
                unidade_id,

                codigo_receita,
                descricao,

                fonte_id,

                float(
                    valor_inicial
                ),
                float(
                    valor_atual
                ),
                float(
                    valor_arrecadado
                )
            )
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            # =================================================
            # MENSAGEM
            # =================================================

            st.session_state[
                "sisget_mensagem_receita_incluir"
            ] = (
                f"✅ Ficha de Receita nº "
                f"{numero_ficha} cadastrada com sucesso! "
                f"Código: {codigo_receita}"
            )

            # =================================================
            # GUARDAR PRÓXIMO NÚMERO
            # =================================================

            st.session_state[
                "sisget_proxima_ficha_receita"
            ] = (
                int(numero_ficha) + 1
            )

            # =================================================
            # RESETAR TODOS OS CAMPOS
            # =================================================

            st.session_state[
                "sisget_receita_reset"
            ] += 1

            # =================================================
            # RECARREGAR
            # =================================================

            st.rerun()
def ficha_receita_localizar():

    st.subheader(
        "🔎 Localizar Fichas de Receita"
    )

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    exercicio = col1.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="receita_localizar_exercicio"
    )

    pesquisa = col2.text_input(
        "Ficha / código / descrição",
        key="receita_localizar_pesquisa"
    )

    situacao = col3.selectbox(
        "Situação",
        [
            "Todas",
            "Ativas",
            "Inativas"
        ],
        key="receita_localizar_situacao"
    )

    sql = """
        SELECT
            r.id,
            r.numero_ficha AS "Ficha",
            o.codigo || ' - ' || o.nome AS "Órgão",
            e.codigo || ' - ' || e.nome AS "Entidade",
            u.codigo || ' - ' || u.nome AS "Unidade Orçamentária",
            r.codigo_receita AS "Código Receita",
            r.descricao AS "Descrição",
            COALESCE(fr.codigo, '') AS "Fonte",
            r.valor_previsto_inicial AS "Previsão Inicial",
            r.valor_previsto_atual AS "Previsão Atual",
            r.valor_arrecadado AS "Arrecadado",
            (r.valor_previsto_atual - r.valor_arrecadado)
                AS "Saldo a Arrecadar",
            CASE
                WHEN r.ativo = TRUE THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM fichas_receitas r
        INNER JOIN orgaos o
            ON o.id = r.orgao_id
        INNER JOIN entidades e
            ON e.id = r.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = r.unidade_orcamentaria_id
        LEFT JOIN fontes_recursos fr
            ON fr.id = r.fonte_recurso_id
        WHERE r.exercicio = ?
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
                CAST(r.numero_ficha AS TEXT) ILIKE ?
                OR r.codigo_receita ILIKE ?
                OR COALESCE(r.descricao, '') ILIKE ?
                OR e.nome ILIKE ?
                OR u.nome ILIKE ?
            )
        """

        parametros.extend([
            termo,
            termo,
            termo,
            termo,
            termo
        ])

    if situacao == "Ativas":

        sql += """
            AND r.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND r.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            r.numero_ficha
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma Ficha de Receita encontrada."
        )

        return None

    st.caption(
        f"Total encontrado: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="fichas_receitas",
        coluna_id="id",
        altura=470
    )


# ============================================================
# FICHA DE RECEITA - ALTERAR
# ============================================================

def ficha_receita_alterar(
    ficha_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            r.exercicio,
            r.numero_ficha,
            r.codigo_receita,
            r.descricao,
            r.fonte_recurso_id,
            r.valor_previsto_inicial,
            r.valor_previsto_atual,
            r.valor_arrecadado,
            r.ativo,
            o.codigo,
            o.nome,
            e.codigo,
            e.nome,
            u.codigo,
            u.nome
        FROM fichas_receitas r
        INNER JOIN orgaos o
            ON o.id = r.orgao_id
        INNER JOIN entidades e
            ON e.id = r.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = r.unidade_orcamentaria_id
        WHERE r.id = ?
        """,
        (
            ficha_id,
        )
    )

    if not registro:

        st.error(
            "❌ Ficha de Receita não encontrada."
        )

        return

    (
        exercicio,
        numero_ficha,
        codigo_atual,
        descricao_atual,
        fonte_atual_id,
        valor_inicial_atual,
        valor_atual_atual,
        valor_arrecadado_atual,
        ativo,
        codigo_orgao,
        nome_orgao,
        codigo_entidade,
        nome_entidade,
        codigo_unidade,
        nome_unidade
    ) = registro

    st.info(
        f"📄 Ficha {numero_ficha} | "
        f"Exercício {exercicio}"
    )

    st.caption(
        f"🏛️ {codigo_orgao} - {nome_orgao} | "
        f"{codigo_entidade} - {nome_entidade} | "
        f"{codigo_unidade} - {nome_unidade}"
    )

    fontes = sisget_mapa_fontes_fichas()

    opcoes_fontes = list(
        fontes.keys()
    )

    indice_fonte = 0

    for indice, nome in enumerate(
        opcoes_fontes
    ):

        if fontes[nome] == fonte_atual_id:

            indice_fonte = indice
            break

    with st.form(
        f"form_ficha_receita_alterar_{ficha_id}"
    ):

        col1, col2 = st.columns(
            [1, 3]
        )

        codigo = col1.text_input(
            "Código da Receita *",
            value=(
                codigo_atual
                or ""
            )
        )

        descricao = col2.text_input(
            "Descrição *",
            value=(
                descricao_atual
                or ""
            )
        )

        fonte_nome = st.selectbox(
            "Fonte de Recurso",
            opcoes_fontes,
            index=indice_fonte
        )

        col3, col4, col5 = st.columns(3)

        valor_inicial = col3.number_input(
            "Previsão Inicial",
            min_value=0.0,
            value=float(
                valor_inicial_atual
                or 0
            ),
            format="%.2f"
        )

        valor_atual = col4.number_input(
            "Previsão Atualizada",
            min_value=0.0,
            value=float(
                valor_atual_atual
                or 0
            ),
            format="%.2f"
        )

        valor_arrecadado = col5.number_input(
            "Valor Arrecadado",
            min_value=0.0,
            value=float(
                valor_arrecadado_atual
                or 0
            ),
            format="%.2f"
        )

        col_salvar, col_status = st.columns(2)

        salvar = col_salvar.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        alterar_status = (
            col_status.form_submit_button(
                "🚫 Inativar"
                if ativo
                else "✅ Ativar",
                use_container_width=True
            )
        )

    if alterar_status:

        if _sisget_salvar(
            """
            UPDATE fichas_receitas
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                ficha_id
            )
        ):

            st.session_state[
                "sisget_tela_fichas_receitas"
            ] = "localizar"

            st.rerun()

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo:

            st.warning(
                "⚠️ Informe o Código da Receita."
            )

            return

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        if _sisget_salvar(
            """
            UPDATE fichas_receitas
            SET
                codigo_receita = ?,
                descricao = ?,
                fonte_recurso_id = ?,
                valor_previsto_inicial = ?,
                valor_previsto_atual = ?,
                valor_arrecadado = ?
            WHERE id = ?
            """,
            (
                codigo,
                descricao,
                fontes[fonte_nome],
                float(valor_inicial),
                float(valor_atual),
                float(valor_arrecadado),
                ficha_id
            )
        ):

            st.session_state[
                "sisget_tela_fichas_receitas"
            ] = "localizar"

            st.rerun()


# ============================================================
# FICHA DE RECEITA - EXCLUIR
# ============================================================

def ficha_receita_excluir():

    st.subheader(
        "🗑️ Excluir Ficha de Receita"
    )

    exercicio = st.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="receita_excluir_exercicio"
    )

    df = _sisget_dataframe(
        """
        SELECT
            r.id,
            r.numero_ficha AS "Ficha",
            e.codigo || ' - ' || e.nome AS "Entidade",
            u.codigo || ' - ' || u.nome AS "Unidade Orçamentária",
            r.codigo_receita AS "Código",
            r.descricao AS "Descrição",
            r.valor_previsto_atual AS "Previsão Atual",
            r.valor_arrecadado AS "Arrecadado"
        FROM fichas_receitas r
        INNER JOIN entidades e
            ON e.id = r.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = r.unidade_orcamentaria_id
        WHERE r.exercicio = ?
        ORDER BY r.numero_ficha
        """,
        (
            int(exercicio),
        )
    )

    if df.empty:

        st.info(
            "Nenhuma Ficha de Receita cadastrada."
        )

        return

    ficha_id = sisget_grid_localizar(
        df=df,
        chave="excluir_fichas_receitas",
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
            valor_arrecadado
        FROM fichas_receitas
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
    valor_arrecadado = float(
        registro[2] or 0
    )

    st.error(
        f"⚠️ Ficha de Receita "
        f"**{numero_ficha} - {descricao}**"
    )

    if valor_arrecadado > 0:

        st.warning(
            "🔒 Esta ficha possui valor arrecadado. "
            "Inative a ficha em vez de excluí-la."
        )

        return

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta Ficha de Receita.",
        key=f"confirmar_excluir_receita_{ficha_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_receita_{ficha_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação."
            )

            return

        if _sisget_salvar(
            """
            DELETE FROM fichas_receitas
            WHERE id = ?
            """,
            (
                ficha_id,
            )
        ):

            st.session_state[
                "sisget_tela_fichas_receitas"
            ] = "principal"

            st.rerun()


# ============================================================
# FICHA DE RECEITA - IMPRIMIR
# ============================================================

def ficha_receita_imprimir():

    st.subheader(
        "🖨️ Relatório de Fichas de Receita"
    )

    exercicio = st.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="receita_imprimir_exercicio"
    )

    dados = _sisget_fetch(
        """
        SELECT
            r.numero_ficha,
            u.codigo,
            u.nome,
            r.codigo_receita,
            COALESCE(fr.codigo, ''),
            r.descricao,
            r.valor_previsto_atual,
            r.valor_arrecadado,
            (r.valor_previsto_atual - r.valor_arrecadado),
            r.ativo
        FROM fichas_receitas r
        INNER JOIN unidades_orcamentarias u
            ON u.id = r.unidade_orcamentaria_id
        LEFT JOIN fontes_recursos fr
            ON fr.id = r.fonte_recurso_id
        WHERE r.exercicio = ?
        ORDER BY u.codigo, r.numero_ficha
        """,
        (
            int(exercicio),
        )
    )

    if not dados:

        st.info(
            "Nenhuma Ficha de Receita encontrada."
        )

        return

    tabela_dados = [[
        "Ficha",
        "Unidade",
        "Código",
        "Fonte",
        "Descrição",
        "Prev. Atual",
        "Arrecadado",
        "Saldo"
    ]]

    total_previsto = 0
    total_arrecadado = 0
    total_saldo = 0

    for registro in dados:

        previsto = float(
            registro[6] or 0
        )

        arrecadado = float(
            registro[7] or 0
        )

        saldo = float(
            registro[8] or 0
        )

        total_previsto += previsto
        total_arrecadado += arrecadado
        total_saldo += saldo

        tabela_dados.append([
            str(registro[0]),
            f"{registro[1]} - {registro[2]}",
            str(registro[3] or ""),
            str(registro[4] or ""),
            str(registro[5] or ""),
            f"R$ {previsto:,.2f}",
            f"R$ {arrecadado:,.2f}",
            f"R$ {saldo:,.2f}"
        ])

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
    elementos = []

    elementos.append(
        Paragraph(
            "FICHAS DE RECEITA",
            estilos["Title"]
        )
    )

    elementos.append(
        Paragraph(
            f"Exercício: {int(exercicio)}",
            estilos["Normal"]
        )
    )

    elementos.append(
        Spacer(
            1,
            0.4 * cm
        )
    )

    tabela = Table(
        tabela_dados,
        colWidths=[
            1.0 * cm,
            3.0 * cm,
            2.2 * cm,
            1.5 * cm,
            4.0 * cm,
            2.2 * cm,
            2.2 * cm,
            2.2 * cm
        ],
        repeatRows=1
    )

    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 6)
        ])
    )

    elementos.append(
        tabela
    )

    elementos.append(
        Spacer(
            1,
            0.4 * cm
        )
    )

    elementos.append(
        Paragraph(
            f"Previsão Atual: R$ {total_previsto:,.2f}",
            estilos["Normal"]
        )
    )

    elementos.append(
        Paragraph(
            f"Arrecadado: R$ {total_arrecadado:,.2f}",
            estilos["Normal"]
        )
    )

    elementos.append(
        Paragraph(
            f"Saldo a Arrecadar: R$ {total_saldo:,.2f}",
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
            f"fichas_receitas_{int(exercicio)}.pdf"
        ),
        mime="application/pdf",
        use_container_width=True,
        key="baixar_pdf_fichas_receitas"
    )


# ============================================================
# FICHAS EXTRAORÇAMENTÁRIAS - PRINCIPAL
# ============================================================

def planejamento_fichas_extraorcamentarias():

    sisget_tela_principal(
        titulo="Fichas Extraorçamentárias",
        chave="fichas_extraorcamentarias",
        func_incluir=ficha_extraorcamentaria_incluir,
        func_localizar=ficha_extraorcamentaria_localizar,
        func_alterar=ficha_extraorcamentaria_alterar,
        func_excluir=ficha_extraorcamentaria_excluir,
        func_imprimir=ficha_extraorcamentaria_imprimir,
        icone="🔄"
    )


# ============================================================
# EXTRAORÇAMENTÁRIA - INCLUIR
# ============================================================

def ficha_extraorcamentaria_incluir():

    # ========================================================
    # CONTROLE DE RESET
    # ========================================================

    if "sisget_extra_reset" not in st.session_state:

        st.session_state[
            "sisget_extra_reset"
        ] = 0

    reset_extra = st.session_state[
        "sisget_extra_reset"
    ]

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.subheader(
        "🔄 Cadastro de Ficha Extraorçamentária"
    )

    st.caption(
        "Cadastre receitas e despesas "
        "extraorçamentárias."
    )

    # ========================================================
    # MENSAGEM DE SUCESSO
    # ========================================================

    if (
        "sisget_mensagem_extra_incluir"
        in st.session_state
    ):

        st.success(
            st.session_state.pop(
                "sisget_mensagem_extra_incluir"
            )
        )

    # ========================================================
    # ESTRUTURA ADMINISTRATIVA
    # ========================================================

    with st.container(
        border=True
    ):

        st.markdown(
            "### 🏛️ Estrutura Administrativa"
        )

        (
            orgao_id,
            entidade_id,
            unidade_id,
            _,
            _,
            _
        ) = sisget_ficha_estrutura_administrativa(
            f"extra_incluir_{reset_extra}"
        )

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    col_ex1, col_ex2 = st.columns(
        [1, 2]
    )

    exercicio = (
        col_ex1.number_input(
            "Exercício *",
            min_value=2000,
            max_value=2100,
            value=datetime.now().year,
            step=1,
            key=(
                f"extra_incluir_exercicio_"
                f"{reset_extra}"
            )
        )
    )

    # ========================================================
    # PRÓXIMO NÚMERO DA FICHA
    # ========================================================

    numero_ficha = None

    if entidade_id is not None:

        numero_ficha = (
            sisget_proximo_numero_ficha_nova(
                "fichas_extraorcamentarias",
                exercicio,
                entidade_id
            )
        )

    elif (
        "sisget_proxima_ficha_extra"
        in st.session_state
    ):

        numero_ficha = (
            st.session_state[
                "sisget_proxima_ficha_extra"
            ]
        )

    else:

        numero_ficha = 1

    # ========================================================
    # NÚMERO DA FICHA EDITÁVEL
    # ========================================================

    numero_ficha_digitado = (
        col_ex2.number_input(
            "Número da Ficha *",
            min_value=1,
            value=int(
                numero_ficha
            ),
            step=1,
            key=(
                f"extra_numero_ficha_"
                f"{reset_extra}_"
                f"{entidade_id}"
            )
        )
    )

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo_automatico = ""

    if entidade_id is not None:

        codigo_automatico = (
            sisget_proximo_codigo_ficha_extra(
                exercicio,
                entidade_id
            )
        )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        (
            f"form_ficha_extraorcamentaria_"
            f"incluir_{reset_extra}_"
            f"{entidade_id}"
        )
    ):

        # ====================================================
        # TIPO
        # ====================================================

        tipo = st.selectbox(
            "Tipo *",
            [
                "Receita Extraorçamentária",
                "Despesa Extraorçamentária"
            ]
        )

        # ====================================================
        # CÓDIGO / DESCRIÇÃO
        # ====================================================

        col1, col2 = st.columns(
            [1, 3]
        )

        codigo = col1.text_input(
            "Código",
            value=codigo_automatico,
            disabled=True
        )

        descricao = (
            col2.text_input(
                "Descrição *",
                max_chars=300
            )
        )

        st.markdown("---")

        # ====================================================
        # VALORES
        # ====================================================

        col3, col4 = st.columns(2)

        valor_inicial = (
            col3.number_input(
                "Valor Inicial",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f"
            )
        )

        valor_movimentado = (
            col4.number_input(
                "Valor Movimentado",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f"
            )
        )

        salvar = (
            st.form_submit_button(
                "💾 Salvar Ficha Extraorçamentária",
                type="primary",
                use_container_width=True
            )
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        # ====================================================
        # VALIDAR ESTRUTURA
        # ====================================================

        if (
            orgao_id is None
            or entidade_id is None
            or unidade_id is None
        ):

            st.warning(
                "⚠️ Selecione Órgão, Entidade "
                "e Unidade Orçamentária."
            )

            return

        # ====================================================
        # DESCRIÇÃO
        # ====================================================

        descricao = (
            descricao.strip()
        )

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        # ====================================================
        # NÚMERO DA FICHA
        # ====================================================

        numero_ficha = int(
            numero_ficha_digitado
        )

        # ====================================================
        # VALIDAR FICHA DUPLICADA
        # ====================================================

        ficha_existente = (
            _sisget_fetchone(
                """
                SELECT id
                FROM fichas_extraorcamentarias
                WHERE exercicio = ?
                  AND entidade_id = ?
                  AND numero_ficha = ?
                """,
                (
                    int(exercicio),
                    entidade_id,
                    numero_ficha
                )
            )
        )

        if ficha_existente:

            st.warning(
                f"⚠️ Já existe a Ficha nº "
                f"{numero_ficha} cadastrada "
                f"para esta Entidade no exercício "
                f"{int(exercicio)}."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO AUTOMÁTICO
        # ====================================================

        codigo = (
            sisget_proximo_codigo_ficha_extra(
                exercicio,
                entidade_id
            )
        )

        # ====================================================
        # VALIDAR CÓDIGO DUPLICADO
        # ====================================================

        codigo_existente = (
            _sisget_fetchone(
                """
                SELECT id
                FROM fichas_extraorcamentarias
                WHERE exercicio = ?
                  AND entidade_id = ?
                  AND codigo = ?
                """,
                (
                    int(exercicio),
                    entidade_id,
                    codigo
                )
            )
        )

        if codigo_existente:

            st.warning(
                f"⚠️ O código "
                f"{codigo} "
                f"já está cadastrado."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
            """
            INSERT INTO fichas_extraorcamentarias
            (
                exercicio,
                numero_ficha,

                orgao_id,
                entidade_id,
                unidade_orcamentaria_id,

                tipo,

                codigo,
                descricao,

                valor_inicial,
                valor_movimentado,

                ativo
            )
            VALUES
            (
                ?, ?,
                ?, ?, ?,
                ?,
                ?, ?,
                ?, ?,
                TRUE
            )
            """,
            (
                int(exercicio),
                numero_ficha,

                orgao_id,
                entidade_id,
                unidade_id,

                tipo,

                codigo,
                descricao,

                float(
                    valor_inicial
                ),
                float(
                    valor_movimentado
                )
            )
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            # =================================================
            # MENSAGEM
            # =================================================

            st.session_state[
                "sisget_mensagem_extra_incluir"
            ] = (
                f"✅ Ficha Extraorçamentária nº "
                f"{numero_ficha} cadastrada com sucesso! "
                f"Código: {codigo}"
            )

            # =================================================
            # GUARDAR PRÓXIMO NÚMERO
            # =================================================

            st.session_state[
                "sisget_proxima_ficha_extra"
            ] = (
                int(numero_ficha) + 1
            )

            # =================================================
            # RESETAR TODOS OS CAMPOS
            # =================================================

            st.session_state[
                "sisget_extra_reset"
            ] += 1

            # =================================================
            # RECARREGAR
            # =================================================

            st.rerun()
def sisget_proximo_codigo_ficha_receita(
    exercicio,
    entidade_id
):

    registros = _sisget_fetch(
        """
        SELECT codigo_receita
        FROM fichas_receitas
        WHERE exercicio = ?
          AND entidade_id = ?
        ORDER BY codigo_receita
        """,
        (
            int(exercicio),
            entidade_id
        )
    )

    numeros_utilizados = set()

    for registro in registros:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            numeros_utilizados.add(
                int(codigo)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    proximo = 1

    while proximo in numeros_utilizados:

        proximo += 1

    return str(
        proximo
    ).zfill(3)
def ficha_extraorcamentaria_localizar():

    st.subheader(
        "🔎 Localizar Fichas Extraorçamentárias"
    )

    col1, col2, col3, col4 = st.columns(
        [1, 2, 2, 1]
    )

    exercicio = col1.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="extra_localizar_exercicio"
    )

    pesquisa = col2.text_input(
        "Ficha / código / descrição",
        key="extra_localizar_pesquisa"
    )

    tipo_filtro = col3.selectbox(
        "Tipo",
        [
            "Todos",
            "Receita Extraorçamentária",
            "Despesa Extraorçamentária"
        ],
        key="extra_localizar_tipo"
    )

    situacao = col4.selectbox(
        "Situação",
        [
            "Todas",
            "Ativas",
            "Inativas"
        ],
        key="extra_localizar_situacao"
    )

    sql = """
        SELECT
            x.id,
            x.numero_ficha AS "Ficha",
            o.codigo || ' - ' || o.nome AS "Órgão",
            e.codigo || ' - ' || e.nome AS "Entidade",
            u.codigo || ' - ' || u.nome AS "Unidade Orçamentária",
            x.tipo AS "Tipo",
            x.codigo AS "Código",
            x.descricao AS "Descrição",
            x.valor_inicial AS "Valor Inicial",
            x.valor_movimentado AS "Movimentado",
            CASE
                WHEN x.ativo = TRUE THEN 'Ativa'
                ELSE 'Inativa'
            END AS "Situação"
        FROM fichas_extraorcamentarias x
        INNER JOIN orgaos o
            ON o.id = x.orgao_id
        INNER JOIN entidades e
            ON e.id = x.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = x.unidade_orcamentaria_id
        WHERE x.exercicio = ?
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
                CAST(x.numero_ficha AS TEXT) ILIKE ?
                OR x.codigo ILIKE ?
                OR COALESCE(x.descricao, '') ILIKE ?
                OR e.nome ILIKE ?
                OR u.nome ILIKE ?
            )
        """

        parametros.extend([
            termo,
            termo,
            termo,
            termo,
            termo
        ])

    if tipo_filtro != "Todos":

        sql += """
            AND x.tipo = ?
        """

        parametros.append(
            tipo_filtro
        )

    if situacao == "Ativas":

        sql += """
            AND x.ativo = TRUE
        """

    elif situacao == "Inativas":

        sql += """
            AND x.ativo = FALSE
        """

    sql += """
        ORDER BY
            o.codigo,
            e.codigo,
            u.codigo,
            x.numero_ficha
    """

    df = _sisget_dataframe(
        sql,
        tuple(parametros)
    )

    if df.empty:

        st.info(
            "Nenhuma Ficha Extraorçamentária encontrada."
        )

        return None

    st.caption(
        f"Total encontrado: {len(df)}"
    )

    return sisget_grid_localizar(
        df=df,
        chave="fichas_extraorcamentarias",
        coluna_id="id",
        altura=470
    )


# ============================================================
# EXTRAORÇAMENTÁRIA - ALTERAR
# ============================================================

def ficha_extraorcamentaria_alterar(
    ficha_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            x.exercicio,
            x.numero_ficha,
            x.tipo,
            x.codigo,
            x.descricao,
            x.valor_inicial,
            x.valor_movimentado,
            x.ativo,
            o.codigo,
            o.nome,
            e.codigo,
            e.nome,
            u.codigo,
            u.nome
        FROM fichas_extraorcamentarias x
        INNER JOIN orgaos o
            ON o.id = x.orgao_id
        INNER JOIN entidades e
            ON e.id = x.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = x.unidade_orcamentaria_id
        WHERE x.id = ?
        """,
        (
            ficha_id,
        )
    )

    if not registro:

        st.error(
            "❌ Ficha Extraorçamentária não encontrada."
        )

        return

    (
        exercicio,
        numero_ficha,
        tipo_atual,
        codigo_atual,
        descricao_atual,
        valor_inicial_atual,
        valor_movimentado_atual,
        ativo,
        codigo_orgao,
        nome_orgao,
        codigo_entidade,
        nome_entidade,
        codigo_unidade,
        nome_unidade
    ) = registro

    st.info(
        f"📄 Ficha {numero_ficha} | "
        f"Exercício {exercicio}"
    )

    st.caption(
        f"🏛️ {codigo_orgao} - {nome_orgao} | "
        f"{codigo_entidade} - {nome_entidade} | "
        f"{codigo_unidade} - {nome_unidade}"
    )

    tipos = [
        "Receita Extraorçamentária",
        "Despesa Extraorçamentária"
    ]

    indice_tipo = (
        tipos.index(tipo_atual)
        if tipo_atual in tipos
        else 0
    )

    with st.form(
        f"form_extra_alterar_{ficha_id}"
    ):

        tipo = st.selectbox(
            "Tipo *",
            tipos,
            index=indice_tipo
        )

        col1, col2 = st.columns(
            [1, 3]
        )

        codigo = col1.text_input(
            "Código *",
            value=(
                codigo_atual
                or ""
            )
        )

        descricao = col2.text_input(
            "Descrição *",
            value=(
                descricao_atual
                or ""
            )
        )

        col3, col4 = st.columns(2)

        valor_inicial = col3.number_input(
            "Valor Inicial",
            min_value=0.0,
            value=float(
                valor_inicial_atual
                or 0
            ),
            format="%.2f"
        )

        valor_movimentado = col4.number_input(
            "Valor Movimentado",
            min_value=0.0,
            value=float(
                valor_movimentado_atual
                or 0
            ),
            format="%.2f"
        )

        col_salvar, col_status = st.columns(2)

        salvar = col_salvar.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        alterar_status = col_status.form_submit_button(
            "🚫 Inativar"
            if ativo
            else "✅ Ativar",
            use_container_width=True
        )

    if alterar_status:

        if _sisget_salvar(
            """
            UPDATE fichas_extraorcamentarias
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                ficha_id
            )
        ):

            st.session_state[
                "sisget_tela_fichas_extraorcamentarias"
            ] = "localizar"

            st.rerun()

    if salvar:

        codigo = codigo.strip()
        descricao = descricao.strip()

        if not codigo:

            st.warning(
                "⚠️ Informe o código."
            )

            return

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        if _sisget_salvar(
            """
            UPDATE fichas_extraorcamentarias
            SET
                tipo = ?,
                codigo = ?,
                descricao = ?,
                valor_inicial = ?,
                valor_movimentado = ?
            WHERE id = ?
            """,
            (
                tipo,
                codigo,
                descricao,
                float(valor_inicial),
                float(valor_movimentado),
                ficha_id
            )
        ):

            st.session_state[
                "sisget_tela_fichas_extraorcamentarias"
            ] = "localizar"

            st.rerun()


# ============================================================
# EXTRAORÇAMENTÁRIA - EXCLUIR
# ============================================================

def ficha_extraorcamentaria_excluir():

    st.subheader(
        "🗑️ Excluir Ficha Extraorçamentária"
    )

    exercicio = st.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="extra_excluir_exercicio"
    )

    df = _sisget_dataframe(
        """
        SELECT
            x.id,
            x.numero_ficha AS "Ficha",
            e.codigo || ' - ' || e.nome AS "Entidade",
            u.codigo || ' - ' || u.nome AS "Unidade Orçamentária",
            x.tipo AS "Tipo",
            x.codigo AS "Código",
            x.descricao AS "Descrição",
            x.valor_inicial AS "Valor Inicial",
            x.valor_movimentado AS "Movimentado"
        FROM fichas_extraorcamentarias x
        INNER JOIN entidades e
            ON e.id = x.entidade_id
        INNER JOIN unidades_orcamentarias u
            ON u.id = x.unidade_orcamentaria_id
        WHERE x.exercicio = ?
        ORDER BY x.numero_ficha
        """,
        (
            int(exercicio),
        )
    )

    if df.empty:

        st.info(
            "Nenhuma Ficha Extraorçamentária cadastrada."
        )

        return

    ficha_id = sisget_grid_localizar(
        df=df,
        chave="excluir_fichas_extraorcamentarias",
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
            valor_movimentado
        FROM fichas_extraorcamentarias
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
    valor_movimentado = float(
        registro[2] or 0
    )

    st.error(
        f"⚠️ Ficha Extraorçamentária "
        f"**{numero_ficha} - {descricao}**"
    )

    if valor_movimentado > 0:

        st.warning(
            "🔒 Esta ficha possui movimentação. "
            "Inative a ficha em vez de excluí-la."
        )

        return

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta Ficha Extraorçamentária.",
        key=f"confirmar_excluir_extra_{ficha_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_extra_{ficha_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação."
            )

            return

        if _sisget_salvar(
            """
            DELETE FROM fichas_extraorcamentarias
            WHERE id = ?
            """,
            (
                ficha_id,
            )
        ):

            st.session_state[
                "sisget_tela_fichas_extraorcamentarias"
            ] = "principal"

            st.rerun()


# ============================================================
# EXTRAORÇAMENTÁRIA - IMPRIMIR
# ============================================================

def ficha_extraorcamentaria_imprimir():

    st.subheader(
        "🖨️ Relatório de Fichas Extraorçamentárias"
    )

    col1, col2 = st.columns(2)

    exercicio = col1.number_input(
        "Exercício",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="extra_imprimir_exercicio"
    )

    tipo_filtro = col2.selectbox(
        "Tipo",
        [
            "Todos",
            "Receita Extraorçamentária",
            "Despesa Extraorçamentária"
        ],
        key="extra_imprimir_tipo"
    )

    sql = """
        SELECT
            x.numero_ficha,
            u.codigo,
            u.nome,
            x.tipo,
            x.codigo,
            x.descricao,
            x.valor_inicial,
            x.valor_movimentado,
            x.ativo
        FROM fichas_extraorcamentarias x
        INNER JOIN unidades_orcamentarias u
            ON u.id = x.unidade_orcamentaria_id
        WHERE x.exercicio = ?
    """

    parametros = [
        int(exercicio)
    ]

    if tipo_filtro != "Todos":

        sql += """
            AND x.tipo = ?
        """

        parametros.append(
            tipo_filtro
        )

    sql += """
        ORDER BY
            u.codigo,
            x.numero_ficha
    """

    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )

    if not dados:

        st.info(
            "Nenhuma Ficha Extraorçamentária encontrada."
        )

        return

    tabela_dados = [[
        "Ficha",
        "Unidade",
        "Tipo",
        "Código",
        "Descrição",
        "Inicial",
        "Movimentado",
        "Situação"
    ]]

    total_inicial = 0
    total_movimentado = 0

    for registro in dados:

        inicial = float(
            registro[6] or 0
        )

        movimentado = float(
            registro[7] or 0
        )

        total_inicial += inicial
        total_movimentado += movimentado

        tabela_dados.append([
            str(registro[0]),
            f"{registro[1]} - {registro[2]}",
            str(registro[3] or ""),
            str(registro[4] or ""),
            str(registro[5] or ""),
            f"R$ {inicial:,.2f}",
            f"R$ {movimentado:,.2f}",
            (
                "Ativa"
                if registro[8]
                else "Inativa"
            )
        ])

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
    elementos = []

    elementos.append(
        Paragraph(
            "FICHAS EXTRAORÇAMENTÁRIAS",
            estilos["Title"]
        )
    )

    elementos.append(
        Paragraph(
            f"Exercício: {int(exercicio)}",
            estilos["Normal"]
        )
    )

    if tipo_filtro != "Todos":

        elementos.append(
            Paragraph(
                f"Tipo: {tipo_filtro}",
                estilos["Normal"]
            )
        )

    elementos.append(
        Spacer(
            1,
            0.4 * cm
        )
    )

    tabela = Table(
        tabela_dados,
        colWidths=[
            1.0 * cm,
            3.0 * cm,
            3.4 * cm,
            1.8 * cm,
            4.0 * cm,
            2.1 * cm,
            2.1 * cm,
            1.7 * cm
        ],
        repeatRows=1
    )

    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 6)
        ])
    )

    elementos.append(
        tabela
    )

    elementos.append(
        Spacer(
            1,
            0.4 * cm
        )
    )

    elementos.append(
        Paragraph(
            f"Valor Inicial: R$ {total_inicial:,.2f}",
            estilos["Normal"]
        )
    )

    elementos.append(
        Paragraph(
            f"Movimentado: R$ {total_movimentado:,.2f}",
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
            f"fichas_extraorcamentarias_"
            f"{int(exercicio)}.pdf"
        ),
        mime="application/pdf",
        use_container_width=True,
        key="baixar_pdf_fichas_extra"
    )


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

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_funcao()
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_funcao_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        # ====================================================
        # CÓDIGO AUTOMÁTICO / BLOQUEADO
        # ====================================================

        col1.text_input(
            "Código *",
            value=codigo,
            disabled=True
        )

        # ====================================================
        # DESCRIÇÃO
        # ====================================================

        descricao = col2.text_input(
            "Descrição *",
            max_chars=200
        )

        salvar = st.form_submit_button(
            "💾 Salvar",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        descricao = (
            descricao.strip()
        )

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO ANTES DE SALVAR
        # ====================================================

        codigo = (
            sisget_proximo_codigo_funcao()
        )

        # ====================================================
        # VERIFICAR DUPLICIDADE
        # ====================================================

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
                "⚠️ Esta Função já está cadastrada."
            )

            return

        # ====================================================
        # SALVAR
        # ====================================================

        sucesso = _sisget_salvar(
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
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            st.success(
                f"✅ Função cadastrada com sucesso! "
                f"Código: {codigo}"
            )

            st.rerun()


# ============================================================
# FUNÇÃO - LOCALIZAR
# ============================================================
# ============================================================
# FUNÇÃO - LOCALIZAR
# ============================================================

def sisget_proximo_codigo_funcao():

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM funcoes_orcamentarias
        ORDER BY codigo
        """
    )

    codigos_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            codigos_usados.add(
                int(codigo)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    proximo = 1

    while proximo in codigos_usados:

        proximo += 1

    return str(
        proximo
    ).zfill(2)
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

def planejamento_subfuncoes_orcamentarias():

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

    # ========================================================
    # CARREGAR FUNÇÕES
    # ========================================================

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
            "⚠️ Cadastre uma Função primeiro."
        )

        return

    # ========================================================
    # MAPA DAS FUNÇÕES
    # ========================================================

    mapa = {
        f"{codigo} - {descricao}": id_
        for (
            id_,
            codigo,
            descricao
        ) in funcoes
    }

    # ========================================================
    # SELECIONAR FUNÇÃO
    # ========================================================

    funcao_nome = st.selectbox(
        "Função *",
        list(
            mapa.keys()
        ),
        key="subfuncao_incluir_funcao"
    )

    funcao_id = mapa[
        funcao_nome
    ]

    # ========================================================
    # CÓDIGO AUTOMÁTICO
    # ========================================================

    codigo = (
        sisget_proximo_codigo_subfuncao(
            funcao_id
        )
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        "form_subfuncao_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        # ====================================================
        # CÓDIGO AUTOMÁTICO / BLOQUEADO
        # ====================================================

        col1.text_input(
            "Código *",
            value=codigo,
            disabled=True
        )

        # ====================================================
        # DESCRIÇÃO
        # ====================================================

        descricao = col2.text_input(
            "Descrição *"
        )

        salvar = (
            st.form_submit_button(
                "💾 Salvar",
                type="primary",
                use_container_width=True
            )
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        descricao = (
            descricao.strip()
        )

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        # ====================================================
        # RECALCULAR CÓDIGO ANTES DE SALVAR
        # ====================================================

        codigo = (
            sisget_proximo_codigo_subfuncao(
                funcao_id
            )
        )

        # ====================================================
        # VERIFICAR DUPLICIDADE
        # ====================================================

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
                "⚠️ Subfunção já cadastrada."
            )

            return

        # ====================================================
        # INSERT
        # ====================================================

        sucesso = _sisget_salvar(
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
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        if sucesso:

            st.success(
                f"✅ Subfunção cadastrada com sucesso! "
                f"Código: {codigo}"
            )

            st.rerun()
def sisget_proximo_codigo_subfuncao(
    funcao_id
):

    dados = _sisget_fetch(
        """
        SELECT codigo
        FROM subfuncoes_orcamentarias
        WHERE funcao_id = ?
        ORDER BY codigo
        """,
        (
            funcao_id,
        )
    )

    codigos_usados = set()

    for registro in dados:

        codigo = str(
            registro[0] or ""
        ).strip()

        try:

            codigos_usados.add(
                int(codigo)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    proximo = 1

    while proximo in codigos_usados:

        proximo += 1

    return str(
        proximo
    ).zfill(3)
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

def planejamento_programas_orcamentarios():

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

def planejamento_acoes_orcamentarias():

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

# ============================================================
# SISGET - MÓDULO DE SOLICITAÇÕES
# ============================================================
# Estrutura:
#   Fornecedores
#   Grupos
#   Subgrupos
#   Produtos
#   Unidades
#   Solicitações:
#       Interna
#       Licitação
#       Compra
#   Planejamento de Compras
#
# Fluxo da Solicitação para Licitação:
# Solicitação -> Aprovação -> DFD -> ETP -> Mapa de Riscos
# -> Compras/Cotação -> Contabilidade/Fichas -> Financeiro
# -> Ordenador -> Enquadramento Licitação -> TR
# -> Liberação para módulo de Licitações/Contratação Direta
# ============================================================


# ============================================================
# AUXILIAR - PRÓXIMO CÓDIGO
# ============================================================

def sisget_proximo_codigo(
    tabela,
    campo="codigo",
    tamanho=3,
    filtro_sql="",
    parametros=()
):
    dados = _sisget_fetch(
        f"""
        SELECT {campo}
        FROM {tabela}
        WHERE {campo} IS NOT NULL
        {filtro_sql}
        ORDER BY {campo}
        """,
        parametros
    )

    usados = set()

    for registro in dados:
        valor = str(registro[0] or "").strip()

        try:
            usados.add(int(valor))
        except (ValueError, TypeError):
            pass

    proximo = 1

    while proximo in usados:
        proximo += 1

    return str(proximo).zfill(tamanho)


# ============================================================
# AUXILIAR - PRÓXIMO NÚMERO SOLICITAÇÃO
# ============================================================

def sisget_proximo_numero_solicitacao(
    tipo_solicitacao=None,
    exercicio=None
):

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    if exercicio is None:

        exercicio = datetime.now().year

    # ========================================================
    # SQL
    # ========================================================

    sql = """
        SELECT
            MAX(
                CASE

                    WHEN TRIM(
                        numero::TEXT
                    ) ~ '^[0-9]+$'

                    THEN TRIM(
                        numero::TEXT
                    )::BIGINT

                    ELSE NULL

                END
            )

        FROM solicitacoes

        WHERE 1 = 1
    """

    parametros = []

    # ========================================================
    # TIPO
    # ========================================================

    if tipo_solicitacao is not None:

        sql += """
            AND tipo_solicitacao = ?
        """

        parametros.append(
            tipo_solicitacao
        )

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    if exercicio is not None:

        sql += """
            AND exercicio = ?
        """

        parametros.append(
            int(exercicio)
        )

    # ========================================================
    # CONSULTA
    # ========================================================

    registro = _sisget_fetchone(
        sql,
        tuple(
            parametros
        )
    )

    # ========================================================
    # ERRO DE CONSULTA
    # ========================================================

    if registro is None:

        st.error(
            "❌ Não foi possível gerar "
            "o número da solicitação."
        )

        return None

    # ========================================================
    # PRIMEIRA SOLICITAÇÃO
    # ========================================================

    if registro[0] is None:

        return 1

    # ========================================================
    # PRÓXIMO NÚMERO
    # ========================================================

    return int(
        registro[0]
    ) + 1

def modulo_solicitacoes():

    st.title("📝 Solicitações")

    st.caption(
        "Cadastros, solicitações e planejamento de compras."
    )

    st.divider()

    modulo = st.selectbox(
        "Módulo *",
        options=[
            "Selecione...",
            "🏢 Fornecedores",
            "📁 Grupos",
            "📂 Subgrupos",
            "📦 Produtos",
            "📏 Unidades",
            "📝 Solicitações",
            "📊 Planejamento de Compras"
        ],
        key="sisget_modulo_solicitacoes"
    )

    st.divider()

    if modulo == "Selecione...":
        st.info("Selecione um módulo acima para continuar.")
        return

    elif modulo == "🏢 Fornecedores":
        cadastro_fornecedores()

    elif modulo == "📁 Grupos":
        cadastro_grupos_produtos()

    elif modulo == "📂 Subgrupos":
        cadastro_subgrupos_produtos()

    elif modulo == "📦 Produtos":
        cadastro_produtos()

    elif modulo == "📏 Unidades":
        modulo_unidades_produtos()

    elif modulo == "📝 Solicitações":
        modulo_tipos_solicitacoes()

    elif modulo == "📊 Planejamento de Compras":
        modulo_planejamento_compras()


# ============================================================
# FORNECEDORES
# ============================================================

# ============================================================
# FORNECEDORES - TELA PRINCIPAL
# ============================================================

def cadastro_fornecedores():

    sisget_tela_principal(
        titulo="Fornecedores",
        chave="fornecedores",

        func_incluir=fornecedor_incluir,

        func_localizar=fornecedor_localizar,

        func_alterar=fornecedor_alterar,

        func_excluir=fornecedor_excluir,

        func_imprimir=fornecedor_imprimir,

        icone="🏢",

        botoes_extras=[
            {
                "titulo": "👥 Representantes",
                "tela": "representantes",
                "funcao": fornecedor_representantes_principal
            },
            {
                "titulo": "📑 Regularidades / Documentos",
                "tela": "documentos",
                "funcao": fornecedor_documentos_principal
            }
        ]
    )

# ============================================================
# REPRESENTANTES - ACESSO PRINCIPAL
# SOMENTE FORNECEDORES PESSOA JURÍDICA
# ============================================================

def fornecedor_representantes_principal():

    fornecedores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            razao_social,
            cpf_cnpj
        FROM fornecedores
        WHERE ativo = TRUE
          AND tipo_pessoa = 'Jurídica'
        ORDER BY
            razao_social,
            codigo
        """
    )

    if not fornecedores:
        st.info(
            "Nenhum fornecedor Pessoa Jurídica cadastrado."
        )
        return

    mapa_fornecedores = {}

    for registro in fornecedores:

        fornecedor_id = registro[0]
        codigo = registro[1]
        razao_social = registro[2]
        cnpj = registro[3]

        descricao = (
            f"{codigo} - "
            f"{razao_social} - "
            f"{cnpj or ''}"
        )

        mapa_fornecedores[
            descricao
        ] = fornecedor_id

    fornecedor_selecionado = st.selectbox(
        "Fornecedor *",
        list(
            mapa_fornecedores.keys()
        ),
        key="sisget_representante_fornecedor"
    )

    fornecedor_id = mapa_fornecedores[
        fornecedor_selecionado
    ]

    st.markdown("---")

    fornecedor_representantes(
        fornecedor_id
    )
def fornecedor_documentos_principal():

    st.subheader(
        "📑 Regularidades e Documentos"
    )

    fornecedores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            razao_social
        FROM fornecedores
        WHERE ativo = TRUE
        ORDER BY
            razao_social,
            codigo
        """
    )

    if not fornecedores:

        st.info(
            "Nenhum fornecedor ativo cadastrado."
        )

        return

    mapa = {
        f"{codigo} - {razao_social}": id_
        for id_, codigo, razao_social
        in fornecedores
    }

    fornecedor_nome = st.selectbox(
        "Fornecedor *",
        list(
            mapa.keys()
        ),
        key="sisget_doc_fornecedor_principal"
    )

    fornecedor_id = mapa[
        fornecedor_nome
    ]

    st.divider()

    fornecedor_regularidades_documentos(
        fornecedor_id
    )

# ============================================================
# CONSULTAR CNPJ
# ============================================================

# ============================================================
# CONSULTAR CNPJ DO FORNECEDOR
# ============================================================

def consultar_cnpj_fornecedor(
    cnpj,
    importar_todos_cnaes=True
):

    try:

        # ====================================================
        # LIMPAR CNPJ
        # ====================================================

        cnpj_limpo = re.sub(
            r"[^0-9A-Za-z]",
            "",
            str(cnpj)
        ).upper()

        if len(cnpj_limpo) != 14:

            st.warning(
                "⚠️ Informe um CNPJ válido com 14 caracteres."
            )

            return None

        # ====================================================
        # CONSULTA
        # ====================================================

        url = (
            "https://brasilapi.com.br/api/cnpj/v1/"
            f"{cnpj_limpo}"
        )

        resposta = requests.get(
            url,
            timeout=20
        )

        if resposta.status_code == 404:

            st.warning(
                "⚠️ CNPJ não encontrado."
            )

            return None

        if resposta.status_code == 400:

            st.warning(
                "⚠️ CNPJ inválido."
            )

            return None

        if resposta.status_code != 200:

            st.error(
                "❌ Não foi possível consultar o CNPJ."
            )

            return None

        dados = resposta.json()

        # ====================================================
        # CNAE PRINCIPAL
        # ====================================================

        cnae_codigo = str(
            dados.get(
                "cnae_fiscal"
            )
            or ""
        )

        cnae_descricao = (
            dados.get(
                "cnae_fiscal_descricao"
            )
            or ""
        )

        if cnae_codigo and cnae_descricao:

            cnae_principal = (
                f"{cnae_codigo} - "
                f"{cnae_descricao}"
            )

        else:

            cnae_principal = (
                cnae_codigo
                or cnae_descricao
                or ""
            )

        # ====================================================
        # TODOS OS CNAES
        # ====================================================

        lista_cnaes = []

        if cnae_principal:

            lista_cnaes.append(
                {
                    "codigo": cnae_codigo,
                    "descricao": cnae_descricao,
                    "tipo": "Principal"
                }
            )

        if importar_todos_cnaes:

            cnaes_secundarios = (
                dados.get(
                    "cnaes_secundarios"
                )
                or []
            )

            for item in cnaes_secundarios:

                codigo_secundario = str(
                    item.get(
                        "codigo"
                    )
                    or ""
                )

                descricao_secundaria = (
                    item.get(
                        "descricao"
                    )
                    or ""
                )

                if (
                    codigo_secundario
                    or descricao_secundaria
                ):

                    lista_cnaes.append(
                        {
                            "codigo": codigo_secundario,
                            "descricao": descricao_secundaria,
                            "tipo": "Secundário"
                        }
                    )

        # ====================================================
        # TEXTO COM TODOS OS CNAES
        # ====================================================

        linhas_cnaes = []

        for item in lista_cnaes:

            codigo_item = (
                item.get(
                    "codigo"
                )
                or ""
            )

            descricao_item = (
                item.get(
                    "descricao"
                )
                or ""
            )

            tipo_item = (
                item.get(
                    "tipo"
                )
                or ""
            )

            linhas_cnaes.append(
                f"{codigo_item} - "
                f"{descricao_item} "
                f"({tipo_item})"
            )

        todos_cnaes_texto = "\n".join(
            linhas_cnaes
        )

        # ====================================================
        # TELEFONE
        # ====================================================

        telefone1 = str(
            dados.get(
                "ddd_telefone_1"
            )
            or ""
        ).strip()

        telefone2 = str(
            dados.get(
                "ddd_telefone_2"
            )
            or ""
        ).strip()

        telefone = (
            telefone1
            if telefone1
            else telefone2
        )

        # ====================================================
        # RETORNO
        # ====================================================

        return {

            "cnpj": (
                dados.get(
                    "cnpj"
                )
                or cnpj_limpo
            ),

            "razao_social": (
                dados.get(
                    "razao_social"
                )
                or ""
            ),

            "nome_fantasia": (
                dados.get(
                    "nome_fantasia"
                )
                or ""
            ),

            "natureza_juridica": (
                dados.get(
                    "natureza_juridica"
                )
                or ""
            ),

            "porte": (
                dados.get(
                    "porte"
                )
                or ""
            ),

            "cnae": (
                cnae_principal
            ),

            "cnae_descricao": (
                cnae_descricao
            ),

            "todos_cnaes": (
                todos_cnaes_texto
            ),

            "lista_cnaes": (
                lista_cnaes
            ),

            "telefone": (
                telefone
            ),

            "email": (
                dados.get(
                    "email"
                )
                or ""
            ),

            "cep": str(
                dados.get(
                    "cep"
                )
                or ""
            ),

            "logradouro": (
                dados.get(
                    "logradouro"
                )
                or ""
            ),

            "numero": str(
                dados.get(
                    "numero"
                )
                or ""
            ),

            "complemento": (
                dados.get(
                    "complemento"
                )
                or ""
            ),

            "bairro": (
                dados.get(
                    "bairro"
                )
                or ""
            ),

            "cidade": (
                dados.get(
                    "municipio"
                )
                or ""
            ),

            "uf": (
                dados.get(
                    "uf"
                )
                or ""
            ),

            "situacao_receita": (
                dados.get(
                    "descricao_situacao_cadastral"
                )
                or ""
            ),

            "data_abertura": (
                dados.get(
                    "data_inicio_atividade"
                )
                or None
            ),

            "fonte": (
                "Consulta pública de CNPJ"
            )
        }

    except requests.exceptions.Timeout:

        st.error(
            "❌ A consulta demorou demais. "
            "Tente novamente."
        )

        return None

    except requests.exceptions.RequestException as erro:

        st.error(
            f"❌ Erro de comunicação: {erro}"
        )

        return None

    except Exception as erro:

        st.error(
            f"❌ Erro ao consultar CNPJ: {erro}"
        )

        return None

# ============================================================
# FORNECEDOR - INCLUIR
# ============================================================

def fornecedor_incluir():

    # ========================================================
    # RESET
    # ========================================================

    if "sisget_fornecedor_reset" not in st.session_state:

        st.session_state[
            "sisget_fornecedor_reset"
        ] = 0

    reset = st.session_state[
        "sisget_fornecedor_reset"
    ]

    # ========================================================
    # DADOS DA CONSULTA
    # ========================================================

    if "sisget_fornecedor_receita" not in st.session_state:

        st.session_state[
            "sisget_fornecedor_receita"
        ] = {}

    dados_receita = st.session_state[
        "sisget_fornecedor_receita"
    ]

    # ========================================================
    # MENSAGEM
    # ========================================================

    if "sisget_mensagem_fornecedor" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_fornecedor"
            )
        )

    # ========================================================
    # CÓDIGO
    # ========================================================

    codigo = sisget_proximo_codigo(
        "fornecedores",
        tamanho=6
    )

    # ========================================================
    # TIPO DE PESSOA
    # FORA DO FORM, MAS VISUALMENTE DENTRO DO BLOCO
    # ========================================================

    st.markdown(
        "### 🏢 Dados Gerais"
    )

    col_tipo1, col_tipo2 = st.columns(
        [1, 3]
    )

    col_tipo1.text_input(
        "Código",
        value=codigo,
        disabled=True,
        key=f"fornecedor_codigo_{reset}"
    )

    tipo_pessoa = col_tipo2.selectbox(
        "Tipo de Pessoa *",
        [
            "Jurídica",
            "Física"
        ],
        key=f"fornecedor_tipo_pessoa_{reset}"
    )

    # ========================================================
    # CNPJ + CONSULTAR
    # ========================================================

    if tipo_pessoa == "Jurídica":

        col_cnpj1, col_cnpj2 = st.columns(
            [4, 1]
        )

        cnpj_consulta = col_cnpj1.text_input(
            "CNPJ *",
            value=(
                dados_receita.get(
                    "cnpj",
                    ""
                )
            ),
            key=f"fornecedor_cnpj_consulta_{reset}"
        )

        consultar = col_cnpj2.button(
            "🔎 Consultar CNPJ",
            use_container_width=True,
            key=f"fornecedor_consultar_cnpj_{reset}"
        )

        if consultar:

            if not cnpj_consulta.strip():

                st.warning(
                    "⚠️ Informe o CNPJ."
                )

                return

            with st.spinner(
                "Consultando CNPJ..."
            ):

                dados = consultar_cnpj_fornecedor(
                    cnpj_consulta,
                    True
                )

            if dados:

                st.session_state[
                    "sisget_fornecedor_receita"
                ] = dados

                st.rerun()

        dados_receita = st.session_state.get(
            "sisget_fornecedor_receita",
            {}
        )

        if dados_receita:

            situacao_receita = (
                dados_receita.get(
                    "situacao_receita",
                    ""
                )
            )

            if str(
                situacao_receita
            ).upper() == "ATIVA":

                st.success(
                    f"✅ Situação Cadastral: "
                    f"{situacao_receita}"
                )

            elif situacao_receita:

                st.warning(
                    f"⚠️ Situação Cadastral: "
                    f"{situacao_receita}"
                )

    else:

        # ====================================================
        # PESSOA FÍSICA
        # ====================================================

        cnpj_consulta = ""

        dados_receita = {}

    st.markdown("---")

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_fornecedor_incluir_{reset}"
    ):

        # ====================================================
        # DADOS PRINCIPAIS
        # ====================================================

        if tipo_pessoa == "Jurídica":

            cpf_cnpj = st.text_input(
                "CNPJ *",
                value=(
                    dados_receita.get(
                        "cnpj",
                        ""
                    )
                )
            )

        else:

            cpf_cnpj = st.text_input(
                "CPF *"
            )

        col1, col2 = st.columns(2)

        razao_social = col1.text_input(
            (
                "Razão Social *"
                if tipo_pessoa == "Jurídica"
                else "Nome *"
            ),
            value=(
                dados_receita.get(
                    "razao_social",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        nome_fantasia = col2.text_input(
            "Nome Fantasia",
            value=(
                dados_receita.get(
                    "nome_fantasia",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            ),
            disabled=(
                tipo_pessoa == "Física"
            )
        )

        # ====================================================
        # CAMPOS DA PESSOA JURÍDICA
        # ====================================================

        if tipo_pessoa == "Jurídica":

            col3, col4 = st.columns(2)

            natureza_juridica = col3.text_input(
                "Natureza Jurídica",
                value=(
                    dados_receita.get(
                        "natureza_juridica",
                        ""
                    )
                )
            )

            col4.text_input(
                "Situação na Receita",
                value=(
                    dados_receita.get(
                        "situacao_receita",
                        ""
                    )
                ),
                disabled=True
            )

            col5, col6 = st.columns(2)

            inscricao_estadual = col5.text_input(
                "Inscrição Estadual"
            )

            inscricao_municipal = col6.text_input(
                "Inscrição Municipal"
            )

            # =================================================
            # PORTE
            # =================================================

            portes = [
                "Não informado",
                "MEI",
                "ME",
                "EPP",
                "Demais"
            ]

            porte_receita = str(
                dados_receita.get(
                    "porte",
                    ""
                )
            ).upper()

            indice_porte = 0

            if "MICRO EMPRESA" in porte_receita:

                indice_porte = 2

            elif (
                "EMPRESA DE PEQUENO PORTE"
                in porte_receita
            ):

                indice_porte = 3

            elif porte_receita:

                indice_porte = 4

            col7, col8 = st.columns(2)

            porte_empresa = col7.selectbox(
                "Porte",
                portes,
                index=indice_porte
            )

            optante_simples = col8.selectbox(
                "Simples Nacional",
                [
                    "Não informado",
                    "Sim",
                    "Não"
                ]
            )

            # =================================================
            # CNAES
            # =================================================

            st.markdown(
                "### 📚 Atividades Econômicas"
            )

            cnae = st.text_input(
                "CNAE Principal",
                value=(
                    dados_receita.get(
                        "cnae",
                        ""
                    )
                )
            )

            todos_cnaes = st.text_area(
                "Todos os CNAEs",
                value=(
                    dados_receita.get(
                        "todos_cnaes",
                        ""
                    )
                ),
                height=180
            )

            categoria_fornecedor = st.text_input(
                "Categoria / Ramo de Atividade",
                value=(
                    dados_receita.get(
                        "cnae_descricao",
                        ""
                    )
                )
            )

        else:

            natureza_juridica = ""
            inscricao_estadual = ""
            inscricao_municipal = ""
            porte_empresa = "Não informado"
            optante_simples = "Não informado"
            cnae = ""
            todos_cnaes = ""

            categoria_fornecedor = st.text_input(
                "Categoria / Atividade"
            )

        # ====================================================
        # CONTATO
        # ====================================================

        st.markdown(
            "### ☎️ Contato"
        )

        col9, col10 = st.columns(2)

        telefone = col9.text_input(
            "Telefone",
            value=(
                dados_receita.get(
                    "telefone",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        whatsapp = col10.text_input(
            "WhatsApp"
        )

        col11, col12 = st.columns(2)

        email = col11.text_input(
            "E-mail",
            value=(
                dados_receita.get(
                    "email",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        site = col12.text_input(
            "Site"
        )

        # ====================================================
        # ENDEREÇO
        # ====================================================

        st.markdown(
            "### 📍 Endereço"
        )

        col13, col14, col15 = st.columns(
            [1, 3, 1]
        )

        cep = col13.text_input(
            "CEP",
            value=(
                dados_receita.get(
                    "cep",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        logradouro = col14.text_input(
            "Logradouro",
            value=(
                dados_receita.get(
                    "logradouro",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        numero_endereco = col15.text_input(
            "Número",
            value=(
                dados_receita.get(
                    "numero",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        col16, col17 = st.columns(2)

        complemento = col16.text_input(
            "Complemento",
            value=(
                dados_receita.get(
                    "complemento",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        bairro = col17.text_input(
            "Bairro",
            value=(
                dados_receita.get(
                    "bairro",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        col18, col19, col20 = st.columns(
            [2, 1, 1]
        )

        cidade = col18.text_input(
            "Cidade",
            value=(
                dados_receita.get(
                    "cidade",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            )
        )

        uf = col19.text_input(
            "UF",
            value=(
                dados_receita.get(
                    "uf",
                    ""
                )
                if tipo_pessoa == "Jurídica"
                else ""
            ),
            max_chars=2
        )

        pais = col20.text_input(
            "País",
            value="Brasil"
        )

        # ====================================================
        # DADOS BANCÁRIOS
        # ====================================================

        st.markdown(
            "### 🏦 Dados Bancários"
        )

        col21, col22 = st.columns(2)

        banco = col21.text_input(
            "Banco"
        )

        codigo_banco = col22.text_input(
            "Código do Banco"
        )

        col23, col24, col25 = st.columns(3)

        agencia = col23.text_input(
            "Agência"
        )

        conta = col24.text_input(
            "Conta"
        )

        tipo_conta = col25.selectbox(
            "Tipo da Conta",
            [
                "Não informado",
                "Corrente",
                "Poupança",
                "Pagamento"
            ]
        )

        col26, col27 = st.columns(2)

        tipo_chave_pix = col26.selectbox(
            "Tipo da Chave Pix",
            [
                "Não informado",
                "CPF",
                "CNPJ",
                "E-mail",
                "Telefone",
                "Aleatória"
            ]
        )

        chave_pix = col27.text_input(
            "Chave Pix"
        )

        # ====================================================
        # OBSERVAÇÕES
        # ====================================================

        st.markdown(
            "### 📝 Observações"
        )

        observacoes = st.text_area(
            "Observações Gerais",
            height=120
        )

        salvar = st.form_submit_button(
            "💾 Salvar Fornecedor",
            type="primary",
            use_container_width=True
        )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        cpf_cnpj = cpf_cnpj.strip()
        razao_social = razao_social.strip()

        if not cpf_cnpj:

            st.warning(
                "⚠️ Informe CPF/CNPJ."
            )

            return

        if not razao_social:

            st.warning(
                "⚠️ Informe Razão Social/Nome."
            )

            return

        existe = _sisget_fetchone(
            """
            SELECT id
            FROM fornecedores
            WHERE cpf_cnpj = ?
            """,
            (
                cpf_cnpj,
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe fornecedor com "
                "este CPF/CNPJ."
            )

            return

        codigo = sisget_proximo_codigo(
            "fornecedores",
            tamanho=6
        )

        situacao_receita = None
        data_abertura = None
        fonte_dados = None

        if tipo_pessoa == "Jurídica":

            situacao_receita = (
                dados_receita.get(
                    "situacao_receita"
                )
                or None
            )

            data_abertura = (
                dados_receita.get(
                    "data_abertura"
                )
                or None
            )

            fonte_dados = (
                dados_receita.get(
                    "fonte"
                )
                or None
            )

        sucesso = _sisget_salvar(
            """
            INSERT INTO fornecedores
            (
                codigo,
                tipo_pessoa,
                cpf_cnpj,
                razao_social,
                nome_fantasia,
                natureza_juridica,
                inscricao_estadual,
                inscricao_municipal,
                porte_empresa,
                optante_simples,
                cnae,
                todos_cnaes,
                categoria_fornecedor,

                telefone,
                whatsapp,
                email,
                site,

                cep,
                logradouro,
                numero_endereco,
                complemento,
                bairro,
                cidade,
                uf,
                pais,

                banco,
                codigo_banco,
                agencia,
                conta,
                tipo_conta,
                tipo_chave_pix,
                chave_pix,

                situacao_receita,
                data_abertura,
                consulta_receita_em,
                fonte_dados_cnpj,

                observacoes,

                ativo,
                criado_em
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?,
                TRUE,
                CURRENT_TIMESTAMP
            )
            """,
            (
                codigo,
                tipo_pessoa,
                cpf_cnpj,
                razao_social,

                nome_fantasia.strip()
                or None,

                natureza_juridica.strip()
                or None,

                inscricao_estadual.strip()
                or None,

                inscricao_municipal.strip()
                or None,

                None
                if porte_empresa == "Não informado"
                else porte_empresa,

                None
                if optante_simples == "Não informado"
                else optante_simples,

                cnae.strip()
                or None,

                todos_cnaes.strip()
                or None,

                categoria_fornecedor.strip()
                or None,

                telefone.strip()
                or None,

                whatsapp.strip()
                or None,

                email.strip()
                or None,

                site.strip()
                or None,

                cep.strip()
                or None,

                logradouro.strip()
                or None,

                numero_endereco.strip()
                or None,

                complemento.strip()
                or None,

                bairro.strip()
                or None,

                cidade.strip()
                or None,

                uf.strip().upper()
                or None,

                pais.strip()
                or None,

                banco.strip()
                or None,

                codigo_banco.strip()
                or None,

                agencia.strip()
                or None,

                conta.strip()
                or None,

                None
                if tipo_conta == "Não informado"
                else tipo_conta,

                None
                if tipo_chave_pix == "Não informado"
                else tipo_chave_pix,

                chave_pix.strip()
                or None,

                situacao_receita,

                data_abertura,

                fonte_dados,

                observacoes.strip()
                or None
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_fornecedor"
            ] = (
                f"✅ Fornecedor cadastrado. "
                f"Código: {codigo}"
            )

            st.session_state.pop(
                "sisget_fornecedor_receita",
                None
            )

            st.session_state[
                "sisget_fornecedor_reset"
            ] += 1

            st.rerun()
def fornecedor_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            id,

            codigo AS "Código",

            cpf_cnpj AS "CPF / CNPJ",

            razao_social AS "Razão Social / Nome",

            nome_fantasia AS "Nome Fantasia",

            categoria_fornecedor AS "Categoria",

            telefone AS "Telefone",

            whatsapp AS "WhatsApp",

            email AS "E-mail",

            cidade AS "Cidade",

            uf AS "UF",

            CASE
                WHEN ativo THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"

        FROM fornecedores

        ORDER BY
            razao_social,
            codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhum fornecedor cadastrado."
        )

        return None

    st.caption(
        "Dê duplo clique no fornecedor "
        "para alterar."
    )

    registro_id = sisget_grid_localizar(
        df=df,
        chave="fornecedores_localizar",
        coluna_id="id",
        altura=500
    )

    return registro_id
# ============================================================
# FORNECEDOR - ALTERAR
# ============================================================

# ============================================================
# FORNECEDOR - ALTERAR
# ============================================================

def fornecedor_alterar(
    registro_id
):

    # ========================================================
    # BUSCAR FORNECEDOR
    # ========================================================

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            tipo_pessoa,
            cpf_cnpj,
            razao_social,
            nome_fantasia,
            natureza_juridica,
            inscricao_estadual,
            inscricao_municipal,
            porte_empresa,
            optante_simples,
            cnae,
            categoria_fornecedor,

            telefone,
            whatsapp,
            email,
            site,

            cep,
            logradouro,
            numero_endereco,
            complemento,
            bairro,
            cidade,
            uf,
            pais,

            banco,
            codigo_banco,
            agencia,
            conta,
            tipo_conta,
            tipo_chave_pix,
            chave_pix,

            observacoes,

            ativo

        FROM fornecedores

        WHERE id = ?
        """,
        (
            registro_id,
        )
    )

    if not registro:

        st.warning(
            "⚠️ Fornecedor não encontrado."
        )

        return

    (
        codigo,
        tipo_atual,
        cpf_cnpj_atual,
        razao_social_atual,
        nome_fantasia_atual,
        natureza_juridica_atual,
        inscricao_estadual_atual,
        inscricao_municipal_atual,
        porte_atual,
        simples_atual,
        cnae_atual,
        categoria_atual,

        telefone_atual,
        whatsapp_atual,
        email_atual,
        site_atual,

        cep_atual,
        logradouro_atual,
        numero_atual,
        complemento_atual,
        bairro_atual,
        cidade_atual,
        uf_atual,
        pais_atual,

        banco_atual,
        codigo_banco_atual,
        agencia_atual,
        conta_atual,
        tipo_conta_atual,
        tipo_pix_atual,
        chave_pix_atual,

        observacoes_atual,

        ativo
    ) = registro

    # ========================================================
    # LISTAS
    # ========================================================

    tipos_pessoa = [
        "Jurídica",
        "Física"
    ]

    portes = [
        "Não informado",
        "MEI",
        "ME",
        "EPP",
        "Demais"
    ]

    simples_opcoes = [
        "Não informado",
        "Sim",
        "Não"
    ]

    tipos_conta = [
        "Não informado",
        "Corrente",
        "Poupança",
        "Pagamento"
    ]

    tipos_pix = [
        "Não informado",
        "CPF",
        "CNPJ",
        "E-mail",
        "Telefone",
        "Aleatória"
    ]

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.info(
        f"🏢 Fornecedor: "
        f"{codigo} - "
        f"{razao_social_atual or ''}"
    )

    # ========================================================
    # FORMULÁRIO
    # ========================================================

    with st.form(
        f"form_fornecedor_alterar_{registro_id}"
    ):

        # ====================================================
        # DADOS GERAIS
        # ====================================================

        st.markdown(
            "### 🏢 Dados Gerais"
        )

        col1, col2 = st.columns(
            [1, 3]
        )

        col1.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        tipo_pessoa = col2.selectbox(
            "Tipo de Pessoa *",
            tipos_pessoa,
            index=(
                tipos_pessoa.index(
                    tipo_atual
                )
                if tipo_atual
                in tipos_pessoa
                else 0
            )
        )

        col3, col4 = st.columns(2)

        cpf_cnpj = col3.text_input(
            "CPF / CNPJ *",
            value=cpf_cnpj_atual or ""
        )

        razao_social = col4.text_input(
            "Razão Social / Nome *",
            value=razao_social_atual or ""
        )

        col5, col6 = st.columns(2)

        nome_fantasia = col5.text_input(
            "Nome Fantasia",
            value=nome_fantasia_atual or ""
        )

        natureza_juridica = col6.text_input(
            "Natureza Jurídica",
            value=natureza_juridica_atual or ""
        )

        col7, col8 = st.columns(2)

        inscricao_estadual = col7.text_input(
            "Inscrição Estadual",
            value=inscricao_estadual_atual or ""
        )

        inscricao_municipal = col8.text_input(
            "Inscrição Municipal",
            value=inscricao_municipal_atual or ""
        )

        col9, col10, col11 = st.columns(3)

        porte_empresa = col9.selectbox(
            "Porte",
            portes,
            index=(
                portes.index(
                    porte_atual
                )
                if porte_atual
                in portes
                else 0
            )
        )

        optante_simples = col10.selectbox(
            "Simples Nacional",
            simples_opcoes,
            index=(
                simples_opcoes.index(
                    simples_atual
                )
                if simples_atual
                in simples_opcoes
                else 0
            )
        )

        cnae = col11.text_input(
            "CNAE Principal",
            value=cnae_atual or ""
        )

        categoria_fornecedor = st.text_input(
            "Categoria / Ramo de Atividade",
            value=categoria_atual or ""
        )

        # ====================================================
        # CONTATO
        # ====================================================

        st.markdown(
            "### ☎️ Contato"
        )

        col12, col13 = st.columns(2)

        telefone = col12.text_input(
            "Telefone",
            value=telefone_atual or ""
        )

        whatsapp = col13.text_input(
            "WhatsApp",
            value=whatsapp_atual or ""
        )

        col14, col15 = st.columns(2)

        email = col14.text_input(
            "E-mail",
            value=email_atual or ""
        )

        site = col15.text_input(
            "Site",
            value=site_atual or ""
        )

        # ====================================================
        # ENDEREÇO
        # ====================================================

        st.markdown(
            "### 📍 Endereço"
        )

        col16, col17, col18 = st.columns(
            [1, 3, 1]
        )

        cep = col16.text_input(
            "CEP",
            value=cep_atual or ""
        )

        logradouro = col17.text_input(
            "Logradouro",
            value=logradouro_atual or ""
        )

        numero_endereco = col18.text_input(
            "Número",
            value=numero_atual or ""
        )

        col19, col20 = st.columns(2)

        complemento = col19.text_input(
            "Complemento",
            value=complemento_atual or ""
        )

        bairro = col20.text_input(
            "Bairro",
            value=bairro_atual or ""
        )

        col21, col22, col23 = st.columns(
            [2, 1, 1]
        )

        cidade = col21.text_input(
            "Cidade",
            value=cidade_atual or ""
        )

        uf = col22.text_input(
            "UF",
            value=uf_atual or "",
            max_chars=2
        )

        pais = col23.text_input(
            "País",
            value=pais_atual or "Brasil"
        )

        # ====================================================
        # DADOS BANCÁRIOS
        # ====================================================

        st.markdown(
            "### 🏦 Dados Bancários"
        )

        col24, col25 = st.columns(2)

        banco = col24.text_input(
            "Banco",
            value=banco_atual or ""
        )

        codigo_banco = col25.text_input(
            "Código do Banco",
            value=codigo_banco_atual or ""
        )

        col26, col27, col28 = st.columns(3)

        agencia = col26.text_input(
            "Agência",
            value=agencia_atual or ""
        )

        conta = col27.text_input(
            "Conta",
            value=conta_atual or ""
        )

        tipo_conta = col28.selectbox(
            "Tipo da Conta",
            tipos_conta,
            index=(
                tipos_conta.index(
                    tipo_conta_atual
                )
                if tipo_conta_atual
                in tipos_conta
                else 0
            )
        )

        col29, col30 = st.columns(2)

        tipo_chave_pix = col29.selectbox(
            "Tipo da Chave Pix",
            tipos_pix,
            index=(
                tipos_pix.index(
                    tipo_pix_atual
                )
                if tipo_pix_atual
                in tipos_pix
                else 0
            )
        )

        chave_pix = col30.text_input(
            "Chave Pix",
            value=chave_pix_atual or ""
        )

        # ====================================================
        # OBSERVAÇÕES
        # ====================================================

        st.markdown(
            "### 📝 Observações"
        )

        observacoes = st.text_area(
            "Observações Gerais",
            value=observacoes_atual or "",
            height=120
        )

        # ====================================================
        # BOTÕES
        # ====================================================

        col31, col32 = st.columns(2)

        salvar = col31.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        mudar_status = col32.form_submit_button(
            "🚫 Inativar"
            if ativo
            else "✅ Ativar",
            use_container_width=True
        )

    # ========================================================
    # ATIVAR / INATIVAR
    # ========================================================

    if mudar_status:

        if _sisget_salvar(
            """
            UPDATE fornecedores
            SET
                ativo = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                not ativo,
                registro_id
            )
        ):

            st.session_state[
                "sisget_mensagem_fornecedor"
            ] = (
                "✅ Situação do fornecedor "
                "alterada com sucesso."
            )

            st.session_state[
                "sisget_tela_fornecedores"
            ] = "localizar"

            st.rerun()

    # ========================================================
    # SALVAR ALTERAÇÕES
    # ========================================================

    if salvar:

        cpf_cnpj = cpf_cnpj.strip()
        razao_social = razao_social.strip()

        if not cpf_cnpj:

            st.warning(
                "⚠️ Informe CPF/CNPJ."
            )

            return

        if not razao_social:

            st.warning(
                "⚠️ Informe Razão Social/Nome."
            )

            return

        # ====================================================
        # DUPLICIDADE
        # ====================================================

        duplicado = _sisget_fetchone(
            """
            SELECT id
            FROM fornecedores
            WHERE cpf_cnpj = ?
              AND id <> ?
            """,
            (
                cpf_cnpj,
                registro_id
            )
        )

        if duplicado:

            st.warning(
                "⚠️ Já existe outro fornecedor "
                "com este CPF/CNPJ."
            )

            return

        # ====================================================
        # UPDATE
        # ====================================================

        sucesso = _sisget_salvar(
            """
            UPDATE fornecedores

            SET
                tipo_pessoa = ?,
                cpf_cnpj = ?,
                razao_social = ?,
                nome_fantasia = ?,
                natureza_juridica = ?,
                inscricao_estadual = ?,
                inscricao_municipal = ?,
                porte_empresa = ?,
                optante_simples = ?,
                cnae = ?,
                categoria_fornecedor = ?,

                telefone = ?,
                whatsapp = ?,
                email = ?,
                site = ?,

                cep = ?,
                logradouro = ?,
                numero_endereco = ?,
                complemento = ?,
                bairro = ?,
                cidade = ?,
                uf = ?,
                pais = ?,

                banco = ?,
                codigo_banco = ?,
                agencia = ?,
                conta = ?,
                tipo_conta = ?,
                tipo_chave_pix = ?,
                chave_pix = ?,

                observacoes = ?,

                atualizado_em = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                tipo_pessoa,
                cpf_cnpj,
                razao_social,

                nome_fantasia.strip() or None,

                natureza_juridica.strip() or None,

                inscricao_estadual.strip() or None,

                inscricao_municipal.strip() or None,

                None
                if porte_empresa == "Não informado"
                else porte_empresa,

                None
                if optante_simples == "Não informado"
                else optante_simples,

                cnae.strip() or None,

                categoria_fornecedor.strip() or None,

                telefone.strip() or None,

                whatsapp.strip() or None,

                email.strip() or None,

                site.strip() or None,

                cep.strip() or None,

                logradouro.strip() or None,

                numero_endereco.strip() or None,

                complemento.strip() or None,

                bairro.strip() or None,

                cidade.strip() or None,

                uf.strip().upper() or None,

                pais.strip() or None,

                banco.strip() or None,

                codigo_banco.strip() or None,

                agencia.strip() or None,

                conta.strip() or None,

                None
                if tipo_conta == "Não informado"
                else tipo_conta,

                None
                if tipo_chave_pix == "Não informado"
                else tipo_chave_pix,

                chave_pix.strip() or None,

                observacoes.strip() or None,

                registro_id
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_fornecedor"
            ] = (
                "✅ Fornecedor alterado com sucesso."
            )

            st.session_state[
                "sisget_tela_fornecedores"
            ] = "localizar"

            st.session_state[
                "sisget_fornecedor_id"
            ] = None

            st.rerun()

# ============================================================
# FORNECEDOR - EXCLUIR
# ============================================================

def fornecedor_excluir():

    registro_id = fornecedor_localizar()

    if not registro_id:

        return

    uso_cotacoes = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM cotacoes
        WHERE fornecedor_id = ?
        """,
        (
            registro_id,
        )
    )

    if uso_cotacoes and uso_cotacoes[0] > 0:

        st.warning(
            "⚠️ Este fornecedor já possui cotações. "
            "Use a opção Inativar."
        )

        return

    representantes = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM fornecedores_representantes
        WHERE fornecedor_id = ?
        """,
        (
            registro_id,
        )
    )

    if representantes and representantes[0] > 0:

        st.warning(
            "⚠️ Este fornecedor possui representantes "
            "cadastrados. Inative o fornecedor "
            "ou exclua os representantes primeiro."
        )

        return

    confirmar = st.checkbox(
        "Confirmo a exclusão deste fornecedor.",
        key=f"confirmar_fornecedor_{registro_id}"
    )

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_fornecedor_{registro_id}"
    ):

        if not confirmar:

            st.warning(
                "⚠️ Marque a confirmação."
            )

            return

        if _sisget_salvar(
            """
            DELETE FROM fornecedores
            WHERE id = ?
            """,
            (
                registro_id,
            )
        ):

            st.rerun()


# ============================================================
# FORNECEDOR - IMPRIMIR
# ============================================================

def fornecedor_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            cpf_cnpj AS "CPF/CNPJ",
            razao_social AS "Razão Social",
            nome_fantasia AS "Nome Fantasia",
            categoria_fornecedor AS "Categoria",
            telefone AS "Telefone",
            whatsapp AS "WhatsApp",
            email AS "E-mail",
            cidade AS "Cidade",
            uf AS "UF",
            situacao_cadastral AS "Cadastro",
            CASE
                WHEN ativo
                THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM fornecedores
        ORDER BY
            razao_social,
            codigo
        """
    )

    if df.empty:

        st.info(
            "Nenhum fornecedor para imprimir."
        )

        return

    sisget_relatorio_classificacao(
        "Fornecedores",
        df,
        "fornecedores.pdf"
    )

def fornecedor_pesquisar_pessoa_fisica():

    pessoas = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            cpf_cnpj,
            razao_social,
            telefone,
            whatsapp,
            email
        FROM fornecedores
        WHERE ativo = TRUE
          AND tipo_pessoa = 'Física'
        ORDER BY
            razao_social,
            codigo
        """
    )

    return pessoas
# ============================================================
# REPRESENTANTES DO FORNECEDOR
# ============================================================

def fornecedor_representantes(
    fornecedor_id
):

    # ========================================================
    # FORNECEDOR
    # ========================================================

    fornecedor = _sisget_fetchone(
        """
        SELECT
            codigo,
            razao_social,
            cpf_cnpj,
            tipo_pessoa
        FROM fornecedores
        WHERE id = ?
        """,
        (
            fornecedor_id,
        )
    )

    if not fornecedor:

        st.warning(
            "⚠️ Fornecedor não encontrado."
        )

        return

    (
        codigo_fornecedor,
        razao_social,
        cnpj_fornecedor,
        tipo_pessoa_fornecedor
    ) = fornecedor

    # ========================================================
    # SOMENTE PESSOA JURÍDICA
    # ========================================================

    if tipo_pessoa_fornecedor != "Jurídica":

        st.warning(
            "⚠️ Representantes somente podem ser "
            "vinculados a fornecedores Pessoa Jurídica."
        )

        return

    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.info(
        f"🏢 {codigo_fornecedor} - "
        f"{razao_social} | "
        f"CNPJ: {cnpj_fornecedor or ''}"
    )

    # ========================================================
    # ESTADOS
    # ========================================================

    chave_tela = (
        f"sisget_representante_tela_"
        f"{fornecedor_id}"
    )

    chave_id = (
        f"sisget_representante_id_"
        f"{fornecedor_id}"
    )

    chave_reset = (
        f"sisget_representante_reset_"
        f"{fornecedor_id}"
    )

    chave_pf = (
        f"sisget_representante_pf_"
        f"{fornecedor_id}"
    )

    chave_pesquisa = (
        f"sisget_representante_pesquisa_"
        f"{fornecedor_id}"
    )

    if chave_tela not in st.session_state:

        st.session_state[
            chave_tela
        ] = "lista"

    if chave_id not in st.session_state:

        st.session_state[
            chave_id
        ] = None

    if chave_reset not in st.session_state:

        st.session_state[
            chave_reset
        ] = 0

    if chave_pf not in st.session_state:

        st.session_state[
            chave_pf
        ] = {}

    if chave_pesquisa not in st.session_state:

        st.session_state[
            chave_pesquisa
        ] = False

    tela = st.session_state[
        chave_tela
    ]

    reset = st.session_state[
        chave_reset
    ]

    dados_pf = st.session_state[
        chave_pf
    ]

    # ========================================================
    # OPÇÕES
    # ========================================================

    tipos_representante = [
        "1 - Representante legal",
        "2 - Demais membros do quadro societário",
        "3 - Microempreendedor Individual (MEI)",
        "4 - Empresário Individual (EI)",
        "5 - Empresa Individual de Responsabilidade Limitada (EIRELI)",
        "6 - Sociedade LTDA Unipessoal (Lei 13.874/2019)"
    ]

    tipos_registro = [
        "Junta Comercial",
        "Portal do Empreendedor",
        "Cartório de Registro"
    ]

    # ========================================================
    # TELA - LISTA
    # ========================================================

    if tela == "lista":

        col1, col2 = st.columns(
            [4, 1]
        )

        with col1:

            st.markdown(
                "### 👥 Pessoas Vinculadas"
            )

        with col2:

            adicionar = st.button(
                "➕ Adicionar Pessoa",
                use_container_width=True,
                type="primary",
                key=(
                    f"btn_adicionar_representante_"
                    f"{fornecedor_id}"
                )
            )

        if adicionar:

            st.session_state[
                chave_pf
            ] = {}

            st.session_state[
                chave_pesquisa
            ] = False

            st.session_state[
                chave_tela
            ] = "incluir"

            st.rerun()

        # ====================================================
        # LISTAGEM
        # ====================================================

        df = _sisget_dataframe(
            """
            SELECT
                id,

                codigo AS "Código",

                nome AS "Nome",

                cpf AS "CPF",

                tipo_representante
                    AS "Qualificação",

                cargo
                    AS "Cargo / Função",

                tipo_registro
                    AS "Tipo Registro",

                numero_registro
                    AS "Nº Registro",

                CASE
                    WHEN principal = TRUE
                    THEN '⭐ Sim'
                    ELSE 'Não'
                END AS "Responsável",

                CASE
                    WHEN autorizado_assinar = TRUE
                    THEN 'Sim'
                    ELSE 'Não'
                END AS "Pode Assinar",

                CASE
                    WHEN ativo = TRUE
                    THEN 'Ativo'
                    ELSE 'Inativo'
                END AS "Situação"

            FROM fornecedores_representantes

            WHERE fornecedor_id = ?

            ORDER BY
                principal DESC,
                nome
            """,
            (
                fornecedor_id,
            )
        )

        if df.empty:

            st.info(
                "Nenhuma pessoa vinculada a este fornecedor."
            )

            return

        st.caption(
            "Dê duplo clique em uma pessoa para alterar."
        )

        representante_id = sisget_grid_localizar(
            df=df,
            chave=(
                f"representantes_"
                f"{fornecedor_id}"
            ),
            coluna_id="id",
            altura=450
        )

        if representante_id:

            st.session_state[
                chave_id
            ] = representante_id

            st.session_state[
                chave_tela
            ] = "alterar"

            st.rerun()

    # ========================================================
    # TELA - INCLUIR
    # ========================================================

    elif tela == "incluir":

        sisget_cabecalho_tela(
            "➕ Adicionar Pessoa",
            voltar=lambda: (
                st.session_state.__setitem__(
                    chave_tela,
                    "lista"
                ),
                st.rerun()
            ),
            chave=(
                f"representante_incluir_"
                f"{fornecedor_id}"
            )
        )

        # ====================================================
        # CÓDIGO
        # ====================================================

        codigo = sisget_proximo_codigo(
            "fornecedores_representantes",
            tamanho=3,
            filtro_sql=(
                "AND fornecedor_id = ?"
            ),
            parametros=(
                fornecedor_id,
            )
        )

        # ====================================================
        # IDENTIFICAÇÃO
        # ====================================================

        st.markdown(
            "### 👤 Pessoa Física"
        )

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True,
            key=(
                f"rep_codigo_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        nome = col2.text_input(
            "Nome Completo *",
            value=(
                dados_pf.get(
                    "nome",
                    ""
                )
            ),
            key=(
                f"rep_nome_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        # ====================================================
        # CPF + PESQUISAR + CARGO
        # ====================================================

        col3, col4, col5 = st.columns(
            [3, 1.3, 3]
        )

        cpf = col3.text_input(
            "CPF *",
            value=(
                dados_pf.get(
                    "cpf",
                    ""
                )
            ),
            max_chars=14,
            key=(
                f"rep_cpf_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        pesquisar = col4.button(
            "🔎 Pesquisar",
            use_container_width=True,
            key=(
                f"rep_pesquisar_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        cargo = col5.text_input(
            "Cargo / Função",
            key=(
                f"rep_cargo_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        if pesquisar:

            st.session_state[
                chave_pesquisa
            ] = True

            st.rerun()

        # ====================================================
        # PESQUISA DE PESSOA FÍSICA
        # ====================================================

        if st.session_state[
            chave_pesquisa
        ]:

            with st.container(
                border=True
            ):

                st.markdown(
                    "#### 🔎 Localizar Pessoa Física"
                )

                filtro = st.text_input(
                    "Pesquisar por Nome ou CPF",
                    key=(
                        f"filtro_pf_"
                        f"{fornecedor_id}"
                    )
                )

                parametros = []

                sql = """
                    SELECT
                        id,
                        codigo,
                        cpf_cnpj,
                        razao_social,
                        telefone,
                        whatsapp,
                        email

                    FROM fornecedores

                    WHERE ativo = TRUE
                      AND tipo_pessoa = 'Física'
                """

                if filtro.strip():

                    filtro_cpf = re.sub(
                        r"\D",
                        "",
                        filtro
                    )

                    sql += """
                        AND
                        (
                            UPPER(
                                razao_social
                            )
                            LIKE UPPER(?)

                            OR

                            REGEXP_REPLACE(
                                COALESCE(
                                    cpf_cnpj,
                                    ''
                                ),
                                '[^0-9]',
                                '',
                                'g'
                            )
                            LIKE ?
                        )
                    """

                    parametros.extend(
                        [
                            f"%{filtro.strip()}%",
                            f"%{filtro_cpf}%"
                        ]
                    )

                sql += """
                    ORDER BY
                        razao_social
                """

                pessoas = _sisget_fetch(
                    sql,
                    tuple(
                        parametros
                    )
                )

                if pessoas:

                    mapa_pessoas = {}

                    for registro in pessoas:

                        (
                            pessoa_id,
                            codigo_pf,
                            cpf_pf,
                            nome_pf,
                            telefone_pf,
                            whatsapp_pf,
                            email_pf
                        ) = registro

                        descricao = (
                            f"{codigo_pf} - "
                            f"{nome_pf} - "
                            f"{cpf_pf or ''}"
                        )

                        mapa_pessoas[
                            descricao
                        ] = {

                            "id": pessoa_id,

                            "nome": (
                                nome_pf
                                or ""
                            ),

                            "cpf": (
                                cpf_pf
                                or ""
                            ),

                            "telefone": (
                                telefone_pf
                                or ""
                            ),

                            "whatsapp": (
                                whatsapp_pf
                                or ""
                            ),

                            "email": (
                                email_pf
                                or ""
                            )
                        }

                    pessoa_selecionada = st.selectbox(
                        "Pessoa Física",
                        list(
                            mapa_pessoas.keys()
                        ),
                        key=(
                            f"rep_pf_select_"
                            f"{fornecedor_id}"
                        )
                    )

                    col6, col7 = st.columns(2)

                    selecionar = col6.button(
                        "✅ Selecionar Pessoa",
                        type="primary",
                        use_container_width=True,
                        key=(
                            f"rep_usar_pf_"
                            f"{fornecedor_id}"
                        )
                    )

                    fechar = col7.button(
                        "❌ Fechar",
                        use_container_width=True,
                        key=(
                            f"rep_fechar_pf_"
                            f"{fornecedor_id}"
                        )
                    )

                    if selecionar:

                        st.session_state[
                            chave_pf
                        ] = mapa_pessoas[
                            pessoa_selecionada
                        ]

                        st.session_state[
                            chave_pesquisa
                        ] = False

                        st.session_state[
                            chave_reset
                        ] += 1

                        st.rerun()

                    if fechar:

                        st.session_state[
                            chave_pesquisa
                        ] = False

                        st.rerun()

                else:

                    st.info(
                        "Nenhuma Pessoa Física encontrada."
                    )

        # ====================================================
        # RECARREGAR PF
        # ====================================================

        dados_pf = st.session_state.get(
            chave_pf,
            {}
        )

        # ====================================================
        # QUALIFICAÇÃO
        # ====================================================

        st.markdown(
            "### 📋 Qualificação"
        )

        tipo_representante = st.selectbox(
            "Tipo / Qualificação *",
            tipos_representante,
            key=(
                f"rep_qualificacao_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        # ====================================================
        # REGISTRO
        # ====================================================

        st.markdown(
            "### 🏛️ Registro"
        )

        col8, col9 = st.columns(2)

        tipo_registro = col8.selectbox(
            "Tipo do Registro *",
            tipos_registro,
            key=(
                f"rep_tipo_registro_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        numero_registro = col9.text_input(
            "Número do Registro *",
            key=(
                f"rep_numero_registro_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        # ====================================================
        # CONTATO
        # ====================================================

        st.markdown(
            "### ☎️ Contato"
        )

        col10, col11 = st.columns(2)

        telefone = col10.text_input(
            "Telefone",
            value=(
                dados_pf.get(
                    "telefone",
                    ""
                )
            ),
            key=(
                f"rep_telefone_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        whatsapp = col11.text_input(
            "WhatsApp",
            value=(
                dados_pf.get(
                    "whatsapp",
                    ""
                )
            ),
            key=(
                f"rep_whatsapp_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        email = st.text_input(
            "E-mail",
            value=(
                dados_pf.get(
                    "email",
                    ""
                )
            ),
            key=(
                f"rep_email_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        # ====================================================
        # RESPONSABILIDADE
        # ====================================================

        st.markdown(
            "### ⚙️ Responsabilidade"
        )

        col12, col13 = st.columns(2)

        responsavel = col12.checkbox(
            "⭐ Responsável Principal",
            key=(
                f"rep_responsavel_"
                f"{fornecedor_id}_"
                f"{reset}"
            ),
            help=(
                "Somente uma pessoa pode ser "
                "responsável principal por fornecedor."
            )
        )

        autorizado_assinar = col13.checkbox(
            "✍️ Autorizado a Assinar Documentos",
            key=(
                f"rep_assinar_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        observacao = st.text_area(
            "Observações",
            height=100,
            key=(
                f"rep_observacao_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        )

        # ====================================================
        # SALVAR
        # ====================================================

        if st.button(
            "💾 Salvar Pessoa",
            type="primary",
            use_container_width=True,
            key=(
                f"rep_salvar_"
                f"{fornecedor_id}_"
                f"{reset}"
            )
        ):

            nome = nome.strip()

            cpf_limpo = re.sub(
                r"\D",
                "",
                cpf
            )

            numero_registro = (
                numero_registro.strip()
            )

            if not nome:

                st.warning(
                    "⚠️ Informe o nome."
                )

                return

            if len(cpf_limpo) != 11:

                st.warning(
                    "⚠️ Informe um CPF com 11 números."
                )

                return

            if not numero_registro:

                st.warning(
                    "⚠️ Informe o número do registro."
                )

                return

            # ================================================
            # DUPLICIDADE
            # ================================================

            existe = _sisget_fetchone(
                """
                SELECT
                    id
                FROM fornecedores_representantes
                WHERE fornecedor_id = ?
                  AND REGEXP_REPLACE(
                        COALESCE(
                            cpf,
                            ''
                        ),
                        '[^0-9]',
                        '',
                        'g'
                      ) = ?
                """,
                (
                    fornecedor_id,
                    cpf_limpo
                )
            )

            if existe:

                st.warning(
                    "⚠️ Esta pessoa já está vinculada "
                    "a este fornecedor."
                )

                return

            # ================================================
            # RESPONSÁVEL ÚNICO
            # ================================================

            if responsavel:

                _sisget_salvar(
                    """
                    UPDATE fornecedores_representantes
                    SET principal = FALSE
                    WHERE fornecedor_id = ?
                    """,
                    (
                        fornecedor_id,
                    )
                )

            # ================================================
            # INSERT
            # ================================================

            sucesso = _sisget_salvar(
                """
                INSERT INTO fornecedores_representantes
                (
                    fornecedor_id,
                    codigo,
                    nome,
                    cpf,
                    cargo,
                    tipo_representante,
                    tipo_registro,
                    numero_registro,
                    telefone,
                    whatsapp,
                    email,
                    principal,
                    autorizado_assinar,
                    observacao,
                    ativo,
                    criado_em
                )
                VALUES
                (
                    ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    TRUE,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    fornecedor_id,
                    codigo,
                    nome,
                    cpf_limpo,

                    cargo.strip()
                    or None,

                    tipo_representante,

                    tipo_registro,
                    numero_registro,

                    telefone.strip()
                    or None,

                    whatsapp.strip()
                    or None,

                    email.strip()
                    or None,

                    responsavel,
                    autorizado_assinar,

                    observacao.strip()
                    or None
                )
            )

            if sucesso:

                st.session_state[
                    chave_pf
                ] = {}

                st.session_state[
                    chave_pesquisa
                ] = False

                st.session_state[
                    chave_reset
                ] += 1

                st.session_state[
                    chave_tela
                ] = "lista"

                st.rerun()

    # ========================================================
    # TELA - ALTERAR
    # ========================================================

    elif tela == "alterar":

        representante_id = (
            st.session_state.get(
                chave_id
            )
        )

        if not representante_id:

            st.session_state[
                chave_tela
            ] = "lista"

            st.rerun()

        sisget_cabecalho_tela(
            "✏️ Alterar Pessoa",
            voltar=lambda: (
                st.session_state.__setitem__(
                    chave_tela,
                    "lista"
                ),
                st.rerun()
            ),
            chave=(
                f"representante_alterar_"
                f"{fornecedor_id}"
            )
        )

        fornecedor_representante_alterar(
            representante_id
        )

def fornecedor_representante_alterar(
    representante_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            fornecedor_id,
            codigo,
            nome,
            cpf,
            cargo,
            tipo_representante,
            tipo_registro,
            numero_registro,
            telefone,
            whatsapp,
            email,
            principal,
            autorizado_assinar,
            observacao,
            ativo
        FROM fornecedores_representantes
        WHERE id = ?
        """,
        (
            representante_id,
        )
    )

    if not registro:

        st.warning(
            "⚠️ Representante não encontrado."
        )

        return

    (
        fornecedor_id,
        codigo,
        nome_atual,
        cpf_atual,
        cargo_atual,
        tipo_representante_atual,
        tipo_registro_atual,
        numero_registro_atual,
        telefone_atual,
        whatsapp_atual,
        email_atual,
        principal_atual,
        autorizado_atual,
        observacao_atual,
        ativo_atual
    ) = registro

    tipos_representante = [
        "1 - Representante legal",
        "2 - Demais membros do quadro societário",
        "3 - Microempreendedor Individual (MEI)",
        "4 - Empresário Individual (EI)",
        "5 - Empresa Individual de Responsabilidade Limitada (EIRELI)",
        "6 - Sociedade LTDA Unipessoal (Lei 13.874/2019)"
    ]

    tipos_registro = [
        "Junta Comercial",
        "Portal do Empreendedor",
        "Cartório de Registro"
    ]

    try:

        indice_tipo = tipos_representante.index(
            tipo_representante_atual
        )

    except Exception:

        indice_tipo = 0

    try:

        indice_registro = tipos_registro.index(
            tipo_registro_atual
        )

    except Exception:

        indice_registro = 0

    with st.form(
        f"form_alterar_representante_{representante_id}"
    ):

        st.markdown(
            "#### 👤 Identificação"
        )

        col1, col2, col3 = st.columns(
            [1, 1.5, 4]
        )

        col1.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        col2.text_input(
            "Tipo de Pessoa",
            value="Física",
            disabled=True
        )

        nome = col3.text_input(
            "Nome Completo *",
            value=nome_atual or ""
        )

        col4, col5 = st.columns(2)

        cpf = col4.text_input(
            "CPF *",
            value=cpf_atual or ""
        )

        cargo = col5.text_input(
            "Cargo / Função",
            value=cargo_atual or ""
        )

        st.markdown(
            "#### 📋 Qualificação"
        )

        tipo_representante = st.selectbox(
            "Tipo / Qualificação *",
            tipos_representante,
            index=indice_tipo
        )

        st.markdown(
            "#### 🏛️ Registro"
        )

        col6, col7 = st.columns(2)

        tipo_registro = col6.selectbox(
            "Tipo do Registro *",
            tipos_registro,
            index=indice_registro
        )

        numero_registro = col7.text_input(
            "Número do Registro *",
            value=numero_registro_atual or ""
        )

        st.markdown(
            "#### ☎️ Contato"
        )

        col8, col9 = st.columns(2)

        telefone = col8.text_input(
            "Telefone",
            value=telefone_atual or ""
        )

        whatsapp = col9.text_input(
            "WhatsApp",
            value=whatsapp_atual or ""
        )

        email = st.text_input(
            "E-mail",
            value=email_atual or ""
        )

        col10, col11 = st.columns(2)

        principal = col10.checkbox(
            "Representante Principal",
            value=bool(
                principal_atual
            )
        )

        autorizado_assinar = col11.checkbox(
            "Autorizado a Assinar Documentos",
            value=bool(
                autorizado_atual
            )
        )

        observacao = st.text_area(
            "Observações",
            value=observacao_atual or ""
        )

        col12, col13 = st.columns(2)

        salvar = col12.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        status = col13.form_submit_button(
            (
                "🚫 Inativar"
                if ativo_atual
                else "✅ Ativar"
            ),
            use_container_width=True
        )

    if status:

        sucesso = _sisget_salvar(
            """
            UPDATE fornecedores_representantes
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo_atual,
                representante_id
            )
        )

        if sucesso:

            st.rerun()

    if salvar:

        nome = nome.strip()

        cpf_limpo = re.sub(
            r"\D",
            "",
            cpf
        )

        numero_registro = (
            numero_registro.strip()
        )

        if not nome:

            st.warning(
                "⚠️ Informe o nome."
            )

            return

        if len(cpf_limpo) != 11:

            st.warning(
                "⚠️ Informe um CPF com 11 números."
            )

            return

        if not numero_registro:

            st.warning(
                "⚠️ Informe o número do registro."
            )

            return

        if principal:

            _sisget_salvar(
                """
                UPDATE fornecedores_representantes
                SET principal = FALSE
                WHERE fornecedor_id = ?
                  AND id <> ?
                """,
                (
                    fornecedor_id,
                    representante_id
                )
            )

        sucesso = _sisget_salvar(
            """
            UPDATE fornecedores_representantes
            SET
                nome = ?,
                cpf = ?,
                cargo = ?,
                tipo_representante = ?,
                tipo_registro = ?,
                numero_registro = ?,
                telefone = ?,
                whatsapp = ?,
                email = ?,
                principal = ?,
                autorizado_assinar = ?,
                observacao = ?
            WHERE id = ?
            """,
            (
                nome,
                cpf_limpo,

                cargo.strip()
                or None,

                tipo_representante,

                tipo_registro,
                numero_registro,

                telefone.strip()
                or None,

                whatsapp.strip()
                or None,

                email.strip()
                or None,

                principal,
                autorizado_assinar,

                observacao.strip()
                or None,

                representante_id
            )
        )

        if sucesso:

            st.success(
                "✅ Representante alterado com sucesso."
            )

            st.rerun()

# ============================================================
# GRUPOS
# ============================================================

def cadastro_grupos_produtos():
    sisget_tela_principal(
        titulo="Grupos de Produtos",
        chave="grupos_produtos",
        func_incluir=grupo_produto_incluir,
        func_localizar=grupo_produto_localizar,
        func_alterar=grupo_produto_alterar,
        func_excluir=grupo_produto_excluir,
        func_imprimir=grupo_produto_imprimir,
        icone="📁"
    )



def grupo_produto_incluir():

    entidade_id = st.session_state.get(
        "entidade_id"
    )

    if entidade_id is None:

        st.error(
            "❌ Entidade não identificada no usuário logado."
        )

        return

    if "sisget_grupo_reset" not in st.session_state:

        st.session_state[
            "sisget_grupo_reset"
        ] = 0

    reset = st.session_state[
        "sisget_grupo_reset"
    ]

    codigo = sisget_proximo_codigo(
        "grupos_produtos",
        tamanho=3,
        filtro_sql="AND entidade_id = ?",
        parametros=(
            entidade_id,
        )
    )

    with st.form(
        f"form_grupo_incluir_{reset}"
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Grupo",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_grupo" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_grupo"
            )
        )

    if salvar:

        descricao = descricao.strip()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        existe = _sisget_fetchone(
            """
            SELECT
                id
            FROM grupos_produtos
            WHERE entidade_id = ?
              AND UPPER(descricao) = UPPER(?)
            """,
            (
                entidade_id,
                descricao
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe um grupo com esta descrição."
            )

            return

        codigo = sisget_proximo_codigo(
            "grupos_produtos",
            tamanho=3,
            filtro_sql="AND entidade_id = ?",
            parametros=(
                entidade_id,
            )
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO grupos_produtos
            (
                entidade_id,
                codigo,
                descricao,
                ativo
            )
            VALUES
            (
                ?, ?, ?, TRUE
            )
            """,
            (
                entidade_id,
                codigo,
                descricao
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_grupo"
            ] = (
                f"✅ Grupo salvo com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_grupo_reset"
            ] += 1

            st.rerun()


def grupo_produto_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            CASE
                WHEN ativo THEN 'Ativo'
                ELSE 'Inativo'
            END AS "Situação"
        FROM grupos_produtos
        ORDER BY codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="grupos_produtos",
        coluna_id="id",
        altura=420
    )


def grupo_produto_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT codigo, descricao, ativo
        FROM grupos_produtos
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    codigo, descricao_atual, ativo = registro

    with st.form(
        f"form_grupo_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
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

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            "UPDATE grupos_produtos SET ativo = ? WHERE id = ?",
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if _sisget_salvar(
            """
            UPDATE grupos_produtos
            SET descricao = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                registro_id
            )
        ):
            st.rerun()


def grupo_produto_excluir():

    registro_id = grupo_produto_localizar()

    if not registro_id:
        return

    dependencias = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM subgrupos_produtos
        WHERE grupo_id = ?
        """,
        (registro_id,)
    )

    if dependencias and dependencias[0] > 0:
        st.warning(
            "⚠️ Grupo possui subgrupos vinculados."
        )
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_grupo_{registro_id}"
    ):
        if _sisget_salvar(
            "DELETE FROM grupos_produtos WHERE id = ?",
            (registro_id,)
        ):
            st.rerun()


def grupo_produto_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            descricao AS "Descrição"
        FROM grupos_produtos
        ORDER BY codigo
        """
    )

    sisget_relatorio_classificacao(
        "Grupos de Produtos",
        df,
        "grupos_produtos.pdf"
    )


# ============================================================
# SUBGRUPOS
# ============================================================

def cadastro_subgrupos_produtos():
    sisget_tela_principal(
        titulo="Subgrupos de Produtos",
        chave="subgrupos_produtos",
        func_incluir=subgrupo_produto_incluir,
        func_localizar=subgrupo_produto_localizar,
        func_alterar=subgrupo_produto_alterar,
        func_excluir=subgrupo_produto_excluir,
        func_imprimir=subgrupo_produto_imprimir,
        icone="📂"
    )


def subgrupo_produto_incluir():

    entidade_id = st.session_state.get(
        "entidade_id"
    )

    if entidade_id is None:

        st.error(
            "❌ Entidade não identificada no usuário logado."
        )

        return

    if "sisget_subgrupo_reset" not in st.session_state:

        st.session_state[
            "sisget_subgrupo_reset"
        ] = 0

    reset = st.session_state[
        "sisget_subgrupo_reset"
    ]

    grupos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM grupos_produtos
        WHERE ativo = TRUE
          AND entidade_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )

    if not grupos:

        st.warning(
            "⚠️ Cadastre um Grupo primeiro."
        )

        return

    mapa_grupos = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in grupos
    }

    grupo_nome = st.selectbox(
        "Grupo *",
        list(
            mapa_grupos.keys()
        ),
        key=f"subgrupo_grupo_{reset}"
    )

    grupo_id = mapa_grupos[
        grupo_nome
    ]

    codigo = sisget_proximo_codigo(
        "subgrupos_produtos",
        tamanho=3,
        filtro_sql="AND grupo_id = ?",
        parametros=(
            grupo_id,
        )
    )

    with st.form(
        f"form_subgrupo_incluir_{reset}_{grupo_id}"
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Subgrupo",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_subgrupo" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_subgrupo"
            )
        )

    if salvar:

        descricao = descricao.strip()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        existe = _sisget_fetchone(
            """
            SELECT
                id
            FROM subgrupos_produtos
            WHERE grupo_id = ?
              AND UPPER(descricao) = UPPER(?)
            """,
            (
                grupo_id,
                descricao
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe um subgrupo com esta descrição neste Grupo."
            )

            return

        codigo = sisget_proximo_codigo(
            "subgrupos_produtos",
            tamanho=3,
            filtro_sql="AND grupo_id = ?",
            parametros=(
                grupo_id,
            )
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO subgrupos_produtos
            (
                grupo_id,
                codigo,
                descricao,
                ativo
            )
            VALUES
            (
                ?, ?, ?, TRUE
            )
            """,
            (
                grupo_id,
                codigo,
                descricao
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_subgrupo"
            ] = (
                f"✅ Subgrupo salvo com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_subgrupo_reset"
            ] += 1

            st.rerun()


def subgrupo_produto_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            s.id,
            g.codigo || ' - ' || g.descricao AS "Grupo",
            s.codigo AS "Código",
            s.descricao AS "Descrição"
        FROM subgrupos_produtos s
        INNER JOIN grupos_produtos g
            ON g.id = s.grupo_id
        ORDER BY g.codigo, s.codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="subgrupos_produtos",
        coluna_id="id",
        altura=420
    )


def subgrupo_produto_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT codigo, descricao, ativo
        FROM subgrupos_produtos
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    codigo, descricao_atual, ativo = registro

    with st.form(
        f"form_subgrupo_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
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

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            """
            UPDATE subgrupos_produtos
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if _sisget_salvar(
            """
            UPDATE subgrupos_produtos
            SET descricao = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                registro_id
            )
        ):
            st.rerun()


def subgrupo_produto_excluir():

    registro_id = subgrupo_produto_localizar()

    if not registro_id:
        return

    dependencias = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE subgrupo_id = ?
        """,
        (registro_id,)
    )

    if dependencias and dependencias[0] > 0:
        st.warning(
            "⚠️ Subgrupo possui produtos vinculados."
        )
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_subgrupo_{registro_id}"
    ):
        if _sisget_salvar(
            "DELETE FROM subgrupos_produtos WHERE id = ?",
            (registro_id,)
        ):
            st.rerun()


def subgrupo_produto_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            g.descricao AS "Grupo",
            s.codigo AS "Código",
            s.descricao AS "Subgrupo"
        FROM subgrupos_produtos s
        INNER JOIN grupos_produtos g
            ON g.id = s.grupo_id
        ORDER BY g.codigo, s.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Subgrupos de Produtos",
        df,
        "subgrupos_produtos.pdf"
    )


# ============================================================
# UNIDADES
# ============================================================

def modulo_unidades_produtos():

    st.subheader("📏 Unidades")

    tipo = st.selectbox(
        "Tipo de Unidade *",
        [
            "Selecione...",
            "📐 Unidades de Medida",
            "🛒 Unidades de Compra",
            "🔄 Unidades de Movimentação"
        ],
        key="sisget_unidades_produtos"
    )

    st.divider()

    if tipo == "Selecione...":
        st.info("Selecione o tipo de unidade.")
        return

    elif tipo == "📐 Unidades de Medida":
        cadastro_unidades_medida()

    elif tipo == "🛒 Unidades de Compra":
        cadastro_unidades_compra()

    elif tipo == "🔄 Unidades de Movimentação":
        cadastro_unidades_movimentacao()


def cadastro_unidades_medida():
    sisget_tela_principal(
        titulo="Unidades de Medida",
        chave="unidades_medida",
        func_incluir=unidade_medida_incluir,
        func_localizar=unidade_medida_localizar,
        func_alterar=unidade_medida_alterar,
        func_excluir=unidade_medida_excluir,
        func_imprimir=unidade_medida_imprimir,
        icone="📐"
    )


def unidade_medida_incluir():

    if "sisget_unidade_medida_reset" not in st.session_state:

        st.session_state[
            "sisget_unidade_medida_reset"
        ] = 0

    reset = st.session_state[
        "sisget_unidade_medida_reset"
    ]

    codigo = sisget_proximo_codigo(
        "unidades_medida",
        tamanho=3
    )

    with st.form(
        f"form_unidade_medida_incluir_{reset}"
    ):

        col1, col2, col3 = st.columns(
            [1, 3, 1]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *",
            placeholder="Ex.: Unidade"
        )

        sigla = col3.text_input(
            "Sigla *",
            placeholder="UN"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Unidade de Medida",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_unidade_medida" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_unidade_medida"
            )
        )

    if salvar:

        descricao = descricao.strip()
        sigla = sigla.strip().upper()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        if not sigla:

            st.warning(
                "⚠️ Informe a sigla."
            )

            return

        existe = _sisget_fetchone(
            """
            SELECT
                id
            FROM unidades_medida
            WHERE UPPER(sigla) = UPPER(?)
               OR UPPER(descricao) = UPPER(?)
            """,
            (
                sigla,
                descricao
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe Unidade de Medida com esta descrição ou sigla."
            )

            return

        codigo = sisget_proximo_codigo(
            "unidades_medida",
            tamanho=3
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO unidades_medida
            (
                codigo,
                descricao,
                sigla,
                ativo
            )
            VALUES
            (
                ?, ?, ?, TRUE
            )
            """,
            (
                codigo,
                descricao,
                sigla
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_unidade_medida"
            ] = (
                f"✅ Unidade de Medida salva com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_unidade_medida_reset"
            ] += 1

            st.rerun()


# ============================================================
# UNIDADE DE COMPRA
# ============================================================

def unidade_compra_incluir():

    if "sisget_unidade_compra_reset" not in st.session_state:

        st.session_state[
            "sisget_unidade_compra_reset"
        ] = 0

    reset = st.session_state[
        "sisget_unidade_compra_reset"
    ]

    medidas = _sisget_fetch(
        """
        SELECT
            id,
            sigla,
            descricao
        FROM unidades_medida
        WHERE ativo = TRUE
        ORDER BY descricao
        """
    )

    if not medidas:

        st.warning(
            "⚠️ Cadastre uma Unidade de Medida primeiro."
        )

        return

    mapa_medidas = {
        f"{sigla} - {descricao}": id_
        for id_, sigla, descricao in medidas
    }

    codigo = sisget_proximo_codigo(
        "unidades_compra",
        tamanho=3
    )

    with st.form(
        f"form_unidade_compra_{reset}"
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *",
            placeholder="Ex.: Caixa"
        )

        medida_nome = st.selectbox(
            "Unidade de Medida *",
            list(
                mapa_medidas.keys()
            )
        )

        salvar = st.form_submit_button(
            "💾 Salvar Unidade de Compra",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_unidade_compra" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_unidade_compra"
            )
        )

    if salvar:

        descricao = descricao.strip()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        existe = _sisget_fetchone(
            """
            SELECT
                id
            FROM unidades_compra
            WHERE UPPER(descricao) = UPPER(?)
            """,
            (
                descricao,
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe uma Unidade de Compra com esta descrição."
            )

            return

        codigo = sisget_proximo_codigo(
            "unidades_compra",
            tamanho=3
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO unidades_compra
            (
                codigo,
                descricao,
                unidade_medida_id,
                ativo
            )
            VALUES
            (
                ?, ?, ?, TRUE
            )
            """,
            (
                codigo,
                descricao,
                mapa_medidas[
                    medida_nome
                ]
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_unidade_compra"
            ] = (
                f"✅ Unidade de Compra salva com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_unidade_compra_reset"
            ] += 1

            st.rerun()

def unidade_medida_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            descricao AS "Descrição",
            sigla AS "Sigla"
        FROM unidades_medida
        ORDER BY codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="unidades_medida",
        coluna_id="id",
        altura=420
    )


def unidade_medida_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT codigo, descricao, sigla, ativo
        FROM unidades_medida
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    codigo, descricao_atual, sigla_atual, ativo = registro

    with st.form(
        f"form_unidade_medida_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        sigla = st.text_input(
            "Sigla *",
            value=sigla_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            "UPDATE unidades_medida SET ativo = ? WHERE id = ?",
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if _sisget_salvar(
            """
            UPDATE unidades_medida
            SET descricao = ?, sigla = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                sigla.strip().upper(),
                registro_id
            )
        ):
            st.rerun()


def unidade_medida_excluir():

    registro_id = unidade_medida_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_unidade_medida_{registro_id}"
    ):
        if _sisget_salvar(
            "DELETE FROM unidades_medida WHERE id = ?",
            (registro_id,)
        ):
            st.rerun()


def unidade_medida_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            descricao AS "Descrição",
            sigla AS "Sigla"
        FROM unidades_medida
        ORDER BY codigo
        """
    )

    sisget_relatorio_classificacao(
        "Unidades de Medida",
        df,
        "unidades_medida.pdf"
    )


def cadastro_unidades_compra():
    sisget_tela_principal(
        titulo="Unidades de Compra",
        chave="unidades_compra",
        func_incluir=unidade_compra_incluir,
        func_localizar=unidade_compra_localizar,
        func_alterar=unidade_compra_alterar,
        func_excluir=unidade_compra_excluir,
        func_imprimir=unidade_compra_imprimir,
        icone="🛒"
    )


def unidade_compra_incluir():

    if "sisget_unidade_compra_reset" not in st.session_state:
        st.session_state["sisget_unidade_compra_reset"] = 0

    reset = st.session_state[
        "sisget_unidade_compra_reset"
    ]

    medidas = _sisget_fetch(
        """
        SELECT id, sigla, descricao
        FROM unidades_medida
        WHERE ativo = TRUE
        ORDER BY descricao
        """
    )

    if not medidas:
        st.warning(
            "⚠️ Cadastre uma Unidade de Medida primeiro."
        )
        return

    mapa = {
        f"{sigla} - {descricao}": id_
        for id_, sigla, descricao in medidas
    }

    codigo = sisget_proximo_codigo(
        "unidades_compra",
        tamanho=3
    )

    with st.form(
        f"form_unidade_compra_{reset}"
    ):
        col1, col2 = st.columns([1, 4])

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *",
            placeholder="Ex.: Caixa"
        )

        medida_nome = st.selectbox(
            "Unidade de Medida *",
            list(mapa.keys())
        )

        salvar = st.form_submit_button(
            "💾 Salvar Unidade de Compra",
            type="primary",
            use_container_width=True
        )

    if salvar:

        codigo = sisget_proximo_codigo(
            "unidades_compra",
            tamanho=3
        )

        if _sisget_salvar(
            """
            INSERT INTO unidades_compra
            (codigo, descricao, unidade_medida_id, ativo)
            VALUES (?, ?, ?, TRUE)
            """,
            (
                codigo,
                descricao.strip(),
                mapa[medida_nome]
            )
        ):
            st.session_state[
                "sisget_unidade_compra_reset"
            ] += 1

            st.rerun()


def unidade_compra_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            uc.id,
            uc.codigo AS "Código",
            uc.descricao AS "Descrição",
            um.sigla AS "Unidade"
        FROM unidades_compra uc
        INNER JOIN unidades_medida um
            ON um.id = uc.unidade_medida_id
        ORDER BY uc.codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="unidades_compra",
        coluna_id="id",
        altura=420
    )


def unidade_compra_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT codigo, descricao, ativo
        FROM unidades_compra
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    codigo, descricao_atual, ativo = registro

    with st.form(
        f"form_unidade_compra_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
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

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            "UPDATE unidades_compra SET ativo = ? WHERE id = ?",
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if _sisget_salvar(
            """
            UPDATE unidades_compra
            SET descricao = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                registro_id
            )
        ):
            st.rerun()


def unidade_compra_excluir():

    registro_id = unidade_compra_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_unidade_compra_{registro_id}"
    ):
        if _sisget_salvar(
            "DELETE FROM unidades_compra WHERE id = ?",
            (registro_id,)
        ):
            st.rerun()


def unidade_compra_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            descricao AS "Descrição"
        FROM unidades_compra
        ORDER BY codigo
        """
    )

    sisget_relatorio_classificacao(
        "Unidades de Compra",
        df,
        "unidades_compra.pdf"
    )


def cadastro_unidades_movimentacao():
    sisget_tela_principal(
        titulo="Unidades de Movimentação",
        chave="unidades_movimentacao",
        func_incluir=unidade_movimentacao_incluir,
        func_localizar=unidade_movimentacao_localizar,
        func_alterar=unidade_movimentacao_alterar,
        func_excluir=unidade_movimentacao_excluir,
        func_imprimir=unidade_movimentacao_imprimir,
        icone="🔄"
    )


def unidade_movimentacao_incluir():

    if "sisget_unidade_mov_reset" not in st.session_state:

        st.session_state[
            "sisget_unidade_mov_reset"
        ] = 0

    reset = st.session_state[
        "sisget_unidade_mov_reset"
    ]

    compras = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM unidades_compra
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    medidas = _sisget_fetch(
        """
        SELECT
            id,
            sigla,
            descricao
        FROM unidades_medida
        WHERE ativo = TRUE
        ORDER BY descricao
        """
    )

    if not compras or not medidas:

        st.warning(
            "⚠️ Cadastre Unidade de Compra e Unidade de Medida primeiro."
        )

        return

    mapa_compras = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in compras
    }

    mapa_medidas = {
        f"{sigla} - {descricao}": id_
        for id_, sigla, descricao in medidas
    }

    codigo = sisget_proximo_codigo(
        "unidades_movimentacao",
        tamanho=3
    )

    with st.form(
        f"form_unidade_movimentacao_{reset}"
    ):

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição *",
            placeholder="Ex.: Comprimido"
        )

        col3, col4 = st.columns(2)

        compra_nome = col3.selectbox(
            "Unidade de Compra *",
            list(
                mapa_compras.keys()
            )
        )

        medida_nome = col4.selectbox(
            "Unidade de Movimentação *",
            list(
                mapa_medidas.keys()
            )
        )

        fator = st.number_input(
            "Fator de Conversão *",
            min_value=0.000001,
            value=1.0,
            format="%.6f",
            help="Ex.: 1 caixa = 30 unidades → fator 30."
        )

        salvar = st.form_submit_button(
            "💾 Salvar Unidade de Movimentação",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_unidade_mov" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_unidade_mov"
            )
        )

    if salvar:

        descricao = descricao.strip()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição."
            )

            return

        codigo = sisget_proximo_codigo(
            "unidades_movimentacao",
            tamanho=3
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO unidades_movimentacao
            (
                codigo,
                descricao,
                unidade_compra_id,
                unidade_medida_id,
                fator_conversao,
                ativo
            )
            VALUES
            (
                ?, ?, ?, ?, ?, TRUE
            )
            """,
            (
                codigo,
                descricao,
                mapa_compras[
                    compra_nome
                ],
                mapa_medidas[
                    medida_nome
                ],
                float(
                    fator
                )
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_unidade_mov"
            ] = (
                f"✅ Unidade de Movimentação salva com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_unidade_mov_reset"
            ] += 1

            st.rerun()


def unidade_movimentacao_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            umv.id,
            umv.codigo AS "Código",
            umv.descricao AS "Descrição",
            uc.descricao AS "Compra",
            um.sigla AS "Movimentação",
            umv.fator_conversao AS "Fator"
        FROM unidades_movimentacao umv
        INNER JOIN unidades_compra uc
            ON uc.id = umv.unidade_compra_id
        INNER JOIN unidades_medida um
            ON um.id = umv.unidade_medida_id
        ORDER BY umv.codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="unidades_movimentacao",
        coluna_id="id",
        altura=420
    )


def unidade_movimentacao_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT codigo, descricao, fator_conversao, ativo
        FROM unidades_movimentacao
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    codigo, descricao_atual, fator_atual, ativo = registro

    with st.form(
        f"form_unidade_mov_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        fator = st.number_input(
            "Fator de Conversão *",
            min_value=0.000001,
            value=float(fator_atual or 1),
            format="%.6f"
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            """
            UPDATE unidades_movimentacao
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if _sisget_salvar(
            """
            UPDATE unidades_movimentacao
            SET descricao = ?, fator_conversao = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                float(fator),
                registro_id
            )
        ):
            st.rerun()


def unidade_movimentacao_excluir():

    registro_id = unidade_movimentacao_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_unidade_mov_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM unidades_movimentacao
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def unidade_movimentacao_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            umv.codigo AS "Código",
            umv.descricao AS "Descrição",
            uc.descricao AS "Compra",
            um.sigla AS "Movimentação",
            umv.fator_conversao AS "Fator"
        FROM unidades_movimentacao umv
        INNER JOIN unidades_compra uc
            ON uc.id = umv.unidade_compra_id
        INNER JOIN unidades_medida um
            ON um.id = umv.unidade_medida_id
        ORDER BY umv.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Unidades de Movimentação",
        df,
        "unidades_movimentacao.pdf"
    )


# ============================================================
# PRODUTOS
# ============================================================

def cadastro_produtos():
    sisget_tela_principal(
        titulo="Produtos",
        chave="produtos",
        func_incluir=produto_incluir,
        func_localizar=produto_localizar,
        func_alterar=produto_alterar,
        func_excluir=produto_excluir,
        func_imprimir=produto_imprimir,
        icone="📦"
    )


def produto_incluir():

    entidade_id = st.session_state.get(
        "entidade_id"
    )

    if entidade_id is None:

        st.error(
            "❌ Entidade não identificada no usuário logado."
        )

        return

    if "sisget_produto_reset" not in st.session_state:

        st.session_state[
            "sisget_produto_reset"
        ] = 0

    reset = st.session_state[
        "sisget_produto_reset"
    ]

    grupos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM grupos_produtos
        WHERE ativo = TRUE
          AND entidade_id = ?
        ORDER BY codigo
        """,
        (
            entidade_id,
        )
    )

    if not grupos:

        st.warning(
            "⚠️ Cadastre um Grupo primeiro."
        )

        return

    mapa_grupos = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in grupos
    }

    grupo_nome = st.selectbox(
        "Grupo *",
        list(
            mapa_grupos.keys()
        ),
        key=f"produto_grupo_{reset}"
    )

    grupo_id = mapa_grupos[
        grupo_nome
    ]

    subgrupos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM subgrupos_produtos
        WHERE grupo_id = ?
          AND ativo = TRUE
        ORDER BY codigo
        """,
        (
            grupo_id,
        )
    )

    if not subgrupos:

        st.warning(
            "⚠️ Cadastre um Subgrupo para o Grupo selecionado."
        )

        return

    mapa_subgrupos = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in subgrupos
    }

    compras = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM unidades_compra
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    movimentos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao,
            fator_conversao
        FROM unidades_movimentacao
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    if not compras:

        st.warning(
            "⚠️ Cadastre uma Unidade de Compra primeiro."
        )

        return

    if not movimentos:

        st.warning(
            "⚠️ Cadastre uma Unidade de Movimentação primeiro."
        )

        return

    mapa_compras = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in compras
    }

    mapa_movimentos = {}

    for (
        id_,
        codigo_mov,
        descricao_mov,
        fator
    ) in movimentos:

        try:

            fator_texto = (
                f"{float(fator):g}"
            )

        except Exception:

            fator_texto = str(
                fator or 1
            )

        descricao_mapa = (
            f"{codigo_mov} - "
            f"{descricao_mov} | "
            f"fator {fator_texto}"
        )

        mapa_movimentos[
            descricao_mapa
        ] = id_

    codigo = sisget_proximo_codigo(
        "produtos",
        tamanho=6,
        filtro_sql="AND entidade_id = ?",
        parametros=(
            entidade_id,
        )
    )

    with st.form(
        f"form_produto_{reset}_{grupo_id}"
    ):

        st.markdown(
            "### 📦 Identificação"
        )

        col1, col2 = st.columns(
            [1, 4]
        )

        col1.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = col2.text_input(
            "Descrição do Produto *",
            placeholder="Ex.: Papel A4 branco 75 g/m²"
        )

        descricao_complementar = st.text_area(
            "Descrição Complementar",
            height=100,
            placeholder=(
                "Informações adicionais que complementam "
                "a descrição principal do item."
            )
        )

        st.markdown(
            "### 📁 Classificação"
        )

        col3, col4 = st.columns(2)

        col3.text_input(
            "Grupo",
            value=grupo_nome,
            disabled=True
        )

        subgrupo_nome = col4.selectbox(
            "Subgrupo *",
            list(
                mapa_subgrupos.keys()
            )
        )

        tipo_item = st.selectbox(
            "Tipo do Item *",
            [
                "Consumo",
                "Patrimonial",
                "Serviço"
            ]
        )

        st.markdown(
            "### 📏 Unidades"
        )

        col5, col6 = st.columns(2)

        unidade_compra_nome = col5.selectbox(
            "Unidade de Compra *",
            list(
                mapa_compras.keys()
            )
        )

        unidade_mov_nome = col6.selectbox(
            "Unidade de Movimentação *",
            list(
                mapa_movimentos.keys()
            )
        )

        st.markdown(
            "### 📊 Controle de Estoque"
        )

        col7, col8 = st.columns(2)

        controla_estoque = col7.checkbox(
            "Controla Estoque",
            value=True
        )

        estoque_minimo = col8.number_input(
            "Estoque Mínimo",
            min_value=0.0,
            value=0.0,
            format="%.6f"
        )

        st.markdown(
            "### 💰 Contas / Naturezas Orçamentárias"
        )

        col9, col10 = st.columns(2)

        conta_orcamentaria_entrada = col9.text_input(
            "Conta / Natureza Orçamentária Padrão - Entrada"
        )

        conta_orcamentaria_saida = col10.text_input(
            "Conta / Natureza Orçamentária Padrão - Saída"
        )

        codigo_tribunal = st.text_input(
            "Classificação Tribunal de Contas"
        )

        st.markdown(
            "### 📝 Especificação Técnica"
        )

        especificacao = st.text_area(
            "Especificação Técnica",
            height=160,
            placeholder=(
                "Características técnicas, material, medidas, "
                "qualidade, padrão e demais requisitos."
            )
        )

        salvar = st.form_submit_button(
            "💾 Salvar Produto",
            type="primary",
            use_container_width=True
        )

    if "sisget_mensagem_produto" in st.session_state:

        st.success(
            st.session_state.pop(
                "sisget_mensagem_produto"
            )
        )

    if salvar:

        descricao = descricao.strip()

        if not descricao:

            st.warning(
                "⚠️ Informe a descrição do produto."
            )

            return

        item_patrimonial = (
            tipo_item == "Patrimonial"
        )

        if tipo_item == "Serviço":

            controla_estoque_salvar = False
            estoque_minimo_salvar = 0.0

        else:

            controla_estoque_salvar = (
                controla_estoque
            )

            estoque_minimo_salvar = float(
                estoque_minimo
            )

        subgrupo_id = mapa_subgrupos[
            subgrupo_nome
        ]

        existe = _sisget_fetchone(
            """
            SELECT
                id
            FROM produtos
            WHERE entidade_id = ?
              AND UPPER(COALESCE(produto, descricao)) = UPPER(?)
              AND grupo_id = ?
              AND subgrupo_id = ?
            """,
            (
                entidade_id,
                descricao,
                grupo_id,
                subgrupo_id
            )
        )

        if existe:

            st.warning(
                "⚠️ Já existe um produto com esta descrição neste Grupo/Subgrupo."
            )

            return

        codigo = sisget_proximo_codigo(
            "produtos",
            tamanho=6,
            filtro_sql="AND entidade_id = ?",
            parametros=(
                entidade_id,
            )
        )

        sucesso = _sisget_salvar(
            """
            INSERT INTO produtos
            (
                entidade_id,
                codigo,

                produto,
                descricao,
                descricao_complementar,

                grupo_id,
                subgrupo_id,

                tipo_produto,
                tipo_item,
                item_patrimonial,

                unidade_compra_id,
                unidade_movimentacao_id,

                controla_estoque,
                estoque_minimo,

                conta_orcamentaria_padrao,
                conta_orcamentaria_entrada,
                conta_orcamentaria_saida,

                codigo_tribunal,
                especificacao,

                ativo
            )
            VALUES
            (
                ?, ?,

                ?, ?, ?,

                ?, ?,

                ?, ?, ?,

                ?, ?,

                ?, ?,

                ?, ?, ?,

                ?, ?,

                TRUE
            )
            """,
            (
                entidade_id,
                codigo,

                descricao,
                descricao,
                descricao_complementar.strip()
                or None,

                grupo_id,
                subgrupo_id,

                tipo_item,
                tipo_item,
                item_patrimonial,

                mapa_compras[
                    unidade_compra_nome
                ],

                mapa_movimentos[
                    unidade_mov_nome
                ],

                controla_estoque_salvar,
                estoque_minimo_salvar,

                conta_orcamentaria_entrada.strip()
                or None,

                conta_orcamentaria_entrada.strip()
                or None,

                conta_orcamentaria_saida.strip()
                or None,

                codigo_tribunal.strip()
                or None,

                especificacao.strip()
                or None
            )
        )

        if sucesso:

            st.session_state[
                "sisget_mensagem_produto"
            ] = (
                f"✅ Produto salvo com sucesso. Código: {codigo}"
            )

            st.session_state[
                "sisget_produto_reset"
            ] += 1

            st.rerun()
def produto_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            p.id,
            p.codigo AS "Código",
            p.descricao AS "Produto",
            g.descricao AS "Grupo",
            sg.descricao AS "Subgrupo",
            p.tipo_item AS "Tipo"
        FROM produtos p
        INNER JOIN grupos_produtos g
            ON g.id = p.grupo_id
        INNER JOIN subgrupos_produtos sg
            ON sg.id = p.subgrupo_id
        ORDER BY p.codigo
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="produtos",
        coluna_id="id",
        altura=480
    )


def produto_alterar(registro_id):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            descricao,
            tipo_item,
            item_patrimonial,
            controla_estoque,
            estoque_minimo,
            conta_orcamentaria_padrao,
            codigo_tribunal,
            especificacao,
            ativo
        FROM produtos
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        descricao_atual,
        tipo_atual,
        patrimonial_atual,
        controla_atual,
        minimo_atual,
        conta_atual,
        tribunal_atual,
        especificacao_atual,
        ativo
    ) = registro

    tipos = ["Consumo", "Patrimonial", "Serviço"]

    indice = (
        tipos.index(tipo_atual)
        if tipo_atual in tipos
        else 0
    )

    with st.form(
        f"form_produto_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        descricao = st.text_input(
            "Descrição *",
            value=descricao_atual or ""
        )

        tipo_item = st.selectbox(
            "Tipo do Item *",
            tipos,
            index=indice
        )

        item_patrimonial = st.checkbox(
            "Item Patrimonial",
            value=bool(patrimonial_atual)
        )

        controla_estoque = st.checkbox(
            "Controla Estoque",
            value=bool(controla_atual)
        )

        estoque_minimo = st.number_input(
            "Estoque Mínimo",
            min_value=0.0,
            value=float(minimo_atual or 0),
            format="%.6f"
        )

        conta = st.text_input(
            "Conta / Natureza Padrão",
            value=conta_atual or ""
        )

        tribunal = st.text_input(
            "Classificação Tribunal",
            value=tribunal_atual or ""
        )

        especificacao = st.text_area(
            "Especificação",
            value=especificacao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        mudar = col2.form_submit_button(
            "🚫 Inativar" if ativo else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            "UPDATE produtos SET ativo = ? WHERE id = ?",
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        if tipo_item == "Patrimonial":
            item_patrimonial = True

        if _sisget_salvar(
            """
            UPDATE produtos
            SET
                descricao = ?,
                tipo_item = ?,
                item_patrimonial = ?,
                controla_estoque = ?,
                estoque_minimo = ?,
                conta_orcamentaria_padrao = ?,
                codigo_tribunal = ?,
                especificacao = ?
            WHERE id = ?
            """,
            (
                descricao.strip(),
                tipo_item,
                item_patrimonial,
                controla_estoque,
                float(estoque_minimo),
                conta.strip() or None,
                tribunal.strip() or None,
                especificacao.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def produto_excluir():

    registro_id = produto_localizar()

    if not registro_id:
        return

    uso = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM solicitacoes_itens
        WHERE produto_id = ?
        """,
        (registro_id,)
    )

    if uso and uso[0] > 0:
        st.warning(
            "⚠️ Produto já utilizado. Inative em vez de excluir."
        )
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_produto_{registro_id}"
    ):
        if _sisget_salvar(
            "DELETE FROM produtos WHERE id = ?",
            (registro_id,)
        ):
            st.rerun()


def produto_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            p.codigo AS "Código",
            p.descricao AS "Produto",
            g.descricao AS "Grupo",
            sg.descricao AS "Subgrupo",
            p.tipo_item AS "Tipo"
        FROM produtos p
        INNER JOIN grupos_produtos g
            ON g.id = p.grupo_id
        INNER JOIN subgrupos_produtos sg
            ON sg.id = p.subgrupo_id
        ORDER BY p.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Produtos",
        df,
        "produtos.pdf"
    )


# ============================================================
# TIPOS DE SOLICITAÇÃO
# ============================================================

def modulo_tipos_solicitacoes():

    st.subheader("📝 Solicitações")

    tipo = st.selectbox(
        "Tipo de Solicitação *",
        [
            "Selecione...",
            "📦 Solicitação Interna",
            "⚖️ Solicitação para Licitação",
            "🛒 Solicitação de Compra"
        ],
        key="sisget_tipo_solicitacao"
    )

    st.divider()

    if tipo == "Selecione...":
        st.info("Selecione o tipo de solicitação.")
        return

    elif tipo == "📦 Solicitação Interna":
        modulo_solicitacao_interna()

    elif tipo == "⚖️ Solicitação para Licitação":
        modulo_solicitacao_licitacao()

    elif tipo == "🛒 Solicitação de Compra":
        modulo_solicitacao_compra()


def modulo_solicitacao_interna():
    sisget_tela_principal(
        titulo="Solicitação Interna",
        chave="solicitacao_interna",
        func_incluir=solicitacao_interna_incluir,
        func_localizar=solicitacao_interna_localizar,
        func_alterar=solicitacao_interna_alterar,
        func_excluir=solicitacao_interna_excluir,
        func_imprimir=solicitacao_interna_imprimir,
        icone="📦"
    )


def modulo_solicitacao_compra():
    sisget_tela_principal(
        titulo="Solicitação de Compra",
        chave="solicitacao_compra",
        func_incluir=solicitacao_compra_incluir,
        func_localizar=solicitacao_compra_localizar,
        func_alterar=solicitacao_compra_alterar,
        func_excluir=solicitacao_compra_excluir,
        func_imprimir=solicitacao_compra_imprimir,
        icone="🛒"
    )


def modulo_solicitacao_licitacao():
    sisget_tela_principal(
        titulo="Solicitação para Licitação",
        chave="solicitacao_licitacao",
        func_incluir=solicitacao_licitacao_incluir,
        func_localizar=solicitacao_licitacao_localizar,
        func_alterar=solicitacao_licitacao_alterar,
        func_excluir=solicitacao_licitacao_excluir,
        func_imprimir=solicitacao_licitacao_imprimir,
        icone="⚖️"
    )


# ============================================================
# BASE DE INCLUSÃO DAS SOLICITAÇÕES
# ============================================================

def sisget_solicitacao_incluir_base(
    tipo_solicitacao,
    titulo,
    chave_reset,
    etapa_inicial
):

    # ========================================================
    # RESET
    # ========================================================

    if chave_reset not in st.session_state:

        st.session_state[
            chave_reset
        ] = 0

    reset = st.session_state[
        chave_reset
    ]

    # ========================================================
    # EXERCÍCIO
    # ========================================================

    exercicio = datetime.now().year

    # ========================================================
    # NÚMERO
    # ========================================================

    numero = sisget_proximo_numero_solicitacao(
        tipo_solicitacao,
        exercicio
    )

    if numero is None:

        return

    # ========================================================
    # PREFIXOS
    # ========================================================

    prefixos = {
        "INTERNA": "INT",
        "COMPRA": "COM",
        "LICITACAO": "LIC"
    }

    codigo = (
        f"{prefixos[tipo_solicitacao]}"
        f"-{exercicio}-"
        f"{str(numero).zfill(6)}"
    )

    # ========================================================
    # TÍTULO
    # ========================================================

    st.subheader(
        titulo
    )

    st.info(
        f"🔢 Código da Solicitação: {codigo}"
    )

    # ========================================================
    # MENSAGEM DE SUCESSO
    # ========================================================

    chave_mensagem = (
        f"sisget_mensagem_"
        f"{tipo_solicitacao.lower()}"
    )

    if chave_mensagem in st.session_state:

        st.success(
            st.session_state.pop(
                chave_mensagem
            )
        )

    # ========================================================
    # ENTIDADE DA SESSÃO
    # ========================================================

    entidade_sessao = st.session_state.get(
        "entidade_id"
    )

    # ========================================================
    # UNIDADES ADMINISTRATIVAS
    # ========================================================

    unidades = _sisget_fetch(
        """
        SELECT
            a.id,
            a.codigo,
            a.nome,

            a.entidade_id,
            a.orgao_id,
            a.unidade_orcamentaria_id,

            e.codigo,
            e.nome,

            o.codigo,
            o.nome,

            u.codigo,
            u.nome

        FROM unidades_administrativas a

        INNER JOIN entidades e
            ON e.id = a.entidade_id

        INNER JOIN orgaos o
            ON o.id = a.orgao_id

        INNER JOIN unidades_orcamentarias u
            ON u.id = a.unidade_orcamentaria_id

        WHERE a.ativo = TRUE
          AND e.ativo = TRUE
          AND o.ativo = TRUE
          AND u.ativo = TRUE

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
    # MAPA DAS UNIDADES
    # ========================================================

    mapa_unidades = {}

    for (
        unidade_id,
        codigo_unidade,
        nome_unidade,

        entidade_id_unidade,
        orgao_id,
        unidade_orcamentaria_id,

        codigo_entidade,
        nome_entidade,

        codigo_orgao,
        nome_orgao,

        codigo_uo,
        nome_uo
    ) in unidades:

        rotulo = (
            f"{codigo_orgao} - {nome_orgao}"
            f" → "
            f"{codigo_entidade} - {nome_entidade}"
            f" → "
            f"{codigo_uo} - {nome_uo}"
            f" → "
            f"{codigo_unidade} - {nome_unidade}"
        )

        mapa_unidades[
            rotulo
        ] = {
            "unidade_id": unidade_id,
            "entidade_id": entidade_id_unidade,
            "orgao_id": orgao_id,
            "uo_id": unidade_orcamentaria_id
        }

    # ========================================================
    # UNIDADE SELECIONADA
    # ========================================================

    unidade_nome = st.selectbox(
        "Unidade Administrativa *",
        list(
            mapa_unidades.keys()
        ),
        key=(
            f"sisget_sol_unidade_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    dados_unidade = mapa_unidades[
        unidade_nome
    ]

    unidade_administrativa_id = (
        dados_unidade[
            "unidade_id"
        ]
    )

    entidade_id = (
        dados_unidade[
            "entidade_id"
        ]
    )

    orgao_id = (
        dados_unidade[
            "orgao_id"
        ]
    )

    unidade_orcamentaria_id = (
        dados_unidade[
            "uo_id"
        ]
    )

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

    mapa_setores = {
        "Sem setor específico": None
    }

    for (
        setor_id_banco,
        codigo_setor,
        nome_setor
    ) in setores:

        mapa_setores[
            f"{codigo_setor} - {nome_setor}"
        ] = setor_id_banco

    setor_nome = st.selectbox(
        "Setor Solicitante",
        list(
            mapa_setores.keys()
        ),
        key=(
            f"sisget_sol_setor_"
            f"{tipo_solicitacao}_"
            f"{reset}_"
            f"{unidade_administrativa_id}"
        )
    )

    setor_id = mapa_setores[
        setor_nome
    ]

    # ========================================================
    # DOTAÇÕES
    # SOMENTE PARA LICITAÇÃO
    # ========================================================

    fichas_escolhidas = []
    mapa_fichas = {}

    if tipo_solicitacao == "LICITACAO":

        st.markdown("---")

        st.markdown(
            "### 💰 Dotações Orçamentárias"
        )

        fichas = _sisget_fetch(
            """
            SELECT
                id,
                numero_ficha,
                descricao,
                natureza_despesa,
                valor_atual,
                valor_reservado

            FROM fichas_orcamentarias

            WHERE entidade_id = ?
              AND unidade_orcamentaria_id = ?
              AND exercicio = ?
              AND ativo = TRUE

            ORDER BY
                numero_ficha
            """,
            (
                entidade_id,
                unidade_orcamentaria_id,
                exercicio
            )
        )

        for (
            ficha_id,
            numero_ficha,
            descricao_ficha,
            natureza_despesa,
            valor_atual,
            valor_reservado
        ) in fichas:

            valor_disponivel = (
                float(
                    valor_atual or 0
                )
                -
                float(
                    valor_reservado or 0
                )
            )

            rotulo_ficha = (
                f"Ficha {numero_ficha}"
                f" | "
                f"{descricao_ficha or 'Sem descrição'}"
                f" | Natureza: "
                f"{natureza_despesa or '-'}"
                f" | Disponível: "
                f"R$ {valor_disponivel:,.2f}"
            )

            mapa_fichas[
                rotulo_ficha
            ] = ficha_id

        if mapa_fichas:

            fichas_escolhidas = st.multiselect(
                "Dotações / Fichas Orçamentárias *",
                options=list(
                    mapa_fichas.keys()
                ),
                key=(
                    f"sisget_sol_fichas_"
                    f"{tipo_solicitacao}_"
                    f"{reset}_"
                    f"{unidade_orcamentaria_id}"
                )
            )

        else:

            st.warning(
                "⚠️ Não existem dotações/fichas "
                "orçamentárias ativas para esta "
                "Unidade Orçamentária."
            )

    # ========================================================
    # DADOS DA SOLICITAÇÃO
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📝 Dados da Solicitação"
    )

    st.text_input(
        "Código",
        value=codigo,
        disabled=True
    )

    prioridade = st.selectbox(
        "Prioridade *",
        [
            "Normal",
            "Alta",
            "Urgente"
        ],
        key=(
            f"sisget_sol_prioridade_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    objeto = st.text_area(
        "Objeto / Resumo *",
        height=120,
        key=(
            f"sisget_sol_objeto_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    justificativa = st.text_area(
        "Justificativa *",
        height=120,
        key=(
            f"sisget_sol_justificativa_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    data_necessidade = st.date_input(
        "Data da Necessidade",
        value=datetime.now().date(),
        key=(
            f"sisget_sol_data_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    observacao = st.text_area(
        "Observações",
        key=(
            f"sisget_sol_observacao_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    # ========================================================
    # ITENS
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📦 Itens da Solicitação"
    )

    chave_itens = (
        f"sisget_itens_nova_"
        f"{tipo_solicitacao}_"
        f"{reset}"
    )

    if chave_itens not in st.session_state:

        st.session_state[
            chave_itens
        ] = []

    # ========================================================
    # ENTIDADE PARA BUSCAR PRODUTOS
    #
    # PRIMEIRO: entidade da sessão
    # SEGUNDO: entidade da unidade selecionada
    # ========================================================

    entidade_produtos = entidade_sessao

    # ========================================================
    # PRODUTOS - PRIMEIRA BUSCA
    # ========================================================

    produtos = []

    if entidade_produtos is not None:

        produtos = _sisget_fetch(
            """
            SELECT
                p.id,
                p.codigo,

                COALESCE(
                    NULLIF(
                        TRIM(p.produto),
                        ''
                    ),
                    NULLIF(
                        TRIM(p.descricao),
                        ''
                    ),
                    'Produto sem descrição'
                ),

                p.descricao_complementar,

                p.tipo_item,

                g.codigo,
                g.descricao,

                sg.codigo,
                sg.descricao,

                uc.descricao,

                um.descricao,
                um.fator_conversao

            FROM produtos p

            LEFT JOIN grupos_produtos g
                ON g.id = p.grupo_id

            LEFT JOIN subgrupos_produtos sg
                ON sg.id = p.subgrupo_id

            LEFT JOIN unidades_compra uc
                ON uc.id = p.unidade_compra_id

            LEFT JOIN unidades_movimentacao um
                ON um.id = p.unidade_movimentacao_id

            WHERE p.ativo = TRUE
              AND p.entidade_id = ?

            ORDER BY
                p.codigo
            """,
            (
                entidade_produtos,
            )
        )

    # ========================================================
    # PRODUTOS - SEGUNDA BUSCA
    # ========================================================

    if not produtos:

        produtos = _sisget_fetch(
            """
            SELECT
                p.id,
                p.codigo,

                COALESCE(
                    NULLIF(
                        TRIM(p.produto),
                        ''
                    ),
                    NULLIF(
                        TRIM(p.descricao),
                        ''
                    ),
                    'Produto sem descrição'
                ),

                p.descricao_complementar,

                p.tipo_item,

                g.codigo,
                g.descricao,

                sg.codigo,
                sg.descricao,

                uc.descricao,

                um.descricao,
                um.fator_conversao

            FROM produtos p

            LEFT JOIN grupos_produtos g
                ON g.id = p.grupo_id

            LEFT JOIN subgrupos_produtos sg
                ON sg.id = p.subgrupo_id

            LEFT JOIN unidades_compra uc
                ON uc.id = p.unidade_compra_id

            LEFT JOIN unidades_movimentacao um
                ON um.id = p.unidade_movimentacao_id

            WHERE p.ativo = TRUE
              AND p.entidade_id = ?

            ORDER BY
                p.codigo
            """,
            (
                entidade_id,
            )
        )

    # ========================================================
    # TERCEIRA BUSCA
    #
    # SE AINDA NÃO ENCONTRAR, BUSCA TODOS OS PRODUTOS ATIVOS.
    # ISSO EVITA TRAVAR O TESTE DO SISTEMA ENQUANTO AS
    # ENTIDADES AINDA ESTÃO SENDO ORGANIZADAS.
    # ========================================================

    if not produtos:

        produtos = _sisget_fetch(
            """
            SELECT
                p.id,
                p.codigo,

                COALESCE(
                    NULLIF(
                        TRIM(p.produto),
                        ''
                    ),
                    NULLIF(
                        TRIM(p.descricao),
                        ''
                    ),
                    'Produto sem descrição'
                ),

                p.descricao_complementar,

                p.tipo_item,

                g.codigo,
                g.descricao,

                sg.codigo,
                sg.descricao,

                uc.descricao,

                um.descricao,
                um.fator_conversao

            FROM produtos p

            LEFT JOIN grupos_produtos g
                ON g.id = p.grupo_id

            LEFT JOIN subgrupos_produtos sg
                ON sg.id = p.subgrupo_id

            LEFT JOIN unidades_compra uc
                ON uc.id = p.unidade_compra_id

            LEFT JOIN unidades_movimentacao um
                ON um.id = p.unidade_movimentacao_id

            WHERE p.ativo = TRUE

            ORDER BY
                p.codigo
            """
        )

    # ========================================================
    # MAPA DOS PRODUTOS
    # ========================================================

    mapa_produtos = {}

    for (
        produto_id,
        codigo_produto,
        nome_produto,

        descricao_complementar,
        tipo_item,

        codigo_grupo,
        descricao_grupo,

        codigo_subgrupo,
        descricao_subgrupo,

        unidade_compra,
        unidade_movimentacao,
        fator_conversao
    ) in produtos:

        grupo_texto = (
            f"{codigo_grupo} - {descricao_grupo}"
            if codigo_grupo
            else "Sem grupo"
        )

        subgrupo_texto = (
            f"{codigo_subgrupo} - {descricao_subgrupo}"
            if codigo_subgrupo
            else "Sem subgrupo"
        )

        rotulo_produto = (
            f"{codigo_produto} - "
            f"{nome_produto}"
        )

        mapa_produtos[
            rotulo_produto
        ] = {
            "id": produto_id,

            "codigo": codigo_produto,

            "produto": nome_produto,

            "descricao_complementar": (
                descricao_complementar
                or ""
            ),

            "tipo_item": (
                tipo_item
                or ""
            ),

            "grupo": grupo_texto,

            "subgrupo": subgrupo_texto,

            "unidade_compra": (
                unidade_compra
                or ""
            ),

            "unidade_movimentacao": (
                unidade_movimentacao
                or ""
            ),

            "fator_conversao": float(
                fator_conversao or 1
            )
        }

    # ========================================================
    # FORMULÁRIO PARA ADICIONAR ITEM
    # ========================================================

    if not mapa_produtos:

        st.warning(
            "⚠️ Nenhum produto ativo encontrado "
            "no Cadastro de Produtos."
        )

    else:

        with st.form(
            f"form_adicionar_item_"
            f"{tipo_solicitacao}_"
            f"{reset}",
            clear_on_submit=True
        ):

            produto_nome = st.selectbox(
                "Produto *",
                list(
                    mapa_produtos.keys()
                )
            )

            dados_produto = mapa_produtos[
                produto_nome
            ]

            # =================================================
            # CLASSIFICAÇÃO
            # =================================================

            col_prod1, col_prod2 = st.columns(
                2
            )

            col_prod1.text_input(
                "Grupo",
                value=dados_produto[
                    "grupo"
                ],
                disabled=True
            )

            col_prod2.text_input(
                "Subgrupo",
                value=dados_produto[
                    "subgrupo"
                ],
                disabled=True
            )

            # =================================================
            # UNIDADES
            # =================================================

            col_un1, col_un2 = st.columns(
                2
            )

            col_un1.text_input(
                "Unidade de Compra",
                value=dados_produto[
                    "unidade_compra"
                ],
                disabled=True
            )

            col_un2.text_input(
                "Unidade de Movimentação",
                value=dados_produto[
                    "unidade_movimentacao"
                ],
                disabled=True
            )

            # =================================================
            # DESCRIÇÃO COMPLEMENTAR
            # =================================================

            if dados_produto[
                "descricao_complementar"
            ]:

                st.text_area(
                    "Descrição Complementar",
                    value=dados_produto[
                        "descricao_complementar"
                    ],
                    disabled=True,
                    height=80
                )

            # =================================================
            # QUANTIDADE / VALOR
            # =================================================

            col_item1, col_item2 = st.columns(
                2
            )

            quantidade = col_item1.number_input(
                "Quantidade *",
                min_value=0.000001,
                value=1.0,
                format="%.6f"
            )

            valor_unitario = col_item2.number_input(
                "Valor Estimado Unitário (R$)",
                min_value=0.0,
                value=0.0,
                format="%.2f"
            )

            observacao_item = st.text_input(
                "Observação do Item"
            )

            adicionar = st.form_submit_button(
                "➕ Adicionar Item",
                type="primary",
                use_container_width=True
            )

        # ====================================================
        # ADICIONAR ITEM
        # ====================================================

        if adicionar:

            dados_produto = mapa_produtos[
                produto_nome
            ]

            st.session_state[
                chave_itens
            ].append(
                {
                    "produto_id": (
                        dados_produto[
                            "id"
                        ]
                    ),

                    "codigo": (
                        dados_produto[
                            "codigo"
                        ]
                    ),

                    "produto": (
                        dados_produto[
                            "produto"
                        ]
                    ),

                    "unidade": (
                        dados_produto[
                            "unidade_compra"
                        ]
                    ),

                    "quantidade": float(
                        quantidade
                    ),

                    "valor_unitario": float(
                        valor_unitario
                    ),

                    "observacao": (
                        observacao_item.strip()
                        or None
                    )
                }
            )

            st.rerun()

    # ========================================================
    # ITENS ADICIONADOS
    # ========================================================

    itens = st.session_state[
        chave_itens
    ]

    if itens:

        st.markdown(
            "#### 📋 Itens adicionados"
        )

        for indice, item in enumerate(
            itens
        ):

            valor_total_item = (
                item[
                    "quantidade"
                ]
                *
                item[
                    "valor_unitario"
                ]
            )

            col_i1, col_i2, col_i3 = st.columns(
                [6, 3, 1]
            )

            col_i1.write(
                f"{item['codigo']} - "
                f"{item['produto']}"
            )

            col_i2.write(
                f"{item['quantidade']:,.2f}"
                f" × "
                f"R$ {item['valor_unitario']:,.2f}"
                f" = "
                f"R$ {valor_total_item:,.2f}"
            )

            if col_i3.button(
                "🗑️",
                key=(
                    f"remover_item_"
                    f"{tipo_solicitacao}_"
                    f"{reset}_"
                    f"{indice}"
                )
            ):

                itens.pop(
                    indice
                )

                st.rerun()

        # ====================================================
        # TOTAL
        # ====================================================

        valor_total = sum(
            item[
                "quantidade"
            ]
            *
            item[
                "valor_unitario"
            ]
            for item in itens
        )

        st.metric(
            "💰 Valor Estimado Total",
            f"R$ {valor_total:,.2f}"
        )

    else:

        st.info(
            "Nenhum item adicionado."
        )

    # ========================================================
    # BOTÃO SALVAR
    # ========================================================

    st.markdown("---")

    salvar = st.button(
        "💾 Salvar Solicitação",
        type="primary",
        use_container_width=True,
        key=(
            f"salvar_solicitacao_"
            f"{tipo_solicitacao}_"
            f"{reset}"
        )
    )

    # ========================================================
    # SALVAR
    # ========================================================

    if salvar:

        # ====================================================
        # VALIDAÇÕES
        # ====================================================

        if not objeto.strip():

            st.warning(
                "⚠️ Informe o objeto da solicitação."
            )

            return

        if not justificativa.strip():

            st.warning(
                "⚠️ Informe a justificativa."
            )

            return

        if not itens:

            st.warning(
                "⚠️ Adicione pelo menos um item."
            )

            return

        if (
            tipo_solicitacao == "LICITACAO"
            and
            not fichas_escolhidas
        ):

            st.warning(
                "⚠️ Selecione pelo menos uma "
                "dotação orçamentária."
            )

            return

        # ====================================================
        # RECALCULAR NÚMERO
        # ====================================================

        numero = sisget_proximo_numero_solicitacao(
            tipo_solicitacao,
            exercicio
        )

        if numero is None:

            return

        codigo = (
            f"{prefixos[tipo_solicitacao]}"
            f"-{exercicio}-"
            f"{str(numero).zfill(6)}"
        )

        # ====================================================
        # GRAVAÇÃO
        # ====================================================

        try:

            # =================================================
            # SOLICITAÇÃO
            # =================================================

            cursor.execute(
                """
                INSERT INTO solicitacoes
                (
                    codigo,
                    exercicio,
                    numero,

                    tipo_solicitacao,

                    unidade_administrativa_id,
                    setor_id,

                    solicitante_usuario_id,

                    prioridade,

                    objeto,
                    justificativa,

                    data_necessidade,
                    observacao,

                    status,
                    etapa_atual,

                    ativo
                )
                VALUES
                (
                    ?, ?, ?,

                    ?,

                    ?, ?,

                    ?,

                    ?,

                    ?, ?,

                    ?, ?,

                    'RASCUNHO',
                    ?,

                    TRUE
                )

                RETURNING id
                """,
                (
                    codigo,
                    exercicio,
                    str(
                        numero
                    ),

                    tipo_solicitacao,

                    unidade_administrativa_id,
                    setor_id,

                    st.session_state.get(
                        "usuario_id"
                    ),

                    prioridade,

                    objeto.strip(),
                    justificativa.strip(),

                    data_necessidade,

                    observacao.strip()
                    or None,

                    etapa_inicial
                )
            )

            retorno = cursor.fetchone()

            if not retorno:

                raise Exception(
                    "Não foi possível obter "
                    "o ID da solicitação."
                )

            solicitacao_id = retorno[
                0
            ]

            # =================================================
            # DOTAÇÕES DA LICITAÇÃO
            # =================================================

            if tipo_solicitacao == "LICITACAO":

                for ficha_nome in fichas_escolhidas:

                    ficha_id = mapa_fichas[
                        ficha_nome
                    ]

                    cursor.execute(
                        """
                        INSERT INTO
                            solicitacoes_fichas_orcamentarias
                        (
                            solicitacao_id,
                            ficha_orcamentaria_id
                        )
                        VALUES
                        (
                            ?, ?
                        )
                        """,
                        (
                            solicitacao_id,
                            ficha_id
                        )
                    )

            # =================================================
            # ITENS
            # =================================================

            for item in itens:

                valor_total_item = (
                    item[
                        "quantidade"
                    ]
                    *
                    item[
                        "valor_unitario"
                    ]
                )

                cursor.execute(
                    """
                    INSERT INTO solicitacoes_itens
                    (
                        solicitacao_id,
                        produto_id,

                        quantidade_solicitada,

                        valor_estimado_unitario,
                        valor_estimado_total,

                        observacao,

                        ativo
                    )
                    VALUES
                    (
                        ?, ?,

                        ?,

                        ?, ?,

                        ?,

                        TRUE
                    )
                    """,
                    (
                        solicitacao_id,

                        item[
                            "produto_id"
                        ],

                        item[
                            "quantidade"
                        ],

                        item[
                            "valor_unitario"
                        ],

                        valor_total_item,

                        item[
                            "observacao"
                        ]
                    )
                )

            # =================================================
            # COMMIT
            # =================================================

            conn.commit()

        except Exception as erro:

            try:

                conn.rollback()

            except Exception:

                pass

            st.error(
                f"❌ Não foi possível salvar "
                f"a solicitação: {erro}"
            )

            return

        # ====================================================
        # SUCESSO
        # ====================================================

        st.session_state[
            chave_mensagem
        ] = (
            f"✅ Solicitação {codigo} "
            f"salva com sucesso!"
        )

        # ====================================================
        # LIMPAR ITENS
        # ====================================================

        st.session_state.pop(
            chave_itens,
            None
        )

        # ====================================================
        # RESET
        # ====================================================

        st.session_state[
            chave_reset
        ] += 1

        # ====================================================
        # RERUN
        # ====================================================

        st.rerun()


def solicitacao_interna_incluir():

    sisget_solicitacao_incluir_base(
        "INTERNA",
        "📦 Solicitação Interna",
        "sisget_solicitacao_interna_reset",
        "ALMOXARIFADO"
    )


def solicitacao_compra_incluir():

    sisget_solicitacao_incluir_base(
        "COMPRA",
        "🛒 Solicitação de Compra",
        "sisget_solicitacao_compra_reset",
        "COMPRAS"
    )


def solicitacao_licitacao_incluir():

    sisget_solicitacao_incluir_base(
        "LICITACAO",
        "⚖️ Solicitação para Licitação",
        "sisget_solicitacao_licitacao_reset",
        "APROVACAO"
    )


# ============================================================
# LOCALIZAR / ALTERAR / EXCLUIR / IMPRIMIR SOLICITAÇÕES
# ============================================================

def sisget_solicitacao_localizar_tipo(
    tipo_solicitacao,
    chave
):
    df = _sisget_dataframe(
        """
        SELECT
            id,
            codigo AS "Código",
            objeto AS "Objeto",
            prioridade AS "Prioridade",
            status AS "Status",
            etapa_atual AS "Etapa"
        FROM solicitacoes
        WHERE tipo_solicitacao = ?
          AND ativo = TRUE
        ORDER BY exercicio DESC, numero DESC
        """,
        (tipo_solicitacao,)
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave=chave,
        coluna_id="id",
        altura=480
    )


def solicitacao_interna_localizar():
    return sisget_solicitacao_localizar_tipo(
        "INTERNA",
        "solicitacao_interna"
    )


def solicitacao_compra_localizar():
    return sisget_solicitacao_localizar_tipo(
        "COMPRA",
        "solicitacao_compra"
    )


def solicitacao_licitacao_localizar():
    return sisget_solicitacao_localizar_tipo(
        "LICITACAO",
        "solicitacao_licitacao"
    )


def sisget_solicitacao_alterar_base(
    solicitacao_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            objeto,
            justificativa,
            prioridade,
            observacao,
            status,
            etapa_atual
        FROM solicitacoes
        WHERE id = ?
        """,
        (solicitacao_id,)
    )

    if not registro:
        return

    (
        codigo,
        objeto_atual,
        justificativa_atual,
        prioridade_atual,
        observacao_atual,
        status,
        etapa_atual
    ) = registro

    prioridades = ["Normal", "Alta", "Urgente"]

    indice = (
        prioridades.index(prioridade_atual)
        if prioridade_atual in prioridades
        else 0
    )

    with st.form(
        f"form_solicitacao_alterar_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        st.text_input(
            "Etapa",
            value=etapa_atual or "",
            disabled=True
        )

        objeto = st.text_area(
            "Objeto *",
            value=objeto_atual or ""
        )

        justificativa = st.text_area(
            "Justificativa *",
            value=justificativa_atual or ""
        )

        prioridade = st.selectbox(
            "Prioridade *",
            prioridades,
            index=indice
        )

        observacao = st.text_area(
            "Observações",
            value=observacao_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes
            SET
                objeto = ?,
                justificativa = ?,
                prioridade = ?,
                observacao = ?
            WHERE id = ?
            """,
            (
                objeto.strip(),
                justificativa.strip(),
                prioridade,
                observacao.strip() or None,
                solicitacao_id
            )
        ):
            st.rerun()

    st.markdown("---")

    solicitacao_itens_editar(
        solicitacao_id
    )


def solicitacao_interna_alterar(solicitacao_id):
    sisget_solicitacao_alterar_base(
        solicitacao_id
    )


def solicitacao_compra_alterar(solicitacao_id):
    sisget_solicitacao_alterar_base(
        solicitacao_id
    )


def solicitacao_licitacao_alterar(solicitacao_id):
    sisget_solicitacao_alterar_base(
        solicitacao_id
    )

    st.markdown("---")

    solicitacao_licitacao_fluxo(
        solicitacao_id
    )


def sisget_solicitacao_excluir_tipo(
    tipo_solicitacao,
    chave
):
    solicitacao_id = sisget_solicitacao_localizar_tipo(
        tipo_solicitacao,
        chave
    )

    if not solicitacao_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_solicitacao_{solicitacao_id}"
    ):
        if _sisget_salvar(
            """
            UPDATE solicitacoes
            SET ativo = FALSE
            WHERE id = ?
            """,
            (solicitacao_id,)
        ):
            st.rerun()


def solicitacao_interna_excluir():
    sisget_solicitacao_excluir_tipo(
        "INTERNA",
        "excluir_solicitacao_interna"
    )


def solicitacao_compra_excluir():
    sisget_solicitacao_excluir_tipo(
        "COMPRA",
        "excluir_solicitacao_compra"
    )


def solicitacao_licitacao_excluir():
    sisget_solicitacao_excluir_tipo(
        "LICITACAO",
        "excluir_solicitacao_licitacao"
    )


def sisget_solicitacao_imprimir_tipo(
    tipo_solicitacao,
    titulo,
    arquivo
):
    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Código",
            objeto AS "Objeto",
            prioridade AS "Prioridade",
            status AS "Status",
            etapa_atual AS "Etapa"
        FROM solicitacoes
        WHERE tipo_solicitacao = ?
          AND ativo = TRUE
        ORDER BY exercicio DESC, numero DESC
        """,
        (tipo_solicitacao,)
    )

    sisget_relatorio_classificacao(
        titulo,
        df,
        arquivo
    )


def solicitacao_interna_imprimir():
    sisget_solicitacao_imprimir_tipo(
        "INTERNA",
        "Solicitações Internas",
        "solicitacoes_internas.pdf"
    )


def solicitacao_compra_imprimir():
    sisget_solicitacao_imprimir_tipo(
        "COMPRA",
        "Solicitações de Compra",
        "solicitacoes_compra.pdf"
    )


def solicitacao_licitacao_imprimir():
    sisget_solicitacao_imprimir_tipo(
        "LICITACAO",
        "Solicitações para Licitação",
        "solicitacoes_licitacao.pdf"
    )


# ============================================================
# ITENS DAS SOLICITAÇÕES
# ============================================================

def solicitacao_itens_editar(
    solicitacao_id
):

    produtos = _sisget_fetch(
        """
        SELECT id, codigo, descricao
        FROM produtos
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    if not produtos:
        st.warning("⚠️ Nenhum produto cadastrado.")
        return

    mapa = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in produtos
    }

    with st.form(
        f"form_item_solicitacao_{solicitacao_id}",
        clear_on_submit=True
    ):
        produto_nome = st.selectbox(
            "Produto *",
            list(mapa.keys())
        )

        quantidade = st.number_input(
            "Quantidade *",
            min_value=0.000001,
            value=1.0,
            format="%.6f"
        )

        valor_unitario = st.number_input(
            "Valor Estimado Unitário",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        observacao = st.text_input(
            "Observação"
        )

        adicionar = st.form_submit_button(
            "➕ Adicionar Item",
            type="primary",
            use_container_width=True
        )

    if adicionar:

        valor_total = (
            float(quantidade)
            *
            float(valor_unitario)
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_itens
            (
                solicitacao_id,
                produto_id,
                quantidade_solicitada,
                valor_estimado_unitario,
                valor_estimado_total,
                observacao,
                ativo
            )
            VALUES (?, ?, ?, ?, ?, ?, TRUE)
            """,
            (
                solicitacao_id,
                mapa[produto_nome],
                float(quantidade),
                float(valor_unitario),
                valor_total,
                observacao.strip() or None
            )
        ):
            st.rerun()

    df = _sisget_dataframe(
        """
        SELECT
            si.id,
            p.codigo AS "Código",
            p.descricao AS "Produto",
            si.quantidade_solicitada AS "Quantidade",
            si.valor_estimado_unitario AS "Valor Unitário",
            si.valor_estimado_total AS "Valor Total"
        FROM solicitacoes_itens si
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.solicitacao_id = ?
          AND si.ativo = TRUE
        ORDER BY si.id
        """,
        (solicitacao_id,)
    )

    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# AUXILIAR - MOVER ETAPA
# ============================================================

def sisget_solicitacao_mover_etapa(
    solicitacao_id,
    etapa_origem,
    etapa_destino,
    acao,
    observacao=None,
    status=None
):

    if status:
        sucesso = _sisget_salvar(
            """
            UPDATE solicitacoes
            SET
                etapa_atual = ?,
                status = ?
            WHERE id = ?
            """,
            (
                etapa_destino,
                status,
                solicitacao_id
            )
        )
    else:
        sucesso = _sisget_salvar(
            """
            UPDATE solicitacoes
            SET etapa_atual = ?
            WHERE id = ?
            """,
            (
                etapa_destino,
                solicitacao_id
            )
        )

    if sucesso:
        _sisget_salvar(
            """
            INSERT INTO solicitacoes_historico
            (
                solicitacao_id,
                usuario_id,
                etapa_origem,
                etapa_destino,
                acao,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                solicitacao_id,
                st.session_state.get("usuario_id"),
                etapa_origem,
                etapa_destino,
                acao,
                observacao
            )
        )

    return sucesso


# ============================================================
# FLUXO DA SOLICITAÇÃO PARA LICITAÇÃO
# ============================================================

def solicitacao_licitacao_fluxo(
    solicitacao_id
):

    registro = _sisget_fetchone(
        """
        SELECT etapa_atual, status
        FROM solicitacoes
        WHERE id = ?
        """,
        (solicitacao_id,)
    )

    if not registro:
        return

    etapa_atual, status = registro

    st.subheader("🔄 Fluxo da Solicitação")

    st.info(
        f"Status: {status} | Etapa: {etapa_atual}"
    )

    etapas = [
        "APROVACAO",
        "DFD",
        "ETP",
        "RISCOS",
        "COMPRAS",
        "CONTABILIDADE",
        "FINANCEIRO",
        "ORDENADOR",
        "LICITACAO",
        "TR",
        "LIBERACAO_LICITACAO"
    ]

    nomes = {
        "APROVACAO": "✅ Aprovação",
        "DFD": "📄 DFD",
        "ETP": "📘 ETP",
        "RISCOS": "⚠️ Mapa de Riscos",
        "COMPRAS": "🛒 Compras / Cotação",
        "CONTABILIDADE": "🧾 Contabilidade / Fichas",
        "FINANCEIRO": "💰 Financeiro",
        "ORDENADOR": "✍️ Ordenador",
        "LICITACAO": "⚖️ Enquadramento",
        "TR": "📑 Termo de Referência",
        "LIBERACAO_LICITACAO": "🚀 Liberação"
    }

    indice_atual = (
        etapas.index(etapa_atual)
        if etapa_atual in etapas
        else 0
    )

    for indice, etapa in enumerate(etapas):

        if indice < indice_atual:
            marcador = "✅"
        elif indice == indice_atual:
            marcador = "🟡"
        else:
            marcador = "🔒"

        st.write(
            f"{marcador} {nomes[etapa]}"
        )

    st.divider()

    if etapa_atual == "APROVACAO":
        solicitacao_etapa_aprovacao(
            solicitacao_id
        )

    elif etapa_atual == "DFD":
        solicitacao_dfd_editar(
            solicitacao_id
        )

    elif etapa_atual == "ETP":
        solicitacao_etp_editar(
            solicitacao_id
        )

    elif etapa_atual == "RISCOS":
        solicitacao_riscos_editar(
            solicitacao_id
        )

    elif etapa_atual == "COMPRAS":
        solicitacao_compras_cotacao(
            solicitacao_id
        )

    elif etapa_atual == "CONTABILIDADE":
        solicitacao_contabilidade_fichas(
            solicitacao_id
        )

    elif etapa_atual == "FINANCEIRO":
        solicitacao_financeiro_validar(
            solicitacao_id
        )

    elif etapa_atual == "ORDENADOR":
        solicitacao_ordenador_autorizar(
            solicitacao_id
        )

    elif etapa_atual == "LICITACAO":
        solicitacao_enquadramento_licitacao(
            solicitacao_id
        )

    elif etapa_atual == "TR":
        solicitacao_tr_editar(
            solicitacao_id
        )

    elif etapa_atual == "LIBERACAO_LICITACAO":
        solicitacao_liberar_licitacao(
            solicitacao_id
        )


# ============================================================
# APROVAÇÃO
# ============================================================

def solicitacao_etapa_aprovacao(
    solicitacao_id
):

    with st.form(
        f"form_aprovacao_{solicitacao_id}"
    ):
        observacao = st.text_area(
            "Observação"
        )

        col1, col2 = st.columns(2)

        aprovar = col1.form_submit_button(
            "✅ Aprovar",
            type="primary",
            use_container_width=True
        )

        rejeitar = col2.form_submit_button(
            "❌ Rejeitar",
            use_container_width=True
        )

    if aprovar:
        if sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "APROVACAO",
            "DFD",
            "SOLICITACAO_APROVADA",
            observacao.strip() or None,
            "EM_TRAMITACAO"
        ):
            st.rerun()

    if rejeitar:
        if sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "APROVACAO",
            "APROVACAO",
            "SOLICITACAO_REJEITADA",
            observacao.strip() or None,
            "REJEITADA"
        ):
            st.rerun()


# ============================================================
# DFD
# ============================================================

def solicitacao_dfd_editar(
    solicitacao_id
):

    with st.form(
        f"form_dfd_{solicitacao_id}"
    ):
        necessidade = st.text_area(
            "Descrição da Necessidade *"
        )

        justificativa = st.text_area(
            "Justificativa da Demanda *"
        )

        quantidade = st.text_area(
            "Quantidade Preliminar / Justificativa *"
        )

        previsao = st.date_input(
            "Previsão da Contratação"
        )

        alinhamento = st.text_area(
            "Alinhamento com o Planejamento"
        )

        salvar = st.form_submit_button(
            "💾 Salvar e Concluir DFD",
            type="primary",
            use_container_width=True
        )

    if salvar:

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_dfd
            (
                solicitacao_id,
                descricao_necessidade,
                justificativa_demanda,
                quantidade_preliminar,
                previsao_contratacao,
                alinhamento_planejamento
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (solicitacao_id)
            DO UPDATE SET
                descricao_necessidade = EXCLUDED.descricao_necessidade,
                justificativa_demanda = EXCLUDED.justificativa_demanda,
                quantidade_preliminar = EXCLUDED.quantidade_preliminar,
                previsao_contratacao = EXCLUDED.previsao_contratacao,
                alinhamento_planejamento = EXCLUDED.alinhamento_planejamento
            """,
            (
                solicitacao_id,
                necessidade.strip(),
                justificativa.strip(),
                quantidade.strip(),
                previsao,
                alinhamento.strip() or None
            )
        ):
            sisget_solicitacao_mover_etapa(
                solicitacao_id,
                "DFD",
                "ETP",
                "DFD_CONCLUIDO"
            )
            st.rerun()


# ============================================================
# ETP
# ============================================================

def solicitacao_etp_editar(
    solicitacao_id
):

    with st.form(
        f"form_etp_{solicitacao_id}"
    ):
        necessidade = st.text_area(
            "Necessidade / Problema *"
        )

        requisitos = st.text_area(
            "Requisitos da Contratação *"
        )

        mercado = st.text_area(
            "Levantamento de Mercado *"
        )

        solucao = st.text_area(
            "Solução Escolhida *"
        )

        justificativa_solucao = st.text_area(
            "Justificativa da Solução *"
        )

        quantidades = st.text_area(
            "Estimativa das Quantidades *"
        )

        valor = st.number_input(
            "Estimativa Inicial do Valor",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        parcelamento = st.checkbox(
            "Contratação parcelada?"
        )

        impactos = st.text_area(
            "Impactos / Sustentabilidade"
        )

        viabilidade = st.selectbox(
            "Conclusão *",
            ["Viável", "Inviável"]
        )

        salvar = st.form_submit_button(
            "💾 Salvar e Concluir ETP",
            type="primary",
            use_container_width=True
        )

    if salvar:

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_etp
            (
                solicitacao_id,
                necessidade,
                requisitos,
                levantamento_mercado,
                solucao_escolhida,
                justificativa_solucao,
                estimativa_quantidades,
                estimativa_valor,
                parcelamento,
                impactos,
                conclusao_viabilidade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (solicitacao_id)
            DO UPDATE SET
                necessidade = EXCLUDED.necessidade,
                requisitos = EXCLUDED.requisitos,
                levantamento_mercado = EXCLUDED.levantamento_mercado,
                solucao_escolhida = EXCLUDED.solucao_escolhida,
                justificativa_solucao = EXCLUDED.justificativa_solucao,
                estimativa_quantidades = EXCLUDED.estimativa_quantidades,
                estimativa_valor = EXCLUDED.estimativa_valor,
                parcelamento = EXCLUDED.parcelamento,
                impactos = EXCLUDED.impactos,
                conclusao_viabilidade = EXCLUDED.conclusao_viabilidade
            """,
            (
                solicitacao_id,
                necessidade.strip(),
                requisitos.strip(),
                mercado.strip(),
                solucao.strip(),
                justificativa_solucao.strip(),
                quantidades.strip(),
                float(valor),
                parcelamento,
                impactos.strip() or None,
                viabilidade
            )
        ):
            if viabilidade == "Viável":
                sisget_solicitacao_mover_etapa(
                    solicitacao_id,
                    "ETP",
                    "RISCOS",
                    "ETP_CONCLUIDO"
                )
            else:
                _sisget_salvar(
                    """
                    UPDATE solicitacoes
                    SET status = 'ETP_INVIAVEL'
                    WHERE id = ?
                    """,
                    (solicitacao_id,)
                )

            st.rerun()


# ============================================================
# MAPA DE RISCOS
# ============================================================

def solicitacao_riscos_editar(
    solicitacao_id
):

    with st.form(
        f"form_risco_{solicitacao_id}",
        clear_on_submit=True
    ):
        categoria = st.selectbox(
            "Categoria *",
            [
                "Técnico",
                "Financeiro",
                "Orçamentário",
                "Jurídico",
                "Operacional",
                "Prazo",
                "Fornecedor",
                "Mercado",
                "Fiscal",
                "Ambiental",
                "Logístico",
                "Outro"
            ]
        )

        evento = st.text_area(
            "Evento de Risco *"
        )

        causa = st.text_area(
            "Causa *"
        )

        consequencia = st.text_area(
            "Consequência *"
        )

        col1, col2 = st.columns(2)

        probabilidade = col1.selectbox(
            "Probabilidade",
            [1, 2, 3, 4, 5]
        )

        impacto = col2.selectbox(
            "Impacto",
            [1, 2, 3, 4, 5]
        )

        nivel = (
            int(probabilidade)
            *
            int(impacto)
        )

        st.info(
            f"Nível do Risco: {nivel}"
        )

        resposta = st.selectbox(
            "Resposta",
            [
                "Aceitar",
                "Mitigar",
                "Evitar",
                "Transferir"
            ]
        )

        preventiva = st.text_area(
            "Ação Preventiva"
        )

        contingencia = st.text_area(
            "Contingência"
        )

        responsavel = st.text_input(
            "Responsável"
        )

        adicionar = st.form_submit_button(
            "➕ Adicionar Risco",
            type="primary",
            use_container_width=True
        )

    if adicionar:
        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_riscos
            (
                solicitacao_id,
                categoria,
                evento,
                causa,
                consequencia,
                probabilidade,
                impacto,
                nivel,
                resposta,
                acao_preventiva,
                contingencia,
                responsavel,
                situacao
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'IDENTIFICADO'
            )
            """,
            (
                solicitacao_id,
                categoria,
                evento.strip(),
                causa.strip(),
                consequencia.strip(),
                int(probabilidade),
                int(impacto),
                nivel,
                resposta,
                preventiva.strip() or None,
                contingencia.strip() or None,
                responsavel.strip() or None
            )
        ):
            st.rerun()

    df = _sisget_dataframe(
        """
        SELECT
            categoria AS "Categoria",
            evento AS "Risco",
            probabilidade AS "Prob.",
            impacto AS "Impacto",
            nivel AS "Nível",
            resposta AS "Resposta"
        FROM solicitacoes_riscos
        WHERE solicitacao_id = ?
        ORDER BY nivel DESC
        """,
        (solicitacao_id,)
    )

    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    if st.button(
        "✅ Concluir Mapa de Riscos",
        type="primary",
        use_container_width=True,
        key=f"concluir_riscos_{solicitacao_id}"
    ):
        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "RISCOS",
            "COMPRAS",
            "RISCOS_CONCLUIDOS"
        )
        st.rerun()

# ============================================================
# FORNECEDORES - TELA PRINCIPAL
# ============================================================

def solicitacao_compras_cotacao(
    solicitacao_id
):

    itens = _sisget_fetch(
        """
        SELECT
            si.id,
            p.codigo,
            p.descricao
        FROM solicitacoes_itens si
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.solicitacao_id = ?
          AND si.ativo = TRUE
        ORDER BY si.id
        """,
        (solicitacao_id,)
    )

    fornecedores = _sisget_fetch(
        """
        SELECT id, codigo, razao_social
        FROM fornecedores
        WHERE ativo = TRUE
        ORDER BY razao_social
        """
    )

    if not itens or not fornecedores:
        st.warning(
            "⚠️ Necessário ter itens e fornecedores cadastrados."
        )
        return

    mapa_itens = {
        f"{codigo} - {descricao}": item_id
        for item_id, codigo, descricao in itens
    }

    mapa_fornecedores = {
        f"{codigo} - {razao}": fornecedor_id
        for fornecedor_id, codigo, razao in fornecedores
    }

    with st.form(
        f"form_cotacao_{solicitacao_id}",
        clear_on_submit=True
    ):
        item_nome = st.selectbox(
            "Item *",
            list(mapa_itens.keys())
        )

        fornecedor_nome = st.selectbox(
            "Fornecedor *",
            list(mapa_fornecedores.keys())
        )

        fonte = st.selectbox(
            "Fonte da Pesquisa *",
            [
                "Cotação com fornecedor",
                "Painel de preços",
                "Contratação anterior",
                "Ata / ARP",
                "Banco de preços",
                "Outra fonte"
            ]
        )

        valor_unitario = st.number_input(
            "Valor Unitário *",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        adicionar = st.form_submit_button(
            "➕ Adicionar Cotação",
            type="primary",
            use_container_width=True
        )

    if adicionar:

        if _sisget_salvar(
            """
            INSERT INTO cotacoes
            (
                solicitacao_id,
                solicitacao_item_id,
                fornecedor_id,
                fonte_pesquisa,
                valor_unitario
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                solicitacao_id,
                mapa_itens[item_nome],
                mapa_fornecedores[fornecedor_nome],
                fonte,
                float(valor_unitario)
            )
        ):
            st.rerun()

    df = _sisget_dataframe(
        """
        SELECT
            p.descricao AS "Item",
            f.razao_social AS "Fornecedor",
            c.fonte_pesquisa AS "Fonte",
            c.valor_unitario AS "Valor Unitário"
        FROM cotacoes c
        INNER JOIN solicitacoes_itens si
            ON si.id = c.solicitacao_item_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        INNER JOIN fornecedores f
            ON f.id = c.fornecedor_id
        WHERE c.solicitacao_id = ?
        ORDER BY p.descricao, c.valor_unitario
        """,
        (solicitacao_id,)
    )

    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    if st.button(
        "✅ Concluir Cotação",
        type="primary",
        use_container_width=True,
        key=f"concluir_cotacao_{solicitacao_id}"
    ):
        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "COMPRAS",
            "CONTABILIDADE",
            "COTACAO_CONCLUIDA"
        )
        st.rerun()


# ============================================================
# CONTABILIDADE / FICHAS
# ============================================================

def solicitacao_contabilidade_fichas(
    solicitacao_id
):

    fichas = _sisget_fetch(
        """
        SELECT id, exercicio, numero_ficha, descricao
        FROM fichas_orcamentarias
        WHERE ativo = TRUE
        ORDER BY exercicio DESC, numero_ficha
        """
    )

    if not fichas:
        st.warning(
            "⚠️ Nenhuma ficha orçamentária ativa."
        )
        return

    mapa = {
        (
            f"{exercicio}"
            f" | Ficha {numero_ficha}"
            f" | {descricao or ''}"
        ): ficha_id
        for (
            ficha_id,
            exercicio,
            numero_ficha,
            descricao
        ) in fichas
    }

    with st.form(
        f"form_fichas_{solicitacao_id}",
        clear_on_submit=True
    ):
        ficha_nome = st.selectbox(
            "Ficha Orçamentária *",
            list(mapa.keys())
        )

        valor = st.number_input(
            "Valor Vinculado *",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        adicionar = st.form_submit_button(
            "➕ Vincular Ficha",
            type="primary",
            use_container_width=True
        )

    if adicionar:
        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_fichas
            (
                solicitacao_id,
                ficha_orcamentaria_id,
                valor_vinculado,
                validada_contabilidade
            )
            VALUES (?, ?, ?, TRUE)
            """,
            (
                solicitacao_id,
                mapa[ficha_nome],
                float(valor)
            )
        ):
            st.rerun()

    df = _sisget_dataframe(
        """
        SELECT
            f.numero_ficha AS "Ficha",
            f.exercicio AS "Exercício",
            sf.valor_vinculado AS "Valor"
        FROM solicitacoes_fichas sf
        INNER JOIN fichas_orcamentarias f
            ON f.id = sf.ficha_orcamentaria_id
        WHERE sf.solicitacao_id = ?
        ORDER BY sf.id
        """,
        (solicitacao_id,)
    )

    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    if st.button(
        "✅ Validar Contabilidade",
        type="primary",
        use_container_width=True,
        key=f"validar_contabilidade_{solicitacao_id}"
    ):
        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "CONTABILIDADE",
            "FINANCEIRO",
            "CONTABILIDADE_VALIDOU"
        )
        st.rerun()


# ============================================================
# FINANCEIRO
# ============================================================

def solicitacao_financeiro_validar(
    solicitacao_id
):

    with st.form(
        f"form_financeiro_{solicitacao_id}"
    ):
        valor_validado = st.number_input(
            "Valor Validado *",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        cota = st.number_input(
            "Cota Financeira",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        reserva = st.number_input(
            "Reserva",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        parecer = st.text_area(
            "Parecer Financeiro"
        )

        validar = st.form_submit_button(
            "✅ Validar Financeiro",
            type="primary",
            use_container_width=True
        )

    if validar:
        _sisget_salvar(
            """
            INSERT INTO solicitacoes_financeiro
            (
                solicitacao_id,
                valor_validado,
                cota,
                reserva,
                parecer
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                solicitacao_id,
                float(valor_validado),
                float(cota),
                float(reserva),
                parecer.strip() or None
            )
        )

        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "FINANCEIRO",
            "ORDENADOR",
            "FINANCEIRO_VALIDOU"
        )

        st.rerun()


# ============================================================
# ORDENADOR
# ============================================================

def solicitacao_ordenador_autorizar(
    solicitacao_id
):

    with st.form(
        f"form_ordenador_{solicitacao_id}"
    ):
        despacho = st.text_area(
            "Despacho"
        )

        col1, col2 = st.columns(2)

        autorizar = col1.form_submit_button(
            "✍️ Autorizar",
            type="primary",
            use_container_width=True
        )

        devolver = col2.form_submit_button(
            "↩️ Devolver",
            use_container_width=True
        )

    if autorizar:
        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "ORDENADOR",
            "LICITACAO",
            "ORDENADOR_AUTORIZOU",
            despacho.strip() or None,
            "AUTORIZADA"
        )
        st.rerun()

    if devolver:
        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "ORDENADOR",
            "COMPRAS",
            "ORDENADOR_DEVOLVEU",
            despacho.strip() or None,
            "DEVOLVIDA"
        )
        st.rerun()


# ============================================================
# ENQUADRAMENTO
# ============================================================

def solicitacao_enquadramento_licitacao(
    solicitacao_id
):

    with st.form(
        f"form_enquadramento_{solicitacao_id}"
    ):
        tipo_processo = st.selectbox(
            "Tipo do Processo *",
            [
                "Licitação",
                "Contratação Direta"
            ]
        )

        tipo_objeto = st.selectbox(
            "Tipo do Objeto *",
            [
                "Aquisição de bens",
                "Serviço",
                "Serviço de engenharia",
                "Obra",
                "Locação",
                "Tecnologia da Informação",
                "Outro"
            ]
        )

        modalidade = st.selectbox(
            "Modalidade / Forma *",
            (
                [
                    "Pregão",
                    "Concorrência",
                    "Concurso",
                    "Leilão",
                    "Diálogo Competitivo"
                ]
                if tipo_processo == "Licitação"
                else
                [
                    "Dispensa",
                    "Inexigibilidade"
                ]
            )
        )

        criterio = st.selectbox(
            "Critério de Julgamento",
            [
                "Menor preço",
                "Maior desconto",
                "Técnica e preço",
                "Melhor técnica",
                "Maior lance",
                "Maior retorno econômico",
                "Não se aplica"
            ]
        )

        modo_disputa = st.selectbox(
            "Modo de Disputa",
            [
                "Aberto",
                "Fechado",
                "Aberto e Fechado",
                "Não se aplica"
            ]
        )

        registro_precos = st.checkbox(
            "Sistema de Registro de Preços - SRP"
        )

        fundamento = st.text_input(
            "Fundamento Legal"
        )

        justificativa = st.text_area(
            "Justificativa do Enquadramento *"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Enquadramento",
            type="primary",
            use_container_width=True
        )

    if salvar:

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_enquadramento
            (
                solicitacao_id,
                tipo_processo,
                tipo_objeto,
                modalidade,
                criterio_julgamento,
                modo_disputa,
                registro_precos,
                fundamento_legal,
                justificativa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (solicitacao_id)
            DO UPDATE SET
                tipo_processo = EXCLUDED.tipo_processo,
                tipo_objeto = EXCLUDED.tipo_objeto,
                modalidade = EXCLUDED.modalidade,
                criterio_julgamento = EXCLUDED.criterio_julgamento,
                modo_disputa = EXCLUDED.modo_disputa,
                registro_precos = EXCLUDED.registro_precos,
                fundamento_legal = EXCLUDED.fundamento_legal,
                justificativa = EXCLUDED.justificativa
            """,
            (
                solicitacao_id,
                tipo_processo,
                tipo_objeto,
                modalidade,
                criterio,
                modo_disputa,
                registro_precos,
                fundamento.strip() or None,
                justificativa.strip()
            )
        ):
            sisget_solicitacao_mover_etapa(
                solicitacao_id,
                "LICITACAO",
                "TR",
                "ENQUADRAMENTO_CONCLUIDO"
            )

            st.rerun()


# ============================================================
# TERMO DE REFERÊNCIA
# ============================================================

def solicitacao_tr_editar(
    solicitacao_id
):

    with st.form(
        f"form_tr_{solicitacao_id}"
    ):
        objeto = st.text_area(
            "1. Definição do Objeto *"
        )

        fundamentacao = st.text_area(
            "2. Fundamentação *"
        )

        solucao = st.text_area(
            "3. Descrição da Solução *"
        )

        requisitos = st.text_area(
            "4. Requisitos da Contratação *"
        )

        execucao = st.text_area(
            "5. Modelo de Execução *"
        )

        gestao = st.text_area(
            "6. Gestão e Fiscalização"
        )

        pagamento = st.text_area(
            "7. Medição e Pagamento"
        )

        selecao = st.text_area(
            "8. Critérios de Seleção"
        )

        valor = st.text_area(
            "9. Estimativa do Valor"
        )

        adequacao = st.text_area(
            "10. Adequação Orçamentária"
        )

        obrigacoes_contratada = st.text_area(
            "11. Obrigações da Contratada"
        )

        obrigacoes_adm = st.text_area(
            "12. Obrigações da Administração"
        )

        sancoes = st.text_area(
            "13. Sanções"
        )

        salvar = st.form_submit_button(
            "💾 Salvar e Concluir TR",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_tr
            (
                solicitacao_id,
                objeto,
                fundamentacao,
                descricao_solucao,
                requisitos,
                modelo_execucao,
                gestao_fiscalizacao,
                medicao_pagamento,
                criterios_selecao,
                estimativa_valor,
                adequacao_orcamentaria,
                obrigacoes_contratada,
                obrigacoes_administracao,
                sancoes
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (solicitacao_id)
            DO UPDATE SET
                objeto = EXCLUDED.objeto,
                fundamentacao = EXCLUDED.fundamentacao,
                descricao_solucao = EXCLUDED.descricao_solucao,
                requisitos = EXCLUDED.requisitos,
                modelo_execucao = EXCLUDED.modelo_execucao,
                gestao_fiscalizacao = EXCLUDED.gestao_fiscalizacao,
                medicao_pagamento = EXCLUDED.medicao_pagamento,
                criterios_selecao = EXCLUDED.criterios_selecao,
                estimativa_valor = EXCLUDED.estimativa_valor,
                adequacao_orcamentaria = EXCLUDED.adequacao_orcamentaria,
                obrigacoes_contratada = EXCLUDED.obrigacoes_contratada,
                obrigacoes_administracao = EXCLUDED.obrigacoes_administracao,
                sancoes = EXCLUDED.sancoes
            """,
            (
                solicitacao_id,
                objeto.strip(),
                fundamentacao.strip(),
                solucao.strip(),
                requisitos.strip(),
                execucao.strip(),
                gestao.strip() or None,
                pagamento.strip() or None,
                selecao.strip() or None,
                valor.strip() or None,
                adequacao.strip() or None,
                obrigacoes_contratada.strip() or None,
                obrigacoes_adm.strip() or None,
                sancoes.strip() or None
            )
        ):
            sisget_solicitacao_mover_etapa(
                solicitacao_id,
                "TR",
                "LIBERACAO_LICITACAO",
                "TR_CONCLUIDO"
            )

            st.rerun()


# ============================================================
# LIBERAÇÃO
# ============================================================

def solicitacao_liberar_licitacao(
    solicitacao_id
):

    verificacoes = {
        "DFD": _sisget_fetchone(
            "SELECT id FROM solicitacoes_dfd WHERE solicitacao_id = ?",
            (solicitacao_id,)
        ),
        "ETP": _sisget_fetchone(
            "SELECT id FROM solicitacoes_etp WHERE solicitacao_id = ?",
            (solicitacao_id,)
        ),
        "Riscos": _sisget_fetchone(
            "SELECT id FROM solicitacoes_riscos WHERE solicitacao_id = ? LIMIT 1",
            (solicitacao_id,)
        ),
        "Cotação": _sisget_fetchone(
            "SELECT id FROM cotacoes WHERE solicitacao_id = ? LIMIT 1",
            (solicitacao_id,)
        ),
        "Fichas": _sisget_fetchone(
            "SELECT id FROM solicitacoes_fichas WHERE solicitacao_id = ? LIMIT 1",
            (solicitacao_id,)
        ),
        "Financeiro": _sisget_fetchone(
            "SELECT id FROM solicitacoes_financeiro WHERE solicitacao_id = ? LIMIT 1",
            (solicitacao_id,)
        ),
        "Enquadramento": _sisget_fetchone(
            "SELECT id FROM solicitacoes_enquadramento WHERE solicitacao_id = ?",
            (solicitacao_id,)
        ),
        "TR": _sisget_fetchone(
            "SELECT id FROM solicitacoes_tr WHERE solicitacao_id = ?",
            (solicitacao_id,)
        )
    }

    tudo_ok = True

    for nome, registro in verificacoes.items():
        if registro:
            st.success(
                f"✅ {nome}"
            )
        else:
            st.error(
                f"❌ {nome}"
            )
            tudo_ok = False

    if not tudo_ok:
        st.warning(
            "⚠️ O processo ainda possui pendências."
        )
        return

    if st.button(
        "🚀 Liberar Processo",
        type="primary",
        use_container_width=True,
        key=f"liberar_processo_{solicitacao_id}"
    ):
        enquadramento = _sisget_fetchone(
            """
            SELECT tipo_processo
            FROM solicitacoes_enquadramento
            WHERE solicitacao_id = ?
            """,
            (solicitacao_id,)
        )

        tipo = (
            enquadramento[0]
            if enquadramento
            else "Licitação"
        )

        destino = (
            "MODULO_LICITACOES"
            if tipo == "Licitação"
            else "MODULO_CONTRATACAO_DIRETA"
        )

        sisget_solicitacao_mover_etapa(
            solicitacao_id,
            "LIBERACAO_LICITACAO",
            destino,
            "PROCESSO_LIBERADO",
            tipo,
            "LIBERADA"
        )

        st.rerun()


# ============================================================
# PLANEJAMENTO DE COMPRAS
# ============================================================

def modulo_planejamento_compras():

    st.title("📊 Planejamento de Compras")

    opcao = st.selectbox(
        "Planejamento *",
        [
            "Selecione...",
            "📥 Necessidades das Solicitações",
            "📦 Análise de Estoque",
            "⚠️ Itens em Falta",
            "🛒 Necessidade de Compra",
            "🔗 Consolidação de Demandas",
            "📋 Agrupamento para Licitação",
            "🔄 Processos em Andamento",
            "📑 ARP / Contratos com Saldo",
            "🚨 Alertas",
            "📊 Dashboard"
        ],
        key="sisget_planejamento_compras"
    )

    st.divider()

    if opcao == "Selecione...":
        st.info("Selecione uma opção.")
        return

    elif opcao == "📥 Necessidades das Solicitações":
        planejamento_necessidades_solicitacoes()

    elif opcao == "📦 Análise de Estoque":
        planejamento_analise_estoque()

    elif opcao == "⚠️ Itens em Falta":
        planejamento_itens_falta()

    elif opcao == "🛒 Necessidade de Compra":
        planejamento_necessidade_compra()

    elif opcao == "🔗 Consolidação de Demandas":
        planejamento_consolidacao_demandas()

    elif opcao == "📋 Agrupamento para Licitação":
        planejamento_agrupar_licitacao()

    elif opcao == "🔄 Processos em Andamento":
        planejamento_processos_andamento()

    elif opcao == "📑 ARP / Contratos com Saldo":
        planejamento_atas_contratos()

    elif opcao == "🚨 Alertas":
        planejamento_alertas()

    elif opcao == "📊 Dashboard":
        planejamento_dashboard()


def planejamento_necessidades_solicitacoes():

    df = _sisget_dataframe(
        """
        SELECT
            p.id,
            p.codigo AS "Código",
            p.descricao AS "Produto",
            SUM(si.quantidade_solicitada) AS "Solicitado"
        FROM solicitacoes_itens si
        INNER JOIN solicitacoes s
            ON s.id = si.solicitacao_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE s.ativo = TRUE
          AND si.ativo = TRUE
          AND s.status NOT IN ('REJEITADA', 'CANCELADA')
        GROUP BY
            p.id,
            p.codigo,
            p.descricao
        ORDER BY p.descricao
        """
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def planejamento_analise_estoque():
    st.info(
        "Integração futura com Almoxarifado: "
        "solicitações + estoque atual + estoque mínimo + entradas pendentes."
    )


def planejamento_itens_falta():
    st.info(
        "Listará itens cujo estoque não cobre a demanda."
    )


def planejamento_necessidade_compra():
    st.info(
        "Fórmula: Solicitado + Estoque Mínimo "
        "- Estoque Disponível - Em Compra."
    )


def planejamento_consolidacao_demandas():
    st.info(
        "Consolidação do mesmo produto solicitado por várias unidades."
    )


def planejamento_agrupar_licitacao():
    st.info(
        "Agrupamento das necessidades para futura licitação."
    )


def planejamento_processos_andamento():

    df = _sisget_dataframe(
        """
        SELECT
            codigo AS "Solicitação",
            objeto AS "Objeto",
            status AS "Status",
            etapa_atual AS "Etapa"
        FROM solicitacoes
        WHERE ativo = TRUE
        ORDER BY exercicio DESC, numero DESC
        """
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def planejamento_atas_contratos():
    st.info(
        "Integração futura com Atas/ARP e Contratos."
    )


def planejamento_alertas():
    st.info(
        "Alertas de estoque baixo, múltiplas demandas, "
        "ARP vencendo e processos em andamento."
    )


def planejamento_dashboard():

    total = _sisget_fetchone(
        """
        SELECT COUNT(*)
        FROM solicitacoes
        WHERE ativo = TRUE
        """
    )

    st.metric(
        "Solicitações",
        int(total[0] or 0)
        if total
        else 0
    )

# ============================================================
# COMPLEMENTO CRUD COMPLETO - DOCUMENTOS E FLUXO
# ============================================================
# As defs abaixo completam o módulo com telas próprias de:
# Itens, DFD, ETP, Riscos, Cotações, Fichas, Financeiro,
# Enquadramento, TR, Histórico e Assinaturas.
#
# IMPORTANTE:
# No início do SISGET.py deixe:
# import hashlib
# from datetime import datetime
# ============================================================


# ============================================================
# MAPA / SELEÇÃO DE SOLICITAÇÕES
# ============================================================

def sisget_mapa_solicitacoes(
    tipo_solicitacao=None,
    somente_ativas=True
):
    sql = """
        SELECT
            id,
            codigo,
            objeto,
            tipo_solicitacao,
            status,
            etapa_atual
        FROM solicitacoes
        WHERE 1 = 1
    """

    parametros = []

    if somente_ativas:
        sql += " AND ativo = TRUE "

    if tipo_solicitacao:
        sql += " AND tipo_solicitacao = ? "
        parametros.append(tipo_solicitacao)

    sql += """
        ORDER BY
            exercicio DESC,
            numero DESC
    """

    dados = _sisget_fetch(
        sql,
        tuple(parametros)
    )

    mapa = {}

    for (
        id_,
        codigo,
        objeto,
        tipo,
        status,
        etapa
    ) in dados:

        nome = (
            f"{codigo or id_}"
            f" | {tipo or ''}"
            f" | {objeto or ''}"
            f" | {status or ''}"
            f" | {etapa or ''}"
        )

        mapa[nome] = id_

    return mapa


def sisget_selecionar_solicitacao(
    label,
    key,
    tipo_solicitacao=None
):
    mapa = sisget_mapa_solicitacoes(
        tipo_solicitacao=tipo_solicitacao
    )

    if not mapa:
        st.warning(
            "⚠️ Nenhuma solicitação disponível."
        )
        return None

    nome = st.selectbox(
        label,
        list(mapa.keys()),
        key=key
    )

    return mapa[nome]


# ============================================================
# SUBMENU COMPLETO DE SOLICITAÇÕES
# Esta definição substitui a anterior.
# ============================================================

def modulo_tipos_solicitacoes():

    st.subheader(
        "📝 Solicitações"
    )

    tipo = st.selectbox(
        "Área *",
        [
            "Selecione...",
            "📦 Solicitação Interna",
            "⚖️ Solicitação para Licitação",
            "🛒 Solicitação de Compra",
            "🧩 Documentos / Fluxo",
            "📜 Histórico Geral",
            "✍️ Assinaturas"
        ],
        key="sisget_tipo_solicitacao"
    )

    st.divider()

    if tipo == "Selecione...":
        st.info(
            "Selecione uma opção."
        )
        return

    elif tipo == "📦 Solicitação Interna":
        modulo_solicitacao_interna()

    elif tipo == "⚖️ Solicitação para Licitação":
        modulo_solicitacao_licitacao()

    elif tipo == "🛒 Solicitação de Compra":
        modulo_solicitacao_compra()

    elif tipo == "🧩 Documentos / Fluxo":
        modulo_documentos_solicitacoes()

    elif tipo == "📜 Histórico Geral":
        cadastro_historico_solicitacoes()

    elif tipo == "✍️ Assinaturas":
        cadastro_assinaturas_solicitacoes()


# ============================================================
# DOCUMENTOS / FLUXO
# ============================================================

def modulo_documentos_solicitacoes():

    st.subheader(
        "🧩 Documentos / Fluxo"
    )

    opcao = st.selectbox(
        "Cadastro *",
        [
            "Selecione...",
            "📦 Itens",
            "📄 DFD",
            "📘 ETP",
            "⚠️ Mapa de Riscos",
            "💲 Cotações",
            "🧾 Fichas Orçamentárias",
            "💰 Financeiro",
            "⚖️ Enquadramento",
            "📑 Termo de Referência - TR"
        ],
        key="sisget_documentos_fluxo_solicitacoes"
    )

    st.divider()

    if opcao == "Selecione...":
        st.info(
            "Selecione o cadastro."
        )
        return

    elif opcao == "📦 Itens":
        cadastro_itens_solicitacoes()

    elif opcao == "📄 DFD":
        cadastro_dfd_solicitacoes()

    elif opcao == "📘 ETP":
        cadastro_etp_solicitacoes()

    elif opcao == "⚠️ Mapa de Riscos":
        cadastro_riscos_solicitacoes()

    elif opcao == "💲 Cotações":
        cadastro_cotacoes_solicitacoes()

    elif opcao == "🧾 Fichas Orçamentárias":
        cadastro_fichas_solicitacoes()

    elif opcao == "💰 Financeiro":
        cadastro_financeiro_solicitacoes()

    elif opcao == "⚖️ Enquadramento":
        cadastro_enquadramento_solicitacoes()

    elif opcao == "📑 Termo de Referência - TR":
        cadastro_tr_solicitacoes()


# ============================================================
# ITENS - TELA PRINCIPAL
# ============================================================

def cadastro_itens_solicitacoes():

    sisget_tela_principal(
        titulo="Itens das Solicitações",
        chave="solicitacoes_itens",
        func_incluir=solicitacao_item_incluir,
        func_localizar=solicitacao_item_localizar,
        func_alterar=solicitacao_item_alterar,
        func_excluir=solicitacao_item_excluir,
        func_imprimir=solicitacao_item_imprimir,
        icone="📦"
    )


def solicitacao_item_incluir():

    if "sisget_item_solicitacao_reset" not in st.session_state:
        st.session_state[
            "sisget_item_solicitacao_reset"
        ] = 0

    reset = st.session_state[
        "sisget_item_solicitacao_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"item_solicitacao_{reset}"
    )

    if not solicitacao_id:
        return

    produtos = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            descricao
        FROM produtos
        WHERE ativo = TRUE
        ORDER BY codigo
        """
    )

    if not produtos:
        st.warning(
            "⚠️ Nenhum produto ativo cadastrado."
        )
        return

    mapa_produtos = {
        f"{codigo} - {descricao}": id_
        for id_, codigo, descricao in produtos
    }

    codigo = sisget_proximo_codigo(
        "solicitacoes_itens",
        tamanho=6
    )

    with st.form(
        f"form_solicitacao_item_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        produto_nome = st.selectbox(
            "Produto *",
            list(mapa_produtos.keys())
        )

        quantidade = st.number_input(
            "Quantidade *",
            min_value=0.000001,
            value=1.0,
            format="%.6f"
        )

        valor_unitario = st.number_input(
            "Valor Estimado Unitário",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        observacao = st.text_area(
            "Observação"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Item",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_itens",
            tamanho=6
        )

        valor_total = (
            float(quantidade)
            *
            float(valor_unitario)
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_itens
            (
                codigo,
                solicitacao_id,
                produto_id,
                quantidade_solicitada,
                valor_estimado_unitario,
                valor_estimado_total,
                observacao,
                ativo
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, TRUE
            )
            """,
            (
                codigo,
                solicitacao_id,
                mapa_produtos[produto_nome],
                float(quantidade),
                float(valor_unitario),
                valor_total,
                observacao.strip() or None
            )
        ):
            st.session_state[
                "sisget_item_solicitacao_reset"
            ] += 1
            st.rerun()


def solicitacao_item_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            si.id,
            si.codigo AS "Código",
            s.codigo AS "Solicitação",
            p.codigo AS "Produto Código",
            p.descricao AS "Produto",
            si.quantidade_solicitada AS "Quantidade",
            si.valor_estimado_unitario AS "Valor Unitário",
            si.valor_estimado_total AS "Valor Total"
        FROM solicitacoes_itens si
        INNER JOIN solicitacoes s
            ON s.id = si.solicitacao_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.ativo = TRUE
        ORDER BY si.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_itens",
        coluna_id="id",
        altura=480
    )


def solicitacao_item_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            quantidade_solicitada,
            valor_estimado_unitario,
            observacao,
            ativo
        FROM solicitacoes_itens
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        quantidade_atual,
        valor_atual,
        observacao_atual,
        ativo
    ) = registro

    with st.form(
        f"form_item_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        quantidade = st.number_input(
            "Quantidade *",
            min_value=0.000001,
            value=float(quantidade_atual or 1),
            format="%.6f"
        )

        valor_unitario = st.number_input(
            "Valor Unitário",
            min_value=0.0,
            value=float(valor_atual or 0),
            format="%.2f"
        )

        observacao = st.text_area(
            "Observação",
            value=observacao_atual or ""
        )

        col1, col2 = st.columns(2)

        salvar = col1.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

        mudar = col2.form_submit_button(
            "🚫 Inativar"
            if ativo
            else "✅ Ativar",
            use_container_width=True
        )

    if mudar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_itens
            SET ativo = ?
            WHERE id = ?
            """,
            (
                not ativo,
                registro_id
            )
        ):
            st.rerun()

    if salvar:
        valor_total = (
            float(quantidade)
            *
            float(valor_unitario)
        )

        if _sisget_salvar(
            """
            UPDATE solicitacoes_itens
            SET
                quantidade_solicitada = ?,
                valor_estimado_unitario = ?,
                valor_estimado_total = ?,
                observacao = ?
            WHERE id = ?
            """,
            (
                float(quantidade),
                float(valor_unitario),
                valor_total,
                observacao.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def solicitacao_item_excluir():

    registro_id = solicitacao_item_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_item_solicitacao_{registro_id}"
    ):
        if _sisget_salvar(
            """
            UPDATE solicitacoes_itens
            SET ativo = FALSE
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def solicitacao_item_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            p.codigo AS "Produto",
            p.descricao AS "Descrição",
            si.quantidade_solicitada AS "Quantidade",
            si.valor_estimado_unitario AS "Valor Unitário",
            si.valor_estimado_total AS "Valor Total"
        FROM solicitacoes_itens si
        INNER JOIN solicitacoes s
            ON s.id = si.solicitacao_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.ativo = TRUE
        ORDER BY s.codigo, p.codigo
        """
    )

    sisget_relatorio_classificacao(
        "Itens das Solicitações",
        df,
        "solicitacoes_itens.pdf"
    )


# ============================================================
# DFD - CRUD
# ============================================================

def cadastro_dfd_solicitacoes():
    sisget_tela_principal(
        titulo="DFD - Documento de Formalização da Demanda",
        chave="solicitacoes_dfd",
        func_incluir=dfd_incluir,
        func_localizar=dfd_localizar,
        func_alterar=dfd_alterar,
        func_excluir=dfd_excluir,
        func_imprimir=dfd_imprimir,
        icone="📄"
    )


def dfd_incluir():

    if "sisget_dfd_reset" not in st.session_state:
        st.session_state["sisget_dfd_reset"] = 0

    reset = st.session_state[
        "sisget_dfd_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação para Licitação *",
        f"dfd_solicitacao_{reset}",
        "LICITACAO"
    )

    if not solicitacao_id:
        return

    existe = _sisget_fetchone(
        """
        SELECT id
        FROM solicitacoes_dfd
        WHERE solicitacao_id = ?
        """,
        (solicitacao_id,)
    )

    if existe:
        st.warning(
            "⚠️ Esta solicitação já possui DFD."
        )
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_dfd",
        tamanho=6
    )

    with st.form(
        f"form_dfd_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        necessidade = st.text_area(
            "Descrição da Necessidade *"
        )

        justificativa = st.text_area(
            "Justificativa da Demanda *"
        )

        quantidade = st.text_area(
            "Quantidade Preliminar / Justificativa"
        )

        previsao = st.date_input(
            "Previsão da Contratação"
        )

        alinhamento = st.text_area(
            "Alinhamento com o Planejamento"
        )

        observacoes = st.text_area(
            "Observações"
        )

        salvar = st.form_submit_button(
            "💾 Salvar DFD",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_dfd",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_dfd
            (
                codigo,
                solicitacao_id,
                descricao_necessidade,
                justificativa_demanda,
                quantidade_preliminar,
                previsao_contratacao,
                alinhamento_planejamento,
                observacoes
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                necessidade.strip(),
                justificativa.strip(),
                quantidade.strip() or None,
                previsao,
                alinhamento.strip() or None,
                observacoes.strip() or None
            )
        ):
            st.session_state[
                "sisget_dfd_reset"
            ] += 1
            st.rerun()


def dfd_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            d.id,
            d.codigo AS "Código",
            s.codigo AS "Solicitação",
            s.objeto AS "Objeto",
            d.previsao_contratacao AS "Previsão"
        FROM solicitacoes_dfd d
        INNER JOIN solicitacoes s
            ON s.id = d.solicitacao_id
        ORDER BY d.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_dfd",
        coluna_id="id",
        altura=450
    )


def dfd_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            descricao_necessidade,
            justificativa_demanda,
            quantidade_preliminar,
            previsao_contratacao,
            alinhamento_planejamento,
            observacoes
        FROM solicitacoes_dfd
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        necessidade_atual,
        justificativa_atual,
        quantidade_atual,
        previsao_atual,
        alinhamento_atual,
        observacoes_atual
    ) = registro

    with st.form(
        f"form_dfd_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        necessidade = st.text_area(
            "Descrição da Necessidade *",
            value=necessidade_atual or ""
        )

        justificativa = st.text_area(
            "Justificativa da Demanda *",
            value=justificativa_atual or ""
        )

        quantidade = st.text_area(
            "Quantidade Preliminar",
            value=quantidade_atual or ""
        )

        previsao = st.date_input(
            "Previsão da Contratação",
            value=previsao_atual
            if previsao_atual
            else datetime.now().date()
        )

        alinhamento = st.text_area(
            "Alinhamento com Planejamento",
            value=alinhamento_atual or ""
        )

        observacoes = st.text_area(
            "Observações",
            value=observacoes_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_dfd
            SET
                descricao_necessidade = ?,
                justificativa_demanda = ?,
                quantidade_preliminar = ?,
                previsao_contratacao = ?,
                alinhamento_planejamento = ?,
                observacoes = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                necessidade.strip(),
                justificativa.strip(),
                quantidade.strip() or None,
                previsao,
                alinhamento.strip() or None,
                observacoes.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def dfd_excluir():

    registro_id = dfd_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão do DFD",
        type="primary",
        use_container_width=True,
        key=f"excluir_dfd_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_dfd
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def dfd_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            d.codigo AS "Código",
            s.codigo AS "Solicitação",
            s.objeto AS "Objeto",
            d.descricao_necessidade AS "Necessidade",
            d.justificativa_demanda AS "Justificativa",
            d.previsao_contratacao AS "Previsão"
        FROM solicitacoes_dfd d
        INNER JOIN solicitacoes s
            ON s.id = d.solicitacao_id
        ORDER BY d.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "DFD - Documentos de Formalização da Demanda",
        df,
        "dfd_solicitacoes.pdf"
    )


# ============================================================
# ETP - CRUD
# ============================================================

def cadastro_etp_solicitacoes():
    sisget_tela_principal(
        titulo="ETP - Estudo Técnico Preliminar",
        chave="solicitacoes_etp",
        func_incluir=etp_incluir,
        func_localizar=etp_localizar,
        func_alterar=etp_alterar,
        func_excluir=etp_excluir,
        func_imprimir=etp_imprimir,
        icone="📘"
    )


def etp_incluir():

    if "sisget_etp_reset" not in st.session_state:
        st.session_state["sisget_etp_reset"] = 0

    reset = st.session_state[
        "sisget_etp_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação para Licitação *",
        f"etp_solicitacao_{reset}",
        "LICITACAO"
    )

    if not solicitacao_id:
        return

    existe = _sisget_fetchone(
        """
        SELECT id
        FROM solicitacoes_etp
        WHERE solicitacao_id = ?
        """,
        (solicitacao_id,)
    )

    if existe:
        st.warning(
            "⚠️ Esta solicitação já possui ETP."
        )
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_etp",
        tamanho=6
    )

    with st.form(
        f"form_etp_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        necessidade = st.text_area(
            "Necessidade / Problema *"
        )

        requisitos = st.text_area(
            "Requisitos da Contratação *"
        )

        mercado = st.text_area(
            "Levantamento de Mercado *"
        )

        solucao = st.text_area(
            "Solução Escolhida *"
        )

        justificativa = st.text_area(
            "Justificativa da Solução *"
        )

        quantidades = st.text_area(
            "Estimativa / Justificativa das Quantidades *"
        )

        valor = st.number_input(
            "Estimativa de Valor",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        parcelamento = st.checkbox(
            "Contratação parcelada?"
        )

        justificativa_parcelamento = st.text_area(
            "Justificativa do Parcelamento / Não Parcelamento"
        )

        impactos = st.text_area(
            "Impactos / Sustentabilidade"
        )

        viabilidade = st.selectbox(
            "Conclusão de Viabilidade *",
            ["Viável", "Inviável"]
        )

        salvar = st.form_submit_button(
            "💾 Salvar ETP",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_etp",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_etp
            (
                codigo,
                solicitacao_id,
                necessidade,
                requisitos,
                levantamento_mercado,
                solucao_escolhida,
                justificativa_solucao,
                estimativa_quantidades,
                estimativa_valor,
                parcelamento,
                justificativa_parcelamento,
                impactos,
                conclusao_viabilidade
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                necessidade.strip(),
                requisitos.strip(),
                mercado.strip(),
                solucao.strip(),
                justificativa.strip(),
                quantidades.strip(),
                float(valor),
                parcelamento,
                justificativa_parcelamento.strip() or None,
                impactos.strip() or None,
                viabilidade
            )
        ):
            st.session_state[
                "sisget_etp_reset"
            ] += 1
            st.rerun()


def etp_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            e.id,
            e.codigo AS "Código",
            s.codigo AS "Solicitação",
            s.objeto AS "Objeto",
            e.estimativa_valor AS "Valor",
            e.conclusao_viabilidade AS "Viabilidade"
        FROM solicitacoes_etp e
        INNER JOIN solicitacoes s
            ON s.id = e.solicitacao_id
        ORDER BY e.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_etp",
        coluna_id="id",
        altura=450
    )


def etp_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            necessidade,
            requisitos,
            levantamento_mercado,
            solucao_escolhida,
            justificativa_solucao,
            estimativa_quantidades,
            estimativa_valor,
            parcelamento,
            justificativa_parcelamento,
            impactos,
            conclusao_viabilidade
        FROM solicitacoes_etp
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        necessidade_atual,
        requisitos_atual,
        mercado_atual,
        solucao_atual,
        justificativa_atual,
        quantidades_atual,
        valor_atual,
        parcelamento_atual,
        justificativa_parc_atual,
        impactos_atual,
        viabilidade_atual
    ) = registro

    with st.form(
        f"form_etp_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        necessidade = st.text_area(
            "Necessidade *",
            value=necessidade_atual or ""
        )

        requisitos = st.text_area(
            "Requisitos *",
            value=requisitos_atual or ""
        )

        mercado = st.text_area(
            "Levantamento de Mercado *",
            value=mercado_atual or ""
        )

        solucao = st.text_area(
            "Solução Escolhida *",
            value=solucao_atual or ""
        )

        justificativa = st.text_area(
            "Justificativa da Solução *",
            value=justificativa_atual or ""
        )

        quantidades = st.text_area(
            "Estimativa das Quantidades *",
            value=quantidades_atual or ""
        )

        valor = st.number_input(
            "Estimativa de Valor",
            min_value=0.0,
            value=float(valor_atual or 0),
            format="%.2f"
        )

        parcelamento = st.checkbox(
            "Parcelamento",
            value=bool(parcelamento_atual)
        )

        justificativa_parc = st.text_area(
            "Justificativa do Parcelamento",
            value=justificativa_parc_atual or ""
        )

        impactos = st.text_area(
            "Impactos",
            value=impactos_atual or ""
        )

        viabilidade = st.selectbox(
            "Viabilidade",
            ["Viável", "Inviável"],
            index=(
                0
                if viabilidade_atual != "Inviável"
                else 1
            )
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_etp
            SET
                necessidade = ?,
                requisitos = ?,
                levantamento_mercado = ?,
                solucao_escolhida = ?,
                justificativa_solucao = ?,
                estimativa_quantidades = ?,
                estimativa_valor = ?,
                parcelamento = ?,
                justificativa_parcelamento = ?,
                impactos = ?,
                conclusao_viabilidade = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                necessidade.strip(),
                requisitos.strip(),
                mercado.strip(),
                solucao.strip(),
                justificativa.strip(),
                quantidades.strip(),
                float(valor),
                parcelamento,
                justificativa_parc.strip() or None,
                impactos.strip() or None,
                viabilidade,
                registro_id
            )
        ):
            st.rerun()


def etp_excluir():

    registro_id = etp_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão do ETP",
        type="primary",
        use_container_width=True,
        key=f"excluir_etp_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_etp
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def etp_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            e.codigo AS "Código",
            s.codigo AS "Solicitação",
            s.objeto AS "Objeto",
            e.solucao_escolhida AS "Solução",
            e.estimativa_valor AS "Valor",
            e.conclusao_viabilidade AS "Viabilidade"
        FROM solicitacoes_etp e
        INNER JOIN solicitacoes s
            ON s.id = e.solicitacao_id
        ORDER BY e.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "Estudos Técnicos Preliminares",
        df,
        "etp_solicitacoes.pdf"
    )


# ============================================================
# RISCOS - CRUD
# ============================================================

def cadastro_riscos_solicitacoes():
    sisget_tela_principal(
        titulo="Mapa de Riscos",
        chave="solicitacoes_riscos",
        func_incluir=risco_incluir,
        func_localizar=risco_localizar,
        func_alterar=risco_alterar,
        func_excluir=risco_excluir,
        func_imprimir=risco_imprimir,
        icone="⚠️"
    )


def risco_incluir():

    if "sisget_risco_reset" not in st.session_state:
        st.session_state["sisget_risco_reset"] = 0

    reset = st.session_state[
        "sisget_risco_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"risco_solicitacao_{reset}",
        "LICITACAO"
    )

    if not solicitacao_id:
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_riscos",
        tamanho=6
    )

    with st.form(
        f"form_risco_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        categoria = st.selectbox(
            "Categoria *",
            [
                "Técnico",
                "Financeiro",
                "Orçamentário",
                "Jurídico",
                "Operacional",
                "Prazo",
                "Fornecedor",
                "Mercado",
                "Fiscal",
                "Ambiental",
                "Logístico",
                "Outro"
            ]
        )

        evento = st.text_area(
            "Evento de Risco *"
        )

        causa = st.text_area(
            "Causa *"
        )

        consequencia = st.text_area(
            "Consequência *"
        )

        col1, col2 = st.columns(2)

        probabilidade = col1.selectbox(
            "Probabilidade",
            [1, 2, 3, 4, 5]
        )

        impacto = col2.selectbox(
            "Impacto",
            [1, 2, 3, 4, 5]
        )

        nivel = (
            int(probabilidade)
            *
            int(impacto)
        )

        st.info(
            f"Nível calculado: {nivel}"
        )

        resposta = st.selectbox(
            "Resposta",
            [
                "Aceitar",
                "Mitigar",
                "Evitar",
                "Transferir"
            ]
        )

        preventiva = st.text_area(
            "Ação Preventiva"
        )

        contingencia = st.text_area(
            "Contingência"
        )

        responsavel = st.text_input(
            "Responsável"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Risco",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_riscos",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_riscos
            (
                codigo,
                solicitacao_id,
                categoria,
                evento,
                causa,
                consequencia,
                probabilidade,
                impacto,
                nivel,
                resposta,
                acao_preventiva,
                contingencia,
                responsavel,
                situacao
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IDENTIFICADO')
            """,
            (
                codigo,
                solicitacao_id,
                categoria,
                evento.strip(),
                causa.strip(),
                consequencia.strip(),
                int(probabilidade),
                int(impacto),
                nivel,
                resposta,
                preventiva.strip() or None,
                contingencia.strip() or None,
                responsavel.strip() or None
            )
        ):
            st.session_state[
                "sisget_risco_reset"
            ] += 1
            st.rerun()


def risco_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            r.id,
            r.codigo AS "Código",
            s.codigo AS "Solicitação",
            r.categoria AS "Categoria",
            r.evento AS "Risco",
            r.probabilidade AS "Prob.",
            r.impacto AS "Impacto",
            r.nivel AS "Nível",
            r.situacao AS "Situação"
        FROM solicitacoes_riscos r
        INNER JOIN solicitacoes s
            ON s.id = r.solicitacao_id
        ORDER BY r.nivel DESC, r.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_riscos",
        coluna_id="id",
        altura=480
    )


def risco_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            evento,
            causa,
            consequencia,
            probabilidade,
            impacto,
            resposta,
            acao_preventiva,
            contingencia,
            responsavel,
            situacao
        FROM solicitacoes_riscos
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        evento_atual,
        causa_atual,
        consequencia_atual,
        prob_atual,
        impacto_atual,
        resposta_atual,
        preventiva_atual,
        contingencia_atual,
        responsavel_atual,
        situacao_atual
    ) = registro

    respostas = [
        "Aceitar",
        "Mitigar",
        "Evitar",
        "Transferir"
    ]

    situacoes = [
        "IDENTIFICADO",
        "EM_TRATAMENTO",
        "MITIGADO",
        "OCORRIDO",
        "ENCERRADO"
    ]

    with st.form(
        f"form_risco_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        evento = st.text_area(
            "Evento",
            value=evento_atual or ""
        )

        causa = st.text_area(
            "Causa",
            value=causa_atual or ""
        )

        consequencia = st.text_area(
            "Consequência",
            value=consequencia_atual or ""
        )

        col1, col2 = st.columns(2)

        probabilidade = col1.selectbox(
            "Probabilidade",
            [1, 2, 3, 4, 5],
            index=max(
                0,
                min(
                    4,
                    int(prob_atual or 1) - 1
                )
            )
        )

        impacto = col2.selectbox(
            "Impacto",
            [1, 2, 3, 4, 5],
            index=max(
                0,
                min(
                    4,
                    int(impacto_atual or 1) - 1
                )
            )
        )

        resposta = st.selectbox(
            "Resposta",
            respostas,
            index=(
                respostas.index(resposta_atual)
                if resposta_atual in respostas
                else 0
            )
        )

        preventiva = st.text_area(
            "Ação Preventiva",
            value=preventiva_atual or ""
        )

        contingencia = st.text_area(
            "Contingência",
            value=contingencia_atual or ""
        )

        responsavel = st.text_input(
            "Responsável",
            value=responsavel_atual or ""
        )

        situacao = st.selectbox(
            "Situação",
            situacoes,
            index=(
                situacoes.index(situacao_atual)
                if situacao_atual in situacoes
                else 0
            )
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        nivel = (
            int(probabilidade)
            *
            int(impacto)
        )

        if _sisget_salvar(
            """
            UPDATE solicitacoes_riscos
            SET
                evento = ?,
                causa = ?,
                consequencia = ?,
                probabilidade = ?,
                impacto = ?,
                nivel = ?,
                resposta = ?,
                acao_preventiva = ?,
                contingencia = ?,
                responsavel = ?,
                situacao = ?
            WHERE id = ?
            """,
            (
                evento.strip(),
                causa.strip(),
                consequencia.strip(),
                int(probabilidade),
                int(impacto),
                nivel,
                resposta,
                preventiva.strip() or None,
                contingencia.strip() or None,
                responsavel.strip() or None,
                situacao,
                registro_id
            )
        ):
            st.rerun()


def risco_excluir():

    registro_id = risco_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão do Risco",
        type="primary",
        use_container_width=True,
        key=f"excluir_risco_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_riscos
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def risco_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            r.codigo AS "Código",
            r.categoria AS "Categoria",
            r.evento AS "Risco",
            r.probabilidade AS "Prob.",
            r.impacto AS "Impacto",
            r.nivel AS "Nível",
            r.resposta AS "Resposta",
            r.situacao AS "Situação"
        FROM solicitacoes_riscos r
        INNER JOIN solicitacoes s
            ON s.id = r.solicitacao_id
        ORDER BY s.codigo, r.nivel DESC
        """
    )

    sisget_relatorio_classificacao(
        "Mapa de Riscos",
        df,
        "mapa_riscos.pdf"
    )


# ============================================================
# COTAÇÕES - CRUD
# ============================================================

def cadastro_cotacoes_solicitacoes():
    sisget_tela_principal(
        titulo="Cotações / Pesquisa de Preços",
        chave="cotacoes",
        func_incluir=cotacao_incluir,
        func_localizar=cotacao_localizar,
        func_alterar=cotacao_alterar,
        func_excluir=cotacao_excluir,
        func_imprimir=cotacao_imprimir,
        icone="💲"
    )


def cotacao_incluir():

    if "sisget_cotacao_reset" not in st.session_state:
        st.session_state["sisget_cotacao_reset"] = 0

    reset = st.session_state[
        "sisget_cotacao_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"cotacao_solicitacao_{reset}"
    )

    if not solicitacao_id:
        return

    itens = _sisget_fetch(
        """
        SELECT
            si.id,
            p.codigo,
            p.descricao,
            si.quantidade_solicitada
        FROM solicitacoes_itens si
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.solicitacao_id = ?
          AND si.ativo = TRUE
        ORDER BY si.id
        """,
        (solicitacao_id,)
    )

    fornecedores = _sisget_fetch(
        """
        SELECT
            id,
            codigo,
            razao_social
        FROM fornecedores
        WHERE ativo = TRUE
        ORDER BY razao_social
        """
    )

    if not itens:
        st.warning(
            "⚠️ Solicitação sem itens."
        )
        return

    if not fornecedores:
        st.warning(
            "⚠️ Cadastre fornecedores."
        )
        return

    mapa_itens = {
        (
            f"{codigo} - {descricao}"
            f" | Qtd: {float(qtd):g}"
        ): item_id
        for item_id, codigo, descricao, qtd in itens
    }

    mapa_fornecedores = {
        f"{codigo} - {razao}": fornecedor_id
        for fornecedor_id, codigo, razao in fornecedores
    }

    codigo = sisget_proximo_codigo(
        "cotacoes",
        tamanho=6
    )

    with st.form(
        f"form_cotacao_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        item_nome = st.selectbox(
            "Item *",
            list(mapa_itens.keys())
        )

        fornecedor_nome = st.selectbox(
            "Fornecedor *",
            list(mapa_fornecedores.keys())
        )

        fonte = st.selectbox(
            "Fonte da Pesquisa *",
            [
                "Cotação com fornecedor",
                "Painel de preços",
                "Contratação anterior",
                "Ata / ARP",
                "Banco de preços",
                "Outra fonte"
            ]
        )

        valor_unitario = st.number_input(
            "Valor Unitário *",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        observacao = st.text_area(
            "Observação"
        )

        documento_url = st.text_input(
            "Documento / URL"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Cotação",
            type="primary",
            use_container_width=True
        )

    if salvar:
        item_id = mapa_itens[item_nome]

        qtd_registro = _sisget_fetchone(
            """
            SELECT quantidade_solicitada
            FROM solicitacoes_itens
            WHERE id = ?
            """,
            (item_id,)
        )

        quantidade = float(
            qtd_registro[0] or 0
        )

        valor_total = (
            quantidade
            *
            float(valor_unitario)
        )

        codigo = sisget_proximo_codigo(
            "cotacoes",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO cotacoes
            (
                codigo,
                solicitacao_id,
                solicitacao_item_id,
                fornecedor_id,
                fonte_pesquisa,
                valor_unitario,
                valor_total,
                observacao,
                documento_url
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                item_id,
                mapa_fornecedores[fornecedor_nome],
                fonte,
                float(valor_unitario),
                valor_total,
                observacao.strip() or None,
                documento_url.strip() or None
            )
        ):
            st.session_state[
                "sisget_cotacao_reset"
            ] += 1
            st.rerun()


def cotacao_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            c.id,
            c.codigo AS "Código",
            s.codigo AS "Solicitação",
            p.descricao AS "Item",
            f.razao_social AS "Fornecedor",
            c.fonte_pesquisa AS "Fonte",
            c.valor_unitario AS "Valor Unitário",
            c.valor_total AS "Valor Total"
        FROM cotacoes c
        INNER JOIN solicitacoes s
            ON s.id = c.solicitacao_id
        INNER JOIN solicitacoes_itens si
            ON si.id = c.solicitacao_item_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        LEFT JOIN fornecedores f
            ON f.id = c.fornecedor_id
        ORDER BY c.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="cotacoes",
        coluna_id="id",
        altura=480
    )


def cotacao_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            valor_unitario,
            observacao,
            documento_url
        FROM cotacoes
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        valor_atual,
        observacao_atual,
        documento_atual
    ) = registro

    with st.form(
        f"form_cotacao_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        valor = st.number_input(
            "Valor Unitário *",
            min_value=0.0,
            value=float(valor_atual or 0),
            format="%.2f"
        )

        observacao = st.text_area(
            "Observação",
            value=observacao_atual or ""
        )

        documento = st.text_input(
            "Documento / URL",
            value=documento_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        item = _sisget_fetchone(
            """
            SELECT
                si.quantidade_solicitada
            FROM cotacoes c
            INNER JOIN solicitacoes_itens si
                ON si.id = c.solicitacao_item_id
            WHERE c.id = ?
            """,
            (registro_id,)
        )

        quantidade = float(
            item[0] or 0
        )

        total = (
            quantidade
            *
            float(valor)
        )

        if _sisget_salvar(
            """
            UPDATE cotacoes
            SET
                valor_unitario = ?,
                valor_total = ?,
                observacao = ?,
                documento_url = ?
            WHERE id = ?
            """,
            (
                float(valor),
                total,
                observacao.strip() or None,
                documento.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def cotacao_excluir():

    registro_id = cotacao_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão da Cotação",
        type="primary",
        use_container_width=True,
        key=f"excluir_cotacao_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM cotacoes
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def cotacao_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            p.descricao AS "Item",
            f.razao_social AS "Fornecedor",
            c.fonte_pesquisa AS "Fonte",
            c.valor_unitario AS "Valor Unitário",
            c.valor_total AS "Valor Total"
        FROM cotacoes c
        INNER JOIN solicitacoes s
            ON s.id = c.solicitacao_id
        INNER JOIN solicitacoes_itens si
            ON si.id = c.solicitacao_item_id
        INNER JOIN produtos p
            ON p.id = si.produto_id
        LEFT JOIN fornecedores f
            ON f.id = c.fornecedor_id
        ORDER BY s.codigo, p.descricao, c.valor_unitario
        """
    )

    sisget_relatorio_classificacao(
        "Cotações / Pesquisa de Preços",
        df,
        "cotacoes.pdf"
    )


# ============================================================
# FICHAS ORÇAMENTÁRIAS DA SOLICITAÇÃO - CRUD
# ============================================================

def cadastro_fichas_solicitacoes():
    sisget_tela_principal(
        titulo="Fichas Orçamentárias das Solicitações",
        chave="solicitacoes_fichas",
        func_incluir=solicitacao_ficha_incluir,
        func_localizar=solicitacao_ficha_localizar,
        func_alterar=solicitacao_ficha_alterar,
        func_excluir=solicitacao_ficha_excluir,
        func_imprimir=solicitacao_ficha_imprimir,
        icone="🧾"
    )


def solicitacao_ficha_incluir():

    if "sisget_sol_ficha_reset" not in st.session_state:
        st.session_state["sisget_sol_ficha_reset"] = 0

    reset = st.session_state[
        "sisget_sol_ficha_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"sol_ficha_solicitacao_{reset}"
    )

    if not solicitacao_id:
        return

    fichas = _sisget_fetch(
        """
        SELECT
            id,
            exercicio,
            numero_ficha,
            descricao
        FROM fichas_orcamentarias
        WHERE ativo = TRUE
        ORDER BY exercicio DESC, numero_ficha
        """
    )

    if not fichas:
        st.warning(
            "⚠️ Nenhuma ficha orçamentária ativa."
        )
        return

    mapa_fichas = {
        (
            f"{exercicio}"
            f" | Ficha {numero_ficha}"
            f" | {descricao or ''}"
        ): id_
        for id_, exercicio, numero_ficha, descricao in fichas
    }

    itens = _sisget_fetch(
        """
        SELECT
            si.id,
            p.codigo,
            p.descricao
        FROM solicitacoes_itens si
        INNER JOIN produtos p
            ON p.id = si.produto_id
        WHERE si.solicitacao_id = ?
          AND si.ativo = TRUE
        ORDER BY si.id
        """,
        (solicitacao_id,)
    )

    mapa_itens = {
        "Toda a Solicitação": None
    }

    for id_, codigo, descricao in itens:
        mapa_itens[
            f"{codigo} - {descricao}"
        ] = id_

    codigo = sisget_proximo_codigo(
        "solicitacoes_fichas",
        tamanho=6
    )

    with st.form(
        f"form_sol_ficha_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        ficha_nome = st.selectbox(
            "Ficha Orçamentária *",
            list(mapa_fichas.keys())
        )

        item_nome = st.selectbox(
            "Vincular ao Item",
            list(mapa_itens.keys())
        )

        valor = st.number_input(
            "Valor Vinculado *",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        observacao = st.text_area(
            "Observação"
        )

        salvar = st.form_submit_button(
            "💾 Vincular Ficha",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_fichas",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_fichas
            (
                codigo,
                solicitacao_id,
                ficha_orcamentaria_id,
                solicitacao_item_id,
                valor_vinculado,
                validada_contabilidade,
                observacao
            )
            VALUES
            (?, ?, ?, ?, ?, TRUE, ?)
            """,
            (
                codigo,
                solicitacao_id,
                mapa_fichas[ficha_nome],
                mapa_itens[item_nome],
                float(valor),
                observacao.strip() or None
            )
        ):
            st.session_state[
                "sisget_sol_ficha_reset"
            ] += 1
            st.rerun()


def solicitacao_ficha_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            sf.id,
            sf.codigo AS "Código",
            s.codigo AS "Solicitação",
            f.numero_ficha AS "Ficha",
            f.exercicio AS "Exercício",
            sf.valor_vinculado AS "Valor",
            CASE
                WHEN sf.validada_contabilidade
                THEN 'Validada'
                ELSE 'Pendente'
            END AS "Situação"
        FROM solicitacoes_fichas sf
        INNER JOIN solicitacoes s
            ON s.id = sf.solicitacao_id
        INNER JOIN fichas_orcamentarias f
            ON f.id = sf.ficha_orcamentaria_id
        ORDER BY sf.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_fichas",
        coluna_id="id",
        altura=480
    )


def solicitacao_ficha_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            valor_vinculado,
            validada_contabilidade,
            observacao
        FROM solicitacoes_fichas
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        valor_atual,
        validada_atual,
        observacao_atual
    ) = registro

    with st.form(
        f"form_sol_ficha_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        valor = st.number_input(
            "Valor Vinculado",
            min_value=0.0,
            value=float(valor_atual or 0),
            format="%.2f"
        )

        validada = st.checkbox(
            "Validada pela Contabilidade",
            value=bool(validada_atual)
        )

        observacao = st.text_area(
            "Observação",
            value=observacao_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_fichas
            SET
                valor_vinculado = ?,
                validada_contabilidade = ?,
                observacao = ?
            WHERE id = ?
            """,
            (
                float(valor),
                validada,
                observacao.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def solicitacao_ficha_excluir():

    registro_id = solicitacao_ficha_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão do Vínculo",
        type="primary",
        use_container_width=True,
        key=f"excluir_sol_ficha_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_fichas
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def solicitacao_ficha_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            f.numero_ficha AS "Ficha",
            f.exercicio AS "Exercício",
            sf.valor_vinculado AS "Valor",
            sf.observacao AS "Observação"
        FROM solicitacoes_fichas sf
        INNER JOIN solicitacoes s
            ON s.id = sf.solicitacao_id
        INNER JOIN fichas_orcamentarias f
            ON f.id = sf.ficha_orcamentaria_id
        ORDER BY s.codigo, f.numero_ficha
        """
    )

    sisget_relatorio_classificacao(
        "Fichas Orçamentárias das Solicitações",
        df,
        "solicitacoes_fichas.pdf"
    )


# ============================================================
# FINANCEIRO - CRUD
# ============================================================

def cadastro_financeiro_solicitacoes():
    sisget_tela_principal(
        titulo="Validação Financeira das Solicitações",
        chave="solicitacoes_financeiro",
        func_incluir=financeiro_solicitacao_incluir,
        func_localizar=financeiro_solicitacao_localizar,
        func_alterar=financeiro_solicitacao_alterar,
        func_excluir=financeiro_solicitacao_excluir,
        func_imprimir=financeiro_solicitacao_imprimir,
        icone="💰"
    )


def financeiro_solicitacao_incluir():

    if "sisget_financeiro_sol_reset" not in st.session_state:
        st.session_state[
            "sisget_financeiro_sol_reset"
        ] = 0

    reset = st.session_state[
        "sisget_financeiro_sol_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"financeiro_sol_{reset}"
    )

    if not solicitacao_id:
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_financeiro",
        tamanho=6
    )

    total = _sisget_fetchone(
        """
        SELECT COALESCE(
            SUM(valor_estimado_total),
            0
        )
        FROM solicitacoes_itens
        WHERE solicitacao_id = ?
          AND ativo = TRUE
        """,
        (solicitacao_id,)
    )

    valor_estimado = float(
        total[0] or 0
    )

    with st.form(
        f"form_financeiro_sol_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        st.number_input(
            "Valor Estimado",
            value=valor_estimado,
            disabled=True,
            format="%.2f"
        )

        valor_validado = st.number_input(
            "Valor Validado *",
            min_value=0.0,
            value=valor_estimado,
            format="%.2f"
        )

        cota = st.number_input(
            "Cota Financeira",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        reserva = st.number_input(
            "Reserva",
            min_value=0.0,
            value=0.0,
            format="%.2f"
        )

        parecer = st.text_area(
            "Parecer Financeiro"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Validação",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_financeiro",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_financeiro
            (
                codigo,
                solicitacao_id,
                valor_estimado,
                valor_validado,
                cota,
                reserva,
                parecer,
                usuario_id
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                valor_estimado,
                float(valor_validado),
                float(cota),
                float(reserva),
                parecer.strip() or None,
                st.session_state.get("usuario_id")
            )
        ):
            st.session_state[
                "sisget_financeiro_sol_reset"
            ] += 1
            st.rerun()


def financeiro_solicitacao_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            sf.id,
            sf.codigo AS "Código",
            s.codigo AS "Solicitação",
            sf.valor_estimado AS "Estimado",
            sf.valor_validado AS "Validado",
            sf.cota AS "Cota",
            sf.reserva AS "Reserva"
        FROM solicitacoes_financeiro sf
        INNER JOIN solicitacoes s
            ON s.id = sf.solicitacao_id
        ORDER BY sf.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_financeiro",
        coluna_id="id",
        altura=450
    )


def financeiro_solicitacao_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            valor_estimado,
            valor_validado,
            cota,
            reserva,
            parecer
        FROM solicitacoes_financeiro
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        estimado_atual,
        validado_atual,
        cota_atual,
        reserva_atual,
        parecer_atual
    ) = registro

    with st.form(
        f"form_financeiro_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        st.number_input(
            "Valor Estimado",
            value=float(estimado_atual or 0),
            disabled=True,
            format="%.2f"
        )

        validado = st.number_input(
            "Valor Validado",
            min_value=0.0,
            value=float(validado_atual or 0),
            format="%.2f"
        )

        cota = st.number_input(
            "Cota",
            min_value=0.0,
            value=float(cota_atual or 0),
            format="%.2f"
        )

        reserva = st.number_input(
            "Reserva",
            min_value=0.0,
            value=float(reserva_atual or 0),
            format="%.2f"
        )

        parecer = st.text_area(
            "Parecer",
            value=parecer_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_financeiro
            SET
                valor_validado = ?,
                cota = ?,
                reserva = ?,
                parecer = ?
            WHERE id = ?
            """,
            (
                float(validado),
                float(cota),
                float(reserva),
                parecer.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def financeiro_solicitacao_excluir():

    registro_id = financeiro_solicitacao_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão da Validação",
        type="primary",
        use_container_width=True,
        key=f"excluir_financeiro_sol_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_financeiro
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def financeiro_solicitacao_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            sf.valor_estimado AS "Estimado",
            sf.valor_validado AS "Validado",
            sf.cota AS "Cota",
            sf.reserva AS "Reserva",
            sf.parecer AS "Parecer"
        FROM solicitacoes_financeiro sf
        INNER JOIN solicitacoes s
            ON s.id = sf.solicitacao_id
        ORDER BY sf.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "Validações Financeiras",
        df,
        "solicitacoes_financeiro.pdf"
    )


# ============================================================
# ENQUADRAMENTO - CRUD
# ============================================================

def cadastro_enquadramento_solicitacoes():
    sisget_tela_principal(
        titulo="Enquadramento da Contratação",
        chave="solicitacoes_enquadramento",
        func_incluir=enquadramento_incluir,
        func_localizar=enquadramento_localizar,
        func_alterar=enquadramento_alterar,
        func_excluir=enquadramento_excluir,
        func_imprimir=enquadramento_imprimir,
        icone="⚖️"
    )


def enquadramento_incluir():

    if "sisget_enquadramento_reset" not in st.session_state:
        st.session_state[
            "sisget_enquadramento_reset"
        ] = 0

    reset = st.session_state[
        "sisget_enquadramento_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação para Licitação *",
        f"enquadramento_sol_{reset}",
        "LICITACAO"
    )

    if not solicitacao_id:
        return

    existe = _sisget_fetchone(
        """
        SELECT id
        FROM solicitacoes_enquadramento
        WHERE solicitacao_id = ?
        """,
        (solicitacao_id,)
    )

    if existe:
        st.warning(
            "⚠️ Esta solicitação já possui enquadramento."
        )
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_enquadramento",
        tamanho=6
    )

    with st.form(
        f"form_enquadramento_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        tipo_processo = st.selectbox(
            "Tipo do Processo *",
            [
                "Licitação",
                "Contratação Direta"
            ]
        )

        tipo_objeto = st.selectbox(
            "Tipo do Objeto *",
            [
                "Aquisição de bens",
                "Serviço",
                "Serviço de engenharia",
                "Obra",
                "Locação",
                "Tecnologia da Informação",
                "Outro"
            ]
        )

        natureza_objeto = st.text_input(
            "Natureza do Objeto"
        )

        modalidade = st.text_input(
            "Modalidade / Forma *"
        )

        criterio = st.text_input(
            "Critério de Julgamento"
        )

        modo = st.text_input(
            "Modo de Disputa"
        )

        forma = st.selectbox(
            "Forma",
            [
                "Eletrônica",
                "Presencial",
                "Não se aplica"
            ]
        )

        srp = st.checkbox(
            "Sistema de Registro de Preços - SRP"
        )

        fundamento = st.text_input(
            "Fundamento Legal"
        )

        justificativa = st.text_area(
            "Justificativa *"
        )

        salvar = st.form_submit_button(
            "💾 Salvar Enquadramento",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_enquadramento",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_enquadramento
            (
                codigo,
                solicitacao_id,
                tipo_processo,
                tipo_objeto,
                natureza_objeto,
                modalidade,
                criterio_julgamento,
                modo_disputa,
                forma,
                registro_precos,
                fundamento_legal,
                justificativa
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                tipo_processo,
                tipo_objeto,
                natureza_objeto.strip() or None,
                modalidade.strip(),
                criterio.strip() or None,
                modo.strip() or None,
                forma,
                srp,
                fundamento.strip() or None,
                justificativa.strip()
            )
        ):
            st.session_state[
                "sisget_enquadramento_reset"
            ] += 1
            st.rerun()


def enquadramento_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            e.id,
            e.codigo AS "Código",
            s.codigo AS "Solicitação",
            e.tipo_processo AS "Tipo",
            e.tipo_objeto AS "Objeto",
            e.modalidade AS "Modalidade",
            e.criterio_julgamento AS "Critério",
            CASE
                WHEN e.registro_precos
                THEN 'Sim'
                ELSE 'Não'
            END AS "SRP"
        FROM solicitacoes_enquadramento e
        INNER JOIN solicitacoes s
            ON s.id = e.solicitacao_id
        ORDER BY e.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_enquadramento",
        coluna_id="id",
        altura=450
    )


def enquadramento_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            tipo_processo,
            tipo_objeto,
            natureza_objeto,
            modalidade,
            criterio_julgamento,
            modo_disputa,
            forma,
            registro_precos,
            fundamento_legal,
            justificativa
        FROM solicitacoes_enquadramento
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        tipo_atual,
        objeto_atual,
        natureza_atual,
        modalidade_atual,
        criterio_atual,
        modo_atual,
        forma_atual,
        srp_atual,
        fundamento_atual,
        justificativa_atual
    ) = registro

    tipos = [
        "Licitação",
        "Contratação Direta"
    ]

    formas = [
        "Eletrônica",
        "Presencial",
        "Não se aplica"
    ]

    with st.form(
        f"form_enquadramento_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        tipo = st.selectbox(
            "Tipo do Processo",
            tipos,
            index=(
                tipos.index(tipo_atual)
                if tipo_atual in tipos
                else 0
            )
        )

        objeto = st.text_input(
            "Tipo do Objeto",
            value=objeto_atual or ""
        )

        natureza = st.text_input(
            "Natureza",
            value=natureza_atual or ""
        )

        modalidade = st.text_input(
            "Modalidade",
            value=modalidade_atual or ""
        )

        criterio = st.text_input(
            "Critério",
            value=criterio_atual or ""
        )

        modo = st.text_input(
            "Modo de Disputa",
            value=modo_atual or ""
        )

        forma = st.selectbox(
            "Forma",
            formas,
            index=(
                formas.index(forma_atual)
                if forma_atual in formas
                else 0
            )
        )

        srp = st.checkbox(
            "SRP",
            value=bool(srp_atual)
        )

        fundamento = st.text_input(
            "Fundamento Legal",
            value=fundamento_atual or ""
        )

        justificativa = st.text_area(
            "Justificativa",
            value=justificativa_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_enquadramento
            SET
                tipo_processo = ?,
                tipo_objeto = ?,
                natureza_objeto = ?,
                modalidade = ?,
                criterio_julgamento = ?,
                modo_disputa = ?,
                forma = ?,
                registro_precos = ?,
                fundamento_legal = ?,
                justificativa = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                tipo,
                objeto.strip(),
                natureza.strip() or None,
                modalidade.strip(),
                criterio.strip() or None,
                modo.strip() or None,
                forma,
                srp,
                fundamento.strip() or None,
                justificativa.strip(),
                registro_id
            )
        ):
            st.rerun()


def enquadramento_excluir():

    registro_id = enquadramento_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão",
        type="primary",
        use_container_width=True,
        key=f"excluir_enquadramento_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_enquadramento
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def enquadramento_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            e.tipo_processo AS "Tipo",
            e.tipo_objeto AS "Objeto",
            e.modalidade AS "Modalidade",
            e.criterio_julgamento AS "Critério",
            e.modo_disputa AS "Modo",
            e.forma AS "Forma"
        FROM solicitacoes_enquadramento e
        INNER JOIN solicitacoes s
            ON s.id = e.solicitacao_id
        ORDER BY e.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "Enquadramentos das Contratações",
        df,
        "enquadramentos.pdf"
    )


# ============================================================
# TR - CRUD
# ============================================================

def cadastro_tr_solicitacoes():
    sisget_tela_principal(
        titulo="Termo de Referência - TR",
        chave="solicitacoes_tr",
        func_incluir=tr_incluir,
        func_localizar=tr_localizar,
        func_alterar=tr_alterar,
        func_excluir=tr_excluir,
        func_imprimir=tr_imprimir,
        icone="📑"
    )


def tr_incluir():

    if "sisget_tr_reset" not in st.session_state:
        st.session_state["sisget_tr_reset"] = 0

    reset = st.session_state[
        "sisget_tr_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação para Licitação *",
        f"tr_solicitacao_{reset}",
        "LICITACAO"
    )

    if not solicitacao_id:
        return

    existe = _sisget_fetchone(
        """
        SELECT id
        FROM solicitacoes_tr
        WHERE solicitacao_id = ?
        """,
        (solicitacao_id,)
    )

    if existe:
        st.warning(
            "⚠️ Esta solicitação já possui TR."
        )
        return

    solicitacao = _sisget_fetchone(
        """
        SELECT objeto
        FROM solicitacoes
        WHERE id = ?
        """,
        (solicitacao_id,)
    )

    objeto_base = (
        solicitacao[0]
        if solicitacao
        else ""
    )

    codigo = sisget_proximo_codigo(
        "solicitacoes_tr",
        tamanho=6
    )

    with st.form(
        f"form_tr_incluir_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        objeto = st.text_area(
            "1. Definição do Objeto *",
            value=objeto_base or ""
        )

        fundamentacao = st.text_area(
            "2. Fundamentação *"
        )

        solucao = st.text_area(
            "3. Descrição da Solução *"
        )

        requisitos = st.text_area(
            "4. Requisitos *"
        )

        execucao = st.text_area(
            "5. Modelo de Execução *"
        )

        gestao = st.text_area(
            "6. Gestão e Fiscalização"
        )

        pagamento = st.text_area(
            "7. Medição e Pagamento"
        )

        selecao = st.text_area(
            "8. Critérios de Seleção"
        )

        estimativa = st.text_area(
            "9. Estimativa do Valor"
        )

        adequacao = st.text_area(
            "10. Adequação Orçamentária"
        )

        obrigacoes_contratada = st.text_area(
            "11. Obrigações da Contratada"
        )

        obrigacoes_adm = st.text_area(
            "12. Obrigações da Administração"
        )

        sancoes = st.text_area(
            "13. Sanções"
        )

        salvar = st.form_submit_button(
            "💾 Salvar TR",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_tr",
            tamanho=6
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_tr
            (
                codigo,
                solicitacao_id,
                objeto,
                fundamentacao,
                descricao_solucao,
                requisitos,
                modelo_execucao,
                gestao_fiscalizacao,
                medicao_pagamento,
                criterios_selecao,
                estimativa_valor,
                adequacao_orcamentaria,
                obrigacoes_contratada,
                obrigacoes_administracao,
                sancoes
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                objeto.strip(),
                fundamentacao.strip(),
                solucao.strip(),
                requisitos.strip(),
                execucao.strip(),
                gestao.strip() or None,
                pagamento.strip() or None,
                selecao.strip() or None,
                estimativa.strip() or None,
                adequacao.strip() or None,
                obrigacoes_contratada.strip() or None,
                obrigacoes_adm.strip() or None,
                sancoes.strip() or None
            )
        ):
            st.session_state[
                "sisget_tr_reset"
            ] += 1
            st.rerun()


def tr_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            t.id,
            t.codigo AS "Código",
            s.codigo AS "Solicitação",
            s.objeto AS "Objeto"
        FROM solicitacoes_tr t
        INNER JOIN solicitacoes s
            ON s.id = t.solicitacao_id
        ORDER BY t.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_tr",
        coluna_id="id",
        altura=450
    )


def tr_alterar(
    registro_id
):

    registro = _sisget_fetchone(
        """
        SELECT
            codigo,
            objeto,
            fundamentacao,
            descricao_solucao,
            requisitos,
            modelo_execucao,
            gestao_fiscalizacao,
            medicao_pagamento,
            criterios_selecao,
            estimativa_valor,
            adequacao_orcamentaria,
            obrigacoes_contratada,
            obrigacoes_administracao,
            sancoes
        FROM solicitacoes_tr
        WHERE id = ?
        """,
        (registro_id,)
    )

    if not registro:
        return

    (
        codigo,
        objeto_atual,
        fundamentacao_atual,
        solucao_atual,
        requisitos_atual,
        execucao_atual,
        gestao_atual,
        pagamento_atual,
        selecao_atual,
        estimativa_atual,
        adequacao_atual,
        contratada_atual,
        adm_atual,
        sancoes_atual
    ) = registro

    with st.form(
        f"form_tr_alterar_{registro_id}"
    ):
        st.text_input(
            "Código",
            value=codigo or "",
            disabled=True
        )

        objeto = st.text_area(
            "1. Objeto",
            value=objeto_atual or ""
        )

        fundamentacao = st.text_area(
            "2. Fundamentação",
            value=fundamentacao_atual or ""
        )

        solucao = st.text_area(
            "3. Solução",
            value=solucao_atual or ""
        )

        requisitos = st.text_area(
            "4. Requisitos",
            value=requisitos_atual or ""
        )

        execucao = st.text_area(
            "5. Execução",
            value=execucao_atual or ""
        )

        gestao = st.text_area(
            "6. Gestão/Fiscalização",
            value=gestao_atual or ""
        )

        pagamento = st.text_area(
            "7. Medição/Pagamento",
            value=pagamento_atual or ""
        )

        selecao = st.text_area(
            "8. Seleção",
            value=selecao_atual or ""
        )

        estimativa = st.text_area(
            "9. Estimativa",
            value=estimativa_atual or ""
        )

        adequacao = st.text_area(
            "10. Adequação Orçamentária",
            value=adequacao_atual or ""
        )

        contratada = st.text_area(
            "11. Obrigações da Contratada",
            value=contratada_atual or ""
        )

        adm = st.text_area(
            "12. Obrigações da Administração",
            value=adm_atual or ""
        )

        sancoes = st.text_area(
            "13. Sanções",
            value=sancoes_atual or ""
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações",
            type="primary",
            use_container_width=True
        )

    if salvar:
        if _sisget_salvar(
            """
            UPDATE solicitacoes_tr
            SET
                objeto = ?,
                fundamentacao = ?,
                descricao_solucao = ?,
                requisitos = ?,
                modelo_execucao = ?,
                gestao_fiscalizacao = ?,
                medicao_pagamento = ?,
                criterios_selecao = ?,
                estimativa_valor = ?,
                adequacao_orcamentaria = ?,
                obrigacoes_contratada = ?,
                obrigacoes_administracao = ?,
                sancoes = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                objeto.strip(),
                fundamentacao.strip(),
                solucao.strip(),
                requisitos.strip(),
                execucao.strip(),
                gestao.strip() or None,
                pagamento.strip() or None,
                selecao.strip() or None,
                estimativa.strip() or None,
                adequacao.strip() or None,
                contratada.strip() or None,
                adm.strip() or None,
                sancoes.strip() or None,
                registro_id
            )
        ):
            st.rerun()


def tr_excluir():

    registro_id = tr_localizar()

    if not registro_id:
        return

    if st.button(
        "🗑️ Confirmar Exclusão do TR",
        type="primary",
        use_container_width=True,
        key=f"excluir_tr_{registro_id}"
    ):
        if _sisget_salvar(
            """
            DELETE FROM solicitacoes_tr
            WHERE id = ?
            """,
            (registro_id,)
        ):
            st.rerun()


def tr_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            t.codigo AS "Código",
            s.codigo AS "Solicitação",
            t.objeto AS "Objeto",
            t.fundamentacao AS "Fundamentação",
            t.estimativa_valor AS "Estimativa"
        FROM solicitacoes_tr t
        INNER JOIN solicitacoes s
            ON s.id = t.solicitacao_id
        ORDER BY t.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "Termos de Referência",
        df,
        "termos_referencia.pdf"
    )


# ============================================================
# HISTÓRICO - TELA PRÓPRIA
# ============================================================

def cadastro_historico_solicitacoes():
    sisget_tela_principal(
        titulo="Histórico das Solicitações",
        chave="solicitacoes_historico",
        func_incluir=historico_solicitacao_incluir,
        func_localizar=historico_solicitacao_localizar,
        func_alterar=historico_solicitacao_alterar,
        func_excluir=historico_solicitacao_excluir,
        func_imprimir=historico_solicitacao_imprimir,
        icone="📜"
    )


def historico_solicitacao_incluir():

    if "sisget_historico_reset" not in st.session_state:
        st.session_state[
            "sisget_historico_reset"
        ] = 0

    reset = st.session_state[
        "sisget_historico_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"historico_solicitacao_{reset}"
    )

    if not solicitacao_id:
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_historico",
        tamanho=8
    )

    with st.form(
        f"form_historico_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        etapa_origem = st.text_input(
            "Etapa de Origem"
        )

        etapa_destino = st.text_input(
            "Etapa de Destino"
        )

        acao = st.text_input(
            "Ação *"
        )

        observacao = st.text_area(
            "Observação"
        )

        salvar = st.form_submit_button(
            "💾 Registrar Histórico",
            type="primary",
            use_container_width=True
        )

    if salvar:
        codigo = sisget_proximo_codigo(
            "solicitacoes_historico",
            tamanho=8
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_historico
            (
                codigo,
                solicitacao_id,
                usuario_id,
                etapa_origem,
                etapa_destino,
                acao,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                solicitacao_id,
                st.session_state.get("usuario_id"),
                etapa_origem.strip() or None,
                etapa_destino.strip() or None,
                acao.strip(),
                observacao.strip() or None
            )
        ):
            st.session_state[
                "sisget_historico_reset"
            ] += 1
            st.rerun()


def historico_solicitacao_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            h.id,
            h.codigo AS "Código",
            s.codigo AS "Solicitação",
            h.etapa_origem AS "Origem",
            h.etapa_destino AS "Destino",
            h.acao AS "Ação",
            h.observacao AS "Observação",
            h.criado_em AS "Data/Hora"
        FROM solicitacoes_historico h
        INNER JOIN solicitacoes s
            ON s.id = h.solicitacao_id
        ORDER BY h.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_historico",
        coluna_id="id",
        altura=500
    )


def historico_solicitacao_alterar(
    registro_id
):
    st.warning(
        "🔒 Histórico de tramitação é registro de auditoria "
        "e não deve ser alterado."
    )


def historico_solicitacao_excluir():
    st.warning(
        "🔒 Histórico de tramitação não pode ser excluído. "
        "Use um novo registro para correção/retificação."
    )


def historico_solicitacao_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            h.etapa_origem AS "Origem",
            h.etapa_destino AS "Destino",
            h.acao AS "Ação",
            h.observacao AS "Observação",
            h.criado_em AS "Data/Hora"
        FROM solicitacoes_historico h
        INNER JOIN solicitacoes s
            ON s.id = h.solicitacao_id
        ORDER BY h.id
        """
    )

    sisget_relatorio_classificacao(
        "Histórico das Solicitações",
        df,
        "historico_solicitacoes.pdf"
    )


# ============================================================
# ASSINATURAS - TELA PRÓPRIA
# ============================================================

def cadastro_assinaturas_solicitacoes():
    sisget_tela_principal(
        titulo="Assinaturas / Aprovações",
        chave="solicitacoes_assinaturas",
        func_incluir=assinatura_solicitacao_incluir,
        func_localizar=assinatura_solicitacao_localizar,
        func_alterar=assinatura_solicitacao_alterar,
        func_excluir=assinatura_solicitacao_excluir,
        func_imprimir=assinatura_solicitacao_imprimir,
        icone="✍️"
    )


def assinatura_solicitacao_incluir():

    import hashlib

    if "sisget_assinatura_reset" not in st.session_state:
        st.session_state[
            "sisget_assinatura_reset"
        ] = 0

    reset = st.session_state[
        "sisget_assinatura_reset"
    ]

    solicitacao_id = sisget_selecionar_solicitacao(
        "Solicitação *",
        f"assinatura_solicitacao_{reset}"
    )

    if not solicitacao_id:
        return

    codigo = sisget_proximo_codigo(
        "solicitacoes_assinaturas",
        tamanho=8
    )

    with st.form(
        f"form_assinatura_{reset}_{solicitacao_id}"
    ):
        st.text_input(
            "Código",
            value=codigo,
            disabled=True
        )

        etapa = st.selectbox(
            "Etapa *",
            [
                "APROVACAO",
                "DFD",
                "ETP",
                "RISCOS",
                "COMPRAS",
                "CONTABILIDADE",
                "FINANCEIRO",
                "ORDENADOR",
                "LICITACAO",
                "TR"
            ]
        )

        decisao = st.selectbox(
            "Decisão *",
            [
                "ASSINADO",
                "APROVADO",
                "VALIDADO",
                "AUTORIZADO",
                "DEVOLVIDO",
                "REJEITADO"
            ]
        )

        observacao = st.text_area(
            "Observação"
        )

        assinar = st.form_submit_button(
            "✍️ Assinar / Registrar",
            type="primary",
            use_container_width=True
        )

    if assinar:

        usuario_id = st.session_state.get(
            "usuario_id"
        )

        instante = datetime.now().isoformat()

        conteudo = (
            f"{solicitacao_id}|"
            f"{usuario_id}|"
            f"{etapa}|"
            f"{decisao}|"
            f"{instante}"
        )

        hash_assinatura = hashlib.sha256(
            conteudo.encode("utf-8")
        ).hexdigest()

        codigo = sisget_proximo_codigo(
            "solicitacoes_assinaturas",
            tamanho=8
        )

        if _sisget_salvar(
            """
            INSERT INTO solicitacoes_assinaturas
            (
                codigo,
                solicitacao_id,
                usuario_id,
                etapa,
                decisao,
                observacao,
                hash_assinatura,
                assinado_em
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?,
                CURRENT_TIMESTAMP
            )
            """,
            (
                codigo,
                solicitacao_id,
                usuario_id,
                etapa,
                decisao,
                observacao.strip() or None,
                hash_assinatura
            )
        ):
            st.session_state[
                "sisget_assinatura_reset"
            ] += 1
            st.rerun()


def assinatura_solicitacao_localizar():

    df = _sisget_dataframe(
        """
        SELECT
            a.id,
            a.codigo AS "Código",
            s.codigo AS "Solicitação",
            a.etapa AS "Etapa",
            a.decisao AS "Decisão",
            a.hash_assinatura AS "Hash",
            a.assinado_em AS "Data/Hora"
        FROM solicitacoes_assinaturas a
        INNER JOIN solicitacoes s
            ON s.id = a.solicitacao_id
        ORDER BY a.id DESC
        """
    )

    if df.empty:
        return None

    return sisget_grid_localizar(
        df=df,
        chave="solicitacoes_assinaturas",
        coluna_id="id",
        altura=500
    )


def assinatura_solicitacao_alterar(
    registro_id
):
    st.warning(
        "🔒 Assinatura registrada não deve ser alterada. "
        "Se houver erro, registre nova assinatura/decisão."
    )


def assinatura_solicitacao_excluir():
    st.warning(
        "🔒 Assinaturas não podem ser excluídas pelo fluxo normal."
    )


def assinatura_solicitacao_imprimir():

    df = _sisget_dataframe(
        """
        SELECT
            s.codigo AS "Solicitação",
            a.codigo AS "Assinatura",
            a.etapa AS "Etapa",
            a.decisao AS "Decisão",
            a.hash_assinatura AS "Hash",
            a.assinado_em AS "Data/Hora"
        FROM solicitacoes_assinaturas a
        INNER JOIN solicitacoes s
            ON s.id = a.solicitacao_id
        ORDER BY a.id DESC
        """
    )

    sisget_relatorio_classificacao(
        "Assinaturas das Solicitações",
        df,
        "assinaturas_solicitacoes.pdf"
    )



def login():

    st.title("🏛️ SISGET")
    st.subheader("🔐 Login no Sistema")

    with st.form("form_login"):

        usuario = st.text_input(
            "👤 Usuário"
        )

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

        if (
            usuario == "admin"
            and senha == "123"
        ):

            st.session_state[
                "usuario_logado"
            ] = "admin"

            st.session_state[
                "usuario_id"
            ] = 1

            st.session_state[
                "entidade_id"
            ] = 16

            st.session_state[
                "funcao_usuario"
            ] = "Administrador"

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


def main():

    # ========================================================
    # CORRIGIR ENTIDADE DA SESSÃO
    # ========================================================

    if st.session_state.get(
        "usuario_logado"
    ) == "admin":

        st.session_state[
            "entidade_id"
        ] = 16

    if "usuario_logado" not in (
        st.session_state
    ):

        login()

        return

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
