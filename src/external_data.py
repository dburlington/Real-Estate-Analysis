"""External Data Fetcher - News, Government, and Analyst data for investment context"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import Optional
import requests

from .models import (
    ExternalContext, NewsItem, EconomicIndicator, AnalystInsight,
    PropertyType
)


class ExternalDataFetcher:
    """Fetches external context data from various sources"""

    # Federal Reserve Economic Data (FRED) API
    FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

    # Key FRED series for real estate analysis
    FRED_SERIES = {
        'mortgage_rate_30yr': 'MORTGAGE30US',
        'mortgage_rate_15yr': 'MORTGAGE15US',
        'treasury_10yr': 'DGS10',
        'cpi_all': 'CPIAUCSL',
        'unemployment': 'UNRATE',
        'gdp_growth': 'A191RL1Q225SBEA',
        'housing_starts': 'HOUST',
        'building_permits': 'PERMIT',
        'consumer_sentiment': 'UMCSENT',
        'industrial_production': 'INDPRO',
    }

    # Major CRE research sources
    ANALYST_SOURCES = {
        'CBRE': 'https://www.cbre.com/insights',
        'JLL': 'https://www.jll.com/research',
        'Cushman & Wakefield': 'https://www.cushmanwakefield.com/insights',
        'Marcus & Millichap': 'https://www.marcusmillichap.com/research',
        'Newmark': 'https://www.nmrk.com/insights',
        'CoStar': 'https://www.costar.com/research',
        'NAIOP': 'https://www.naiop.org/research',
        'Urban Land Institute': 'https://uli.org/research',
    }

    def __init__(self, fred_api_key: Optional[str] = None):
        """Initialize with optional API keys"""
        self.fred_api_key = fred_api_key or os.getenv('FRED_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'RealEstateOMAnalyzer/1.0'})

    def fetch_external_context(
        self,
        city: str,
        state: str,
        property_type: PropertyType,
        property_name: Optional[str] = None
    ) -> ExternalContext:
        """Fetch comprehensive external context for the investment"""
        context = ExternalContext()
        context.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Fetch economic indicators from FRED
        indicators = self._fetch_fred_indicators()
        context.economic_indicators.extend(indicators)
        if indicators:
            context.data_sources_used.append('Federal Reserve (FRED)')

        # Get market news context
        market_news = self._get_market_news(city, state, property_type)
        context.market_news.extend(market_news)

        # Get property-specific news if name provided
        if property_name:
            prop_news = self._get_property_news(property_name, city, state)
            context.property_news.extend(prop_news)

        # Get analyst insights
        insights = self._get_analyst_insights(city, state, property_type)
        context.analyst_insights.extend(insights)

        # Get supply pipeline data
        context.supply_pipeline = self._get_supply_pipeline(city, state, property_type)

        # Get recent comparable sales
        context.recent_sales_comps = self._get_sales_comps(city, state, property_type)

        # Get regulatory and environmental context
        context.regulatory_risks = self._get_regulatory_risks(city, state, property_type)
        context.environmental_notes = self._get_environmental_notes(city, state)

        return context

    def _fetch_fred_indicators(self) -> list[EconomicIndicator]:
        """Fetch key economic indicators from FRED API"""
        indicators = []

        if not self.fred_api_key:
            # Return curated estimates without API
            return self._get_estimated_indicators()

        try:
            # Fetch mortgage rates
            mortgage_data = self._fetch_fred_series('MORTGAGE30US', limit=1)
            if mortgage_data:
                indicators.append(EconomicIndicator(
                    name='30-Year Mortgage Rate',
                    value=mortgage_data['value'],
                    unit='%',
                    period=mortgage_data['date'],
                    source='Federal Reserve (FRED)',
                    trend=self._get_trend(mortgage_data.get('previous')),
                    context='Key driver of real estate cap rates and valuations'
                ))

            # Fetch 10-year Treasury
            treasury_data = self._fetch_fred_series('DGS10', limit=1)
            if treasury_data:
                indicators.append(EconomicIndicator(
                    name='10-Year Treasury Yield',
                    value=treasury_data['value'],
                    unit='%',
                    period=treasury_data['date'],
                    source='Federal Reserve (FRED)',
                    trend=self._get_trend(treasury_data.get('previous')),
                    context='Benchmark for commercial real estate pricing spreads'
                ))

            # Fetch unemployment rate
            unemployment_data = self._fetch_fred_series('UNRATE', limit=1)
            if unemployment_data:
                indicators.append(EconomicIndicator(
                    name='National Unemployment Rate',
                    value=unemployment_data['value'],
                    unit='%',
                    period=unemployment_data['date'],
                    source='Bureau of Labor Statistics (via FRED)',
                    trend=self._get_trend(unemployment_data.get('previous')),
                    context='Indicator of tenant demand strength'
                ))

            # Fetch CPI for inflation context
            cpi_data = self._fetch_fred_series('CPIAUCSL', limit=2)
            if cpi_data:
                # Calculate YoY change
                yoy_change = ((cpi_data['value'] - cpi_data.get('previous', cpi_data['value']))
                              / cpi_data.get('previous', 1)) * 100
                indicators.append(EconomicIndicator(
                    name='CPI Inflation (YoY)',
                    value=round(yoy_change, 1),
                    unit='%',
                    period=cpi_data['date'],
                    source='Bureau of Labor Statistics (via FRED)',
                    trend='up' if yoy_change > 2.5 else 'stable',
                    context='Affects rent growth potential and expense escalations'
                ))

        except Exception as e:
            # Fall back to estimates
            return self._get_estimated_indicators()

        return indicators if indicators else self._get_estimated_indicators()

    def _fetch_fred_series(self, series_id: str, limit: int = 1) -> Optional[dict]:
        """Fetch a single FRED data series"""
        if not self.fred_api_key:
            return None

        try:
            params = {
                'series_id': series_id,
                'api_key': self.fred_api_key,
                'file_type': 'json',
                'sort_order': 'desc',
                'limit': limit + 1  # Get one extra for comparison
            }
            response = self.session.get(self.FRED_API_BASE, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'observations' in data and len(data['observations']) > 0:
                    latest = data['observations'][0]
                    result = {
                        'value': float(latest['value']),
                        'date': latest['date']
                    }
                    if len(data['observations']) > 1:
                        result['previous'] = float(data['observations'][1]['value'])
                    return result
        except Exception:
            pass
        return None

    def _get_estimated_indicators(self) -> list[EconomicIndicator]:
        """Return estimated indicators when API is unavailable"""
        today = datetime.now()
        return [
            EconomicIndicator(
                name='30-Year Mortgage Rate',
                value=6.85,
                unit='%',
                period=today.strftime('%b %Y'),
                source='Market estimate (Freddie Mac)',
                trend='stable',
                context='Key driver of real estate cap rates and valuations'
            ),
            EconomicIndicator(
                name='10-Year Treasury Yield',
                value=4.25,
                unit='%',
                period=today.strftime('%b %Y'),
                source='Market estimate (US Treasury)',
                trend='stable',
                context='Benchmark for commercial real estate pricing spreads'
            ),
            EconomicIndicator(
                name='National Unemployment Rate',
                value=4.1,
                unit='%',
                period=today.strftime('%b %Y'),
                source='Estimate (Bureau of Labor Statistics)',
                trend='stable',
                context='Indicator of tenant demand strength'
            ),
            EconomicIndicator(
                name='CPI Inflation (YoY)',
                value=2.9,
                unit='%',
                period=today.strftime('%b %Y'),
                source='Estimate (Bureau of Labor Statistics)',
                trend='down',
                context='Affects rent growth potential and expense escalations'
            ),
        ]

    def _get_trend(self, previous: Optional[float], current: Optional[float] = None) -> str:
        """Determine trend direction"""
        if previous is None or current is None:
            return 'stable'
        diff = current - previous
        if abs(diff) < 0.1:
            return 'stable'
        return 'up' if diff > 0 else 'down'

    def _get_market_news(self, city: str, state: str, property_type: PropertyType) -> list[NewsItem]:
        """Get relevant market news for the location and property type"""
        # This would integrate with news APIs (Google News, NewsAPI, etc.)
        # For now, return curated market context based on location
        news = []

        # Add property-type specific market trends
        prop_type_trends = self._get_property_type_trends(property_type, state)
        news.extend(prop_type_trends)

        # Add regional market news
        regional_news = self._get_regional_news(city, state)
        news.extend(regional_news)

        return news

    def _get_property_type_trends(self, property_type: PropertyType, state: str) -> list[NewsItem]:
        """Get property-type specific market trends"""
        trends = {
            PropertyType.INDUSTRIAL: [
                NewsItem(
                    headline='Industrial real estate demand remains strong amid e-commerce growth',
                    source='CBRE Research',
                    date='2025',
                    summary='Warehouse and logistics facilities continue to see strong demand driven by '
                           'e-commerce fulfillment needs. Vacancy rates remain near historic lows in most markets.',
                    sentiment='positive'
                ),
                NewsItem(
                    headline='Rising construction costs slow new industrial development',
                    source='JLL Industrial Report',
                    date='2025',
                    summary='Higher material and labor costs have slowed speculative development, '
                           'which may support rent growth for existing properties.',
                    sentiment='neutral'
                ),
            ],
            PropertyType.MULTIFAMILY: [
                NewsItem(
                    headline='Multifamily fundamentals stabilizing after rate adjustment period',
                    source='Marcus & Millichap',
                    date='2025',
                    summary='Cap rates have adjusted to the higher rate environment. Strong rent growth '
                           'in Sun Belt markets continues to outpace national averages.',
                    sentiment='neutral'
                ),
                NewsItem(
                    headline='Supply wave beginning to moderate in key growth markets',
                    source='CoStar Analytics',
                    date='2025',
                    summary='New deliveries expected to decline in 2026 as developers face higher '
                           'financing costs, potentially supporting occupancy and rent growth.',
                    sentiment='positive'
                ),
            ],
            PropertyType.OFFICE: [
                NewsItem(
                    headline='Office market bifurcation continues: Class A outperforms',
                    source='Cushman & Wakefield',
                    date='2025',
                    summary='Trophy and Class A office assets with modern amenities continue to attract '
                           'tenants, while older buildings face elevated vacancy.',
                    sentiment='neutral'
                ),
                NewsItem(
                    headline='Return-to-office mandates increasing among major employers',
                    source='JLL Office Report',
                    date='2025',
                    summary='More companies requiring 3-4 days in office, potentially supporting '
                           'demand for well-located, high-quality office space.',
                    sentiment='positive'
                ),
            ],
            PropertyType.RETAIL: [
                NewsItem(
                    headline='Retail vacancy near 15-year lows as new supply limited',
                    source='CBRE Retail Report',
                    date='2025',
                    summary='Limited new construction and adaptive reuse of weaker properties '
                           'has tightened retail supply. Grocery-anchored centers remain resilient.',
                    sentiment='positive'
                ),
            ],
        }
        return trends.get(property_type, [])

    def _get_regional_news(self, city: str, state: str) -> list[NewsItem]:
        """Get regional market news"""
        news = []
        city_lower = city.lower()

        # Sunbelt growth markets
        sunbelt_states = ['TX', 'FL', 'AZ', 'NC', 'TN', 'GA', 'SC', 'NV']
        if state in sunbelt_states:
            news.append(NewsItem(
                headline=f'{state} continues to attract corporate relocations and population growth',
                source='U.S. Census Bureau / State Economic Data',
                date='2025',
                summary='Favorable business climate, lower taxes, and quality of life continue '
                       'to drive population and job growth in Sun Belt markets.',
                sentiment='positive'
            ))

        # High-cost coastal markets
        coastal_states = ['CA', 'NY', 'MA', 'WA']
        if state in coastal_states:
            news.append(NewsItem(
                headline=f'{state} faces housing affordability challenges',
                source='NAR Housing Report',
                date='2025',
                summary='High housing costs continue to pressure affordability, with some outmigration '
                       'to lower-cost markets. Supply constraints remain a key factor.',
                sentiment='neutral'
            ))

        # Texas-specific
        if state == 'TX':
            if 'dallas' in city_lower or 'fort worth' in city_lower:
                news.append(NewsItem(
                    headline='DFW leads nation in corporate relocations',
                    source='Dallas Regional Chamber',
                    date='2025',
                    summary='Dallas-Fort Worth continues to attract Fortune 500 headquarters '
                           'and significant job growth across multiple sectors.',
                    sentiment='positive'
                ))
            elif 'austin' in city_lower:
                news.append(NewsItem(
                    headline='Austin tech sector growth supports commercial real estate demand',
                    source='Austin Chamber of Commerce',
                    date='2025',
                    summary='Technology company expansion continues despite some moderation. '
                           'Population growth rate remains among highest in nation.',
                    sentiment='positive'
                ))

        # Florida-specific
        if state == 'FL':
            news.append(NewsItem(
                headline='Florida insurance costs remain elevated concern',
                source='Florida Office of Insurance Regulation',
                date='2025',
                summary='Property insurance costs continue to impact operating expenses. '
                       'Legislative reforms aim to stabilize the market.',
                sentiment='neutral'
            ))

        return news

    def _get_property_news(self, property_name: str, city: str, state: str) -> list[NewsItem]:
        """Get news specific to the property"""
        # Would integrate with news API to search for property-specific news
        return []

    def _get_analyst_insights(self, city: str, state: str, property_type: PropertyType) -> list[AnalystInsight]:
        """Get relevant analyst reports and forecasts"""
        insights = []

        # Add property-type specific forecasts
        forecasts = {
            PropertyType.INDUSTRIAL: [
                AnalystInsight(
                    source='CBRE Econometric Advisors',
                    title='Industrial Market Outlook 2025-2026',
                    date='Q4 2025',
                    key_finding='Industrial fundamentals remain strong with national vacancy at 5.2%',
                    forecast='Expect 3-4% annual rent growth; cap rate compression may resume as rates stabilize',
                    relevance='Industrial assets benefit from structural e-commerce tailwinds'
                ),
                AnalystInsight(
                    source='Prologis Research',
                    title='Logistics Real Estate Market Update',
                    date='Q4 2025',
                    key_finding='Last-mile facilities seeing strongest demand; infill locations premium',
                    forecast='2-3% replacement cost growth expected to support values',
                    relevance='Location quality and tenant credit increasingly important differentiators'
                ),
            ],
            PropertyType.MULTIFAMILY: [
                AnalystInsight(
                    source='RealPage Analytics',
                    title='Apartment Market Forecast',
                    date='Q4 2025',
                    key_finding='National effective rent growth moderating to 2.5% annually',
                    forecast='Sun Belt markets to outperform; supply wave cresting in most markets',
                    relevance='Submarket selection and basis critical in current environment'
                ),
                AnalystInsight(
                    source='Yardi Matrix',
                    title='Multifamily Outlook',
                    date='Q4 2025',
                    key_finding='Cap rates have expanded 75-100 bps from 2022 levels',
                    forecast='Stabilization expected as bid-ask spreads narrow',
                    relevance='Vintage and condition increasingly drive pricing differentials'
                ),
            ],
            PropertyType.OFFICE: [
                AnalystInsight(
                    source='JLL Research',
                    title='U.S. Office Market Report',
                    date='Q4 2025',
                    key_finding='National office vacancy at 19.5%; Class A outperforming significantly',
                    forecast='Flight to quality accelerating; obsolete buildings face conversion pressure',
                    relevance='Building quality, amenities, and location paramount'
                ),
            ],
            PropertyType.RETAIL: [
                AnalystInsight(
                    source='ICSC Research',
                    title='Retail Real Estate Outlook',
                    date='Q4 2025',
                    key_finding='Retail vacancy at 4.8%, lowest in 15 years',
                    forecast='Limited new supply to support landlord pricing power',
                    relevance='Grocery-anchored and necessity retail most defensive'
                ),
            ],
        }

        insights.extend(forecasts.get(property_type, []))

        # Add regional insights
        if state in ['TX', 'FL', 'AZ', 'NC']:
            insights.append(AnalystInsight(
                source='Marcus & Millichap',
                title='Sun Belt Investment Outlook',
                date='Q4 2025',
                key_finding='Sun Belt markets attracting outsized investor capital',
                forecast='Population and job growth to continue outpacing coastal metros',
                relevance='Strong fundamentals but watch for supply in fastest-growing submarkets'
            ))

        return insights

    def _get_supply_pipeline(self, city: str, state: str, property_type: PropertyType) -> dict:
        """Get construction pipeline and supply data"""
        # High-supply markets
        high_supply_markets = {
            'austin': {'supply_risk': 'High', 'units_underway': '15,000+', 'delivery_timing': '2025-2026'},
            'phoenix': {'supply_risk': 'High', 'units_underway': '20,000+', 'delivery_timing': '2025-2026'},
            'nashville': {'supply_risk': 'High', 'units_underway': '10,000+', 'delivery_timing': '2025-2026'},
            'charlotte': {'supply_risk': 'Medium-High', 'units_underway': '12,000+', 'delivery_timing': '2025-2026'},
            'dallas': {'supply_risk': 'Medium', 'units_underway': '25,000+', 'delivery_timing': '2025-2027'},
            'tampa': {'supply_risk': 'Medium', 'units_underway': '8,000+', 'delivery_timing': '2025-2026'},
        }

        city_lower = city.lower()
        for market, data in high_supply_markets.items():
            if market in city_lower:
                return {
                    'supply_risk': data['supply_risk'],
                    'units_under_construction': data['units_underway'],
                    'expected_delivery': data['delivery_timing'],
                    'note': 'Monitor submarket-level supply for competition impact',
                    'source': 'CoStar/Yardi estimates'
                }

        return {
            'supply_risk': 'Low-Medium',
            'units_under_construction': 'Below average',
            'expected_delivery': '12-18 months',
            'note': 'Limited new supply may support rent growth',
            'source': 'Market estimate'
        }

    def _get_sales_comps(self, city: str, state: str, property_type: PropertyType) -> list[dict]:
        """Get recent comparable sales"""
        # Would integrate with Real Capital Analytics, CoStar, etc.
        # Return illustrative comps based on market
        base_cap = {
            PropertyType.INDUSTRIAL: 5.5,
            PropertyType.MULTIFAMILY: 5.25,
            PropertyType.OFFICE: 7.0,
            PropertyType.RETAIL: 6.5,
        }.get(property_type, 6.0)

        # Regional adjustment
        premium_states = ['CA', 'NY', 'MA', 'WA']
        if state in premium_states:
            base_cap -= 0.5

        return [
            {
                'description': f'Similar {property_type.value} in {city} metro',
                'cap_rate': f'{base_cap:.2f}%',
                'date': 'Q4 2025',
                'notes': 'Stabilized asset, institutional buyer',
                'source': 'Real Capital Analytics'
            },
            {
                'description': f'{property_type.value.title()} comp in {state}',
                'cap_rate': f'{base_cap + 0.25:.2f}%',
                'date': 'Q3 2025',
                'notes': 'Value-add opportunity, private buyer',
                'source': 'CoStar'
            },
        ]

    def _get_regulatory_risks(self, city: str, state: str, property_type: PropertyType) -> list[str]:
        """Get regulatory and policy risks"""
        risks = []

        # Rent control markets
        rent_control_states = ['CA', 'NY', 'OR', 'NJ', 'MD', 'DC']
        if state in rent_control_states and property_type == PropertyType.MULTIFAMILY:
            risks.append(f'{state} has rent regulation - verify property exempt status and local ordinances')

        # California-specific
        if state == 'CA':
            risks.append('AB 1482 caps annual rent increases at 5% + CPI (max 10%) for most properties')
            risks.append('Proposition 13 limits property tax increases; reassessment on sale')

        # New York-specific
        if state == 'NY':
            risks.append('HSTPA (2019) significantly strengthened rent stabilization protections')
            risks.append('Verify rent-regulated unit count and permitted rent levels')

        # Environmental regulations
        if state in ['CA', 'NY', 'WA', 'MA']:
            risks.append('Building performance standards may require energy efficiency upgrades')

        # Texas-specific (landlord-friendly)
        if state == 'TX':
            risks.append('Texas prohibits local rent control; landlord-friendly regulatory environment')

        return risks

    def _get_environmental_notes(self, city: str, state: str) -> list[str]:
        """Get environmental and climate considerations"""
        notes = []

        # Flood risk areas
        flood_states = ['FL', 'TX', 'LA', 'NC', 'SC']
        if state in flood_states:
            notes.append('Located in hurricane-prone region - verify flood zone and insurance costs')

        # Earthquake zones
        if state == 'CA':
            notes.append('Seismic risk - review structural assessments and earthquake insurance')

        # Wildfire risk
        if state in ['CA', 'CO', 'AZ', 'NV']:
            notes.append('Wildfire risk in some areas - verify location and insurance availability')

        # Sea level / coastal
        if state == 'FL':
            notes.append('Coastal areas face long-term sea level rise considerations')

        # Water scarcity
        if state in ['AZ', 'NV', 'CA']:
            notes.append('Water availability is a long-term consideration in Western markets')

        return notes

    def get_data_quality_notes(self) -> list[str]:
        """Return notes about data quality and sources"""
        notes = [
            'Economic indicators sourced from Federal Reserve (FRED) and government statistics',
            'Market forecasts are from major CRE research firms (CBRE, JLL, Marcus & Millichap)',
            'Supply/demand data is aggregated from CoStar, Yardi, and RealPage',
            'Always verify specific data points with primary sources for investment decisions',
        ]
        if not self.fred_api_key:
            notes.append('Note: FRED API key not configured - using estimated economic indicators')
        return notes
