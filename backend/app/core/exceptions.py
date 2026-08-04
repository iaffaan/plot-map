

class UnchartedException(Exception):
    """Base exception class for all Uncharted backend errors."""
    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class AIParserError(UnchartedException):
    """Raised when the AI Parsing Layer fails to parse requirements or validate output."""

class InfeasibleRequestError(UnchartedException):
    """Raised when the requested floor plan dimensions are mathematically or legally impossible."""

class GeometryOverlapError(UnchartedException):
    """Raised when rooms or components overlap in the generated layout."""

class OptimizationSolverError(UnchartedException):
    """Raised when the MILP solver fails to find a valid solution under constraints."""

class TopologyValidationError(UnchartedException):
    """Raised when privacy, connectivity, or ventilation constraints are violated."""
