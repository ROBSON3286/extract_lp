🚀 Extrator e Automatizador de Landing Pages - Xiaomi GlobalFerramenta desenvolvida em Python para automatizar a extração de landing pages do site global da Xiaomi conforme demandas da engenharia. O script contorna bloqueios de segurança (Akamai WAF), isola o conteúdo principal (<main>), unifica folhas de estilo CSS, realiza a tradução automática via planilha Excel (en-US ➔ pt-BR) e gera versões independentes para Desktop e Mobile.

Requisitos e Instalação (Bash / Terminal)
Antes de executar o projeto, certifique-se de ter o Python 3.8+ e o Google Chrome instalados em sua máquina.1. 
Instalar as bibliotecas PythonAbra o seu terminal (Git Bash, WSL, Prompt de Comando ou PowerShell) e execute:Bashpip install playwright beautifulsoup4 pandas openpyxl

2. Instalar o navegador Chromium do PlaywrightPara garantir a compatibilidade com o ecossistema do Playwright, rode:Bashplaywright install chromium
📂 Estrutura do Projeto: Organize os arquivos da seguinte forma na pasta do seu projeto: meu-projeto/

├── lp_extract.py   # Script principal em Python
├── traducao.xlsx        # Planilha com as traduções de/para (Opcional)
└── README.md            # Este guia

Formato da Planilha traducao.xlsx: A planilha deve conter duas colunas na primeira aba: en-US pt-BR

💻 Como Rodar no VS Code
Abrir o projeto: Abra o VS Code e vá em File > Open Folder... escolhendo a pasta do projeto.Configurar a URL alvo: Abra o arquivo extrair_landing.py e altere a variável URL_ALVO para o link do produto desejado:
URL_ALVO = "https://www.mi.com/global...."

Executar o Script lp_extract.py

⚠️ Atenção: Uma janela do Google Chrome será aberta automaticamente. Não a feche manualmente; o script a utilizará para simular a navegação humana e fechará sozinho ao concluir.

(Pipeline de Execução)
O script executa um fluxo automatizado dividido em 6 etapas principais:[1. Carrega Excel] ➔ [2. Emula Chrome & Scroll] ➔ [3. Isola <main>] ➔ [4. Converte data-src] ➔ [5. Aplica De/Para] ➔ [6. Unifica e Limpa CSS]

📁 Resultado GeradoApós a finalização, o script criará a pasta pagina_extraida/ na raiz do projeto com a seguinte estrutura pronta para publicação:Plaintextpagina_extraida/

├── desktop/
│   ├── index.html   # Estrutura HTML limpa, traduzida e contendo apenas a tag <main>
│   └── style.css    # Folha de estilo consolidada e corrigida
└── mobile/
    ├── index.html   # Versão otimizada para dispositivos móveis
    └── style.css
