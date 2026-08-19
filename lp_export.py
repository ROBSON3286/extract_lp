import asyncio
import os
import re
import urllib.parse
import urllib.request
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

URL_ALVO = "https://www.mi.com/global/product/redmi-17-5g/"
ARQUIVO_EXCEL_TRADUCAO = "traducao.xlsx"

def carregar_dicionario_traducao(caminho_excel):
    """Lê a planilha Excel e retorna um dicionário ordenado pelo tamanho do texto."""
    if not os.path.exists(caminho_excel):
        print(f"   └ ⚠️ Planilha '{caminho_excel}' não encontrada. A extração continuará sem tradução.")
        return {}
    
    try:
        df = pd.read_excel(caminho_excel)
        df['en-US'] = df['en-US'].astype(str).str.strip()
        df['pt-BR'] = df['pt-BR'].astype(str).str.strip()
        
        de_para = dict(zip(df['en-US'], df['pt-BR']))
        de_para_ordenado = dict(sorted(de_para.items(), key=lambda item: len(item[0]), reverse=True))
        return de_para_ordenado
    except Exception as e:
        print(f"   └ ❌ Erro ao ler planilha de tradução: {e}")
        return {}

def aplicar_traducoes_dom(soup, dicionario_traducao):
    """Substitui os textos no DOM respeitando o mapeamento do Excel."""
    if not dicionario_traducao:
        return soup

    for text_node in soup.find_all(text=True):
        if text_node.parent.name in ['script', 'style', 'head', 'title', 'meta']:
            continue
        
        texto_original = str(text_node)
        texto_modificado = texto_original
        
        for en_text, pt_text in dicionario_traducao.items():
            if en_text in texto_modificado:
                texto_modificado = texto_modificado.replace(en_text, pt_text)
        
        if texto_modificado != texto_original:
            text_node.replace_with(texto_modificado)
            
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
            
    # 4. Aplicação do De/Para do Excel
    soup = aplicar_traducoes_dom(soup, mapa_traducao)

    os.makedirs(pasta_destino, exist_ok=True)
    
    # 5. Agrupamento de CSS
    css_links = []
    for link in soup.find_all('link', rel=lambda x: x and 'stylesheet' in x.lower()):
        href = link.get('href')
        if href:
            url_css_completa = urllib.parse.urljoin(url, href)
            css_links.append((link, url_css_completa))
            
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
        novo_link_css = soup.new_tag("link", rel="stylesheet", href="style.css")
        soup.head.append(novo_link_css)

    caminho_html = os.path.join(pasta_destino, "index.html")
    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write(soup.prettify())
        
    print(f"✅ Versão [{dispositivo_nome}] salva em: {os.path.abspath(pasta_destino)}")

async def main():
    mapa_traducao = carregar_dicionario_traducao(ARQUIVO_EXCEL_TRADUCAO)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        
        # 1. Configuração Contexto Desktop
        context_desktop = await browser.new_context(no_viewport=True)
        await extrair_versao(context_desktop, URL_ALVO, "pagina_extraida/desktop", "DESKTOP", mapa_traducao)
        
        # 2. Configuração Contexto Mobile
        context_mobile = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            viewport={'width': 390, 'height': 844},
            is_mobile=True,
            has_touch=True
        )
        await extrair_versao(context_mobile, URL_ALVO, "pagina_extraida/mobile", "MOBILE", mapa_traducao)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())