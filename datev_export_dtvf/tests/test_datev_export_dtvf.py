# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import datetime
import io
import unittest
import zipfile
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, can_import

from ..models.datev_export_dtvf import DOCUMENT_XML_NAMESPACE

DATEV_EXPORT_MODULE = "odoo.addons.datev_export_dtvf.models.datev_export_dtvf"


class TestDatevExportDtvf(TransactionCase):
    def setUp(self):
        super().setUp()
        self.range = self.env["date.range"].create(
            {
                "name": "testrange",
                "type_id": self.env["date.range.type"]
                .create(
                    {
                        "name": "testtype",
                    }
                )
                .id,
                "date_start": datetime.date.today(),
                "date_end": datetime.date.today(),
            }
        )
        with Form(self.env["datev_export_dtvf.export"]) as WizardForm:
            WizardForm.fiscalyear_id = self.range
            WizardForm.period_ids.add(self.range)
            self.wizard = WizardForm.save()
        self.env.user.company_id.write(
            {
                "datev_consultant_number": "4242424",
                "datev_client_number": "42424",
                "datev_account_code_length": 4,
            }
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Testjournal",
                "type": "sale",
                "code": "DTV",
            }
        )
        self.account1 = self.env["account.account"].create(
            {
                "name": "Revenue",
                "code": "424242",
                "account_type": "income",
            }
        )
        self.account2 = self.env["account.account"].create(
            {
                "name": "Receivable",
                "code": "424243",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        self.customer = self.env["res.partner"].search(
            [("is_company", "=", True)],
            limit=1,
        )
        self.move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account1.id,
                            "credit": 42,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account2.id,
                            "debit": 42,
                            "partner_id": self.customer.id,
                        },
                    ),
                ],
            }
        )

    def test_validation(self):
        """Test that we validate our input data"""
        self.env.user.company_id.write(
            {
                "datev_consultant_number": None,
            }
        )
        with self.assertRaises(ValidationError):
            self.wizard.action_generate()

    def test_happy_flow(self):
        """Test generation works as expected"""
        self.wizard.name = "Hello World"
        self.move.action_post()
        self.wizard.action_generate()
        self.assertEqual(self.wizard.file_name, "Hello_World.zip")
        zip_buffer = io.BytesIO(base64.b64decode(self.wizard.file_data))
        self.assertTrue(zipfile.is_zipfile(zip_buffer))
        with zipfile.ZipFile(zip_buffer) as zip_file:
            files = zip_file.namelist()
            partners = "EXTF_DebKred_Stamm.csv"
            self.assertIn(partners, files)
            self.assertIn(
                self.customer.name,
                zip_file.open(partners).read().decode("utf8"),
            )
        self.wizard.action_draft()
        self.assertEqual(self.wizard.state, "draft")

    def _attach_to_move(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "raw": b"%PDF-1.4 test",
                "res_model": "account.move",
                "res_id": self.move.id,
            }
        )
        self.move.message_main_attachment_id = attachment

    def _get_booking_row(self):
        zip_buffer = io.BytesIO(base64.b64decode(self.wizard.file_data))
        with zipfile.ZipFile(zip_buffer) as zip_file:
            file_name = next(
                f for f in zip_file.namelist() if f.startswith("EXTF_Buchungsstapel")
            )
            rows = zip_file.read(file_name).decode("utf8").splitlines()
        return rows[2]

    def test_attachments(self):
        """Test the bookings link to the exported attachments by the same id"""
        self._attach_to_move()
        self.move.action_post()
        self.wizard.export_attachments = True
        self.wizard.journal_ids = self.journal
        self.wizard.name = "Hello World"
        self.wizard.action_generate()
        self.assertEqual(
            self.wizard.attachment_file_name, "Hello_World_attachments.zip"
        )
        guid = self.wizard._get_attachment_guid(self.move)
        self.assertIn(f'"BEDI ""{guid}"""', self._get_booking_row())

        zip_buffer = io.BytesIO(base64.b64decode(self.wizard.attachment_file_data))
        with zipfile.ZipFile(zip_buffer) as zip_file:
            file_name = self.wizard._get_attachment_filename(self.move)
            self.assertEqual(set(zip_file.namelist()), {file_name, "document.xml"})
            self.assertTrue(file_name.endswith(f"_{self.move.id}.pdf"))
            self.assertEqual(zip_file.read(file_name), b"%PDF-1.4 test")
            root = etree.fromstring(zip_file.read("document.xml"))
        namespaces = {"d": DOCUMENT_XML_NAMESPACE}
        document = root.find("d:content/d:document", namespaces)
        self.assertEqual(document.get("guid"), guid)
        self.assertEqual(document.get("processID"), "1")
        self.assertIsNone(document.get("type"), "An entry is no invoice")
        self.assertEqual(
            document.find("d:extension", namespaces).get("name"), file_name
        )

    def test_attachments_document_type(self):
        """Test incoming and outgoing invoices are declared as such"""
        self._attach_to_move()
        for move_type, expected in (("out_invoice", "2"), ("in_invoice", "1")):
            self.move.move_type = move_type
            root = etree.fromstring(self.wizard._get_document_xml(self.move))
            document = root.find("d:content/d:document", {"d": DOCUMENT_XML_NAMESPACE})
            self.assertEqual(document.get("type"), expected)

    def test_attachments_inactive(self):
        """Test attachments aren't exported unless requested"""
        self._attach_to_move()
        self.move.action_post()
        self.wizard.journal_ids = self.journal
        self.wizard.action_generate()
        self.assertNotIn("BEDI", self._get_booking_row())
        self.assertFalse(self.wizard.attachment_file_data)

    def test_attachments_none_available(self):
        """Test a move without attachment has no link, and we create no archive"""
        self.move.action_post()
        self.wizard.export_attachments = True
        self.wizard.journal_ids = self.journal
        self.wizard.action_generate()
        self.assertNotIn("BEDI", self._get_booking_row())
        self.assertFalse(self.wizard.attachment_file_data)

    def test_attachments_limit(self):
        """Test we refuse an archive DATEV wouldn't accept"""
        self._attach_to_move()
        self.move.action_post()
        self.wizard.export_attachments = True
        self.wizard.journal_ids = self.journal
        with (
            patch(f"{DATEV_EXPORT_MODULE}.DOCUMENT_XML_MAX_DOCUMENTS", 0),
            self.assertRaises(UserError),
        ):
            self.wizard.action_generate()

    def test_nonautomatic_flag(self):
        """Test setting BU-Schlussel 40 works as it should"""
        self.account2.datev_export_nonautomatic = True
        self.move.action_post()
        self.wizard.journal_ids = self.journal
        self.wizard.action_generate()
        zip_buffer = io.BytesIO(base64.b64decode(self.wizard.file_data))
        with zipfile.ZipFile(zip_buffer) as zip_file:
            move_line_file_name = [
                f for f in zip_file.namelist() if f.startswith("EXTF_Buchungsstapel")
            ][0]
            with zip_file.open(move_line_file_name) as move_line_file:
                move_line = move_line_file.readlines()[2].decode("utf8")
                self.assertIn('"40"', move_line)

    def test_move_line_without_account(self):
        """
        Test that non-accounting (display_type!=False) lines don't crash the export
        """
        self.move.write(
            {
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_note",
                            "name": "This should not crash the export",
                        },
                    )
                ],
            }
        )
        self.move.action_post()
        self.wizard.action_generate()

    def test_partner_numbering_sequence(self):
        """Test datev_partner_numbering = sequence"""
        self.wizard.company_id.datev_partner_numbering = "sequence"
        self.wizard.company_id.datev_customer_sequence_id = self.env[
            "ir.sequence"
        ].create(
            {
                "name": "DATEV customer sequence",
            }
        )
        self.wizard.company_id.datev_supplier_sequence_id = self.env[
            "ir.sequence"
        ].create(
            {
                "name": "DATEV supplier sequence",
            }
        )
        self.move.line_ids.write({"partner_id": self.customer.id})
        self.assertFalse(self.customer.l10n_de_datev_export_identifier_customer)
        self.assertFalse(self.customer.l10n_de_datev_export_identifier_supplier)
        self.move.action_post()
        self.wizard.action_generate()
        self.assertTrue(self.customer.l10n_de_datev_export_identifier_customer)

    @unittest.skipUnless(
        can_import("odoo.addons.l10n_de_datev_reports"),
        "l10n_de_datev_reports is not installed, not testing it",
    )
    def test_ee(self):
        """Test datev_partner_numbering = ee"""
        self.wizard.company_id.datev_partner_numbering = "ee"
        self.move.line_ids.write({"partner_id": self.customer.id})
        self.customer.l10n_de_datev_identifier_customer = "424242"
        self.move.action_post()
        self.wizard.action_generate()

    def test_cron(self):
        """Test the cronjob"""
        last_month = self.env["date.range"].create(
            {
                "name": "month range",
                "type_id": self.env["date.range.type"]
                .create(
                    {
                        "name": "test month type",
                    }
                )
                .id,
                "date_start": datetime.date.today() - relativedelta(months=1, day=1),
                "date_end": datetime.date.today()
                - relativedelta(months=1, day=1)
                + relativedelta(months=1, days=-1),
            }
        )
        self.env["date.range"].create(
            {
                "name": "year range",
                "type_id": self.env["date.range.type"]
                .create(
                    {
                        "name": "test year type",
                    }
                )
                .id,
                "date_start": last_month.date_start + relativedelta(month=1, day=1),
                "date_end": last_month.date_start + relativedelta(month=12, day=31),
            }
        )
        cronjob = self.env.ref("datev_export_dtvf.cron_export")

        mails_before = self.env["mail.mail"].search([])
        cronjob.ir_actions_server_id.run()
        new_mail = self.env["mail.mail"].search([]) - mails_before
        self.assertTrue(new_mail)
