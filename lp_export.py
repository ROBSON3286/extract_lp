import asyncio
import os
import re
import urllib.parse
import urllib.request
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

URL_ALVO = "https://www.mi.com/global/product/redmi-17-5g/"  # link da pagina
ARQUIVO_EXCEL_TRADUCAO = "traducao.xlsx"  # nome do Arquivo que sera usado para obter a tradução
NOME_PRODUTO = "redmi17"

CONTEUDO_BUNDLE_JS = """!(function (e, t) {
  var i = t.documentElement;
  var tela = i.clientWidth || 320;
  //mobile
  if(tela <= 720){
        function n() {
          var t = i.clientWidth || 320,
            n = (t > 720 ? 720 : t < 320 ? 320 : t) / 22.5;
          (i.style.fontSize = n + "px"), (e.rootFontSize = n);
        }
        if (
          ((e.oriRootFontSize = 48),
          e.addEventListener(
            "resize",
            function () {
              n();
            },
            !1
          ),
          e.addEventListener(
            "pageshow",
            function (e) {
              e.persisted && n();
            },
            !1
          ),
          n(),
          e.devicePixelRatio && e.devicePixelRatio >= 2)
        ) {
          var o = t.createElement("div"),
            d = t.createElement("body");
          (o.style.border = "0.5px solid transparent"),
            d.appendChild(o),
            i.appendChild(d),
            1 === o.offsetHeight && i.classList.add("hairlines"),
            i.removeChild(d);
        }

  
  }else{
  //desktop
        var i = t.documentElement;
        t.body;
        function n() {
          var t = i.clientWidth,
            n = t >= 1226 ? t/10 : 122.6;//t / 1
          (i.style.fontSize = n + "px"),
            (e.rootFontSize = n),
            (e.oriRootFontSize = 256);
        }
        if (
          (e.addEventListener(
            "resize",
            function () {
              n();
            },
            !1
          ),
          e.addEventListener(
            "pageshow",
            function (e) {
              e.persisted && n();
            },
            !1
          ),
          n(),
          e.devicePixelRatio && e.devicePixelRatio >= 2)
        ) {
          var o = t.createElement("div"),
            d = t.createElement("body");
          (o.style.border = "0.5px solid transparent"),
            d.appendChild(o),
            i.appendChild(d),
            1 === o.offsetHeight && i.classList.add("hairlines"),
            i.removeChild(d);
        }


  }
  
})(window, document);"""

def gerar_bundle_js(caminho_raiz):
    """Cria a pasta assets/js e o arquivo bundle.js."""
    pasta_js = os.path.join(caminho_raiz, "assets", "js")
    os.makedirs(pasta_js, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_js, "bundle.js")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(CONTEUDO_BUNDLE_JS)
    print(f"✅ Arquivo bundle.js gerado em: {os.path.abspath(caminho_arquivo)}")

def normalizar_texto(texto):
    """Padroniza hífens especiais, aspas e remove espaços/quebras de linha extras."""
    if not isinstance(texto, str) or texto == 'nan':
        return ""
    
    # Substitui caracteres especiais de pontuação por equivalentes padrão
    texto = texto.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    texto = texto.replace('\u2033', '"').replace('”', '"').replace('“', '"')
    
    # Remove quebras de linha e múltiplos espaços consecutivos
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def carregar_dicionario_traducao(caminho_excel):
    """Lê a planilha Excel e sanitiza todas as chaves em inglês e traduções."""
    if not os.path.exists(caminho_excel):
        print(f" Planilha '{caminho_excel}' não encontrada. A extração continuará sem tradução.")
        return {}
    
    try:
        # Lê a primeira aba sem assumir cabeçalho fixo
        df = pd.read_excel(caminho_excel, sheet_name=0)
        
        de_para = {}
        for _, row in df.iterrows():
            en_orig = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            pt_orig = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            
            en_clean = normalizar_texto(en_orig)
            pt_clean = normalizar_texto(pt_orig)
            
            if en_clean and pt_clean:
                de_para[en_clean] = pt_clean
                
                # Mapeamento extra sem os caracteres sobrescritos (ex: ¹, ², ³)
                en_sem_sobrescrito = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', en_clean).strip()
                pt_sem_sobrescrito = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', pt_clean).strip()
                if en_sem_sobrescrito and en_sem_sobrescrito not in de_para:
                    de_para[en_sem_sobrescrito] = pt_sem_sobrescrito
        
        # Ordena do texto mais longo para o mais curto
        de_para_ordenado = dict(sorted(de_para.items(), key=lambda item: len(item[0]), reverse=True))
        return de_para_ordenado
    except Exception as e:
        print(f" ❌ Erro ao ler planilha de tradução: {e}")
        return {}

