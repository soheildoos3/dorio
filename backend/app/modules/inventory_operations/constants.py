from enum import StrEnum

class StockTransferStatus(StrEnum):
    PENDING = 'pending'
    IN_TRANSIT = 'in_transit'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class StockAdjustmentType(StrEnum):
    INCREASE = 'increase'
    DECREASE = 'decrease'

class StockAdjustmentReason(StrEnum):
    CYCLE_COUNT = 'cycle_count'
    DAMAGE = 'damage'
    LOSS = 'loss'
    RETURN = 'return'
    CORRECTION = 'correction'
    OTHER = 'other'

class CycleCountStatus(StrEnum):
    DRAFT = 'draft'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class CycleCountLineStatus(StrEnum):
    PENDING = 'pending'
    COUNTED = 'counted'
    ADJUSTED = 'adjusted'
