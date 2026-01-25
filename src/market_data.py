"""Market Data Fetcher - External data for real estate market analysis"""

import os
import json
import time
from typing import Optional
from dataclasses import asdict
import requests
from .models import MarketData, PropertyType


class MarketDataFetcher:
    """Fetches external market data for real estate analysis"""

    # Census Bureau API for demographic data
    CENSUS_API_BASE = "https://api.census.gov/data"

    # Bureau of Labor Statistics API
    BLS_API_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    # HUD Fair Market Rent API
    HUD_API_BASE = "https://www.huduser.gov/hudapi/public"

    # Market benchmarks by property type (national averages)
    MARKET_BENCHMARKS = {
        PropertyType.MULTIFAMILY: {
            'cap_rate': 0.055,  # 5.5%
            'vacancy_rate': 0.065,  # 6.5%
            'expense_ratio': 0.45,  # 45%
            'rent_growth': 0.035,  # 3.5%
        },
        PropertyType.OFFICE: {
            'cap_rate': 0.065,
            'vacancy_rate': 0.12,
            'expense_ratio': 0.40,
            'rent_growth': 0.02,
        },
        PropertyType.RETAIL: {
            'cap_rate': 0.065,
            'vacancy_rate': 0.08,
            'expense_ratio': 0.35,
            'rent_growth': 0.02,
        },
        PropertyType.INDUSTRIAL: {
            'cap_rate': 0.055,
            'vacancy_rate': 0.05,
            'expense_ratio': 0.30,
            'rent_growth': 0.045,
        },
    }

    # Regional cap rate adjustments (premium markets have lower caps)
    REGIONAL_ADJUSTMENTS = {
        # Coastal/Gateway Markets
        'CA': -0.015, 'NY': -0.015, 'MA': -0.01, 'WA': -0.01,
        'FL': -0.005, 'CO': -0.005, 'DC': -0.01,
        # Sunbelt Growth Markets
        'TX': 0.0, 'AZ': 0.0, 'NC': 0.0, 'GA': 0.0, 'TN': 0.0,
        # Midwest/Secondary
        'OH': 0.01, 'MI': 0.01, 'IN': 0.01, 'MO': 0.01,
        'IL': 0.005, 'MN': 0.005, 'WI': 0.01,
    }

    # Metro-level rent data (sample averages per unit/month)
    METRO_RENT_DATA = {
        # High-cost metros
        'San Francisco': 3200, 'New York': 3000, 'Boston': 2800,
        'Los Angeles': 2600, 'Seattle': 2400, 'San Diego': 2500,
        'Miami': 2400, 'Washington': 2300, 'Denver': 2100,
        # Mid-cost metros
        'Austin': 1800, 'Dallas': 1600, 'Atlanta': 1700,
        'Phoenix': 1600, 'Charlotte': 1500, 'Nashville': 1700,
        'Raleigh': 1500, 'Tampa': 1600, 'Orlando': 1500,
        # Lower-cost metros
        'Houston': 1400, 'San Antonio': 1300, 'Chicago': 1600,
        'Philadelphia': 1500, 'Detroit': 1200, 'Cleveland': 1100,
        'Indianapolis': 1200, 'Columbus': 1300, 'Kansas City': 1200,
    }

    # State-level rent growth trends (annual %)
    RENT_GROWTH_BY_STATE = {
        'FL': 0.08, 'TX': 0.06, 'AZ': 0.07, 'TN': 0.06, 'NC': 0.05,
        'GA': 0.05, 'SC': 0.05, 'NV': 0.06, 'ID': 0.07, 'UT': 0.06,
        'CO': 0.04, 'WA': 0.03, 'CA': 0.02, 'NY': 0.02, 'IL': 0.02,
        'OH': 0.03, 'MI': 0.03, 'PA': 0.02,
    }

    # Vacancy rates by state
    VACANCY_BY_STATE = {
        'FL': 0.05, 'TX': 0.07, 'AZ': 0.06, 'CA': 0.04, 'NY': 0.04,
        'WA': 0.05, 'CO': 0.06, 'GA': 0.07, 'NC': 0.06, 'TN': 0.06,
        'OH': 0.08, 'MI': 0.09, 'IL': 0.07, 'PA': 0.07,
    }

    def __init__(self, census_api_key: Optional[str] = None, hud_api_key: Optional[str] = None):
        """Initialize with optional API keys for enhanced data"""
        self.census_api_key = census_api_key or os.getenv('CENSUS_API_KEY')
        self.hud_api_key = hud_api_key or os.getenv('HUD_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'RealEstateOMAnalyzer/1.0'})

    def fetch_market_data(
        self,
        city: str,
        state: str,
        zip_code: str,
        property_type: PropertyType
    ) -> MarketData:
        """Fetch comprehensive market data for a location"""
        market_data = MarketData()

        # Get benchmarks for property type
        benchmarks = self.MARKET_BENCHMARKS.get(
            property_type,
            self.MARKET_BENCHMARKS[PropertyType.MULTIFAMILY]
        )

        # Apply regional adjustments
        regional_adj = self.REGIONAL_ADJUSTMENTS.get(state, 0.005)
        market_data.market_cap_rate = benchmarks['cap_rate'] + regional_adj

        # Get vacancy data
        market_data.market_vacancy_rate = self.VACANCY_BY_STATE.get(state, 0.07)

        # Get rent growth
        market_data.rent_growth_1yr = self.RENT_GROWTH_BY_STATE.get(state, 0.03)
        market_data.rent_growth_5yr = market_data.rent_growth_1yr * 0.8  # Slight moderation

        # Try to get metro-level rent data
        market_data.market_rent_psf = self._get_metro_rent(city, state)

        # Fetch census demographic data
        demo_data = self._fetch_census_demographics(state, zip_code)
        if demo_data:
            market_data.median_household_income = demo_data.get('median_income')
            market_data.population_growth = demo_data.get('population_growth')

        # Fetch employment data
        employment_data = self._fetch_employment_data(state)
        if employment_data:
            market_data.unemployment_rate = employment_data.get('unemployment_rate')
            market_data.job_growth = employment_data.get('job_growth')

        # Fetch HUD fair market rent data
        fmr_data = self._fetch_hud_fmr(state, zip_code)
        if fmr_data and not market_data.market_rent_psf:
            market_data.market_rent_psf = fmr_data.get('fmr_2br', 1500)

        # Get location scores (simplified estimates)
        scores = self._estimate_location_scores(city, state)
        market_data.walk_score = scores.get('walk_score')
        market_data.transit_score = scores.get('transit_score')

        # Get major employers (simplified)
        market_data.major_employers = self._get_major_employers(city, state)

        return market_data

    def _get_metro_rent(self, city: str, state: str) -> Optional[float]:
        """Get metro-level average rent"""
        # Check direct city match
        for metro, rent in self.METRO_RENT_DATA.items():
            if metro.lower() in city.lower() or city.lower() in metro.lower():
                return rent

        # Fallback to state-level estimate
        state_averages = {
            'CA': 2200, 'NY': 2000, 'MA': 2000, 'WA': 1800,
            'FL': 1700, 'CO': 1800, 'TX': 1500, 'GA': 1500,
            'NC': 1400, 'TN': 1400, 'AZ': 1500, 'NV': 1500,
            'OH': 1200, 'MI': 1200, 'IL': 1400, 'PA': 1300,
        }
        return state_averages.get(state, 1400)

    def _fetch_census_demographics(self, state: str, zip_code: str) -> Optional[dict]:
        """Fetch demographic data from Census Bureau API"""
        if not self.census_api_key:
            # Return estimated data based on state
            state_income = {
                'CA': 85000, 'NY': 75000, 'MA': 85000, 'WA': 80000,
                'TX': 65000, 'FL': 60000, 'CO': 75000, 'GA': 62000,
                'NC': 58000, 'TN': 55000, 'AZ': 60000, 'OH': 55000,
            }
            return {
                'median_income': state_income.get(state, 60000),
                'population_growth': 0.01 if state in ['TX', 'FL', 'AZ', 'NC', 'TN'] else 0.005
            }

        try:
            # ACS 5-year estimates for median household income
            url = f"{self.CENSUS_API_BASE}/2022/acs/acs5"
            params = {
                'get': 'B19013_001E',  # Median household income
                'for': f'zip code tabulation area:{zip_code}',
                'key': self.census_api_key
            }
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if len(data) > 1:
                    return {
                        'median_income': float(data[1][0]) if data[1][0] else None,
                        'population_growth': 0.01  # Would need additional call
                    }
        except Exception:
            pass

        return None

    def _fetch_employment_data(self, state: str) -> Optional[dict]:
        """Fetch employment statistics"""
        # State-level unemployment rates (recent estimates)
        unemployment_rates = {
            'CA': 0.048, 'NY': 0.044, 'TX': 0.042, 'FL': 0.032,
            'IL': 0.048, 'PA': 0.042, 'OH': 0.041, 'GA': 0.035,
            'NC': 0.036, 'MI': 0.044, 'AZ': 0.039, 'WA': 0.041,
            'MA': 0.037, 'TN': 0.034, 'CO': 0.035, 'NV': 0.052,
        }

        job_growth_rates = {
            'TX': 0.035, 'FL': 0.038, 'AZ': 0.032, 'NC': 0.028,
            'GA': 0.026, 'TN': 0.025, 'CO': 0.022, 'WA': 0.020,
            'CA': 0.015, 'NY': 0.012, 'IL': 0.010, 'OH': 0.012,
        }

        return {
            'unemployment_rate': unemployment_rates.get(state, 0.04),
            'job_growth': job_growth_rates.get(state, 0.015)
        }

    def _fetch_hud_fmr(self, state: str, zip_code: str) -> Optional[dict]:
        """Fetch HUD Fair Market Rents"""
        if not self.hud_api_key:
            return None

        try:
            url = f"{self.HUD_API_BASE}/fmr/data/{zip_code}"
            headers = {'Authorization': f'Bearer {self.hud_api_key}'}
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'basicdata' in data['data']:
                    basic = data['data']['basicdata']
                    return {
                        'fmr_0br': basic.get('fmr_0'),
                        'fmr_1br': basic.get('fmr_1'),
                        'fmr_2br': basic.get('fmr_2'),
                        'fmr_3br': basic.get('fmr_3'),
                        'fmr_4br': basic.get('fmr_4'),
                    }
        except Exception:
            pass

        return None

    def _estimate_location_scores(self, city: str, state: str) -> dict:
        """Estimate walk and transit scores based on city characteristics"""
        # High walkability/transit cities
        high_scores = ['new york', 'san francisco', 'boston', 'chicago', 'philadelphia', 'washington']
        medium_scores = ['seattle', 'portland', 'denver', 'minneapolis', 'los angeles', 'miami']

        city_lower = city.lower()

        if any(c in city_lower for c in high_scores):
            return {'walk_score': 85, 'transit_score': 80}
        elif any(c in city_lower for c in medium_scores):
            return {'walk_score': 65, 'transit_score': 55}
        else:
            return {'walk_score': 45, 'transit_score': 30}

    def _get_major_employers(self, city: str, state: str) -> list[str]:
        """Get major employers in the area"""
        major_employers_by_state = {
            'TX': ['AT&T', 'ExxonMobil', 'Dell', 'American Airlines', 'Texas Instruments'],
            'CA': ['Apple', 'Google', 'Meta', 'Netflix', 'Salesforce'],
            'NY': ['JPMorgan Chase', 'Verizon', 'Pfizer', 'MetLife', 'Citigroup'],
            'FL': ['Publix', 'Jabil', 'Tech Data', 'World Fuel Services', 'Ryder'],
            'WA': ['Amazon', 'Microsoft', 'Boeing', 'Starbucks', 'Costco'],
            'GA': ['Home Depot', 'UPS', 'Coca-Cola', 'Delta Air Lines', 'Southern Company'],
            'NC': ['Bank of America', 'Lowe\'s', 'Duke Energy', 'Honeywell', 'Nucor'],
            'IL': ['Boeing', 'Walgreens', 'United Airlines', 'Abbott', 'Caterpillar'],
            'AZ': ['Intel', 'Banner Health', 'Honeywell', 'ON Semiconductor', 'Microchip'],
            'CO': ['Lockheed Martin', 'Ball Corporation', 'Arrow Electronics', 'Dish Network', 'Western Union'],
        }
        return major_employers_by_state.get(state, ['Diverse local employers'])

    def get_comparable_sales(self, city: str, state: str, property_type: PropertyType) -> list[dict]:
        """Get comparable sales data (simplified market estimates)"""
        # This would typically integrate with CoStar, Real Capital Analytics, etc.
        base_cap = self.MARKET_BENCHMARKS.get(property_type, {}).get('cap_rate', 0.055)
        regional_adj = self.REGIONAL_ADJUSTMENTS.get(state, 0.005)

        # Generate synthetic comparable data
        return [
            {
                'description': f'Recent {property_type.value} sale in {city}, {state}',
                'cap_rate': base_cap + regional_adj - 0.005,
                'date': '2024 Q4',
            },
            {
                'description': f'Comparable {property_type.value} in metro area',
                'cap_rate': base_cap + regional_adj,
                'date': '2024 Q3',
            },
            {
                'description': f'Larger {property_type.value} portfolio sale',
                'cap_rate': base_cap + regional_adj + 0.005,
                'date': '2024 Q2',
            },
        ]

    def get_supply_pipeline(self, city: str, state: str, property_type: PropertyType) -> dict:
        """Get information about new supply in the market"""
        # High supply growth markets
        high_supply = ['austin', 'phoenix', 'dallas', 'nashville', 'charlotte', 'denver', 'tampa']
        medium_supply = ['atlanta', 'houston', 'raleigh', 'orlando', 'las vegas', 'salt lake']

        city_lower = city.lower()

        if any(c in city_lower for c in high_supply):
            return {
                'supply_risk': 'High',
                'units_under_construction': 'Above average',
                'expected_delivery': '12-24 months',
                'market_absorption': 'Moderate'
            }
        elif any(c in city_lower for c in medium_supply):
            return {
                'supply_risk': 'Medium',
                'units_under_construction': 'Average',
                'expected_delivery': '12-18 months',
                'market_absorption': 'Good'
            }
        else:
            return {
                'supply_risk': 'Low',
                'units_under_construction': 'Below average',
                'expected_delivery': '6-12 months',
                'market_absorption': 'Strong'
            }
