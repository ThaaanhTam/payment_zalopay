import hashlib
import hmac
import logging
import json
import urllib.parse
from werkzeug.exceptions import Forbidden
from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):
    _return_url = "/payment/zlpay/return"
    _callback_url = "/payment/zlpay/callback"

    @http.route(
        _return_url,
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def zlpay_return_from_checkout(self, **data):
        """Handle redirection after payment checkout."""
        _logger.info("Handling redirection from ZaloPay.")
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
        _logger.info("Bắt đầu xử lý callback ZaloPay")
        result = {}
        try:
            cbdata = request.jsonrequest
            _logger.info("Dữ liệu callback nhận được: %s", cbdata)
            
            zlpay_provider = request.env['payment.provider'].sudo().search([('code', '=', 'zlpay')], limit=1)
            if not zlpay_provider:
                raise ValueError("Không tìm thấy nhà cung cấp ZaloPay")
            
            key2 = zlpay_provider.key2

            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            if mac != cbdata['mac']:
                _logger.warning("MAC không hợp lệ")
                result['return_code'] = -1
                result['return_message'] = 'MAC không hợp lệ'
            else:
                data_json = json.loads(cbdata['data'])
                app_trans_id = data_json['app_trans_id']
                _logger.info("Xác thực MAC thành công cho app_trans_id = %s", app_trans_id)
              
                tx = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
                if tx:
                    if data_json.get('status') == 1:  # Giả sử 1 là trạng thái thành công
                        tx._set_done()
                        _logger.info("Đã cập nhật trạng thái giao dịch thành công cho app_trans_id = %s", app_trans_id)
                    else:
                        tx._set_error("ZaloPay: Thanh toán không thành công")
                        _logger.warning("Thanh toán không thành công cho app_trans_id = %s", app_trans_id)
                    
                    result['return_code'] = 1
                    result['return_message'] = 'Xử lý thành công'
                else:
                    _logger.warning("Không tìm thấy giao dịch với app_trans_id = %s", app_trans_id)
                    result['return_code'] = 0
                    result['return_message'] = 'Không tìm thấy giao dịch'
        except Exception as e:
            _logger.exception("Xử lý callback ZaloPay thất bại: %s", str(e))
            result['return_code'] = 0  # ZaloPay server sẽ callback lại (tối đa 3 lần)
            result['return_message'] = 'Lỗi xử lý: ' + str(e)
        
        _logger.info("Kết thúc xử lý callback ZaloPay với kết quả: %s", result)
        return result
    