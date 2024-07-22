# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "ZALOPAY",
    "version": "1.0",
    "category": "Accounting/Payment Providers",
    "sequence": 0,
    "summary": "A Vietnam payment provider.",
    "description": " ",  # Non-empty string to avoid loading the README file.
    "author": "ThanhTam",
    "depends": ["base", "payment"],
    "data": [ # Do no change the order
        "views/payment_zlpay_view.xml",
        "views/payment_zlpay_template.xml",
        "data/payment_method_data.xml",
        "data/payment_provider_data.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}
