from enum import StrEnum

class QCRecordResult(StrEnum):
    PASSED = 'passed'
    FAILED = 'failed'

class DefectSeverity(StrEnum):
    MINOR = 'minor'
    MAJOR = 'major'
    CRITICAL = 'critical'

class LabelType(StrEnum):
    QC = 'qc'
    WARRANTY = 'warranty'
