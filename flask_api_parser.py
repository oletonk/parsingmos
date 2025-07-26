from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urljoin
import json
import logging
from fake_useragent import UserAgent
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MosRuAPIParser:
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        
        # Настройки для обхода блокировок
        self.headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.mos.ru/'
        }
        
        self.session.headers.update(self.headers)
        self.timeout = 30
        self.max_retries = 3
        self.delay_range = (1, 3)
    
    def get_page_with_retries(self, url):
        """Получение страницы с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    delay = random.uniform(*self.delay_range)
                    time.sleep(delay)
                
                # Обновляем User-Agent
                self.session.headers['User-Agent'] = self.ua.random
                
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                
        return None
    
    def parse_news_article(self, url):
        """Парсинг отдельной новости"""
        try:
            logger.info(f"Parsing: {url}")
            response = self.get_page_with_retries(url)
            
            if not response:
                return {
                    'success': False,
                    'error': 'Failed to fetch page',
                    'url': url
                }
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем данные
            article_data = {
                'success': True,
                'url': url,
                'title': '',
                'content': '',
                'date': '',
                'images': [],
                'tags': [],
                'parsed_at': datetime.now().isoformat()
            }
            
            # Заголовок
            title_selectors = ['h1', 'title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    if title_text and len(title_text) > 5:
                        article_data['title'] = title_text
                        break
            
            # Основной контент - улучшенная логика
            content_text = []
            
            # Удаляем ненужные элементы
            for unwanted in soup.select('script, style, nav, footer, header, .navigation, .menu'):
                unwanted.decompose()
            
            # Ищем основной контент
            main_content = soup.select_one('article, .content, .news-content, main, [role="main"]')
            if main_content:
                paragraphs = main_content.find_all(['p', 'div'])
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        # Фильтруем навигационные элементы
                        if not any(skip in text.lower() for skip in 
                                 ['меню', 'навигация', 'войти', 'поиск', 'подписаться', 'cookies']):
                            content_text.append(text)
            
            # Если основной контент не найден, собираем все параграфы
            if not content_text:
                all_paragraphs = soup.find_all('p')
                for p in all_paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 50:
                        content_text.append(text)
            
            article_data['content'] = '\n\n'.join(content_text)
            
            # Дата публикации
            date_selectors = ['[datetime]', '.news-date', '.date', '[data-test="news-date"]']
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    if date_text:
                        article_data['date'] = date_text
                        break
            
            # Изображения
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and not src.startswith('data:'):
                    if src.startswith('/'):
                        src = 'https://www.mos.ru' + src
                    article_data['images'].append(src)
            
            # Теги
            tag_selectors = ['.tags a', '.categories a', '[data-test="tags"] a']
            for selector in tag_selectors:
                tags = soup.select(selector)
                for tag in tags:
                    tag_text = tag.get_text(strip=True)
                    if tag_text:
                        article_data['tags'].append(tag_text)
            
            logger.info(f"Successfully parsed: {article_data['title'][:50]}...")
            return article_data
            
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'parsed_at': datetime.now().isoformat()
            }

# Глобальный экземпляр парсера
parser = MosRuAPIParser()

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'mos.ru parser API'
    })

@app.route('/parse', methods=['POST'])
def parse_article():
    """
    Парсинг статьи по URL
    
    POST /parse
    {
        "url": "https://www.mos.ru/news/item/154988073/"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'URL is required in JSON body'
            }), 400
        
        url = data['url']
        
        # Валидация URL
        if not url.startswith('https://www.mos.ru/news/item/'):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format. Expected: https://www.mos.ru/news/item/...'
            }), 400
        
        # Парсинг
        result = parser.parse_news_article(url)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/parse', methods=['GET'])
def parse_article_get():
    """
    Парсинг статьи по URL через GET параметр
    
    GET /parse?url=https://www.mos.ru/news/item/154988073/
    """
    try:
        url = request.args.get('url')
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'URL parameter is required'
            }), 400
        
        # Валидация URL
        if not url.startswith('https://www.mos.ru/news/item/'):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format. Expected: https://www.mos.ru/news/item/...'
            }), 400
        
        # Парсинг
        result = parser.parse_news_article(url)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/batch', methods=['POST'])
def parse_batch():
    """
    Пакетный парсинг нескольких статей
    
    POST /batch
    {
        "urls": [
            "https://www.mos.ru/news/item/154988073/",
            "https://www.mos.ru/news/item/154988074/"
        ],
        "delay": 2
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data:
            return jsonify({
                'success': False,
                'error': 'URLs array is required in JSON body'
            }), 400
        
        urls = data['urls']
        delay = data.get('delay', 2)  # Задержка между запросами
        
        if not isinstance(urls, list) or len(urls) == 0:
            return jsonify({
                'success': False,
                'error': 'URLs must be a non-empty array'
            }), 400
        
        if len(urls) > 10:  # Ограничение на количество
            return jsonify({
                'success': False,
                'error': 'Maximum 10 URLs per batch request'
            }), 400
        
        results = []
        
        for i, url in enumerate(urls):
            # Валидация каждого URL
            if not url.startswith('https://www.mos.ru/news/item/'):
                results.append({
                    'success': False,
                    'error': 'Invalid URL format',
                    'url': url
                })
                continue
            
            # Парсинг
            result = parser.parse_news_article(url)
            results.append(result)
            
            # Задержка между запросами (кроме последнего)
            if i < len(urls) - 1:
                time.sleep(delay)
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results),
            'successful': len([r for r in results if r.get('success')]),
            'failed': len([r for r in results if not r.get('success')])
        }), 200
        
    except Exception as e:
        logger.error(f"Batch API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/', methods=['GET'])
def api_info():
    """Информация об API"""
    return jsonify({
        'service': 'MosRu News Parser API',
        'version': '1.0',
        'endpoints': {
            'GET /health': 'Health check',
            'POST /parse': 'Parse single article (JSON: {"url": "..."})',
            'GET /parse?url=': 'Parse single article (URL parameter)',
            'POST /batch': 'Parse multiple articles (JSON: {"urls": [...], "delay": 2})'
        },
        'examples': {
            'single_parse': 'curl -X POST -H "Content-Type: application/json" -d \'{"url":"https://www.mos.ru/news/item/154988073/"}\' http://localhost:5000/parse',
            'batch_parse': 'curl -X POST -H "Content-Type: application/json" -d \'{"urls":["https://www.mos.ru/news/item/154988073/"]}\' http://localhost:5000/batch'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
