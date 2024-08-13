import logging
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime,timedelta
from time import time
import random
import threading
import pytz


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
    next_check = fields.Datetime(string="Next Status Check")

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "zalopay":
            return res

        # base_url = self.provider_id.get_base_url()
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
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
            utc_now = datetime.now(pytz.timezone("Etc/GMT-7")).replace(tzinfo=None)
            utc = datetime.now(pytz.timezone("Etc/GMT-7")) + timedelta(minutes=1)
            next_check = utc.replace(tzinfo=None)
            _logger.info("utc_now: %s,next_check: %s", utc_now, next_check)
            # current_datetime = fields.Datetime.context_timestamp(self, utc_now).replace(tzinfo=None)
            # Cập nhật trường app_trans_id
            self.write({
                'app_trans_id': order['app_trans_id'],
                'zalopay_amount': int_amount,
                'last_status_check': utc_now,
                'next_check': next_check  
            })

            cron_job = self.env.ref("payment_zalopay.ir_cron_check_zalopay_status", False)
            if cron_job:
                if not cron_job.active:
                    # Nếu cron job đang tắt, bật nó lên
                    cron_job.write({'active': True})
                    _logger.info("Cron job đã được bật.")
                else:
                    _logger.info("Cron job đã bật, không cần bật lại.")
            else:
                _logger.warning("Cron job 'Check ZaloPay Transaction Status' không tồn tại.")
            # threading.Timer(60, self.query_zalopay_status, args=[order['app_trans_id']]).start()
        
        except Exception as e:
            _logger.error("ZaloPay create order failed: %s", e)
            raise ValidationError(_("fffffffffffffffffffffffff: %s") % e)

        # Trả về các giá trị cần thiết để hiển thị
        rendering_values = {
            "api_url": result.get("order_url"),
        }
         # Xử lý phản hồi từ ZaloPay
        
        return rendering_values
    def is_app_trans_id_exist(self, app_trans_id):
        """Kiểm tra xem app_trans_id có tồn tại trong hệ thống hay không."""
        transaction = self.search([('app_trans_id', '=', app_trans_id)], limit=1)
        return bool(transaction)
        
    def query_zalopay_status(self, app_trans_id):
        _logger.info("Bắt đầu truy vấn trạng thái ZaloPayyy")
        try:
            _logger.info("vô")
            if self.is_app_trans_id_exist(app_trans_id):
                _logger.info("app_trans_id %s tồn tại trong hệ thống", app_trans_id)
            else:
                _logger.error("app_trans_id %s không tồn tại trong hệ thống", app_trans_id)
                return
            config = {
                "app_id": "2554",
                "key1": "sdngKKJmqEMzvh5QQcdD2A9XBSKUNaYn",
                "endpoint": "https://sb-openapi.zalopay.vn/v2/query"
            }

            params = {
                "app_id": config["app_id"],
                "app_trans_id": app_trans_id
            }

            data = "{}|{}|{}".format(config["app_id"], params["app_trans_id"], config["key1"])
            params["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

            _logger.info("Dữ liệu truy vấn: %s", params)
            _logger.info("Chữ ký (mac) truy vấn: %s", params["mac"])

            response = urllib.request.urlopen(url=config["endpoint"], data=urllib.parse.urlencode(params).encode())
            result = json.loads(response.read())

            _logger.info("Kết quả truy vấn ZaloPay cho app_trans_id %s: %s", app_trans_id, result)

            if result.get("return_code") == 1:  # Kiểm tra xem giao dịch thành công hay không
                status = result.get("status")
                if status == 1:  # Giao dịch đã thanh toán thành công
                    self.write({'status': 'paid'})
                    _logger.info("Giao dịch %s đã được thanh toán thành công", app_trans_id)
                elif status == -1:  # Giao dịch thất bại
                    self.write({'status': 'failed'})
                    _logger.info("Giao dịch %s đã thất bại", app_trans_id)
                self.write({'last_status_check': fields.Datetime.now()})

        except Exception as e:
            _logger.error("Lỗi khi truy vấn trạng thái thanh toán ZaloPay cho app_trans_id %s: %s", app_trans_id, str(e))



    @api.model
    def cron_check_zalopay_status(self):
        _logger.info("chạy cronnnnnnnnnnnnn")
        transactions = self.search([
            ('provider_code', '=', 'zalopay'),
            ('status', '=', 'pending'),
            ('next_check', '<=', datetime.now(pytz.timezone("Etc/GMT-7")).replace(tzinfo=None))  # Chỉ lấy các giao dịch cần kiểm tra
        ])
        
        cron_job = self.env.ref("payment_zalopay.ir_cron_check_zalopay_status", False)
        if not cron_job:
            _logger.warning("Cron job 'Check ZaloPay Transaction Status' không tồn tại")
            return
        
        if not transactions:
        # Tắt cron job nếu không tìm thấy giao dịch nào cần kiểm tra
            cron_job = self.env.ref("payment_zalopay.ir_cron_check_zalopay_status", False)
            if cron_job.active:
                try:
                    cron_job.sudo().write({'active': False})
                    _logger.info("Không tìm thấy giao dịch cần kiểm tra. Đã tắt cron job.")
                except Exception as e:
                    _logger.error("Lỗi khi tắt cron job: %s", e)
        else:
            for tx in transactions:
                _logger.info("Kiểm tra trạng thái cho app_trans_id: %s", tx.app_trans_id)
                tx.query_zalopay_status(tx.app_trans_id)          
                # Cập nhật trường next_check
                tx.write({'next_check': False})
            
            # Đảm bảo cron job được bật
            if not cron_job.active:
                try:
                    cron_job.write({'active': True})
                    _logger.info("Đã bật cron job để tiếp tục kiểm tra giao dịch.")
                except Exception as e:
                    _logger.error("Lỗi khi bật cron job: %s", e)