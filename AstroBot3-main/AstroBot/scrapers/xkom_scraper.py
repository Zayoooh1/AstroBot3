import requests
from bs4 import BeautifulSoup
import re

def _parse_price_to_cents(price_text: str) -> int | None:
    """Konwertuje string ceny (np. "1 234,56 zł") na liczbę całkowitą groszy."""
    if not price_text:
        return None
    try:
        # Usuń "zł", spacje (w tym non-breaking space \xa0), zamień przecinek na kropkę
        cleaned_price = re.sub(r'[zł\s]', '', price_text).replace(',', '.')
        price_float = float(cleaned_price)
        return int(price_float * 100)
    except (ValueError, TypeError):
        print(f"Nie udało się sparsować ceny '{price_text}' na grosze.")
        return None

def scrape_xkom_product(url: str) -> dict | None:
    """
    Scrapuje dane produktu (nazwa, cena, dostępność) ze strony X-Kom.
    Zwraca słownik z danymi lub None w przypadku błędu.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Rzuci wyjątek dla kodów błędów HTTP 4xx/5xx
        soup = BeautifulSoup(response.content, 'html.parser')

        product_data = {
            "name": None,
            "price_in_cents": None,
            "availability_str": None
        }

        # Nazwa produktu
        name_tag = soup.find('h1', class_=re.compile(r'sc-.*')) # Bardzo ogólny selektor dla h1
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)

        # Cena produktu
        price_text_raw = None
        # X-Kom często używa specyficznych klas, spróbujmy znaleźć div z ceną
        price_tag = soup.find('div', class_=re.compile(r'price', re.IGNORECASE))
        if price_tag:
            price_text_raw = price_tag.get_text(strip=True)
        else: # Fallback na meta tag, jeśli jest dostępny
            meta_price_tag = soup.find('meta', property='product:price:amount')
            if meta_price_tag and meta_price_tag.get('content'):
                price_text_raw = meta_price_tag.get('content').strip()
        
        # Przetworzenie znalezionego tekstu ceny na grosze
        if price_text_raw:
            product_data["price_in_cents"] = _parse_price_to_cents(price_text_raw)

        # Dostępność produktu
        # To jest najtrudniejsze, bo zależy od wielu czynników, spróbujmy po tekście przycisku
        add_to_cart_button = soup.find('button', {'title': re.compile(r'Dodaj do koszyka', re.IGNORECASE)})
        if add_to_cart_button:
            product_data["availability_str"] = "Dostępny"
        elif soup.find(string=re.compile(r"Produkt niedostępny|Produkt wyprzedany", re.IGNORECASE)):
            product_data["availability_str"] = "Niedostępny"
        elif soup.find(string=re.compile(r"Powiadom o dostępności", re.IGNORECASE)):
            product_data["availability_str"] = "Powiadom o dostępności"
        else:
            product_data["availability_str"] = "Sprawdź na stronie"

        # Zwróć dane tylko jeśli udało się pobrać nazwę
        if product_data["name"]:
            return product_data
        else:
            print(f"Scraping X-Kom: Nie udało się znaleźć kluczowych danych (nazwy) dla {url}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Błąd żądania HTTP dla {url}: {e}")
        return None
    except Exception as e:
        print(f"Nieoczekiwany błąd podczas scrapowania {url}: {e}")
        return None
