# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
import logging

from odoo.addons.payment import setup_provider, reset_payment_provider
_logger = logging.getLogger(__name__)
def post_init_hook(env):
    setup_provider(env, "zalopay")
    payment_zalopay = env["payment.provider"].search([("code", "=", "zalopay")], limit=1)
    payment_method_zalopay = env["payment.method"].search(
        [("code", "=", "zalopay")], limit=1
    )

    if payment_method_zalopay.id is not False:
        payment_zalopay.write(
            {
                "payment_method_ids": [(6, 0, [payment_method_zalopay.id])],
            }
        )
def uninstall_hook(env):
    reset_payment_provider(env, "zalopay")
