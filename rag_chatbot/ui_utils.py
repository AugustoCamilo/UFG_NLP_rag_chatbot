# ui_utils.py
import streamlit as st
from streamlit.components.v1 import html


def add_print_to_pdf_button(label: str = "🖨️ Imprimir página"):
    """
    Adiciona CSS para formatar a página para impressão e um botão
    discreto que aciona o diálogo de impressão (window.print()).

    Esta função injeta CSS que:
    1. Esconde a barra lateral, o cabeçalho e elementos com classe .no-print.
    2. Força o fundo branco e texto preto (essencial para correções em temas escuros).
    3. Renderiza um botão HTML/JS que chama a função de impressão do navegador.

    Args:
        label (str): O texto a ser exibido no botão. Padrão: "🖨️ Imprimir página".
    """

    # 1. CSS (O "Canhão" para forçar tudo preto na impressão e limpar a UI)
    print_css = """
    <style>
    @media print {
        /* Esconde elementos da UI do Streamlit */
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        .no-print { display: none !important; }
        
        /* Otimiza o layout removendo padding superior */
        [data-testid="stAppViewContainer"] { padding-top: 0; }
        
        /* 1. Força o fundo para branco (ignora tema escuro do usuário) */
        body, [data-testid="stAppViewContainer"] {
            background: #ffffff !important;
        }

        /* 2. O "Canhão": Força TODO o texto (títulos, métricas, corpo) 
           a ser PRETO para economizar tinta e garantir legibilidade. */
        * {
            color: #000000 !important;
        }
    }
    </style>
    """
    st.markdown(print_css, unsafe_allow_html=True)

    # 2. Estilo do Botão (CSS Inline para o componente HTML)
    button_style = """
        background-color: transparent;
        border: none;
        color: #0068C9; /* Cor azul (padrão de link do Streamlit) */
        cursor: pointer;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 0.95rem;
        padding: 0.25rem 0rem;
        margin: 0.5rem 0;
        text-align: left;
        opacity: 0.8;
        transition: opacity 0.2s;
    """

    # 3. O HTML do Botão com Trigger JS
    button_html = f"""
    <button
        onclick="window.parent.print()"
        class="no-print"
        style="{button_style}"
        onmouseover="this.style.opacity=1"
        onmouseout="this.style.opacity=0.8"
        title="Imprimir esta página (Salvar como PDF)"
    >
        {label}
    </button>
    """

    # 4. Renderiza o botão no Streamlit
    html(button_html, height=50)


def set_focus_on_chat_input():
    """
    Utilitário extra: Injeta JavaScript para focar automaticamente
    na caixa de entrada de chat (st.chat_input).
    Útil para o app.py.
    """
    script = """
    <script>
    setTimeout(function() {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (input) {
            input.focus();
        }
    }, 100);
    </script>
    """
    html(script, height=0)
