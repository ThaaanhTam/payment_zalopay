import hashlib
import hmac
import logging
import json
import urllib.parse
import urllib.request
from werkzeug.exceptions import Forbidden
from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):
    _return_url = "/payment/zlpay/return"
    _callback_url = "/payment/zlpay/callback"
    _query_status_url = "/payment/zlpay/query_status"

    @http.route(
        _return_url,
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def zlpay_return_from_checkout(self, **kwargs):
        """Handle redirection after payment checkout and query payment status."""
        app_trans_id = kwargs.get('app_trans_id')
        _logger.info("Sau khi thanh toán sẽ vào trang trạng thái với app_trans_id = %s", app_trans_id)

        if app_trans_id:
            _logger.info("Truy vấn trạng thái thanh toán cho app_trans_id = %s", app_trans_id)
            try:
                zlpay_provider = request.env['payment.provider'].sudo().search([('code', '=', 'zlpay')], limit=1)
                if not zlpay_provider:
                    raise ValidationError("ZaloPay provider not configured")

                config = {
                    "app_id": zlpay_provider.app_id,
                    "key1": zlpay_provider.key1,
                    "endpoint": "https://sb-openapi.zalopay.vn/v2/query"
                }

                params = {
                    "app_id": config["app_id"],
                    "app_trans_id": app_trans_id
                }

                data = "{}|{}|{}".format(config["app_id"], params["app_trans_id"], config["key1"])
                params["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

                response = urllib.request.urlopen(url=config["endpoint"], data=urllib.parse.urlencode(params).encode())
                result = json.loads(response.read())

                _logger.info("Kết quả truy vấn trạng thái thanh toán: %s", result)
                return request.redirect("/payment/status?result=%s" % json.dumps(result))

            except Exception as e:
                _logger.error("Truy vấn trạng thái thanh toán thất bại: %s", e)
                return request.redirect("/payment/status?result=%s" % json.dumps({"return_code": 0, "return_message": str(e)}))

        return request.redirect("/payment/status")

    @http.route(
        _callback_url,
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def zlpay_callback(self):
        """Xử lý callback từ ZaloPay."""
        result = {}
        _logger.info("Xử lý callback từ ZaloPay")
        try:
            raw_data = request.httprequest.get_data()
            cbdata = json.loads(raw_data)
            _logger.info("Dữ liệu callback nhận được: %s", cbdata)
            
            zlpay_provider = request.env['payment.provider'].sudo().search([('code', '=', 'zlpay')], limit=1)
            key2 = zlpay_provider.key2

            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            # Kiểm tra callback hợp lệ (đến từ ZaloPay server)
            if mac != cbdata['mac']:
                _logger.info("Callback không hợp lệ: mac không khớp")
                result['return_code'] = -1
                result['return_message'] = 'MAC mismatch'
            else:
                # Thanh toán thành công
                dataJson = json.loads(cbdata['data'])
                app_trans_id = dataJson['app_trans_id']
                _logger.info("Cập nhật trạng thái đơn hàng thành công cho app_trans_id = %s", app_trans_id)
              
                # Tìm giao dịch tương ứng với app_trans_id
                tx = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
                if tx:
                    tx._set_done()
                    _logger.info("Đã cập nhật trạng thái đơn hàng thành công cho app_trans_id = %s", app_trans_id)
                else:
                    _logger.warning("Không tìm thấy giao dịch với app_trans_id = %s", app_trans_id)
                
                result['return_code'] = 1
                result['return_message'] = 'success'
        except Exception as e:
            _logger.error("Xử lý callback ZaloPay thất bại: %s", e)
            result['return_code'] = 0  # ZaloPay server sẽ callback lại (tối đa 3 lần)
            result['return_message'] = str(e)
        
        _logger.info("Kết thúc xử lý callback ZaloPay với kết quả: %s", result)
        return result
