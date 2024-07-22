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
       

        _logger.info("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000: %s", data)
        result = {}

        try:
            cbdata = request.jsonrequest
            key2 = request.env['payment.provider'].search([('code', '=', 'zlpay')], limit=1).key2


            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            if mac != cbdata['mac']:
            
                result['return_code'] = -1
                result['return_message'] = 'mac not equal'
            else:
                # Successful payment
                dataJson = json.loads(cbdata['data'])
                app_trans_id = dataJson['app_trans_id']
                _logger.info("Update order's status = success where app_trans_id = %s", app_trans_id)

                # Update the order status here
                request.env['payment.transaction'].sudo().search([('reference', '=', app_trans_id)]).write({
                    'state': 'done'
                })

                result['return_code'] = 1
                result['return_message'] = 'success'
        except Exception as e:
            _logger.error("ZaloPay callback processing failed: %s", e)
            result['return_code'] = 0  # ZaloPay server will retry the callback (up to 3 times)
            result['error'] = str(e)

        # Respond to ZaloPay server
        return json.dumps(result)

    # @http.route(
    #     '/payment/zlpay/status/<string:app_trans_id>',
    #     type='http',
    #     auth='public',
    #     methods=['POST'],
    #     csrf=False,
    # )
    # def zlpay_status(self, app_trans_id):
        """Check the status of a transaction from ZaloPay."""

        config = {
            'app_id': '2554',  # Replace with your app_id
            'key1': 'sdngKKJmqEMzvh5QQcdD2A9XBSKUNaYn'  # Replace with your key1
        }

        params = {
            "app_id": config["app_id"],
            "app_trans_id": app_trans_id
        }

        # Create MAC to verify request
        data = "{}|{}|{}".format(config["app_id"], params["app_trans_id"], config["key1"])
        params["mac"] = hmac.new(config['key1'].encode(), data.encode(), hashlib.sha256).hexdigest()

        # Send request to ZaloPay
        try:
            response = urllib.request.urlopen(url="https://sb-openapi.zalopay.vn/v2/query", data=urllib.parse.urlencode(params).encode())
            result = json.loads(response.read())

            # Log the result
            _logger.info("ZaloPay query result: %s", result)
            
            return request.make_response(json.dumps(result), headers={"Content-Type": "application/json"})
        except Exception as e:
            _logger.error("Error while making request to ZaloPay: %s", e)
            return request.make_response(json.dumps({"error": str(e)}), headers={"Content-Type": "application/json"}, status=500)
