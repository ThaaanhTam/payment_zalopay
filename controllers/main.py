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
    def zlpay_callback(self, **data):
        _logger.info("ZaloPay callback received: %s", data)
        result = {}

        try:
            # Lấy dữ liệu JSON từ yêu cầu callback của ZaloPay
            cbdata = request.jsonrequest
            key2 = 'trMrHtvjo6myautxDUiAcYsVtaeQ8nhf'

            # Tính toán MAC
            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            # Kiểm tra tính hợp lệ của callback
            if mac != cbdata['mac']:
                # Callback không hợp lệ
                result['return_code'] = -1
                result['return_message'] = 'mac not equal'
            else:
                # Thanh toán thành công
                dataJson = json.loads(cbdata['data'])
                app_trans_id = dataJson['app_trans_id']
                _logger.info("Update order's status = success where app_trans_id = %s", app_trans_id)

                # Cập nhật trạng thái đơn hàng
                # Bạn có thể thay thế đoạn mã này với logic cập nhật thực tế của bạn
                request.env['payment.transaction'].sudo().search([('reference', '=', app_trans_id)]).write({
                    'state': 'done'
                })

                result['return_code'] = 1
                result['return_message'] = 'success'
        except Exception as e:
            _logger.error("ZaloPay callback processing failed: %s", e)
            result['return_code'] = 0  # ZaloPay server sẽ callback lại (tối đa 3 lần)
            result['error'] = str(e)

        # Thông báo kết quả cho ZaloPay server
        return request.make_response(json.dumps(result), headers={"Content-Type": "application/json"})
      