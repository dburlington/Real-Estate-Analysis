"""Data models for Real Estate OM Analysis"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PropertyType(Enum):
    MULTIFAMILY = "multifamily"
    OFFICE = "office"
    RETAIL = "retail"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"
    HOTEL = "hotel"
    SELF_STORAGE = "self_storage"
    SENIOR_HOUSING = "senior_housing"
    STUDENT_HOUSING = "student_housing"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PropertyDetails:
    """Core property information extracted from OM"""
    name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    property_type: PropertyType = PropertyType.UNKNOWN
    year_built: Optional[int] = None
    total_units: Optional[int] = None
    total_sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    parking_spaces: Optional[int] = None
    amenities: list[str] = field(default_factory=list)


@dataclass
class FinancialMetrics:
    """Financial metrics from the OM"""
    asking_price: Optional[float] = None
    price_per_unit: Optional[float] = None
    price_per_sqft: Optional[float] = None
    current_noi: Optional[float] = None
    proforma_noi: Optional[float] = None
    current_cap_rate: Optional[float] = None
    proforma_cap_rate: Optional[float] = None
    current_occupancy: Optional[float] = None
    average_rent: Optional[float] = None
    market_rent: Optional[float] = None
    gross_potential_income: Optional[float] = None
    effective_gross_income: Optional[float] = None
    operating_expenses: Optional[float] = None
    expense_ratio: Optional[float] = None
    debt_service: Optional[float] = None
    cash_on_cash_return: Optional[float] = None
    irr_projected: Optional[float] = None
    equity_multiple: Optional[float] = None


@dataclass
class DealTerms:
    """Deal structure and terms"""
    loan_amount: Optional[float] = None
    loan_to_value: Optional[float] = None
    interest_rate: Optional[float] = None
    loan_term_years: Optional[int] = None
    amortization_years: Optional[int] = None
    loan_type: str = ""  # Fixed, Variable, Bridge, etc.
    prepayment_penalty: str = ""
    assumable_debt: bool = False
    required_equity: Optional[float] = None
    minimum_investment: Optional[float] = None
    preferred_return: Optional[float] = None
    profit_split: str = ""  # e.g., "70/30"
    hold_period_years: Optional[int] = None


@dataclass
class MarketData:
    """External market data for the property location"""
    market_rent_psf: Optional[float] = None
    market_cap_rate: Optional[float] = None
    market_vacancy_rate: Optional[float] = None
    rent_growth_1yr: Optional[float] = None
    rent_growth_5yr: Optional[float] = None
    population_growth: Optional[float] = None
    job_growth: Optional[float] = None
    median_household_income: Optional[float] = None
    unemployment_rate: Optional[float] = None
    crime_index: Optional[float] = None
    walk_score: Optional[int] = None
    transit_score: Optional[int] = None
    school_rating: Optional[float] = None
    major_employers: list[str] = field(default_factory=list)
    new_supply_units: Optional[int] = None
    absorption_rate: Optional[float] = None


@dataclass
class Finding:
    """A single analysis finding (pro, con, or red flag)"""
    category: str
    description: str
    details: str
    risk_level: RiskLevel
    metric_name: Optional[str] = None
    actual_value: Optional[str] = None
    benchmark_value: Optional[str] = None


@dataclass
class OMAnalysis:
    """Complete analysis results"""
    property: PropertyDetails
    financials: FinancialMetrics
    deal_terms: DealTerms
    market_data: MarketData
    pros: list[Finding] = field(default_factory=list)
    cons: list[Finding] = field(default_factory=list)
    red_flags: list[Finding] = field(default_factory=list)
    overall_score: Optional[float] = None
    recommendation: str = ""
    raw_text: str = ""
