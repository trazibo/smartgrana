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

# Yahoo Finance API base URL
YAHOO_FINANCE_CHART_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

@app.route('/api/search_asset', methods=['GET'])
def search_asset_api():
    symbol_input = request.args.get('symbol')
    if not symbol_input:
        return jsonify({'error': 'Símbolo do ativo não fornecido'}), 400

    # Prepare for API call
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Default parameters
    base_params = {
        'interval': request.args.get('interval', '1d'),
        'range': request.args.get('range', '1d'),
        'includeAdjustedClose': request.args.get('includeAdjustedClose', 'true'),
        'events': 'div,split,capitalGains',
        'lang': 'pt-BR'
    }

    # Attempt 1: Determine region based on suffix or default to US
    symbol_to_query = symbol_input.upper()
    query_region = 'US' # Default

    if '.' in symbol_to_query:
        market_suffix = symbol_to_query.split('.')[-1]
        if market_suffix == 'SA':
            query_region = 'BR'
    
    current_params = base_params.copy()
    current_params['region'] = query_region
    
    api_url = YAHOO_FINANCE_CHART_API_URL.format(symbol=symbol_to_query)
    app.logger.info(f"Attempt 1: Querying {api_url} with params {current_params}")
    response = requests.get(api_url, params=current_params, headers=headers)

    # Attempt 2: If Attempt 1 failed with 404 for a non-suffixed symbol tried as US, try as Brazilian (.SA)
    if response.status_code == 404 and '.' not in symbol_input and query_region == 'US':
        app.logger.info(f"Attempt 1 for {symbol_input} (region US) failed with 404. Retrying as Brazilian asset.")
        symbol_to_query_br = symbol_input.upper() + ".SA"
        query_region_br = 'BR'
        
        current_params_br = base_params.copy()
        current_params_br['region'] = query_region_br
        
        api_url_br = YAHOO_FINANCE_CHART_API_URL.format(symbol=symbol_to_query_br)
        app.logger.info(f"Attempt 2: Querying {api_url_br} with params {current_params_br}")
        response = requests.get(api_url_br, params=current_params_br, headers=headers)
        if response.ok:
            symbol_to_query = symbol_to_query_br # Update symbol if BR attempt is successful

    try:
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        chart_data = response.json()
        
        asset_info = {}
        if chart_data and chart_data.get('chart') and chart_data['chart'].get('result'):
            meta = chart_data['chart']['result'][0].get('meta', {})
            indicators = chart_data['chart']['result'][0].get('indicators', {})
            quote = indicators.get('quote', [{}])[0]
            
            asset_info['symbol'] = meta.get('symbol') # This should be the canonical symbol from API
            asset_info['name'] = meta.get('shortName', meta.get('longName', 'N/A'))
            asset_info['price'] = meta.get('regularMarketPrice', 'N/A')
            asset_info['currency'] = meta.get('currency', ">")
            
            current_price_list = quote.get('close', [])
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
            error_description = 'Resposta inesperada da API.'
            if error_details and isinstance(error_details, dict):
                 error_description = error_details.get('description', 'Erro desconhecido da API')
            elif isinstance(error_details, str):
                error_description = error_details
            return jsonify({'error': f"Não foi possível obter dados do gráfico para o símbolo: {symbol_input}. Detalhes: {error_description}"}), 404

        return jsonify(asset_info)

    except requests.exceptions.HTTPError as http_err:
        # Try to parse error from Yahoo Finance if possible
        error_message = f'Erro HTTP ao buscar dados do ativo: {http_err}'
        try:
            error_data = response.json()
            if error_data.get('chart') and error_data['chart'].get('error') and error_data['chart']['error'].get('description'):
                error_message = f"Erro da API Finance: {error_data['chart']['error']['description']}"
        except ValueError: # response.json() fails if not json
            pass
        return jsonify({'error': error_message, 'details': response.text if response else 'Sem resposta detalhada'}), response.status_code if response else 500
    except requests.exceptions.RequestException as req_err:
        return jsonify({'error': f'Erro de requisição ao buscar dados do ativo: {req_err}'}), 500
    except Exception as e:
        app.logger.error(f"Error processing YahooFinance API for symbol {symbol_input}: {e}", exc_info=True)
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
    app.run(host='0.0.0.0', port=5000, debug=False)

