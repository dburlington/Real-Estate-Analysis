"""OM Parser - Extracts deal information from Offering Memorandums"""

import re
from pathlib import Path
from typing import Optional
from .models import (
    PropertyDetails, FinancialMetrics, DealTerms,
    PropertyType, OMAnalysis, MarketData
)

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class OMParser:
    """Parser for Real Estate Offering Memorandums"""

    # Regex patterns for extracting data
    PATTERNS = {
        # Property info
        'address': r'(?:address|location|property\s*address)[:\s]*([^\n,]+(?:,\s*[^\n]+)?)',
        'city_state_zip': r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)',
        'units': r'(?:total\s*)?(?:units?|apartment(?:s)?)[:\s]*(\d+)',
        'sqft': r'(?:total\s*)?(?:sf|sq\.?\s*ft\.?|square\s*feet)[:\s]*([\d,]+)',
        'year_built': r'(?:year\s*built|built\s*in|constructed)[:\s]*(\d{4})',
        'lot_size': r'(?:lot\s*size|land\s*area|acreage)[:\s]*([\d.]+)\s*(?:acres?|ac\.?)',

        # Financial metrics
        'asking_price': r'(?:asking\s*price|list\s*price|price|offering\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)?',
        'price_per_unit': r'(?:price\s*per\s*unit|pp[uU])[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'price_per_sqft': r'(?:price\s*per\s*(?:sf|sq\.?\s*ft\.?))[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'cap_rate': r'(?:cap\s*rate|capitalization\s*rate)[:\s]*([\d.]+)\s*%?',
        'noi': r'(?:net\s*operating\s*income|noi)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'occupancy': r'(?:occupancy|occupied)[:\s]*([\d.]+)\s*%?',
        'avg_rent': r'(?:average\s*rent|avg\.?\s*rent|rent\s*per\s*unit)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'market_rent': r'(?:market\s*rent)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'gpi': r'(?:gross\s*potential\s*income|gpi)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'egi': r'(?:effective\s*gross\s*income|egi)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expenses': r'(?:operating\s*expenses?|opex|total\s*expenses?)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expense_ratio': r'(?:expense\s*ratio|operating\s*expense\s*ratio)[:\s]*([\d.]+)\s*%?',
        'coc': r'(?:cash[\s-]*on[\s-]*cash|coc)[:\s]*([\d.]+)\s*%?',
        'irr': r'(?:irr|internal\s*rate\s*of\s*return)[:\s]*([\d.]+)\s*%?',
        'equity_multiple': r'(?:equity\s*multiple|em)[:\s]*([\d.]+)\s*x?',

        # Loan terms
        'loan_amount': r'(?:loan\s*amount|debt|mortgage)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)?',
        'ltv': r'(?:ltv|loan[\s-]*to[\s-]*value)[:\s]*([\d.]+)\s*%?',
        'interest_rate': r'(?:interest\s*rate|rate)[:\s]*([\d.]+)\s*%?',
        'loan_term': r'(?:loan\s*term|term)[:\s]*(\d+)\s*(?:years?|yrs?)?',
        'amortization': r'(?:amortization|amort\.?)[:\s]*(\d+)\s*(?:years?|yrs?)?',

        # Deal terms
        'min_investment': r'(?:minimum\s*investment|min\.?\s*invest(?:ment)?)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'preferred_return': r'(?:preferred\s*return|pref(?:erred)?\.?\s*return)[:\s]*([\d.]+)\s*%?',
        'profit_split': r'(?:profit\s*split|waterfall|split)[:\s]*(\d+)\s*/\s*(\d+)',
        'hold_period': r'(?:hold\s*period|holding\s*period|investment\s*period)[:\s]*(\d+)\s*(?:years?|yrs?)?',
    }

    PROPERTY_TYPES = {
        'multifamily': PropertyType.MULTIFAMILY,
        'multi-family': PropertyType.MULTIFAMILY,
        'apartment': PropertyType.MULTIFAMILY,
        'residential': PropertyType.MULTIFAMILY,
        'office': PropertyType.OFFICE,
        'retail': PropertyType.RETAIL,
        'shopping': PropertyType.RETAIL,
        'industrial': PropertyType.INDUSTRIAL,
        'warehouse': PropertyType.INDUSTRIAL,
        'logistics': PropertyType.INDUSTRIAL,
        'mixed-use': PropertyType.MIXED_USE,
        'mixed use': PropertyType.MIXED_USE,
        'hotel': PropertyType.HOTEL,
        'hospitality': PropertyType.HOTEL,
        'self-storage': PropertyType.SELF_STORAGE,
        'storage': PropertyType.SELF_STORAGE,
        'senior': PropertyType.SENIOR_HOUSING,
        'assisted living': PropertyType.SENIOR_HOUSING,
        'student': PropertyType.STUDENT_HOUSING,
    }

    def __init__(self):
        self.raw_text = ""

    def parse_file(self, file_path: str) -> OMAnalysis:
        """Parse an OM from a file (PDF or text)"""
        path = Path(file_path)

        if path.suffix.lower() == '.pdf':
            if not PDF_SUPPORT:
                raise ImportError("PDF support requires pdfplumber. Install with: pip install pdfplumber")
            self.raw_text = self._extract_pdf_text(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.raw_text = f.read()

        return self._parse_text(self.raw_text)

    def parse_text(self, text: str) -> OMAnalysis:
        """Parse an OM from raw text"""
        self.raw_text = text
        return self._parse_text(text)

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from a PDF file"""
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    def _parse_text(self, text: str) -> OMAnalysis:
        """Parse text content and extract all deal information"""
        text_lower = text.lower()

        property_details = self._extract_property_details(text, text_lower)
        financials = self._extract_financials(text, text_lower)
        deal_terms = self._extract_deal_terms(text, text_lower)

        # Calculate derived metrics
        self._calculate_derived_metrics(financials, property_details)

        return OMAnalysis(
            property=property_details,
            financials=financials,
            deal_terms=deal_terms,
            market_data=MarketData(),
            raw_text=text
        )

    def _extract_number(self, text: str, pattern: str, multiplier: float = 1.0) -> Optional[float]:
        """Extract a number using a regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value_str = match.group(1).replace(',', '')
                value = float(value_str) * multiplier
                # Check for million indicator
                if 'million' in text[match.start():match.end()+10].lower() or 'M' in match.group(0):
                    if value < 1000:  # Likely already in millions notation
                        value *= 1_000_000
                return value
            except (ValueError, IndexError):
                pass
        return None

    def _extract_property_details(self, text: str, text_lower: str) -> PropertyDetails:
        """Extract property details from text"""
        details = PropertyDetails()

        # Extract property name (usually first prominent line or after "Property:")
        name_match = re.search(r'(?:property\s*name|subject\s*property)[:\s]*([^\n]+)', text_lower)
        if name_match:
            details.name = name_match.group(1).strip().title()

        # Extract address components
        address_match = re.search(self.PATTERNS['address'], text, re.IGNORECASE)
        if address_match:
            details.address = address_match.group(1).strip()

        csz_match = re.search(self.PATTERNS['city_state_zip'], text)
        if csz_match:
            details.city = csz_match.group(1).strip()
            details.state = csz_match.group(2).upper()
            details.zip_code = csz_match.group(3)

        # Extract property type
        for keyword, prop_type in self.PROPERTY_TYPES.items():
            if keyword in text_lower:
                details.property_type = prop_type
                break

        # Extract numeric details
        units = self._extract_number(text, self.PATTERNS['units'])
        if units:
            details.total_units = int(units)

        sqft = self._extract_number(text, self.PATTERNS['sqft'])
        if sqft:
            details.total_sqft = sqft

        year = self._extract_number(text, self.PATTERNS['year_built'])
        if year and 1800 < year < 2030:
            details.year_built = int(year)

        lot_size = self._extract_number(text, self.PATTERNS['lot_size'])
        if lot_size:
            details.lot_size_acres = lot_size

        # Extract amenities
        amenity_keywords = [
            'pool', 'gym', 'fitness', 'clubhouse', 'parking', 'garage',
            'laundry', 'playground', 'dog park', 'business center',
            'concierge', 'rooftop', 'balcony', 'patio', 'storage'
        ]
        details.amenities = [a for a in amenity_keywords if a in text_lower]

        return details

    def _extract_financials(self, text: str, text_lower: str) -> FinancialMetrics:
        """Extract financial metrics from text"""
        financials = FinancialMetrics()

        # Asking price - handle millions
        price_match = re.search(
            r'(?:asking\s*price|list\s*price|offering\s*price|price)[:\s]*\$?([\d,.]+)\s*(M|million)?',
            text, re.IGNORECASE
        )
        if price_match:
            price = float(price_match.group(1).replace(',', ''))
            if price_match.group(2) or price < 1000:
                price *= 1_000_000
            financials.asking_price = price

        financials.price_per_unit = self._extract_number(text, self.PATTERNS['price_per_unit'])
        financials.price_per_sqft = self._extract_number(text, self.PATTERNS['price_per_sqft'])

        # Cap rates
        cap_matches = re.findall(r'(?:(\w+)\s+)?cap\s*rate[:\s]*([\d.]+)\s*%?', text, re.IGNORECASE)
        for prefix, rate in cap_matches:
            rate_val = float(rate)
            if rate_val > 1:  # Convert from percentage
                rate_val /= 100
            if prefix and 'pro' in prefix.lower():
                financials.proforma_cap_rate = rate_val
            elif prefix and ('current' in prefix.lower() or 'in' in prefix.lower() or 'actual' in prefix.lower()):
                financials.current_cap_rate = rate_val
            elif not financials.current_cap_rate:
                financials.current_cap_rate = rate_val

        # NOI
        noi_matches = re.findall(r'(?:(\w+)\s+)?(?:net\s*operating\s*income|noi)[:\s]*\$?([\d,]+)', text, re.IGNORECASE)
        for prefix, noi in noi_matches:
            noi_val = float(noi.replace(',', ''))
            if prefix and 'pro' in prefix.lower():
                financials.proforma_noi = noi_val
            elif not financials.current_noi:
                financials.current_noi = noi_val

        # Occupancy
        occ = self._extract_number(text, self.PATTERNS['occupancy'])
        if occ:
            financials.current_occupancy = occ if occ <= 1 else occ / 100

        financials.average_rent = self._extract_number(text, self.PATTERNS['avg_rent'])
        financials.market_rent = self._extract_number(text, self.PATTERNS['market_rent'])
        financials.gross_potential_income = self._extract_number(text, self.PATTERNS['gpi'])
        financials.effective_gross_income = self._extract_number(text, self.PATTERNS['egi'])
        financials.operating_expenses = self._extract_number(text, self.PATTERNS['expenses'])

        exp_ratio = self._extract_number(text, self.PATTERNS['expense_ratio'])
        if exp_ratio:
            financials.expense_ratio = exp_ratio if exp_ratio <= 1 else exp_ratio / 100

        coc = self._extract_number(text, self.PATTERNS['coc'])
        if coc:
            financials.cash_on_cash_return = coc if coc <= 1 else coc / 100

        irr = self._extract_number(text, self.PATTERNS['irr'])
        if irr:
            financials.irr_projected = irr if irr <= 1 else irr / 100

        financials.equity_multiple = self._extract_number(text, self.PATTERNS['equity_multiple'])

        return financials

    def _extract_deal_terms(self, text: str, text_lower: str) -> DealTerms:
        """Extract deal terms from text"""
        terms = DealTerms()

        # Loan amount
        loan_match = re.search(
            r'(?:loan\s*amount|debt|mortgage)[:\s]*\$?([\d,.]+)\s*(M|million)?',
            text, re.IGNORECASE
        )
        if loan_match:
            loan = float(loan_match.group(1).replace(',', ''))
            if loan_match.group(2) or loan < 1000:
                loan *= 1_000_000
            terms.loan_amount = loan

        ltv = self._extract_number(text, self.PATTERNS['ltv'])
        if ltv:
            terms.loan_to_value = ltv if ltv <= 1 else ltv / 100

        rate = self._extract_number(text, self.PATTERNS['interest_rate'])
        if rate:
            terms.interest_rate = rate if rate <= 1 else rate / 100

        loan_term = self._extract_number(text, self.PATTERNS['loan_term'])
        if loan_term:
            terms.loan_term_years = int(loan_term)

        amort = self._extract_number(text, self.PATTERNS['amortization'])
        if amort:
            terms.amortization_years = int(amort)

        # Loan type
        if 'fixed' in text_lower:
            terms.loan_type = 'Fixed'
        elif 'variable' in text_lower or 'floating' in text_lower:
            terms.loan_type = 'Variable'
        elif 'bridge' in text_lower:
            terms.loan_type = 'Bridge'

        terms.assumable_debt = 'assumable' in text_lower

        terms.minimum_investment = self._extract_number(text, self.PATTERNS['min_investment'])

        pref = self._extract_number(text, self.PATTERNS['preferred_return'])
        if pref:
            terms.preferred_return = pref if pref <= 1 else pref / 100

        split_match = re.search(self.PATTERNS['profit_split'], text, re.IGNORECASE)
        if split_match:
            terms.profit_split = f"{split_match.group(1)}/{split_match.group(2)}"

        hold = self._extract_number(text, self.PATTERNS['hold_period'])
        if hold:
            terms.hold_period_years = int(hold)

        # Prepayment penalty
        prepay_match = re.search(r'prepay(?:ment)?\s*(?:penalty)?[:\s]*([^\n.]+)', text, re.IGNORECASE)
        if prepay_match:
            terms.prepayment_penalty = prepay_match.group(1).strip()

        return terms

    def _calculate_derived_metrics(self, financials: FinancialMetrics, property_details: PropertyDetails):
        """Calculate any derived metrics that weren't explicitly stated"""
        # Price per unit
        if not financials.price_per_unit and financials.asking_price and property_details.total_units:
            financials.price_per_unit = financials.asking_price / property_details.total_units

        # Price per sqft
        if not financials.price_per_sqft and financials.asking_price and property_details.total_sqft:
            financials.price_per_sqft = financials.asking_price / property_details.total_sqft

        # Cap rate from NOI and price
        if not financials.current_cap_rate and financials.current_noi and financials.asking_price:
            financials.current_cap_rate = financials.current_noi / financials.asking_price

        # Expense ratio
        if not financials.expense_ratio and financials.operating_expenses and financials.effective_gross_income:
            financials.expense_ratio = financials.operating_expenses / financials.effective_gross_income
