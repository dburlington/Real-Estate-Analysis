"""Deal Analyzer - Identifies pros, cons, and red flags in real estate deals"""

from datetime import datetime
from typing import Optional
from .models import (
    OMAnalysis, Finding, RiskLevel, PropertyType, MarketData
)
from .market_data import MarketDataFetcher


class DealAnalyzer:
    """Analyzes real estate deals for pros, cons, and red flags"""

    # Benchmark thresholds
    THRESHOLDS = {
        # Cap rate thresholds
        'cap_rate_low': 0.04,  # Below 4% is very aggressive
        'cap_rate_high': 0.08,  # Above 8% may indicate risk

        # Occupancy thresholds
        'occupancy_excellent': 0.95,
        'occupancy_good': 0.90,
        'occupancy_concern': 0.85,
        'occupancy_red_flag': 0.80,

        # Expense ratio thresholds
        'expense_ratio_excellent': 0.35,
        'expense_ratio_good': 0.45,
        'expense_ratio_high': 0.55,
        'expense_ratio_red_flag': 0.65,

        # Rent premium/discount thresholds
        'rent_premium_concern': 0.10,  # 10% above market
        'rent_discount_opportunity': -0.05,  # 5% below market

        # Age thresholds
        'age_new': 10,
        'age_value_add': 20,
        'age_concern': 40,
        'age_red_flag': 50,

        # LTV thresholds
        'ltv_conservative': 0.60,
        'ltv_moderate': 0.70,
        'ltv_aggressive': 0.75,
        'ltv_red_flag': 0.80,

        # Interest rate vs market
        'rate_spread_good': 0.005,  # 50 bps below market
        'rate_spread_high': 0.01,  # 100 bps above market

        # Return thresholds
        'irr_excellent': 0.18,
        'irr_good': 0.15,
        'irr_minimum': 0.12,
        'coc_good': 0.08,
        'coc_minimum': 0.05,

        # Price per unit by market tier
        'ppu_gateway': 350000,  # NYC, SF, LA
        'ppu_primary': 250000,  # Denver, Seattle, Miami
        'ppu_secondary': 175000,  # Austin, Nashville, Charlotte
        'ppu_tertiary': 125000,  # Midwest, smaller markets
    }

    # Current market interest rate benchmark
    CURRENT_MARKET_RATE = 0.065  # 6.5% as of late 2024

    def __init__(self, market_data_fetcher: Optional[MarketDataFetcher] = None):
        self.market_fetcher = market_data_fetcher or MarketDataFetcher()

    def analyze(self, om_analysis: OMAnalysis) -> OMAnalysis:
        """Perform comprehensive deal analysis"""
        # Fetch market data if we have location info
        if om_analysis.property.city and om_analysis.property.state:
            om_analysis.market_data = self.market_fetcher.fetch_market_data(
                om_analysis.property.city,
                om_analysis.property.state,
                om_analysis.property.zip_code or "",
                om_analysis.property.property_type
            )

        # Run all analysis modules
        self._analyze_cap_rate(om_analysis)
        self._analyze_occupancy(om_analysis)
        self._analyze_rent_levels(om_analysis)
        self._analyze_expenses(om_analysis)
        self._analyze_property_condition(om_analysis)
        self._analyze_financing(om_analysis)
        self._analyze_returns(om_analysis)
        self._analyze_deal_structure(om_analysis)
        self._analyze_market_conditions(om_analysis)
        self._analyze_value_add_potential(om_analysis)

        # Calculate overall score and recommendation
        self._calculate_overall_score(om_analysis)

        return om_analysis

    def _analyze_cap_rate(self, analysis: OMAnalysis):
        """Analyze cap rate relative to market"""
        fin = analysis.financials
        market = analysis.market_data

        if not fin.current_cap_rate:
            return

        cap_rate = fin.current_cap_rate
        market_cap = market.market_cap_rate or 0.055

        spread = cap_rate - market_cap

        if spread > 0.015:  # 150+ bps above market
            analysis.pros.append(Finding(
                category="Cap Rate",
                description="Cap rate significantly above market",
                details=f"Property cap rate of {cap_rate:.1%} is {spread:.1%} above market average of {market_cap:.1%}, indicating potential value opportunity",
                risk_level=RiskLevel.LOW,
                metric_name="Cap Rate Spread",
                actual_value=f"{cap_rate:.2%}",
                benchmark_value=f"{market_cap:.2%}"
            ))
        elif spread > 0.005:  # 50+ bps above market
            analysis.pros.append(Finding(
                category="Cap Rate",
                description="Cap rate above market average",
                details=f"Property cap rate of {cap_rate:.1%} exceeds market average, providing cushion for value",
                risk_level=RiskLevel.LOW,
                metric_name="Cap Rate",
                actual_value=f"{cap_rate:.2%}",
                benchmark_value=f"{market_cap:.2%}"
            ))
        elif spread < -0.015:  # 150+ bps below market
            analysis.red_flags.append(Finding(
                category="Cap Rate",
                description="Cap rate significantly below market",
                details=f"Buying at {cap_rate:.1%} cap when market is at {market_cap:.1%} leaves no margin for error. Price appears aggressive.",
                risk_level=RiskLevel.HIGH,
                metric_name="Cap Rate",
                actual_value=f"{cap_rate:.2%}",
                benchmark_value=f"{market_cap:.2%}"
            ))
        elif spread < -0.005:  # Below market
            analysis.cons.append(Finding(
                category="Cap Rate",
                description="Cap rate below market average",
                details=f"Entry cap rate of {cap_rate:.1%} is below market ({market_cap:.1%}), requiring significant rent growth to achieve returns",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Cap Rate",
                actual_value=f"{cap_rate:.2%}",
                benchmark_value=f"{market_cap:.2%}"
            ))

        # Check for unrealistic proforma cap rate
        if fin.proforma_cap_rate and fin.current_cap_rate:
            cap_expansion = fin.proforma_cap_rate - fin.current_cap_rate
            if cap_expansion > 0.02:  # 200+ bps expansion assumed
                analysis.red_flags.append(Finding(
                    category="Cap Rate Assumptions",
                    description="Aggressive cap rate expansion assumed",
                    details=f"Proforma assumes {cap_expansion:.1%} cap rate expansion from {fin.current_cap_rate:.1%} to {fin.proforma_cap_rate:.1%}. This is very aggressive.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Cap Expansion",
                    actual_value=f"{cap_expansion:.1%}",
                    benchmark_value="0-1%"
                ))

    def _analyze_occupancy(self, analysis: OMAnalysis):
        """Analyze occupancy levels"""
        fin = analysis.financials
        market = analysis.market_data

        if not fin.current_occupancy:
            analysis.cons.append(Finding(
                category="Occupancy",
                description="Occupancy data not provided",
                details="Current occupancy rate is not disclosed in the OM, which may indicate unstabilized operations",
                risk_level=RiskLevel.MEDIUM
            ))
            return

        occ = fin.current_occupancy
        market_vac = market.market_vacancy_rate or 0.07
        market_occ = 1 - market_vac

        if occ >= self.THRESHOLDS['occupancy_excellent']:
            analysis.pros.append(Finding(
                category="Occupancy",
                description="Excellent occupancy rate",
                details=f"Current occupancy of {occ:.1%} indicates strong tenant demand and effective management",
                risk_level=RiskLevel.LOW,
                metric_name="Occupancy",
                actual_value=f"{occ:.1%}",
                benchmark_value=f"{market_occ:.1%} (market)"
            ))
        elif occ >= self.THRESHOLDS['occupancy_good']:
            analysis.pros.append(Finding(
                category="Occupancy",
                description="Healthy occupancy rate",
                details=f"Occupancy of {occ:.1%} is at or above market norms",
                risk_level=RiskLevel.LOW,
                metric_name="Occupancy",
                actual_value=f"{occ:.1%}",
                benchmark_value=f"{market_occ:.1%} (market)"
            ))
        elif occ < self.THRESHOLDS['occupancy_red_flag']:
            analysis.red_flags.append(Finding(
                category="Occupancy",
                description="Critically low occupancy",
                details=f"Occupancy of {occ:.1%} is well below market standards. Investigate causes: management issues, property condition, or market softness.",
                risk_level=RiskLevel.CRITICAL,
                metric_name="Occupancy",
                actual_value=f"{occ:.1%}",
                benchmark_value=f">{self.THRESHOLDS['occupancy_concern']:.0%}"
            ))
        elif occ < self.THRESHOLDS['occupancy_concern']:
            analysis.cons.append(Finding(
                category="Occupancy",
                description="Below-market occupancy",
                details=f"Occupancy of {occ:.1%} is below market average. May indicate property issues or present value-add opportunity.",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Occupancy",
                actual_value=f"{occ:.1%}",
                benchmark_value=f"{market_occ:.1%} (market)"
            ))

    def _analyze_rent_levels(self, analysis: OMAnalysis):
        """Analyze rent levels vs market"""
        fin = analysis.financials
        market = analysis.market_data

        if not fin.average_rent:
            return

        market_rent = fin.market_rent or market.market_rent_psf

        if not market_rent:
            return

        rent_spread = (fin.average_rent - market_rent) / market_rent

        if rent_spread < self.THRESHOLDS['rent_discount_opportunity']:
            analysis.pros.append(Finding(
                category="Rent Levels",
                description="Below-market rents present upside",
                details=f"Current rents of ${fin.average_rent:,.0f} are {abs(rent_spread):.1%} below market (${market_rent:,.0f}), indicating rent growth potential",
                risk_level=RiskLevel.LOW,
                metric_name="Rent vs Market",
                actual_value=f"${fin.average_rent:,.0f}",
                benchmark_value=f"${market_rent:,.0f}"
            ))
        elif rent_spread > self.THRESHOLDS['rent_premium_concern'] * 2:
            analysis.red_flags.append(Finding(
                category="Rent Levels",
                description="Rents significantly above market",
                details=f"Current rents of ${fin.average_rent:,.0f} are {rent_spread:.1%} above market. Risk of tenant turnover and rent decline.",
                risk_level=RiskLevel.HIGH,
                metric_name="Rent vs Market",
                actual_value=f"${fin.average_rent:,.0f}",
                benchmark_value=f"${market_rent:,.0f}"
            ))
        elif rent_spread > self.THRESHOLDS['rent_premium_concern']:
            analysis.cons.append(Finding(
                category="Rent Levels",
                description="Rents above market average",
                details=f"Current rents are {rent_spread:.1%} above market, limiting organic rent growth potential",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Rent vs Market",
                actual_value=f"${fin.average_rent:,.0f}",
                benchmark_value=f"${market_rent:,.0f}"
            ))

    def _analyze_expenses(self, analysis: OMAnalysis):
        """Analyze operating expenses"""
        fin = analysis.financials

        if not fin.expense_ratio:
            return

        exp_ratio = fin.expense_ratio

        if exp_ratio <= self.THRESHOLDS['expense_ratio_excellent']:
            analysis.pros.append(Finding(
                category="Operating Expenses",
                description="Excellent expense ratio",
                details=f"Expense ratio of {exp_ratio:.1%} indicates efficient operations",
                risk_level=RiskLevel.LOW,
                metric_name="Expense Ratio",
                actual_value=f"{exp_ratio:.1%}",
                benchmark_value="35-45%"
            ))
        elif exp_ratio >= self.THRESHOLDS['expense_ratio_red_flag']:
            analysis.red_flags.append(Finding(
                category="Operating Expenses",
                description="Extremely high expense ratio",
                details=f"Expense ratio of {exp_ratio:.1%} is unusually high. Investigate for deferred maintenance, management issues, or operational inefficiencies.",
                risk_level=RiskLevel.HIGH,
                metric_name="Expense Ratio",
                actual_value=f"{exp_ratio:.1%}",
                benchmark_value="<55%"
            ))
        elif exp_ratio >= self.THRESHOLDS['expense_ratio_high']:
            analysis.cons.append(Finding(
                category="Operating Expenses",
                description="Above-average expense ratio",
                details=f"Expense ratio of {exp_ratio:.1%} is higher than typical. May indicate operational improvement opportunity.",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Expense Ratio",
                actual_value=f"{exp_ratio:.1%}",
                benchmark_value="35-50%"
            ))

    def _analyze_property_condition(self, analysis: OMAnalysis):
        """Analyze property age and condition"""
        prop = analysis.property

        if not prop.year_built:
            analysis.cons.append(Finding(
                category="Property Condition",
                description="Year built not disclosed",
                details="Property age is not provided, making it difficult to assess condition and capex requirements",
                risk_level=RiskLevel.LOW
            ))
            return

        current_year = datetime.now().year
        age = current_year - prop.year_built

        if age <= self.THRESHOLDS['age_new']:
            analysis.pros.append(Finding(
                category="Property Condition",
                description="Newer construction",
                details=f"Built in {prop.year_built} ({age} years old), property should have modern systems and lower near-term capex needs",
                risk_level=RiskLevel.LOW,
                metric_name="Property Age",
                actual_value=f"{age} years",
                benchmark_value="<10 years (new)"
            ))
        elif age >= self.THRESHOLDS['age_red_flag']:
            analysis.red_flags.append(Finding(
                category="Property Condition",
                description="Aged property requiring significant capex",
                details=f"At {age} years old (built {prop.year_built}), property likely needs major system replacements (roof, HVAC, plumbing). Budget significant capex reserves.",
                risk_level=RiskLevel.HIGH,
                metric_name="Property Age",
                actual_value=f"{age} years",
                benchmark_value="<40 years"
            ))
        elif age >= self.THRESHOLDS['age_concern']:
            analysis.cons.append(Finding(
                category="Property Condition",
                description="Older property with potential capex needs",
                details=f"Property is {age} years old. Major systems may need replacement within hold period.",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Property Age",
                actual_value=f"{age} years",
                benchmark_value="<40 years"
            ))
        elif age >= self.THRESHOLDS['age_value_add']:
            analysis.pros.append(Finding(
                category="Property Condition",
                description="Value-add vintage property",
                details=f"At {age} years old, property may have renovation potential while still having serviceable core systems",
                risk_level=RiskLevel.LOW,
                metric_name="Property Age",
                actual_value=f"{age} years"
            ))

    def _analyze_financing(self, analysis: OMAnalysis):
        """Analyze financing terms"""
        terms = analysis.deal_terms

        # LTV Analysis
        if terms.loan_to_value:
            ltv = terms.loan_to_value
            if ltv <= self.THRESHOLDS['ltv_conservative']:
                analysis.pros.append(Finding(
                    category="Financing",
                    description="Conservative leverage",
                    details=f"LTV of {ltv:.1%} provides equity cushion and lower refinance risk",
                    risk_level=RiskLevel.LOW,
                    metric_name="LTV",
                    actual_value=f"{ltv:.1%}",
                    benchmark_value="<65%"
                ))
            elif ltv >= self.THRESHOLDS['ltv_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Financing",
                    description="High leverage increases risk",
                    details=f"LTV of {ltv:.1%} leaves little equity cushion. Property value decline could result in negative equity position.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="LTV",
                    actual_value=f"{ltv:.1%}",
                    benchmark_value="<75%"
                ))
            elif ltv >= self.THRESHOLDS['ltv_aggressive']:
                analysis.cons.append(Finding(
                    category="Financing",
                    description="Aggressive leverage",
                    details=f"LTV of {ltv:.1%} is on the higher end, increasing refinance and interest rate risk",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="LTV",
                    actual_value=f"{ltv:.1%}",
                    benchmark_value="<70%"
                ))

        # Interest Rate Analysis
        if terms.interest_rate:
            rate = terms.interest_rate
            spread = rate - self.CURRENT_MARKET_RATE

            if spread < -self.THRESHOLDS['rate_spread_good']:
                analysis.pros.append(Finding(
                    category="Financing",
                    description="Below-market interest rate",
                    details=f"Interest rate of {rate:.2%} is below current market rates ({self.CURRENT_MARKET_RATE:.2%})",
                    risk_level=RiskLevel.LOW,
                    metric_name="Interest Rate",
                    actual_value=f"{rate:.2%}",
                    benchmark_value=f"{self.CURRENT_MARKET_RATE:.2%} (market)"
                ))
            elif spread > self.THRESHOLDS['rate_spread_high']:
                analysis.cons.append(Finding(
                    category="Financing",
                    description="Above-market interest rate",
                    details=f"Interest rate of {rate:.2%} is above current market rates, impacting cash flow",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Interest Rate",
                    actual_value=f"{rate:.2%}",
                    benchmark_value=f"{self.CURRENT_MARKET_RATE:.2%} (market)"
                ))

        # Loan Type Analysis
        if terms.loan_type:
            if terms.loan_type.lower() == 'variable' or terms.loan_type.lower() == 'floating':
                analysis.cons.append(Finding(
                    category="Financing",
                    description="Variable rate debt exposure",
                    details="Floating rate debt creates interest rate risk. Consider rate cap cost and break-even rate.",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Loan Type",
                    actual_value=terms.loan_type
                ))
            elif terms.loan_type.lower() == 'bridge':
                analysis.red_flags.append(Finding(
                    category="Financing",
                    description="Bridge loan requires refinancing",
                    details="Bridge financing typically has higher rates and requires refinancing into permanent debt. Execution risk exists.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Loan Type",
                    actual_value="Bridge"
                ))

        # Assumable Debt
        if terms.assumable_debt:
            analysis.pros.append(Finding(
                category="Financing",
                description="Assumable debt available",
                details="Existing assumable financing may provide favorable terms for buyers at exit",
                risk_level=RiskLevel.LOW,
                metric_name="Assumable Debt",
                actual_value="Yes"
            ))

    def _analyze_returns(self, analysis: OMAnalysis):
        """Analyze projected returns"""
        fin = analysis.financials

        # IRR Analysis
        if fin.irr_projected:
            irr = fin.irr_projected
            if irr >= self.THRESHOLDS['irr_excellent']:
                analysis.pros.append(Finding(
                    category="Returns",
                    description="Strong projected IRR",
                    details=f"Projected IRR of {irr:.1%} exceeds typical institutional return requirements",
                    risk_level=RiskLevel.LOW,
                    metric_name="IRR",
                    actual_value=f"{irr:.1%}",
                    benchmark_value=">15%"
                ))
            elif irr < self.THRESHOLDS['irr_minimum']:
                analysis.cons.append(Finding(
                    category="Returns",
                    description="Below-target IRR",
                    details=f"Projected IRR of {irr:.1%} is below typical institutional hurdle rates. Risk-adjusted returns may be insufficient.",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="IRR",
                    actual_value=f"{irr:.1%}",
                    benchmark_value=">12%"
                ))

        # Cash-on-Cash Analysis
        if fin.cash_on_cash_return:
            coc = fin.cash_on_cash_return
            if coc >= self.THRESHOLDS['coc_good']:
                analysis.pros.append(Finding(
                    category="Returns",
                    description="Healthy cash-on-cash return",
                    details=f"Year 1 cash-on-cash of {coc:.1%} provides solid current yield",
                    risk_level=RiskLevel.LOW,
                    metric_name="Cash-on-Cash",
                    actual_value=f"{coc:.1%}",
                    benchmark_value=">8%"
                ))
            elif coc < self.THRESHOLDS['coc_minimum']:
                analysis.cons.append(Finding(
                    category="Returns",
                    description="Low cash-on-cash return",
                    details=f"Year 1 cash-on-cash of {coc:.1%} provides minimal current yield. Returns dependent on appreciation.",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Cash-on-Cash",
                    actual_value=f"{coc:.1%}",
                    benchmark_value=">5%"
                ))

        # Equity Multiple
        if fin.equity_multiple:
            em = fin.equity_multiple
            if em >= 2.0:
                analysis.pros.append(Finding(
                    category="Returns",
                    description="Strong equity multiple",
                    details=f"Projected equity multiple of {em:.2f}x indicates potential to double invested capital",
                    risk_level=RiskLevel.LOW,
                    metric_name="Equity Multiple",
                    actual_value=f"{em:.2f}x",
                    benchmark_value=">1.8x"
                ))
            elif em < 1.5:
                analysis.cons.append(Finding(
                    category="Returns",
                    description="Low equity multiple",
                    details=f"Equity multiple of {em:.2f}x is below typical targets for the hold period",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Equity Multiple",
                    actual_value=f"{em:.2f}x",
                    benchmark_value=">1.8x"
                ))

    def _analyze_deal_structure(self, analysis: OMAnalysis):
        """Analyze deal structure and sponsor terms"""
        terms = analysis.deal_terms

        # Preferred Return
        if terms.preferred_return:
            pref = terms.preferred_return
            if pref >= 0.08:
                analysis.pros.append(Finding(
                    category="Deal Structure",
                    description="Strong preferred return",
                    details=f"Preferred return of {pref:.1%} provides downside protection for LPs",
                    risk_level=RiskLevel.LOW,
                    metric_name="Preferred Return",
                    actual_value=f"{pref:.1%}",
                    benchmark_value="7-8%"
                ))
            elif pref < 0.06:
                analysis.cons.append(Finding(
                    category="Deal Structure",
                    description="Below-market preferred return",
                    details=f"Preferred return of {pref:.1%} is below market standards",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Preferred Return",
                    actual_value=f"{pref:.1%}",
                    benchmark_value="7-8%"
                ))

        # Profit Split
        if terms.profit_split:
            try:
                lp_share, gp_share = map(int, terms.profit_split.split('/'))
                if lp_share >= 70:
                    analysis.pros.append(Finding(
                        category="Deal Structure",
                        description="LP-favorable profit split",
                        details=f"Profit split of {terms.profit_split} provides majority of upside to limited partners",
                        risk_level=RiskLevel.LOW,
                        metric_name="Profit Split",
                        actual_value=terms.profit_split
                    ))
                elif lp_share < 60:
                    analysis.cons.append(Finding(
                        category="Deal Structure",
                        description="GP-heavy profit split",
                        details=f"Profit split of {terms.profit_split} allocates significant upside to sponsor",
                        risk_level=RiskLevel.MEDIUM,
                        metric_name="Profit Split",
                        actual_value=terms.profit_split
                    ))
            except (ValueError, AttributeError):
                pass

        # Hold Period
        if terms.hold_period_years:
            hold = terms.hold_period_years
            if hold >= 7:
                analysis.cons.append(Finding(
                    category="Deal Structure",
                    description="Long hold period",
                    details=f"Projected {hold}-year hold reduces liquidity and increases market cycle risk",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Hold Period",
                    actual_value=f"{hold} years",
                    benchmark_value="3-5 years"
                ))

    def _analyze_market_conditions(self, analysis: OMAnalysis):
        """Analyze market-level factors"""
        market = analysis.market_data
        prop = analysis.property

        # Rent Growth
        if market.rent_growth_1yr:
            growth = market.rent_growth_1yr
            if growth >= 0.05:
                analysis.pros.append(Finding(
                    category="Market",
                    description="Strong rent growth market",
                    details=f"Market rent growth of {growth:.1%} annually indicates strong demand fundamentals",
                    risk_level=RiskLevel.LOW,
                    metric_name="Rent Growth",
                    actual_value=f"{growth:.1%}",
                    benchmark_value="3-4%"
                ))
            elif growth < 0.02:
                analysis.cons.append(Finding(
                    category="Market",
                    description="Slow rent growth market",
                    details=f"Market rent growth of {growth:.1%} is below inflation, limiting organic NOI growth",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Rent Growth",
                    actual_value=f"{growth:.1%}",
                    benchmark_value="3-4%"
                ))

        # Job Growth
        if market.job_growth:
            job_growth = market.job_growth
            if job_growth >= 0.025:
                analysis.pros.append(Finding(
                    category="Market",
                    description="Strong employment growth",
                    details=f"Job growth of {job_growth:.1%} supports housing demand",
                    risk_level=RiskLevel.LOW,
                    metric_name="Job Growth",
                    actual_value=f"{job_growth:.1%}",
                    benchmark_value=">2%"
                ))
            elif job_growth < 0.01:
                analysis.cons.append(Finding(
                    category="Market",
                    description="Weak employment growth",
                    details=f"Job growth of {job_growth:.1%} may limit demand growth",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Job Growth",
                    actual_value=f"{job_growth:.1%}"
                ))

        # Unemployment
        if market.unemployment_rate and market.unemployment_rate > 0.06:
            analysis.cons.append(Finding(
                category="Market",
                description="Elevated unemployment",
                details=f"Local unemployment rate of {market.unemployment_rate:.1%} is above national average",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Unemployment",
                actual_value=f"{market.unemployment_rate:.1%}",
                benchmark_value="<5%"
            ))

        # Major Employers
        if market.major_employers and len(market.major_employers) >= 3:
            analysis.pros.append(Finding(
                category="Market",
                description="Diversified employer base",
                details=f"Market has diverse major employers including {', '.join(market.major_employers[:3])}",
                risk_level=RiskLevel.LOW,
                metric_name="Major Employers",
                actual_value=", ".join(market.major_employers[:3])
            ))

    def _analyze_value_add_potential(self, analysis: OMAnalysis):
        """Identify value-add opportunities"""
        fin = analysis.financials
        prop = analysis.property

        opportunities = []

        # Below-market rents
        if fin.average_rent and fin.market_rent:
            rent_gap = fin.market_rent - fin.average_rent
            if rent_gap > 0:
                opportunities.append(f"Rent increase potential: ${rent_gap:.0f}/unit")

        # Low occupancy
        if fin.current_occupancy and fin.current_occupancy < 0.92:
            occ_gap = 0.95 - fin.current_occupancy
            opportunities.append(f"Occupancy upside: {occ_gap:.1%} to stabilize")

        # Older property with renovation potential
        if prop.year_built and (datetime.now().year - prop.year_built) > 20:
            opportunities.append("Unit renovation/upgrade potential")

        # High expense ratio
        if fin.expense_ratio and fin.expense_ratio > 0.50:
            opportunities.append("Expense reduction opportunity through operational improvements")

        if opportunities:
            analysis.pros.append(Finding(
                category="Value-Add",
                description="Multiple value creation opportunities identified",
                details="; ".join(opportunities),
                risk_level=RiskLevel.LOW,
                metric_name="Value-Add Opportunities",
                actual_value=str(len(opportunities))
            ))

    def _calculate_overall_score(self, analysis: OMAnalysis):
        """Calculate overall deal score and recommendation"""
        # Scoring weights
        weights = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: -1,
            RiskLevel.HIGH: -3,
            RiskLevel.CRITICAL: -5
        }

        # Start with base score
        score = 50

        # Add points for pros (each pro = +5)
        score += len(analysis.pros) * 5

        # Subtract points for cons based on severity
        for con in analysis.cons:
            score += weights[con.risk_level]

        # Heavily penalize red flags
        for flag in analysis.red_flags:
            score += weights[flag.risk_level] * 2

        # Cap score between 0 and 100
        score = max(0, min(100, score))
        analysis.overall_score = score

        # Generate recommendation
        if score >= 75:
            analysis.recommendation = "STRONG BUY - Deal shows attractive fundamentals with limited concerns"
        elif score >= 60:
            analysis.recommendation = "BUY - Deal merits consideration with appropriate due diligence on identified concerns"
        elif score >= 45:
            analysis.recommendation = "HOLD - Proceed with caution; significant concerns require resolution"
        elif score >= 30:
            analysis.recommendation = "WEAK - Material issues identified; renegotiate terms or pass"
        else:
            analysis.recommendation = "PASS - Too many red flags; recommend passing on this opportunity"
