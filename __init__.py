# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
import logging

from odoo.addons.payment import setup_provider, reset_payment_provider

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    setup_provider(env, "zlpay")
    payment_zlpay = env["payment.provider"].search([("code", "=", "zlpay")], limit=1)
    payment_method_zlpay = env["payment.method"].search(
        [("code", "=", "zlpay")], limit=1
    )

    if payment_method_zlpay.id is not False:
        payment_zlpay.write(
            {
                "payment_method_ids": [(6, 0, [payment_method_zlpay.id])],
            }
        )


def uninstall_hook(env):
    reset_payment_provider(env, "zlpay")
