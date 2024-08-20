import hashlib
import hmac
import logging
import json
import urllib.parse
from werkzeug.exceptions import Forbidden
from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request
from datetime import datetime, timedelta
import pytz


_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):
    _return_url = "/payment/zalopay/return"
    _callback_url = "/payment/zalopay/callback"
    _max_retry_count = 0
    

    @http.route('/payment/zalopay/status', type='http', auth='public', methods=['GET'], website=True)
    def query_zalopay_status(self, app_trans_id=None, **kw):
        if not app_trans_id:
            return request.render('payment_zalopay.zalopay_status_error', {
                'error_message': 'app_trans_id is required'
            })

        try:
            transaction = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
            if transaction:
                # Xử lý trạng thái giao dịch ở đây
                _logger.info("Giao dịch tìm thấy: ID = %s, app_trans_id = %s", transaction.id, transaction.app_trans_id)
                return request.render('payment_zalopay.zalopay_status_success', {
                    'transaction': transaction
                })
            else:
                _logger.info("Không tìm thấy giao dịch với app_trans_id = %s", app_trans_id)
                return request.render('payment_zalopay.zalopay_status_error', {
                    'error_message': f'Không tìm thấy giao dịch với app_trans_id = {app_trans_id}'
                })
        except Exception as e:
            _logger.error("Lỗi khi truy vấn trạng thái thanh toán ZaloPay cho app_trans_id %s: %s", app_trans_id, str(e))
            return request.render('payment_zalopay.zalopay_status_error', {
                'error_message': f'Lỗi khi truy vấn trạng thái thanh toán: {str(e)}'
            })
    @http.route(
        _return_url,
        type="http",
        methods=["GET"],
        auth="public",
        csrf=False,
    )
    def zalopay_return_from_checkout(self, **data):
        """Handle redirection after payment checkout."""
        _logger.info("Sau khi thanh toán sẽ vào đâyyyyyyyyyy")
        return request.redirect("/payment/status")

    @http.route(
        _callback_url,
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def zalopay_callback(self):
        """Xử lý callback từ ZaloPay."""
        result = {}
        logging.info("xử lý callback")
        try:
            raw_data = request.httprequest.get_data()
            cbdata = json.loads(raw_data)
            _logger.info("Dữ liệu callback nhận được:%s ",raw_data)
            _logger.info("Dữ liệu callback nhận được: %s", cbdata)
            _logger.info(raw_data)

            zalopay_provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
            key2 = zalopay_provider.key2

            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            # Kiểm tra callback hợp lệ (đến từ ZaloPay server)
            if mac != cbdata['mac']:
                # Callback không hợp lệ
                _logger.info("Không nhận được dữ liệu JSON từ ZaloPay")
                result['return_code'] = -1
                result['return_message'] = 'mac not equal'
            else:
                # Thanh toán thành công
                # Cập nhật trạng thái cho đơn hàng
                dataJson = json.loads(cbdata['data'])
                app_trans_id = dataJson['app_trans_id']
                amount = dataJson['amount']
                _logger.info("Cập nhật trạng thái đơn hàng = success cho app_trans_id = %s", app_trans_id)
              
                _logger.info("Giao dịch hiện có: ")
                all_transactions = request.env['payment.transaction'].sudo().search([])
                for tx in all_transactions:
                    _logger.info("Giao dịch hiện có: %s với app_trans_id: %s", tx.id, tx.app_trans_id)
                #  Tìm giao dịch tương ứng với app_trans_id
                tx = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
                if tx:
                    if int(tx.amount) == int(amount):
                        tx._set_done()
                        tx._reconcile_after_done()
                        # tx.sudo().write({'state': 'paid'})
                        _logger.info("Đã cập nhật trạng thái đơn hàng thành công cho app_trans_id = %s", app_trans_id)
                        result['return_code'] = 1
                        result['return_message'] = 'success'
                    else:
                        _logger.warning("Số tiền không khớp cho app_trans_id = %s", app_trans_id)
                        result['return_code'] = -1
                        result['return_message'] = 'amount not equal'
                else:
                    _logger.warning("Không tìm thấy giao dịch với app_trans_id = %s", app_trans_id)
                    result['return_code'] = -1
                    result['return_message'] = 'Transaction not found'
        except Exception as e:
            _logger.error("Xử lý callback ZaloPay thất bại: %s", e)
            result['return_code'] = 0  # ZaloPay server sẽ callback lại (tối đa 3 lần)
            result['e'] = str(e)
            tx = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
        if tx:
            tx.failed_callback_count = tx.failed_callback_count + 1 if hasattr(tx, 'failed_callback_count') else 1
            _logger.info(tx.failed_callback_count)
            if tx.failed_callback_count > 1:
                # Cộng thêm 15 phút vào next_check
                from datetime import datetime, timedelta
                tx.next_check = datetime.now(pytz.timezone("Etc/GMT-7")) + timedelta(minutes=1)
                _logger.info(f"Đã cập nhật next_check cho app_trans_id {app_trans_id} sau 3 lần thất bại")
        _logger.info("Kết thúc xử lý callback ZaloPay với kết quả: %s", result)
        # Thông báo kết quả cho ZaloPay server
        return request.make_response(json.dumps(result), headers={'Content-Type': 'application/json'})
    