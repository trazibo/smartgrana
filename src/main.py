import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
from src.models.user import db # Assuming this might be used later
from src.routes.user import user_bp # Assuming this might be used later

# Import ApiClient
sys.path.append('/opt/.manus/.sandbox-runtime')
from data_api import ApiClient

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# app.register_blueprint(user_bp, url_prefix='/api') # Keep this if user routes are separate

# Database setup (currently commented out, keep as is unless DB is needed now)
# app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USERNAME', 'root')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'mydb')}"
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db.init_app(app)
# with app.app_context():
#     db.create_all()

@app.route('/api/search_asset', methods=['GET'])
def search_asset_api():
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({'error': 'Símbolo do ativo não fornecido'}), 400

    client = ApiClient()
    try:
        # Fetch chart data (includes price, variation, volume)
        chart_data = client.call_api('YahooFinance/get_stock_chart', query={'symbol': symbol, 'region': 'US', 'interval': '1d', 'range': '1d', 'includeAdjustedClose': 'true'})
        
        asset_info = {}
        if chart_data and chart_data.get('chart') and chart_data['chart'].get('result'):
            meta = chart_data['chart']['result'][0].get('meta', {})
            indicators = chart_data['chart']['result'][0].get('indicators', {})
            quote = indicators.get('quote', [{}])[0]
            
            asset_info['symbol'] = meta.get('symbol')
            asset_info['name'] = meta.get('shortName', meta.get('longName', 'N/A'))
            asset_info['price'] = meta.get('regularMarketPrice', 'N/A')
            asset_info['currency'] = meta.get('currency', '')
            
            if quote.get('close') and len(quote['close']) > 0 and meta.get('chartPreviousClose'):
                current_price = quote['close'][-1]
                previous_close = meta['chartPreviousClose']
                if current_price is not None and previous_close is not None and previous_close != 0:
                    change = current_price - previous_close
                    change_percent = (change / previous_close) * 100
                    asset_info['change'] = round(change, 2)
                    asset_info['change_percent'] = round(change_percent, 2)
                else:
                    asset_info['change'] = 'N/A'
                    asset_info['change_percent'] = 'N/A'
            else:
                asset_info['change'] = 'N/A'
                asset_info['change_percent'] = 'N/A'

            if quote.get('volume') and len(quote['volume']) > 0:
                asset_info['volume'] = quote['volume'][-1]
            else:
                asset_info['volume'] = 'N/A'
        else:
            return jsonify({'error': 'Não foi possível obter dados do gráfico para o símbolo: ' + symbol, 'details': chart_data.get('chart', {}).get('error')}), 404

        # Fetch insights data (optional, can be added later or if needed)
        # insights_data = client.call_api('YahooFinance/get_stock_insights', query={'symbol': symbol})
        # if insights_data and insights_data.get('finance') and insights_data['finance'].get('result'):
        #    asset_info['insights'] = insights_data['finance']['result'].get('instrumentInfo', {}).get('technicalEvents', {}).get('shortTermOutlook', {}).get('stateDescription', 'N/A')
        # else:
        #    asset_info['insights'] = 'N/A'

        return jsonify(asset_info)

    except Exception as e:
        print(f"Error calling YahooFinance API: {e}")
        return jsonify({'error': 'Erro ao buscar dados do ativo.', 'details': str(e)}), 500

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
    app.run(host='0.0.0.0', port=5000, debug=True)

