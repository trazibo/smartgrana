import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests # Import requests library
from flask import Flask, send_from_directory, request, jsonify
# from src.models.user import db # Assuming this might be used later
# from src.routes.user import user_bp # Assuming this might be used later

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# app.register_blueprint(user_bp, url_prefix='/api') # Keep this if user routes are separate

# Yahoo Finance API base URL (v8 is commonly used)
YAHOO_FINANCE_CHART_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

@app.route('/api/search_asset', methods=['GET'])
def search_asset_api():
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({'error': 'Símbolo do ativo não fornecido'}), 400

    # Parameters for Yahoo Finance API (matching what ApiClient might have used)
    params = {
        'region': request.args.get('region', 'US'), # Default to US if not provided
        'interval': request.args.get('interval', '1d'),
        'range': request.args.get('range', '1d'),
        'includeAdjustedClose': request.args.get('includeAdjustedClose', 'true'),
        'events': 'div,split,capitalGains', # Common events
        'lang': 'pt-BR' # Or 'en-US'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        api_url = YAHOO_FINANCE_CHART_API_URL.format(symbol=symbol)
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        chart_data = response.json()
        
        asset_info = {}
        if chart_data and chart_data.get('chart') and chart_data['chart'].get('result'):
            meta = chart_data['chart']['result'][0].get('meta', {})
            indicators = chart_data['chart']['result'][0].get('indicators', {})
            quote = indicators.get('quote', [{}])[0]
            
            asset_info['symbol'] = meta.get('symbol')
            asset_info['name'] = meta.get('shortName', meta.get('longName', 'N/A'))
            asset_info['price'] = meta.get('regularMarketPrice', 'N/A')
            asset_info['currency'] = meta.get('currency', '')
            
            # Calculate change and change_percent if possible
            current_price_list = quote.get('close', [])
            # Get the last valid price from the list, ignoring None values at the end
            last_valid_price = None
            if current_price_list:
                for price_val in reversed(current_price_list):
                    if price_val is not None:
                        last_valid_price = price_val
                        break
            
            previous_close = meta.get('chartPreviousClose')

            if last_valid_price is not None and previous_close is not None and previous_close != 0:
                change = last_valid_price - previous_close
                change_percent = (change / previous_close) * 100
                asset_info['change'] = round(change, 2)
                asset_info['change_percent'] = round(change_percent, 2)
            else:
                asset_info['change'] = 'N/A'
                asset_info['change_percent'] = 'N/A'

            volume_list = quote.get('volume', [])
            last_valid_volume = None
            if volume_list:
                for vol_val in reversed(volume_list):
                    if vol_val is not None:
                        last_valid_volume = vol_val
                        break
            asset_info['volume'] = last_valid_volume if last_valid_volume is not None else 'N/A'

        else:
            error_details = chart_data.get('chart', {}).get('error')
            if error_details:
                return jsonify({'error': f"Não foi possível obter dados do gráfico para o símbolo: {symbol}. Detalhes: {error_details.get('description', 'Erro desconhecido da API')}"}), 404
            return jsonify({'error': f"Não foi possível obter dados do gráfico para o símbolo: {symbol}. Resposta inesperada da API."}), 404

        return jsonify(asset_info)

    except requests.exceptions.HTTPError as http_err:
        return jsonify({'error': f'Erro HTTP ao buscar dados do ativo: {http_err}', 'details': response.text if response else 'Sem resposta'}), response.status_code
    except requests.exceptions.RequestException as req_err:
        return jsonify({'error': f'Erro de requisição ao buscar dados do ativo: {req_err}'}), 500
    except Exception as e:
        # Log the full error for debugging on the server side
        app.logger.error(f"Error processing YahooFinance API for symbol {symbol}: {e}", exc_info=True)
        return jsonify({'error': 'Erro interno ao processar dados do ativo.', 'details': str(e)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) # Set debug=False for production-like testing

