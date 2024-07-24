import logging

import hmac
import hashlib
import urllib.parse

from odoo import _, api, fields, models
from odoo.addons.payment_zlpay import const

_logger = logging.getLogger(__name__)


class PaymentProviderZaloPay(models.Model):
    _inherit = "payment.provider"


   
    code = fields.Selection(
        selection_add=[("zlpay", "ZLPay")], ondelete={"zlpay": "set default"}
    )

    
    key1 = fields.Char(
        string="key1", required_if_provider="zlay"
    )
    key2 = fields.Char(
        string="key2", required_if_provider="zlpay"
    )

    appid = fields.Char(
        string="appid", required_if_provider="zlpay"
    )

    app_user = fields.Char(
        string="App User",
        default=lambda self: self.env.company.name
    )
    @api.model
    def _get_compatible_providers(
        self, *args, currency_id=None, is_validation=False, **kwargs
    ):
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, is_validation=is_validation, **kwargs
        )

        currency = self.env["res.currency"].browse(currency_id).exists()
        if (
            currency and currency.name not in const.SUPPORTED_CURRENCIES
        ) or is_validation:
            providers = providers.filtered(lambda p: p.code != "zlpay")

        return providers

    def _get_supported_currencies(self):

        supported_currencies = super()._get_supported_currencies()
        if self.code == "zlpay":
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies
    
    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != "zlpay":
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES
        
    
    