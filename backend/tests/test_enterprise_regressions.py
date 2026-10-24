from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.accounting.schemas import JournalLineCreate
from app.modules.quality.constants import QCRecordResult
from app.modules.quality.schemas import QCRecordCreate
from app.modules.warranty.urls import resolve_warranty_base


def test_local_warranty_base_uses_request_host_for_mobile_qr():
    assert resolve_warranty_base('http://127.0.0.1:5174/warranty', 'http://192.168.1.20:8000/') == 'http://192.168.1.20:8000/warranty'


def test_custom_warranty_domain_is_preserved():
    assert resolve_warranty_base('https://warranty.example.com/check', 'http://192.168.1.20:8000/') == 'https://warranty.example.com/check'


def test_scrap_qc_requires_waste_class():
    with pytest.raises(ValidationError):
        QCRecordCreate(item_id=1, result=QCRecordResult.FAILED, failure_action='scrap')


def test_rework_qc_does_not_keep_waste_class():
    row = QCRecordCreate(item_id=1, result=QCRecordResult.FAILED, failure_action='rework', waste_class='abnormal')
    assert row.waste_class is None


def test_journal_line_must_be_one_sided():
    with pytest.raises(ValidationError):
        JournalLineCreate(account_id=1, debit=Decimal('10'), credit=Decimal('10'))
    with pytest.raises(ValidationError):
        JournalLineCreate(account_id=1, debit=Decimal('0'), credit=Decimal('0'))
