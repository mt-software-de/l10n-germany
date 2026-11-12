# Copyright 2026 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models

from .res_company import PRIVACY_NOTICE


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_de_eric_test = fields.Boolean(
        related="company_id.l10n_de_eric_test", readonly=False
    )
    l10n_de_eric_store_certificate = fields.Boolean(
        related="company_id.l10n_de_eric_store_certificate", readonly=False
    )
    l10n_de_eric_certificate = fields.Binary(
        related="company_id.l10n_de_eric_certificate", readonly=False
    )
    l10n_de_eric_certificate_name = fields.Char(
        related="company_id.l10n_de_eric_certificate_name", readonly=False
    )
    l10n_de_eric_pin = fields.Char(
        related="company_id.l10n_de_eric_pin", readonly=False
    )
    l10n_de_eric_privacy_notice = fields.Text(
        "ERiC Privacy Notice", default=PRIVACY_NOTICE, readonly=True
    )
    l10n_de_eric_privacy_notice_read = fields.Boolean(
        related="company_id.l10n_de_eric_privacy_notice_read", readonly=False
    )
