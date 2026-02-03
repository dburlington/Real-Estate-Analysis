"""Deal Analyzer - Identifies pros, cons, and red flags in real estate deals"""

from datetime import datetime
from typing import Optional
from .models import (
    OMAnalysis, Finding, RiskLevel, PropertyType, MarketData, SponsorFees
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

    # Industry standard fee benchmarks (as of 2024)
    # Source: NCREIF, Preqin, industry surveys
    FEE_BENCHMARKS = {
        # Acquisition fees - typically 0.5% to 2% of purchase price
        'acquisition_fee_low': 0.005,  # 0.5% - investor-friendly
        'acquisition_fee_market': 0.01,  # 1.0% - market standard
        'acquisition_fee_high': 0.02,  # 2.0% - above market
        'acquisition_fee_red_flag': 0.03,  # 3.0% - excessive

        # Asset management fees - typically 1% to 2% of equity or EGI annually
        'asset_mgmt_fee_low': 0.01,  # 1.0% - investor-friendly
        'asset_mgmt_fee_market': 0.015,  # 1.5% - market standard
        'asset_mgmt_fee_high': 0.02,  # 2.0% - above market
        'asset_mgmt_fee_red_flag': 0.025,  # 2.5% - excessive

        # Property management fees - 3% to 6% of EGI
        'property_mgmt_fee_low': 0.03,  # 3% - institutional
        'property_mgmt_fee_market': 0.05,  # 5% - market standard
        'property_mgmt_fee_high': 0.07,  # 7% - above market
        'property_mgmt_fee_red_flag': 0.10,  # 10% - excessive

        # Construction management fees - 3% to 5% of project costs
        'construction_mgmt_fee_low': 0.03,  # 3% - investor-friendly
        'construction_mgmt_fee_market': 0.05,  # 5% - market standard
        'construction_mgmt_fee_high': 0.08,  # 8% - above market
        'construction_mgmt_fee_red_flag': 0.10,  # 10% - excessive

        # Disposition fees - 0.5% to 1.5% of sale price
        'disposition_fee_low': 0.005,  # 0.5% - investor-friendly
        'disposition_fee_market': 0.01,  # 1.0% - market standard
        'disposition_fee_high': 0.015,  # 1.5% - above market
        'disposition_fee_red_flag': 0.02,  # 2.0% - excessive

        # Refinance fees - 0.25% to 1% of loan amount
        'refinance_fee_low': 0.0025,  # 0.25% - investor-friendly
        'refinance_fee_market': 0.005,  # 0.5% - market standard
        'refinance_fee_high': 0.01,  # 1.0% - above market
        'refinance_fee_red_flag': 0.015,  # 1.5% - excessive

        # Total fees over hold (as % of equity)
        'total_fees_low': 0.15,  # 15% of equity over hold - lean
        'total_fees_market': 0.25,  # 25% - market standard
        'total_fees_high': 0.35,  # 35% - fee heavy
        'total_fees_red_flag': 0.45,  # 45% - excessive
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
        self._analyze_fees(om_analysis)
        self._analyze_external_comparisons(om_analysis)

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

    def _analyze_fees(self, analysis: OMAnalysis):
        """Analyze sponsor fees against industry benchmarks"""
        fees = analysis.fees
        benchmarks = self.FEE_BENCHMARKS

        # Track total fee load for summary
        total_upfront_pct = 0
        total_annual_pct = 0
        fee_issues = []

        # Acquisition Fee Analysis
        if fees.acquisition_fee:
            acq = fees.acquisition_fee
            total_upfront_pct += acq

            if acq >= benchmarks['acquisition_fee_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Excessive acquisition fee",
                    details=f"Acquisition fee of {acq:.1%} significantly exceeds industry standard of 1-2%. This fee alone reduces investor returns substantially.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Acquisition Fee",
                    actual_value=f"{acq:.1%}",
                    benchmark_value=f"{benchmarks['acquisition_fee_market']:.1%} (market)"
                ))
                fee_issues.append("acquisition fee")
            elif acq >= benchmarks['acquisition_fee_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-market acquisition fee",
                    details=f"Acquisition fee of {acq:.1%} is above the industry standard of 1%",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Acquisition Fee",
                    actual_value=f"{acq:.1%}",
                    benchmark_value=f"{benchmarks['acquisition_fee_market']:.1%} (market)"
                ))
            elif acq <= benchmarks['acquisition_fee_low']:
                analysis.pros.append(Finding(
                    category="Fees",
                    description="Low acquisition fee",
                    details=f"Acquisition fee of {acq:.1%} is below market average, benefiting investors",
                    risk_level=RiskLevel.LOW,
                    metric_name="Acquisition Fee",
                    actual_value=f"{acq:.1%}",
                    benchmark_value=f"{benchmarks['acquisition_fee_market']:.1%} (market)"
                ))

        # Asset Management Fee Analysis
        if fees.asset_management_fee:
            am = fees.asset_management_fee
            total_annual_pct += am

            if am >= benchmarks['asset_mgmt_fee_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Excessive asset management fee",
                    details=f"Annual asset management fee of {am:.1%} is well above the industry standard of 1-2%. Over a 5-year hold, this significantly erodes returns.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Asset Management Fee",
                    actual_value=f"{am:.1%}/year",
                    benchmark_value=f"{benchmarks['asset_mgmt_fee_market']:.1%}/year (market)"
                ))
                fee_issues.append("asset management fee")
            elif am >= benchmarks['asset_mgmt_fee_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-market asset management fee",
                    details=f"Asset management fee of {am:.1%} annually exceeds typical institutional rates",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Asset Management Fee",
                    actual_value=f"{am:.1%}/year",
                    benchmark_value=f"{benchmarks['asset_mgmt_fee_market']:.1%}/year (market)"
                ))
            elif am <= benchmarks['asset_mgmt_fee_low']:
                analysis.pros.append(Finding(
                    category="Fees",
                    description="Competitive asset management fee",
                    details=f"Asset management fee of {am:.1%} is at or below institutional rates",
                    risk_level=RiskLevel.LOW,
                    metric_name="Asset Management Fee",
                    actual_value=f"{am:.1%}/year",
                    benchmark_value=f"{benchmarks['asset_mgmt_fee_market']:.1%}/year (market)"
                ))

        # Property Management Fee Analysis
        if fees.property_management_fee:
            pm = fees.property_management_fee
            total_annual_pct += pm

            if pm >= benchmarks['property_mgmt_fee_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Excessive property management fee",
                    details=f"Property management fee of {pm:.1%} is far above the industry standard of 3-6%",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Property Management Fee",
                    actual_value=f"{pm:.1%}",
                    benchmark_value=f"{benchmarks['property_mgmt_fee_market']:.1%} (market)"
                ))
            elif pm >= benchmarks['property_mgmt_fee_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-market property management fee",
                    details=f"Property management fee of {pm:.1%} is higher than typical institutional deals",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Property Management Fee",
                    actual_value=f"{pm:.1%}",
                    benchmark_value=f"{benchmarks['property_mgmt_fee_market']:.1%} (market)"
                ))
            elif pm <= benchmarks['property_mgmt_fee_low']:
                analysis.pros.append(Finding(
                    category="Fees",
                    description="Low property management fee",
                    details=f"Property management fee of {pm:.1%} indicates institutional-quality management rates",
                    risk_level=RiskLevel.LOW,
                    metric_name="Property Management Fee",
                    actual_value=f"{pm:.1%}",
                    benchmark_value=f"{benchmarks['property_mgmt_fee_market']:.1%} (market)"
                ))

        # Construction Management Fee Analysis
        if fees.construction_management_fee:
            cm = fees.construction_management_fee

            if cm >= benchmarks['construction_mgmt_fee_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Excessive construction management fee",
                    details=f"Construction management fee of {cm:.1%} far exceeds market standard of 3-5%",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Construction Mgmt Fee",
                    actual_value=f"{cm:.1%}",
                    benchmark_value=f"{benchmarks['construction_mgmt_fee_market']:.1%} (market)"
                ))
            elif cm >= benchmarks['construction_mgmt_fee_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-market construction management fee",
                    details=f"Construction management fee of {cm:.1%} is above typical rates",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Construction Mgmt Fee",
                    actual_value=f"{cm:.1%}",
                    benchmark_value=f"{benchmarks['construction_mgmt_fee_market']:.1%} (market)"
                ))

        # Disposition Fee Analysis
        if fees.disposition_fee:
            disp = fees.disposition_fee

            if disp >= benchmarks['disposition_fee_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Excessive disposition fee",
                    details=f"Disposition fee of {disp:.1%} is double the industry standard. At exit, this significantly reduces investor proceeds.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Disposition Fee",
                    actual_value=f"{disp:.1%}",
                    benchmark_value=f"{benchmarks['disposition_fee_market']:.1%} (market)"
                ))
            elif disp >= benchmarks['disposition_fee_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-market disposition fee",
                    details=f"Disposition fee of {disp:.1%} exceeds typical rates of 0.5-1%",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Disposition Fee",
                    actual_value=f"{disp:.1%}",
                    benchmark_value=f"{benchmarks['disposition_fee_market']:.1%} (market)"
                ))
            elif disp <= benchmarks['disposition_fee_low']:
                analysis.pros.append(Finding(
                    category="Fees",
                    description="Low disposition fee",
                    details=f"Disposition fee of {disp:.1%} is investor-friendly",
                    risk_level=RiskLevel.LOW,
                    metric_name="Disposition Fee",
                    actual_value=f"{disp:.1%}",
                    benchmark_value=f"{benchmarks['disposition_fee_market']:.1%} (market)"
                ))

        # Calculate estimated total fees over hold period
        hold_years = analysis.deal_terms.hold_period_years or 5
        if total_upfront_pct > 0 or total_annual_pct > 0:
            # Rough estimate of total fee load as % of equity
            total_fee_estimate = total_upfront_pct + (total_annual_pct * hold_years)

            # Store in fees object
            fees.total_upfront_fees_pct = total_upfront_pct
            fees.total_annual_fees_pct = total_annual_pct
            fees.estimated_total_fees_over_hold = total_fee_estimate

            if total_fee_estimate >= benchmarks['total_fees_red_flag']:
                analysis.red_flags.append(Finding(
                    category="Fees",
                    description="Total fee load is excessive",
                    details=f"Estimated total fees of {total_fee_estimate:.1%} of equity over {hold_years} years significantly exceeds industry norms. Consider how this impacts your net returns.",
                    risk_level=RiskLevel.HIGH,
                    metric_name="Total Fee Load",
                    actual_value=f"{total_fee_estimate:.1%}",
                    benchmark_value=f"<{benchmarks['total_fees_market']:.0%}"
                ))
            elif total_fee_estimate >= benchmarks['total_fees_high']:
                analysis.cons.append(Finding(
                    category="Fees",
                    description="Above-average total fee load",
                    details=f"Total estimated fees of {total_fee_estimate:.1%} over the hold period are above market average",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Total Fee Load",
                    actual_value=f"{total_fee_estimate:.1%}",
                    benchmark_value=f"<{benchmarks['total_fees_market']:.0%}"
                ))
            elif total_fee_estimate <= benchmarks['total_fees_low']:
                analysis.pros.append(Finding(
                    category="Fees",
                    description="Lean fee structure",
                    details=f"Total estimated fees of {total_fee_estimate:.1%} over hold period indicate an investor-aligned sponsor",
                    risk_level=RiskLevel.LOW,
                    metric_name="Total Fee Load",
                    actual_value=f"{total_fee_estimate:.1%}",
                    benchmark_value=f"Market avg: {benchmarks['total_fees_market']:.0%}"
                ))

        # Check for fee disclosure issues
        has_any_fees = any([
            fees.acquisition_fee, fees.asset_management_fee,
            fees.property_management_fee, fees.disposition_fee
        ])
        if not has_any_fees:
            analysis.cons.append(Finding(
                category="Fees",
                description="Fee structure not disclosed",
                details="No sponsor fees were identified in the OM. Request a complete fee schedule before investing.",
                risk_level=RiskLevel.MEDIUM,
                metric_name="Fee Disclosure"
            ))

    def _analyze_external_comparisons(self, analysis: OMAnalysis):
        """Compare deal metrics against external market data and benchmarks"""
        market = analysis.market_data
        fin = analysis.financials
        prop = analysis.property

        # Price per unit comparison for multifamily
        if prop.property_type == PropertyType.MULTIFAMILY and fin.price_per_unit:
            ppu = fin.price_per_unit
            state = prop.state

            # Determine market tier based on state
            gateway_states = ['CA', 'NY', 'MA', 'DC']
            primary_states = ['WA', 'CO', 'FL', 'IL']
            secondary_states = ['TX', 'GA', 'NC', 'TN', 'AZ']

            if state in gateway_states:
                tier = 'Gateway'
                benchmark = self.THRESHOLDS['ppu_gateway']
            elif state in primary_states:
                tier = 'Primary'
                benchmark = self.THRESHOLDS['ppu_primary']
            elif state in secondary_states:
                tier = 'Secondary'
                benchmark = self.THRESHOLDS['ppu_secondary']
            else:
                tier = 'Tertiary'
                benchmark = self.THRESHOLDS['ppu_tertiary']

            spread = (ppu - benchmark) / benchmark

            if spread > 0.30:  # 30%+ above market
                analysis.cons.append(Finding(
                    category="Valuation",
                    description=f"Price per unit above {tier} market average",
                    details=f"At ${ppu:,.0f}/unit, this is {spread:.0%} above typical {tier} market pricing of ${benchmark:,.0f}/unit",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Price/Unit vs Market",
                    actual_value=f"${ppu:,.0f}",
                    benchmark_value=f"${benchmark:,.0f} ({tier})"
                ))
            elif spread < -0.20:  # 20%+ below market
                analysis.pros.append(Finding(
                    category="Valuation",
                    description=f"Price per unit below {tier} market average",
                    details=f"At ${ppu:,.0f}/unit, this is {abs(spread):.0%} below typical {tier} market pricing, indicating potential value",
                    risk_level=RiskLevel.LOW,
                    metric_name="Price/Unit vs Market",
                    actual_value=f"${ppu:,.0f}",
                    benchmark_value=f"${benchmark:,.0f} ({tier})"
                ))

        # Vacancy comparison
        if fin.current_occupancy and market.market_vacancy_rate:
            property_vacancy = 1 - fin.current_occupancy
            market_vacancy = market.market_vacancy_rate
            vacancy_spread = property_vacancy - market_vacancy

            if vacancy_spread > 0.05:  # 5%+ higher vacancy than market
                analysis.cons.append(Finding(
                    category="Market Comparison",
                    description="Vacancy above market average",
                    details=f"Property vacancy of {property_vacancy:.1%} is {vacancy_spread:.1%} higher than market average of {market_vacancy:.1%}",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Vacancy vs Market",
                    actual_value=f"{property_vacancy:.1%}",
                    benchmark_value=f"{market_vacancy:.1%} (market)"
                ))
            elif vacancy_spread < -0.03:  # 3%+ lower vacancy than market
                analysis.pros.append(Finding(
                    category="Market Comparison",
                    description="Vacancy below market average",
                    details=f"Property vacancy of {property_vacancy:.1%} outperforms market average of {market_vacancy:.1%}",
                    risk_level=RiskLevel.LOW,
                    metric_name="Vacancy vs Market",
                    actual_value=f"{property_vacancy:.1%}",
                    benchmark_value=f"{market_vacancy:.1%} (market)"
                ))

        # Supply pipeline warning
        if market.new_supply_units and market.new_supply_units > 0:
            if prop.total_units:
                supply_ratio = market.new_supply_units / prop.total_units
                if supply_ratio > 5:  # New supply is 5x+ the property size
                    analysis.cons.append(Finding(
                        category="Market Comparison",
                        description="Significant new supply in pipeline",
                        details=f"Approximately {market.new_supply_units:,} new units are under construction in this market, which may pressure rents and occupancy",
                        risk_level=RiskLevel.MEDIUM,
                        metric_name="Supply Pipeline",
                        actual_value=f"{market.new_supply_units:,} units"
                    ))

        # Income/affordability check
        if market.median_household_income and fin.average_rent:
            annual_rent = fin.average_rent * 12
            rent_to_income = annual_rent / market.median_household_income

            if rent_to_income > 0.35:  # Rent is >35% of median income
                analysis.cons.append(Finding(
                    category="Market Comparison",
                    description="Rent may be unaffordable for median income",
                    details=f"At ${fin.average_rent:,.0f}/month, rent represents {rent_to_income:.0%} of the area's median household income (${market.median_household_income:,.0f}), potentially limiting tenant pool",
                    risk_level=RiskLevel.MEDIUM,
                    metric_name="Rent/Income Ratio",
                    actual_value=f"{rent_to_income:.0%}",
                    benchmark_value="<30%"
                ))
            elif rent_to_income < 0.25:  # Rent is <25% of median income
                analysis.pros.append(Finding(
                    category="Market Comparison",
                    description="Rents affordable relative to local incomes",
                    details=f"Rent represents only {rent_to_income:.0%} of area median income, indicating room for rent growth and stable tenant demand",
                    risk_level=RiskLevel.LOW,
                    metric_name="Rent/Income Ratio",
                    actual_value=f"{rent_to_income:.0%}",
                    benchmark_value="<30%"
                ))

        # Walk score / location quality
        if market.walk_score:
            if market.walk_score >= 70:
                analysis.pros.append(Finding(
                    category="Location",
                    description="Excellent walkability",
                    details=f"Walk score of {market.walk_score} indicates a very walkable location with nearby amenities",
                    risk_level=RiskLevel.LOW,
                    metric_name="Walk Score",
                    actual_value=str(market.walk_score),
                    benchmark_value=">70 (very walkable)"
                ))
            elif market.walk_score < 40:
                analysis.cons.append(Finding(
                    category="Location",
                    description="Car-dependent location",
                    details=f"Walk score of {market.walk_score} indicates a car-dependent location, which may limit tenant appeal",
                    risk_level=RiskLevel.LOW,
                    metric_name="Walk Score",
                    actual_value=str(market.walk_score),
                    benchmark_value=">50 (somewhat walkable)"
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
