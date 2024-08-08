import logging
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime
from time import time
import random
import threading


from werkzeug import urls
from odoo import _, api, fields, models
from odoo.addons.payment_zalopay import const
from odoo.http import request
_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"
    app_trans_id = fields.Char(string="App Transaction ID")
    zalopay_amount = fields.Integer(string="ZaloPay Amount")
    last_status_check = fields.Datetime(string="Last Status Check")
    status = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed')
    ], string="Payment Status", default='pending')
    payment_creation_time = fields.Datetime(string="Payment Creation Time")

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "zalopay":
            return res

        base_url = self.provider_id.get_base_url()
        int_amount = int(self.amount)

        # Tạo ID giao dịch và thời gian hiện tại
        trans_id = random.randrange(1000000)
        app_time = int(round(time() * 1000))  # Thời gian hiện tại tính bằng mili giây

       # Lấy các mục từ đơn hàng
        order_items = []
        for line in self.invoice_ids.mapped('invoice_line_ids'):
            item = {
                "id": line.id,
                "name": line.name,
                "price": int(line.price_unit * 100)  # Giá sản phẩm tính bằng xu
            }
            order_items.append(item)
        # Tạo đơn hàng
        order = {
            "app_id": self.provider_id.appid,
            "app_trans_id": "{:%y%m%d}_{}".format(datetime.today(), trans_id),
            "app_user": self.provider_id.app_user,
            "app_time": app_time,
            "embed_data": json.dumps({"redirecturl": urls.url_join(base_url, '/payment/zalopay/return')}),
            "item": json.dumps(order_items),
            "amount": int_amount,
            "description": f"Nếu đọc được này thì đã lấy đc qr thành công #{trans_id}",
            "bank_code": "",
            "callback_url": urls.url_join(base_url.replace("http://", "https://", 1), '/payment/zalopay/callback'),  # URL callback
        }
        _logger.info(urls.url_join(base_url, '/payment/zalopay/callback'))
            
        # Chuỗi dữ liệu để tạo chữ ký
        data = "{}|{}|{}|{}|{}|{}|{}".format(
            order["app_id"], order["app_trans_id"], order["app_user"],
            order["amount"], order["app_time"], order["embed_data"], order["item"]
        )

        # Tạo chữ ký (mac)
        order["mac"] = hmac.new(self.provider_id.key1.encode(), data.encode(), hashlib.sha256).hexdigest()
        

        # Gửi yêu cầu tạo đơn hàng đến ZaloPay
        try:
            response = urllib.request.urlopen(url="https://sb-openapi.zalopay.vn/v2/create", data=urllib.parse.urlencode(order).encode())
            _logger.info(urllib.parse.urlencode(order).encode())
            result = json.loads(response.read())
            _logger.info("Tạo hóa đơn thành công 13: %s", result)
            # Cập nhật trường app_trans_id
            self.write({
                'app_trans_id': order['app_trans_id'],
                'zalopay_amount': int_amount,
                'last_status_check': fields.Datetime.now()
            })

           
            threading.Timer(20, self.query_zalopay_status).start()
            
        except Exception as e:
            _logger.error("ZaloPay create order failed: %s", e)
            raise ValidationError(_("fffffffffffffffffffffffff: %s") % e)

        # Trả về các giá trị cần thiết để hiển thị
        rendering_values = {
            "api_url": result.get("order_url"),
        }
         # Xử lý phản hồi từ ZaloPay
        
        return rendering_values

        
    def query_zalopay_status(self):
        _logger.info("Bắt đầu truy vấn trạng thái ZaloPay")
        self.ensure_one()
        if self.provider_code != 'zalopay' or not self.app_trans_id:
            _logger.info("Không phải ZaloPay hoặc không có app_trans_id")
            return

        zalopay_provider = self.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
        
        config = {
            "app_id": zalopay_provider.zalopay_app_id,
            "key1": zalopay_provider.key1,
            "key2": zalopay_provider.key2,
            "endpoint": "https://sb-openapi.zalopay.vn/v2/query"
        }

        params = {
            "app_id": config["app_id"],
            "app_trans_id": self.app_trans_id
        }

        data = "{}|{}|{}".format(config["app_id"], params["app_trans_id"], config["key1"])
        params["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

        _logger.info("Dữ liệu truy vấn: %s", params)
        _logger.info("Chữ ký (mac) truy vấn: %s", params["mac"])

        try:
            response = urllib.request.urlopen(url=config["endpoint"], data=urllib.parse.urlencode(params).encode())
            result = json.loads(response.read())

            _logger.info("Kết quả truy vấn ZaloPay cho app_trans_id %s: %s", self.app_trans_id, result)

            if result.get("return_code") == 1:  # Kiểm tra xem giao dịch thành công hay không
                status = result.get("status")
                if status == 1:  # Giao dịch đã thanh toán thành công
                    self.write({'status': 'paid'})
                elif status == -1:  # Giao dịch thất bại
                    self.write({'status': 'failed'})
                self.write({'last_status_check': fields.Datetime.now()})

        except Exception as e:
            _logger.error("Lỗi khi truy vấn trạng thái thanh toán ZaloPay: %s", str(e))


    

    
    


