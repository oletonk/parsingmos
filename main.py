import os
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime

app = Flask(__name__)

class SimpleParser:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self.headers)
    
    def parse_article(self, url):
        # Добавляем случайную задержку
        time.sleep(random.uniform(1, 2))
        
        for attempt in range(3):  # 3 попытки
            try:
                # Обновляем User-Agent для каждой попытки
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
                
                self.session.headers.update({
                    'User-Agent': random.choice(user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1'
                })
                
                response = self.session.get(url, timeout=45, allow_redirects=True)
                
                if response.status_code == 200:
                    break
                elif response.status_code == 429:
                    # Rate limit - ждем больше
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    if attempt == 2:  # Последняя попытка
                        return {
                            'success': False,
                            'error': f'HTTP {response.status_code}',
                            'url': url
                        }
                        
            except Exception as e:
                if attempt == 2:  # Последняя попытка
                    return {
                        'success': False,
                        'error': str(e),
                        'url': url,
                        'parsed_at': datetime.now().isoformat()
                    }
                else:
                    # Ждем перед следующей попыткой
                    time.sleep(2 ** attempt)
                    continue
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Заголовок
            title = ''
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Контент - улучшенная логика
            content_parts = []
            
            # Удаляем ненужные элементы
            for unwanted in soup(["script", "style", "nav", "footer", "header"]):
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
                                 ['меню', 'навигация', 'войти', 'поиск', 'подписаться']):
                            content_parts.append(text)
            
            # Если основной контент не найден
            if not content_parts:
                text = soup.get_text()
                lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 20]
                content_parts = lines
            
            content = '\n\n'.join(content_parts[:50])  # Ограничиваем количество частей
            
            # Изображения
            images = []
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    if src.startswith('/'):
                        src = 'https://www.mos.ru' + src
                    if not src.startswith('data:'):
                        images.append(src)
            
            return {
                'success': True,
                'url': url,
                'title': title,
                'content': content,
                'images': images,
                'content_length': len(content),
                'images_count': len(images),
                'parsed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'parsed_at': datetime.now().isoformat()
            }

parser = SimpleParser()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'mos.ru parser API'
    })

@app.route('/parse', methods=['POST'])
def parse_article():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'URL is required'
            }), 400
        
        url = data['url']
        if not url.startswith('https://www.mos.ru/news/item/'):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format'
            }), 400
        
        result = parser.parse_article(url)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/parse', methods=['GET'])
def parse_article_get():
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({
                'success': False,
                'error': 'URL parameter is required'
            }), 400
        
        if not url.startswith('https://www.mos.ru/news/item/'):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format'
            }), 400
        
        result = parser.parse_article(url)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def api_info():
    return jsonify({
        'service': 'MosRu Parser API',
        'status': 'running',
        'endpoints': {
            'GET /health': 'Health check',
            'POST /parse': 'Parse article',
            'GET /parse?url=': 'Parse article via GET'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
