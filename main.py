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
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'url': url
                }
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Заголовок
            title = ''
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Контент
            content = ''
            # Удаляем скрипты и стили
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            content = '\n'.join(lines)
            
            # Изображения
            images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('/'):
                    src = 'https://www.mos.ru' + src
                if src and not src.startswith('data:'):
                    images.append(src)
            
            return {
                'success': True,
                'url': url,
                'title': title,
                'content': content,
                'images': images,
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
