from enum import StrEnum

class QCStatus(StrEnum):
    PENDING = 'pending'
    PASSED = 'passed'
    FAILED = 'failed'

class ProductItemStatus(StrEnum):
    PENDING_QC = 'pending_qc'
    IN_STOCK = 'in_stock'
    RESERVED = 'reserved'
    SOLD = 'sold'
    RETURNED = 'returned'
    DAMAGED = 'damaged'
    LOST = 'lost'

class StockMovementType(StrEnum):
    IN = 'in'
    OUT = 'out'
    TRANSFER = 'transfer'
    ADJUST = 'adjust'
    QC_PASS = 'qc_pass'
    QC_FAIL = 'qc_fail'
    RESERVE = 'reserve'
    RELEASE = 'release'

class StockReservationStatus(StrEnum):
    ACTIVE = 'active'
    RELEASED = 'released'
    FULFILLED = 'fulfilled'

class OutboundDisposition(StrEnum):
    SALE = 'sale'
    DAMAGE = 'damage'
    LOSS = 'loss'
    RETURN = 'return'
    OTHER = 'other'
