import logging

import hmac
import hashlib
import urllib.parse

from odoo import _, api, fields, models
from odoo.addons.payment_zalopay import const

_logger = logging.getLogger(__name__)


class PaymentProviderZaloPay(models.Model):
    _inherit = "payment.provider"


   
    code = fields.Selection(
        selection_add=[("zalopay", "Zalopay")], ondelete={"zalopay": "set default"}
    )

    
    key1 = fields.Char(
        string="key1", required_if_provider="zalopay"
    )
    key2 = fields.Char(
        string="key2", required_if_provider="zalopay"
    )

    appid = fields.Char(
        string="appid", required_if_provider="zalopay"
    )

    app_user = fields.Char(
        string="App User",
        default=lambda self: self.env.company.name
    )
 
        
    
    