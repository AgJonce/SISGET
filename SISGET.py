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
# CABEÇALHO PADRÃO DAS TELAS
# ============================================================

def sisget_cabecalho_tela(
    titulo,
    chave,
    voltar_para="principal"
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

        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key=f"btn_voltar_{chave}_{voltar_para}"
        ):

            # =================================================
            # LIMPAR REGISTRO SELECIONADO
            # =================================================

            st.session_state[
                f"sisget_id_{chave}"
            ] = None

            # =================================================
            # VOLTAR PARA TELA PRINCIPAL
            # =================================================

            if voltar_para == "principal":

                st.session_state[
                    f"sisget_tela_{chave}"
                ] = "principal"

            # =================================================
            # VOLTAR PARA LOCALIZAR
            # =================================================

            elif voltar_para == "localizar":

                st.session_state[
                    f"sisget_tela_{chave}"
                ] = "localizar"

            # =================================================
            # PADRÃO
            # =================================================

            else:

                st.session_state[
                    f"sisget_tela_{chave}"
                ] = "principal"

            st.rerun()

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
        func_imprimir=entidade_imprimir,
        icone="🏢"
    )


# ============================================================
# ENTIDADES - INCLUIR
# ============================================================

def entidade_incluir():

    st.subheader(
        "🏢 Dados da Entidade"
    )

    with st.form(
        "form_entidade_incluir",
        clear_on_submit=True
    ):

        col1, col2 = st.columns(
            [1, 3]
        )


        with col1:

            codigo = st.text_input(
                "Código *",
                max_chars=20
            )


        with col2:

            nome = st.text_input(
                "Nome da Entidade *",
                max_chars=200
            )


        col3, col4 = st.columns(2)


        with col3:

            cnpj = st.text_input(
                "CNPJ",
                max_chars=18,
                placeholder="00.000.000/0000-00"
            )


        with col4:

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

        codigo = codigo.strip()

        nome = nome.strip()

        cnpj = cnpj.strip()


        # ====================================================
        # VALIDAÇÕES
        # ====================================================

        if not codigo:

            st.warning(
                "⚠️ Informe o código da entidade."
            )

            return


        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return


        # ====================================================
        # VERIFICAR CÓDIGO DUPLICADO
        # ====================================================

        existente = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE codigo = ?
            """,
            (
                codigo,
            )
        )


        if existente:

            st.warning(
                "⚠️ Já existe uma entidade com esse código."
            )

            return


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
                "✅ Entidade cadastrada com sucesso!"
            )


# ============================================================
# ENTIDADES - LOCALIZAR
# ============================================================

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
# ENTIDADES - ALTERAR
# ============================================================

def entidade_alterar(
    entidade_id
):

    # ========================================================
    # LOCALIZAR REGISTRO
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


    st.subheader(
        f"🏢 Entidade #{id_entidade}"
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
    # FORM
    # ========================================================

    with st.form(
        f"form_entidade_alterar_{entidade_id}"
    ):

        col1, col2 = st.columns(
            [1, 3]
        )


        with col1:

            codigo = st.text_input(
                "Código *",
                value=codigo_atual or "",
                max_chars=20
            )


        with col2:

            nome = st.text_input(
                "Nome da Entidade *",
                value=nome_atual or "",
                max_chars=200
            )


        col3, col4 = st.columns(2)


        with col3:

            cnpj = st.text_input(
                "CNPJ",
                value=cnpj_atual or "",
                max_chars=18
            )


        with col4:

            tipo_entidade = st.selectbox(
                "Tipo de Entidade",
                tipos,
                index=indice_tipo
            )


        ativo = st.checkbox(
            "Entidade ativa",
            value=bool(
                ativo_atual
            )
        )


        st.markdown("---")


        col_salvar, col_cancelar = st.columns(2)


        with col_salvar:

            salvar = st.form_submit_button(
                "💾 Salvar Alterações",
                type="primary",
                use_container_width=True
            )


        with col_cancelar:

            cancelar = st.form_submit_button(
                "❌ Cancelar",
                use_container_width=True
            )


    # ========================================================
    # CANCELAR
    # ========================================================

    if cancelar:

        sisget_voltar_localizar(
            "entidades"
        )


    # ========================================================
    # SALVAR ALTERAÇÃO
    # ========================================================

    if salvar:

        codigo = codigo.strip()

        nome = nome.strip()

        cnpj = cnpj.strip()


        if not codigo:

            st.warning(
                "⚠️ Informe o código da entidade."
            )

            return


        if not nome:

            st.warning(
                "⚠️ Informe o nome da entidade."
            )

            return


        # ====================================================
        # VERIFICAR CÓDIGO DUPLICADO
        # ====================================================

        duplicado = _sisget_fetchone(
            """
            SELECT id
            FROM entidades
            WHERE codigo = ?
              AND id <> ?
            """,
            (
                codigo,
                entidade_id
            )
        )


        if duplicado:

            st.warning(
                "⚠️ Já existe outra entidade com esse código."
            )

            return


        # ====================================================
        # UPDATE
        # ====================================================

        sucesso = _sisget_salvar(
            """
            UPDATE entidades

            SET
                codigo = ?,
                nome = ?,
                cnpj = ?,
                tipo_entidade = ?,
                ativo = ?

            WHERE id = ?
            """,
            (
                codigo,
                nome,
                cnpj if cnpj else None,
                tipo_entidade,
                ativo,
                entidade_id
            )
        )


        if sucesso:

            st.success(
                "✅ Entidade alterada com sucesso!"
            )


            st.session_state[
                "sisget_tela_entidades"
            ] = "localizar"


            st.session_state[
                "sisget_id_entidades"
            ] = None


            st.rerun()


# ============================================================
# ENTIDADES - IMPRIMIR
# ============================================================

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
