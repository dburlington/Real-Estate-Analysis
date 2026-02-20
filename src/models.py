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
    num_buildings: Optional[int] = None
    num_tenants: Optional[int] = None
    walt_years: Optional[float] = None  # Weighted Average Lease Term
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
class SponsorFees:
    """Sponsor/GP fee structure"""
    # Upfront fees
    acquisition_fee: Optional[float] = None  # % of purchase price
    acquisition_fee_flat: Optional[float] = None  # Flat dollar amount
    financing_fee: Optional[float] = None  # % of loan amount

    # Ongoing fees
    asset_management_fee: Optional[float] = None  # % of EGI or equity annually
    property_management_fee: Optional[float] = None  # % of EGI
    construction_management_fee: Optional[float] = None  # % of capex/renovation budget

    # Exit fees
    disposition_fee: Optional[float] = None  # % of sale price
    refinance_fee: Optional[float] = None  # % of new loan amount

    # Promote/Carried Interest - structured data
    promote_tier_1_pct: Optional[float] = None      # GP promote % (e.g., 0.20 for 20%)
    promote_tier_1_hurdle: Optional[float] = None   # Hurdle rate (e.g., 0.08 for 8% IRR)
    promote_tier_1_label: str = ""                  # Raw text, e.g. "20% above 8% IRR"
    promote_tier_2_pct: Optional[float] = None      # Second tier promote %
    promote_tier_2_hurdle: Optional[float] = None   # Second tier hurdle
    promote_tier_2_label: str = ""                  # Raw text

    # Other fees
    investor_servicing_fee: Optional[float] = None  # Annual flat or %
    reporting_fee: Optional[float] = None
    other_fees: list[tuple[str, float]] = field(default_factory=list)  # (name, amount/%)

    # Calculated totals
    total_upfront_fees_pct: Optional[float] = None
    total_annual_fees_pct: Optional[float] = None
    estimated_total_fees_over_hold: Optional[float] = None


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
class NewsItem:
    """A news article or media mention"""
    headline: str
    source: str
    date: str
    summary: str
    url: str = ""
    sentiment: str = ""  # positive, negative, neutral


@dataclass
class EconomicIndicator:
    """Government/economic data point"""
    name: str
    value: float
    unit: str  # %, $, count, etc.
    period: str  # e.g., "Q4 2025", "Dec 2025"
    source: str
    trend: str = ""  # up, down, stable
    context: str = ""  # How this compares to national/historical


@dataclass
class AnalystInsight:
    """Professional analyst report or forecast"""
    source: str  # e.g., "CBRE", "JLL", "Marcus & Millichap"
    title: str
    date: str
    key_finding: str
    forecast: str = ""
    relevance: str = ""  # Why this matters for the deal


@dataclass
class ExternalContext:
    """Aggregated external data for investment context"""
    # Recent news about the market/location
    market_news: list[NewsItem] = field(default_factory=list)
    property_news: list[NewsItem] = field(default_factory=list)

    # Government/economic data
    economic_indicators: list[EconomicIndicator] = field(default_factory=list)

    # Analyst reports and forecasts
    analyst_insights: list[AnalystInsight] = field(default_factory=list)

    # Supply/demand dynamics
    supply_pipeline: dict = field(default_factory=dict)
    recent_sales_comps: list[dict] = field(default_factory=list)

    # Risk factors from external sources
    regulatory_risks: list[str] = field(default_factory=list)
    environmental_notes: list[str] = field(default_factory=list)

    # Data freshness
    last_updated: str = ""
    data_sources_used: list[str] = field(default_factory=list)


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
    fees: SponsorFees = field(default_factory=SponsorFees)
    external_context: ExternalContext = field(default_factory=ExternalContext)
    pros: list[Finding] = field(default_factory=list)
    cons: list[Finding] = field(default_factory=list)
    red_flags: list[Finding] = field(default_factory=list)
    overall_score: Optional[float] = None
    recommendation: str = ""
    raw_text: str = ""
