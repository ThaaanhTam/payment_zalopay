# coding=utf-8
# Python 3.6+

from time import time
from datetime import datetime
import json, hmac, hashlib, urllib.request, urllib.parse, random
from flask import Flask, request, jsonify  # pip3 install Flask
import logging

# Cấu hình
config = {
    "app_id": 2554,
    "key1": "sdngKKJmqEMzvh5QQcdD2A9XBSKUNaYn",
    "key2": "trMrHtvjo6myautxDUiAcYsVtaeQ8nhf",
    "endpoint": "https://sb-openapi.zalopay.vn/v2/create"
}

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='zalopay.log', filemode='a',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Tạo đơn hàng
transID = random.randrange(1000000)
order = {
    "app_id": config["app_id"],
    "app_trans_id": "{:%y%m%d}_{}".format(datetime.today(), transID), # mã giao dịch có định dạng yyMMdd_xxxx
    "app_user": "user123",
    "app_time": int(round(time() * 1000)), # mili giây
    "embed_data": json.dumps({}),
    "item": json.dumps([{"id":1,"tên":"abc", "giá": 1200},{"id":2,"tên":"â","giá":1200}]),
    "amount": 50000,
    "description": "Lazada - Payment for the order #" + str(transID),
    "bank_code": "",
    "callback_url": "https://fe5b-2001-ee0-4fc2-4900-cc3e-785c-e7ca-7326.ngrok-free.app/callback",
}

# Chuỗi dữ liệu để tạo chữ ký
data = "{}|{}|{}|{}|{}|{}|{}".format(
    order["app_id"], order["app_trans_id"], order["app_user"],
    order["amount"], order["app_time"], order["embed_data"], order["item"]
)

# Tạo chữ ký (mac)
order["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

# Gửi yêu cầu tạo đơn hàng đến ZaloPay
response = urllib.request.urlopen(url=config["endpoint"], data=urllib.parse.urlencode(order).encode())
result = json.loads(response.read())

# In kết quả
for k, v in result.items():
    print("{}: {}".format(k, v))

# Tạo ứng dụng Flask để xử lý callback từ ZaloPay
app = Flask(__name__)

@app.route('/callback', methods=['POST'])
def callback():
    result = {}

    try:
        cbdata = request.json
        mac = hmac.new(config['key2'].encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

        # kiểm tra callback hợp lệ (đến từ ZaloPay server)
        if mac != cbdata['mac']:
            # callback không hợp lệ
            result['return_code'] = -1
            result['return_message'] = 'mac not equal'
            print("thanh toán thất bại")
        else:
            # thanh toán thành công
            # merchant cập nhật trạng thái cho đơn hàng
            dataJson = json.loads(cbdata['data'])
            print("giao dịch thành công " + dataJson['app_trans_id'])

            result['return_code'] = 1
            result['return_message'] = 'success'
    except Exception as e:
        result['return_code'] = 0 # ZaloPay server sẽ callback lại (tối đa 3 lần)
        result['error'] = str(e)
        print("lỗi")

    # thông báo kết quả cho ZaloPay server
    return jsonify(result)




@app.route('/startus/<app_trans_id>', methods=['POST'])
def startus(app_trans_id):
    params = {
        "app_id": config["app_id"],
        "app_trans_id": app_trans_id  # Input your app_trans_id from URL
    }

    # Tạo chữ ký (mac)
    data = "{}|{}|{}".format(config["app_id"], params["app_trans_id"], config["key1"])  # app_id|app_trans_id|key1
    params["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

    # Gửi yêu cầu đến ZaloPay
    try:
        response = urllib.request.urlopen(url="https://sb-openapi.zalopay.vn/v2/query", data=urllib.parse.urlencode(params).encode())
        result = json.loads(response.read())

        # In kết quả
        for k, v in result.items():
            print("{}: {}".format(k, v))
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error while making request to ZaloPay: {e}")
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)  # Thay đổi cổng ở đây, ví dụ cổng 8000