def aplicar_traducoes_dom(soup, dicionario_traducao):
    """Aplica substituições diretas nos nós de texto e nos elementos contêineres."""
    if not dicionario_traducao:
        return soup

    # Passagem 1: Substituição direta nos nós de texto
    for text_node in soup.find_all(text=True):
        if text_node.parent.name in ['script', 'style', 'head', 'title', 'meta']:
            continue
        
        texto_no = str(text_node)
        texto_no_norm = normalizar_texto(texto_no)
        
        if not texto_no_norm:
            continue

        for en_text, pt_text in dicionario_traducao.items():
            if en_text in texto_no_norm:
                padrao = re.escape(en_text).replace(r'\ ', r'\s+')
                texto_modificado = re.sub(padrao, pt_text, texto_no, flags=re.IGNORECASE)
                if texto_modificado != texto_no:
                    text_node.replace_with(texto_modificado)
                    texto_no = texto_modificado
                    texto_no_norm = normalizar_texto(texto_no)

    # Passagem 2: Verificação em elementos onde o texto está dividido por tags internas (ex: <sup> ou <span>)
    for elem in soup.find_all(['p', 'span', 'h1', 'h2', 'h3', 'h4', 'div', 'li', 'a', 'dt', 'dd']):
        if elem.find(['script', 'style']):
            continue
            
        texto_elem = normalizar_texto(elem.get_text())
        if not texto_elem:
            continue

        for en_text, pt_text in dicionario_traducao.items():
            if en_text == texto_elem and not elem.find_all(['p', 'div']):
                elem.string = pt_text
                break

    return soup

async def extrair_versao(context, url, pasta_destino, dispositivo_nome, mapa_traducao):
    print(f"\n--- Extraindo versão [{dispositivo_nome}] ---")
    page = await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    await page.goto(url, wait_until="domcontentloaded", timeout=90000)
    
    for i in range(1, 11):
        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/10});")
        await page.wait_for_timeout(4000)
        
    await page.evaluate("window.scrollTo(0, 0);")
    await page.wait_for_timeout(1500)
    
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')
    await page.close()
    
    # 1. Limpeza de Scripts
    for script in soup.find_all('script'):
        script.decompose()

    # 2. Isolar apenas a tag <main> dentro do <body>
    if soup.body and soup.main:
        main_content = soup.main.extract() # Remove o <main> temporariamente
        soup.body.clear()                  # Limpa todo o resto do <body>
        soup.body.append(main_content)     # Insere apenas o <main> de volta
    else:
        print("   └ ⚠️ Tag <main> não encontrada. O <body> original será mantido.")

    # 3. Conversão data-src -> src
    for tag in soup.find_all(True):
        if tag.has_attr('data-src'):
            tag['src'] = tag['data-src']
            del tag['data-src']

    for video in soup.find_all('video'):
        video['autoplay'] = ""
        video['muted'] = ""
        video['playsinline'] = ""
            
    # 4. Aplicação do De/Para do Excel
    soup = aplicar_traducoes_dom(soup, mapa_traducao)

    os.makedirs(pasta_destino, exist_ok=True)
    
    # 5. Agrupamento de CSS
    css_links = []
    for link in soup.find_all('link', rel=lambda x: x and 'stylesheet' in x.lower()):
        href = link.get('href')
        if href:
            url_css_completa = urllib.parse.urljoin(url, href)
            if 'main.css' in url_css_completa.lower():
                css_links.append((link, url_css_completa))
            else:
                link.decompose()
            
    conteudo_css = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for link_tag, css_url in css_links:
        try:
            req = urllib.request.Request(css_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                css_text = response.read().decode('utf-8', errors='ignore')
                conteudo_css.append(f"/* Fonte: {css_url} */\n" + css_text + "\n")
            link_tag.decompose()
        except Exception as e:
            pass

    # 6. Limpeza de regras CSS indesejadas
    css_final = "\n".join(conteudo_css)
    css_final = re.sub(r'white-space\s*:\s*break-spaces\s*!important\s*;?', '', css_final, flags=re.IGNORECASE)

    caminho_css = os.path.join(pasta_destino, "style.css")
    with open(caminho_css, "w", encoding="utf-8") as f:
        f.write(css_final)
        
    if soup.head:
        # Script jQuery 3.6.0
        script_jquery = soup.new_tag("script", src="https://code.jquery.com/jquery-3.6.0.min.js")
        soup.head.append(script_jquery)
                
        # CSS do Slick Carousel (Corrigido para tag <link>)
        link_slick = soup.new_tag("link", rel="stylesheet", type="text/css", href="https://cdn.jsdelivr.net/npm/slick-carousel@1.8.1/slick/slick.css")
        soup.head.append(link_slick)

        novo_link_css = soup.new_tag("link", rel="stylesheet", href="style.css")
        soup.head.append(novo_link_css)

    caminho_html = os.path.join(pasta_destino, "index.html")
    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write(soup.prettify())
        
    print(f"✅ Versão [{dispositivo_nome}] salva em: {os.path.abspath(pasta_destino)}")

async def main(): 
    gerar_bundle_js(NOME_PRODUTO)
    mapa_traducao = carregar_dicionario_traducao(ARQUIVO_EXCEL_TRADUCAO)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        
        # 1. Configuração Contexto Desktop
        context_desktop = await browser.new_context(no_viewport=True)
        await extrair_versao(context_desktop, URL_ALVO, NOME_PRODUTO + "/desktop", "DESKTOP", mapa_traducao)
        
        # 2. Configuração Contexto Mobile
        context_mobile = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            viewport={'width': 390, 'height': 844},
            is_mobile=True,
            has_touch=True
        )
        await extrair_versao(context_mobile, URL_ALVO, NOME_PRODUTO + "/mobile", "MOBILE", mapa_traducao)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())