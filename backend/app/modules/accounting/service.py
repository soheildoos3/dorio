from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.model import Account, AuditEvent, CostCenter, JournalEntry, JournalLine
from app.modules.accounting.schemas import InventoryImpairmentCreate, JournalCreate, JournalLineCreate, OverheadVarianceCreate
from app.modules.inventory_operations.numbers import next_document_number


DEFAULT_ACCOUNTS = [
    ("1000", "دارایی‌ها", "asset", None, False),
    ("1100", "صندوق", "asset", "1000", True),
    ("1110", "بانک", "asset", "1000", True),
    ("1200", "حساب‌های دریافتنی", "asset", "1000", True),
    ("1300", "موجودی مواد اولیه", "asset", "1000", True),
    ("1310", "کالای در جریان ساخت", "asset", "1000", True),
    ("1320", "موجودی کالای ساخته‌شده", "asset", "1000", True),
    ("1330", "موجودی قرنطینه", "asset", "1000", True),
    ("1340", "موجودی ضایعات", "asset", "1000", True),
    ("2000", "بدهی‌ها", "liability", None, False),
    ("2100", "حساب‌های پرداختنی تجاری", "liability", "2000", True),
    ("2110", "حقوق پرداختنی", "liability", "2000", True),
    ("2120", "پرداختنی خیاطان", "liability", "2000", False),
    ("3000", "سرمایه", "equity", None, True),
    ("4000", "درآمدها", "revenue", None, False),
    ("4100", "فروش", "revenue", "4000", True),
    ("5000", "بهای تمام‌شده و تولید", "expense", None, False),
    ("5100", "بهای تمام‌شده کالای فروش‌رفته", "expense", "5000", True),
    ("5200", "هزینه ضایعات غیرعادی", "expense", "5000", True),
    ("5300", "سربار ساخت واقعی", "expense", "5000", True),
    ("5310", "سربار جذب‌شده", "expense", "5000", True),
    ("5320", "انحراف سربار", "expense", "5000", True),
    ("6000", "هزینه‌های دوره", "expense", None, False),
    ("6100", "هزینه‌های اداری", "expense", "6000", True),
    ("6200", "هزینه‌های فروش", "expense", "6000", True),
    ("6300", "زیان کاهش ارزش موجودی", "expense", "6000", True),
]

DEFAULT_COST_CENTERS = [
    ("PROD", "خط تولید", "production"),
    ("RAW", "انبار مواد", "warehouse"),
    ("FG", "انبار محصول", "warehouse"),
    ("SALES", "فروش", "sales"),
    ("ADMIN", "اداری", "admin"),
]


class AccountingError(ValueError):
    pass


class AccountingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_defaults(self) -> None:
        existing = {x.code: x for x in (await self.session.scalars(select(Account))).all()}
        for code, name, account_type, parent_code, allow_posting in DEFAULT_ACCOUNTS:
            if code in existing:
                continue
            parent = existing.get(parent_code) if parent_code else None
            obj = Account(code=code, name=name, account_type=account_type, parent_id=parent.id if parent else None, allow_posting=allow_posting, is_system=True)
            self.session.add(obj)
            await self.session.flush()
            existing[code] = obj
        centers = {x.code for x in (await self.session.scalars(select(CostCenter))).all()}
        for code, name, center_type in DEFAULT_COST_CENTERS:
            if code not in centers:
                self.session.add(CostCenter(code=code, name=name, center_type=center_type))
        await self.session.flush()

    async def account_by_code(self, code: str) -> Account:
        await self.ensure_defaults()
        obj = await self.session.scalar(select(Account).where(Account.code == code))
        if not obj:
            raise AccountingError(f"حساب {code} پیدا نشد")
        return obj

    async def cost_center_by_code(self, code: str) -> CostCenter | None:
        await self.ensure_defaults()
        return await self.session.scalar(select(CostCenter).where(CostCenter.code == code))

    async def tailor_payable(self, tailor_user_id: int, tailor_name: str) -> Account:
        parent = await self.account_by_code("2120")
        code = f"2120-{tailor_user_id}"
        obj = await self.session.scalar(select(Account).where(Account.code == code))
        if obj is None:
            obj = Account(code=code, name=f"پرداختنی خیاط - {tailor_name}", account_type="liability", parent_id=parent.id, allow_posting=True, is_system=True)
            self.session.add(obj)
            await self.session.flush()
        return obj

    async def log_audit(self, *, user_id: int | None, action: str, entity_type: str, entity_id: str | int | None = None, source_ref: str | None = None, before_data: dict | None = None, after_data: dict | None = None) -> AuditEvent:
        event = AuditEvent(user_id=user_id, action=action, entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None, source_ref=source_ref, before_data=before_data, after_data=after_data)
        self.session.add(event)
        await self.session.flush()
        return event


    async def _validate_journal(self, payload: JournalCreate) -> tuple[Decimal, Decimal]:
        await self.ensure_defaults()
        account_ids = {line.account_id for line in payload.lines}
        accounts = list((await self.session.scalars(select(Account).where(Account.id.in_(account_ids)))).all())
        account_map = {x.id: x for x in accounts}
        if len(account_map) != len(account_ids):
            raise AccountingError("یکی از حساب‌های سند معتبر نیست")
        center_ids = {line.cost_center_id for line in payload.lines if line.cost_center_id is not None}
        if center_ids:
            centers = list((await self.session.scalars(select(CostCenter).where(CostCenter.id.in_(center_ids)))).all())
            if len(centers) != len(center_ids):
                raise AccountingError("یکی از مراکز هزینه سند معتبر نیست")
        for line in payload.lines:
            account = account_map[line.account_id]
            if not account.is_active or not account.allow_posting:
                raise AccountingError(f"حساب «{account.name}» قابل ثبت مستقیم نیست")
        debit = sum((Decimal(line.debit) for line in payload.lines), Decimal("0"))
        credit = sum((Decimal(line.credit) for line in payload.lines), Decimal("0"))
        if debit <= 0 or debit != credit:
            raise AccountingError("جمع بدهکار و بستانکار سند باید برابر و بزرگ‌تر از صفر باشد")
        return debit, credit

    async def create_draft(self, payload: JournalCreate, user_id: int) -> JournalEntry:
        debit, credit = await self._validate_journal(payload)
        number = await next_document_number(self.session, "JE")
        entry = JournalEntry(
            number=number, entry_date=payload.entry_date, description=payload.description,
            source_type=payload.source_type, source_id=payload.source_id, source_ref=payload.source_ref,
            status="draft", created_by=user_id, posted_by=None, posted_at=None,
        )
        self.session.add(entry)
        await self.session.flush()
        for i, line in enumerate(payload.lines, start=1):
            self.session.add(JournalLine(entry_id=entry.id, line_no=i, **line.model_dump()))
        await self.log_audit(user_id=user_id, action="journal.draft", entity_type="journal_entry", entity_id=entry.id, source_ref=entry.number, after_data={"number": entry.number, "debit": str(debit), "credit": str(credit)})
        try:
            await self.session.commit(); await self.session.refresh(entry)
        except IntegrityError as exc:
            await self.session.rollback(); raise AccountingError("ثبت پیش‌نویس سند به علت تداخل شماره انجام نشد") from exc
        return entry

    async def finalize(self, entry_id: int, user_id: int) -> JournalEntry:
        entry = await self.session.scalar(select(JournalEntry).where(JournalEntry.id == entry_id).with_for_update())
        if not entry:
            raise AccountingError("سند پیدا نشد")
        if entry.status != "draft":
            raise AccountingError("فقط سند پیش‌نویس قابل قطعی‌کردن است")
        if entry.created_by == user_id:
            raise AccountingError("ثبت‌کننده سند نمی‌تواند همان سند را قطعی کند")
        await self.session.refresh(entry, ["lines"])
        # Re-check balance at approval time as a second control gate.
        payload = JournalCreate(
            entry_date=entry.entry_date, description=entry.description, source_type=entry.source_type,
            source_id=entry.source_id, source_ref=entry.source_ref,
            lines=[JournalLineCreate(account_id=x.account_id, cost_center_id=x.cost_center_id, debit=x.debit, credit=x.credit, memo=x.memo) for x in entry.lines],
        )
        debit, credit = await self._validate_journal(payload)
        entry.status = "posted"
        entry.posted_by = user_id
        entry.posted_at = datetime.now(timezone.utc)
        await self.log_audit(user_id=user_id, action="journal.post", entity_type="journal_entry", entity_id=entry.id, source_ref=entry.number, after_data={"number": entry.number, "debit": str(debit), "credit": str(credit)})
        await self.session.commit(); await self.session.refresh(entry)
        return entry

    async def post(self, payload: JournalCreate, user_id: int, *, commit: bool = True) -> JournalEntry:
        debit, credit = await self._validate_journal(payload)
        number = await next_document_number(self.session, "JE")
        entry = JournalEntry(number=number, entry_date=payload.entry_date, description=payload.description, source_type=payload.source_type, source_id=payload.source_id, source_ref=payload.source_ref, status="posted", created_by=user_id, posted_by=user_id, posted_at=datetime.now(timezone.utc))
        self.session.add(entry)
        await self.session.flush()
        for i, line in enumerate(payload.lines, start=1):
            self.session.add(JournalLine(entry_id=entry.id, line_no=i, **line.model_dump()))
        await self.log_audit(user_id=user_id, action="journal.post", entity_type="journal_entry", entity_id=entry.id, source_ref=entry.number, after_data={"number": entry.number, "debit": str(debit), "credit": str(credit)})
        if commit:
            try:
                await self.session.commit()
                await self.session.refresh(entry)
            except IntegrityError as exc:
                await self.session.rollback()
                raise AccountingError("ثبت سند به علت تداخل شماره یا داده مرجع انجام نشد") from exc
        else:
            await self.session.flush()
        return entry

    async def auto_post(self, *, user_id: int, description: str, source_type: str, source_id: int | None, source_ref: str | None, debit_code: str, credit_code: str, amount: Decimal, cost_center_code: str | None = None, commit: bool = False) -> JournalEntry | None:
        amount = Decimal(amount).quantize(Decimal("0.01"))
        if amount <= 0:
            return None
        debit = await self.account_by_code(debit_code)
        credit = await self.account_by_code(credit_code)
        center = await self.cost_center_by_code(cost_center_code) if cost_center_code else None
        payload = JournalCreate(
            entry_date=date.today(),
            description=description,
            source_type=source_type,
            source_id=source_id,
            source_ref=source_ref,
            lines=[
                JournalLineCreate(account_id=debit.id, cost_center_id=center.id if center else None, debit=amount),
                JournalLineCreate(account_id=credit.id, cost_center_id=center.id if center else None, credit=amount),
            ],
        )
        return await self.post(payload, user_id, commit=commit)

    async def create_inventory_impairment_draft(self, payload: InventoryImpairmentCreate, user_id: int) -> JournalEntry:
        loss = await self.account_by_code("6300")
        inventory = await self.account_by_code(payload.inventory_account_code)
        center = await self.cost_center_by_code("FG" if payload.inventory_account_code == "1320" else "RAW")
        amount = Decimal(payload.amount).quantize(Decimal("0.01"))
        journal = JournalCreate(
            entry_date=date.today(),
            description=payload.description or f"کاهش ارزش موجودی تا خالص ارزش فروش - {payload.reference}",
            source_type="inventory_impairment",
            source_ref=payload.reference,
            lines=[
                JournalLineCreate(account_id=loss.id, cost_center_id=center.id if center else None, debit=amount, memo="زیان کاهش ارزش"),
                JournalLineCreate(account_id=inventory.id, cost_center_id=center.id if center else None, credit=amount, memo="کاهش ارزش موجودی"),
            ],
        )
        return await self.create_draft(journal, user_id)

    async def create_overhead_variance_draft(self, payload: OverheadVarianceCreate, user_id: int) -> JournalEntry:
        actual = Decimal(payload.actual_overhead).quantize(Decimal("0.01"))
        absorbed = Decimal(payload.absorbed_overhead).quantize(Decimal("0.01"))
        if actual == 0 and absorbed == 0:
            raise AccountingError("مبلغ سربار واقعی و جذب‌شده نمی‌تواند هر دو صفر باشد")
        actual_acc = await self.account_by_code("5300")
        absorbed_acc = await self.account_by_code("5310")
        cogs_acc = await self.account_by_code("5100")
        fg_acc = await self.account_by_code("1320")
        center = await self.cost_center_by_code("FG")
        lines: list[JournalLineCreate] = []
        if absorbed > 0:
            lines.append(JournalLineCreate(account_id=absorbed_acc.id, cost_center_id=center.id if center else None, debit=absorbed, memo="بستن سربار جذب‌شده"))
        if actual > 0:
            lines.append(JournalLineCreate(account_id=actual_acc.id, cost_center_id=center.id if center else None, credit=actual, memo="بستن سربار واقعی"))
        variance = actual - absorbed
        if variance != 0:
            cogs_share = (abs(variance) * Decimal(payload.cogs_share_percent) / Decimal("100")).quantize(Decimal("0.01"))
            fg_share = abs(variance) - cogs_share
            if variance > 0:
                if cogs_share > 0:
                    lines.append(JournalLineCreate(account_id=cogs_acc.id, cost_center_id=center.id if center else None, debit=cogs_share, memo="انحراف سربار - سهم بهای فروش"))
                if fg_share > 0:
                    lines.append(JournalLineCreate(account_id=fg_acc.id, cost_center_id=center.id if center else None, debit=fg_share, memo="انحراف سربار - سهم موجودی پایان دوره"))
            else:
                if cogs_share > 0:
                    lines.append(JournalLineCreate(account_id=cogs_acc.id, cost_center_id=center.id if center else None, credit=cogs_share, memo="برگشت اضافه‌جذب سربار - بهای فروش"))
                if fg_share > 0:
                    lines.append(JournalLineCreate(account_id=fg_acc.id, cost_center_id=center.id if center else None, credit=fg_share, memo="برگشت اضافه‌جذب سربار - موجودی پایان دوره"))
        journal = JournalCreate(
            entry_date=date.today(),
            description=payload.description or f"تعدیل انحراف سربار - {payload.reference}",
            source_type="overhead_variance_adjustment",
            source_ref=payload.reference,
            lines=lines,
        )
        return await self.create_draft(journal, user_id)

    async def reverse(self, entry_id: int, user_id: int) -> JournalEntry:
        original = await self.session.get(JournalEntry, entry_id)
        if not original:
            raise AccountingError("سند پیدا نشد")
        if original.status != "posted" or original.reversed_by_entry_id is not None:
            raise AccountingError("این سند قبلاً برگشت خورده یا قابل برگشت نیست")
        await self.session.refresh(original, ["lines"])
        payload = JournalCreate(
            entry_date=date.today(),
            description=f"برگشت سند {original.number} - {original.description}",
            source_type="journal_reversal",
            source_id=original.id,
            source_ref=original.number,
            lines=[JournalLineCreate(account_id=x.account_id, cost_center_id=x.cost_center_id, debit=x.credit, credit=x.debit, memo=f"برگشت ردیف {x.line_no}") for x in original.lines],
        )
        reversal = await self.post(payload, user_id, commit=False)
        original.status = "reversed"
        original.reversed_by_entry_id = reversal.id
        await self.log_audit(user_id=user_id, action="journal.reverse", entity_type="journal_entry", entity_id=original.id, source_ref=original.number, after_data={"reversal": reversal.number})
        await self.session.commit()
        await self.session.refresh(reversal)
        return reversal
