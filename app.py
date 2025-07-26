import os
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'service': 'MosRu Parser API',
        'version': '1.0'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'mos.ru parser'
    })

@app.route('/parse', methods=['POST'])
def parse():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'success': False, 'error': 'URL required'}), 400
        
        # Простой запрос
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return jsonify({
                'success': False, 
                'error': f'HTTP {response.status_code}',
                'url': url
            })
        
        # Простой парсинг
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = ''
        title_elem = soup.find('h1')
        if title_elem:
            title = title_elem.text.strip()
        
        # Убираем скрипты и получаем текст
        for script in soup(['script', 'style']):
            script.decompose()
        
        content = soup.get_text()
        content = ' '.join(content.split())  # Чистим пробелы
        
        return jsonify({
            'success': True,
            'url': url,
            'title': title,
            'content': content[:2000],  # Ограничиваем размер
            'content_length': len(content)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'url': url if 'url' in locals() else 'unknown'
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
