"""PDF Report Generator for Real Estate OM Analysis"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from .models import OMAnalysis, Finding, RiskLevel, PropertyType


class PDFReportGenerator:
    """Generates professional PDF reports from OM analysis"""

    # Color scheme
    COLORS = {
        'primary': colors.HexColor('#1a365d'),      # Dark blue
        'secondary': colors.HexColor('#2c5282'),    # Medium blue
        'accent': colors.HexColor('#3182ce'),       # Light blue
        'success': colors.HexColor('#276749'),      # Green
        'warning': colors.HexColor('#c05621'),      # Orange
        'danger': colors.HexColor('#c53030'),       # Red
        'light_gray': colors.HexColor('#f7fafc'),
        'gray': colors.HexColor('#718096'),
        'dark_gray': colors.HexColor('#2d3748'),
    }

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.COLORS['primary'],
            spaceAfter=20,
            alignment=TA_CENTER,
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.COLORS['primary'],
            spaceBefore=15,
            spaceAfter=10,
            borderPadding=5,
        ))

        # Subsection header
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=self.COLORS['secondary'],
            spaceBefore=10,
            spaceAfter=6,
        ))

        # Custom body text (BodyText already exists in base styles)
        self.styles.add(ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['dark_gray'],
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ))

        # Finding styles
        self.styles.add(ParagraphStyle(
            name='ProText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['success'],
            leftIndent=15,
            spaceAfter=4,
        ))

        self.styles.add(ParagraphStyle(
            name='ConText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['warning'],
            leftIndent=15,
            spaceAfter=4,
        ))

        self.styles.add(ParagraphStyle(
            name='RedFlagText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['danger'],
            leftIndent=15,
            spaceAfter=4,
        ))

        # Metric value style
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.COLORS['primary'],
            alignment=TA_RIGHT,
        ))

        # Small text for details
        self.styles.add(ParagraphStyle(
            name='DetailText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['gray'],
            leftIndent=25,
            spaceAfter=8,
        ))

    def generate_report(self, analysis: OMAnalysis, output_path: str) -> str:
        """Generate a PDF report from the analysis"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build the document content
        story = []

        # Title and header
        story.extend(self._build_header(analysis))

        # Executive Summary
        story.extend(self._build_executive_summary(analysis))

        # Property Details
        story.extend(self._build_property_section(analysis))

        # Financial Metrics
        story.extend(self._build_financials_section(analysis))

        # Deal Terms
        story.extend(self._build_deal_terms_section(analysis))

        # Sponsor Fees
        story.extend(self._build_fees_section(analysis))

        # Market Data (if available)
        if self._has_market_data(analysis):
            story.extend(self._build_market_section(analysis))

        # Page break before analysis
        story.append(PageBreak())

        # Detailed Analysis
        story.extend(self._build_analysis_section(analysis))

        # Build the PDF
        doc.build(story)
        return output_path

    def _build_header(self, analysis: OMAnalysis) -> list:
        """Build the report header"""
        elements = []

        # Property name as title
        property_name = analysis.property.name or "Real Estate Investment"
        elements.append(Paragraph(property_name, self.styles['ReportTitle']))

        # Subtitle with location
        location_parts = []
        if analysis.property.city:
            location_parts.append(analysis.property.city)
        if analysis.property.state:
            location_parts.append(analysis.property.state)
        if location_parts:
            location = ", ".join(location_parts)
            elements.append(Paragraph(
                f"<i>{location}</i>",
                ParagraphStyle(
                    'Subtitle',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    textColor=self.COLORS['gray'],
                    alignment=TA_CENTER,
                    spaceAfter=5,
                )
            ))

        # Report date
        elements.append(Paragraph(
            f"Analysis Report - {datetime.now().strftime('%B %d, %Y')}",
            ParagraphStyle(
                'DateLine',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=self.COLORS['gray'],
                alignment=TA_CENTER,
                spaceAfter=20,
            )
        ))

        # Horizontal line
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=self.COLORS['primary'],
            spaceAfter=20,
        ))

        return elements

    def _build_executive_summary(self, analysis: OMAnalysis) -> list:
        """Build the executive summary section"""
        elements = []
        elements.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))

        # Score and recommendation box
        score = analysis.overall_score or 0
        recommendation = analysis.recommendation or "Analysis pending"

        # Determine score color
        if score >= 60:
            score_color = self.COLORS['success']
        elif score >= 45:
            score_color = self.COLORS['warning']
        else:
            score_color = self.COLORS['danger']

        # Summary table
        summary_data = [
            ['Deal Score', f'{score}/100'],
            ['Recommendation', recommendation],
            ['Pros Identified', str(len(analysis.pros))],
            ['Cons Identified', str(len(analysis.cons))],
            ['Red Flags', str(len(analysis.red_flags))],
        ]

        summary_table = Table(summary_data, colWidths=[2.5 * inch, 4 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS['light_gray']),
            ('TEXTCOLOR', (0, 0), (0, -1), self.COLORS['primary']),
            ('TEXTCOLOR', (1, 0), (1, 0), score_color),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTSIZE', (1, 0), (1, 0), 14),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS['gray']),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 15))

        # Quick highlights
        if analysis.pros:
            elements.append(Paragraph("Key Strengths:", self.styles['SubsectionHeader']))
            for pro in analysis.pros[:3]:  # Top 3 pros
                elements.append(Paragraph(
                    f"+ {pro.description}",
                    self.styles['ProText']
                ))

        if analysis.red_flags:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("Critical Concerns:", self.styles['SubsectionHeader']))
            for flag in analysis.red_flags[:3]:  # Top 3 red flags
                elements.append(Paragraph(
                    f"! {flag.description}",
                    self.styles['RedFlagText']
                ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_property_section(self, analysis: OMAnalysis) -> list:
        """Build the property details section"""
        elements = []
        elements.append(Paragraph("PROPERTY DETAILS", self.styles['SectionHeader']))

        prop = analysis.property
        data = []

        if prop.property_type and prop.property_type != PropertyType.UNKNOWN:
            data.append(['Property Type', prop.property_type.value])
        if prop.address:
            data.append(['Address', prop.address])
        if prop.city or prop.state:
            location = f"{prop.city or ''}, {prop.state or ''} {prop.zip_code or ''}".strip(', ')
            data.append(['Location', location])
        if prop.year_built:
            age = datetime.now().year - prop.year_built
            data.append(['Year Built', f"{prop.year_built} ({age} years old)"])
        if prop.total_units:
            data.append(['Total Units/Buildings', str(prop.total_units)])
        if prop.num_buildings:
            data.append(['Number of Buildings', str(prop.num_buildings)])
        if prop.num_tenants:
            data.append(['Number of Tenants', str(prop.num_tenants)])
        if prop.total_sqft:
            data.append(['Total Square Feet', f"{prop.total_sqft:,.0f} SF"])
        if prop.walt_years:
            data.append(['WALT (Lease Term)', f"{prop.walt_years:.1f} years"])
        if prop.lot_size_acres:
            data.append(['Lot Size', f"{prop.lot_size_acres:.2f} acres"])
        if prop.amenities:
            data.append(['Features', ', '.join(prop.amenities[:5])])

        if data:
            table = self._create_data_table(data)
            elements.append(table)
        else:
            elements.append(Paragraph(
                "Property details not available in the offering memorandum.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_financials_section(self, analysis: OMAnalysis) -> list:
        """Build the financial metrics section"""
        elements = []
        elements.append(Paragraph("FINANCIAL METRICS", self.styles['SectionHeader']))

        fin = analysis.financials
        data = []

        if fin.asking_price:
            data.append(['Asking Price', f"${fin.asking_price:,.0f}"])
        if fin.price_per_unit:
            data.append(['Price Per Unit', f"${fin.price_per_unit:,.0f}"])
        if fin.price_per_sqft:
            data.append(['Price Per SF', f"${fin.price_per_sqft:,.2f}"])
        if fin.current_cap_rate:
            data.append(['Current Cap Rate', f"{fin.current_cap_rate:.2%}"])
        if fin.proforma_cap_rate:
            data.append(['Exit/Proforma Cap Rate', f"{fin.proforma_cap_rate:.2%}"])
        if fin.current_noi:
            data.append(['Current NOI', f"${fin.current_noi:,.0f}"])
        if fin.proforma_noi:
            data.append(['Proforma NOI', f"${fin.proforma_noi:,.0f}"])
        if fin.current_occupancy:
            data.append(['Occupancy', f"{fin.current_occupancy:.1%}"])
        if fin.average_rent:
            data.append(['Average Rent', f"${fin.average_rent:,.2f}"])
        if fin.market_rent:
            data.append(['Market Rent', f"${fin.market_rent:,.2f}"])
        if fin.expense_ratio:
            data.append(['Expense Ratio', f"{fin.expense_ratio:.1%}"])

        # Return metrics
        elements.append(Paragraph("Returns", self.styles['SubsectionHeader']))
        return_data = []
        if fin.irr_projected:
            return_data.append(['Projected IRR', f"{fin.irr_projected:.1%}"])
        if fin.equity_multiple:
            return_data.append(['Equity Multiple', f"{fin.equity_multiple:.2f}x"])
        if fin.cash_on_cash_return:
            return_data.append(['Cash-on-Cash Return', f"{fin.cash_on_cash_return:.1%}"])

        if data:
            elements.append(Paragraph("Valuation & Income", self.styles['SubsectionHeader']))
            table = self._create_data_table(data)
            elements.append(table)

        if return_data:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("Projected Returns", self.styles['SubsectionHeader']))
            table = self._create_data_table(return_data)
            elements.append(table)

        if not data and not return_data:
            elements.append(Paragraph(
                "Financial metrics not available in the offering memorandum.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_deal_terms_section(self, analysis: OMAnalysis) -> list:
        """Build the deal terms section"""
        elements = []
        elements.append(Paragraph("DEAL TERMS", self.styles['SectionHeader']))

        terms = analysis.deal_terms
        data = []

        if terms.loan_amount:
            data.append(['Loan Amount', f"${terms.loan_amount:,.0f}"])
        if terms.loan_to_value:
            data.append(['Loan-to-Value (LTV)', f"{terms.loan_to_value:.1%}"])
        if terms.interest_rate:
            data.append(['Interest Rate', f"{terms.interest_rate:.2%}"])
        if terms.loan_type:
            data.append(['Loan Type', terms.loan_type])
        if terms.loan_term_years:
            data.append(['Loan Term', f"{terms.loan_term_years} years"])
        if terms.amortization_years:
            data.append(['Amortization', f"{terms.amortization_years} years"])
        if terms.minimum_investment:
            data.append(['Minimum Investment', f"${terms.minimum_investment:,.0f}"])
        if terms.preferred_return:
            data.append(['Preferred Return', f"{terms.preferred_return:.1%}"])
        if terms.profit_split:
            data.append(['Profit Split (LP/GP)', terms.profit_split])
        if terms.hold_period_years:
            data.append(['Target Hold Period', f"{terms.hold_period_years} years"])

        if data:
            table = self._create_data_table(data)
            elements.append(table)
        else:
            elements.append(Paragraph(
                "Deal terms not available in the offering memorandum.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_fees_section(self, analysis: OMAnalysis) -> list:
        """Build the sponsor fees section"""
        elements = []
        elements.append(Paragraph("SPONSOR FEES", self.styles['SectionHeader']))

        fees = analysis.fees
        data = []

        if fees.acquisition_fee:
            data.append(['Acquisition Fee', f"{fees.acquisition_fee:.2%}"])
        if fees.asset_management_fee:
            data.append(['Asset Management Fee', f"{fees.asset_management_fee:.2%} annually"])
        if fees.property_management_fee:
            data.append(['Property Management Fee', f"{fees.property_management_fee:.2%}"])
        if fees.construction_management_fee:
            data.append(['Construction Mgmt Fee', f"{fees.construction_management_fee:.2%}"])
        if fees.disposition_fee:
            data.append(['Disposition Fee', f"{fees.disposition_fee:.2%}"])
        if fees.refinance_fee:
            data.append(['Refinance Fee', f"{fees.refinance_fee:.2%}"])

        # Total fee load
        if fees.estimated_total_fees_over_hold:
            data.append(['Est. Total Fees (over hold)', f"{fees.estimated_total_fees_over_hold:.1%}"])

        if data:
            table = self._create_data_table(data)
            elements.append(table)

            # Add benchmark note
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                "<i>Industry benchmarks: Acquisition 1%, Asset Mgmt 1.5%/yr, Property Mgmt 5%, Disposition 1%</i>",
                ParagraphStyle(
                    'BenchmarkNote',
                    parent=self.styles['Normal'],
                    fontSize=8,
                    textColor=self.COLORS['gray'],
                )
            ))
        else:
            elements.append(Paragraph(
                "Fee structure not disclosed in the offering memorandum. Request detailed fee schedule.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _has_market_data(self, analysis: OMAnalysis) -> bool:
        """Check if there's meaningful market data to display"""
        market = analysis.market_data
        return any([
            market.market_vacancy_rate,
            market.market_rent_psf,
            market.market_cap_rate,
            market.rent_growth_1yr,
            market.job_growth,
            market.population_growth,
            market.median_household_income,
        ])

    def _build_market_section(self, analysis: OMAnalysis) -> list:
        """Build the market data section"""
        elements = []
        elements.append(Paragraph("MARKET DATA", self.styles['SectionHeader']))

        market = analysis.market_data
        data = []

        if market.market_vacancy_rate:
            data.append(['Market Vacancy Rate', f"{market.market_vacancy_rate:.1%}"])
        if market.market_rent_psf:
            data.append(['Market Rent (PSF)', f"${market.market_rent_psf:.2f}"])
        if market.market_cap_rate:
            data.append(['Market Cap Rate', f"{market.market_cap_rate:.2%}"])
        if market.rent_growth_1yr:
            data.append(['1-Year Rent Growth', f"{market.rent_growth_1yr:.1%}"])
        if market.job_growth:
            data.append(['Job Growth', f"{market.job_growth:.1%}"])
        if market.population_growth:
            data.append(['Population Growth', f"{market.population_growth:.1%}"])
        if market.median_household_income:
            data.append(['Median Household Income', f"${market.median_household_income:,.0f}"])
        if market.unemployment_rate:
            data.append(['Unemployment Rate', f"{market.unemployment_rate:.1%}"])
        if market.walk_score:
            data.append(['Walk Score', str(market.walk_score)])

        if data:
            table = self._create_data_table(data)
            elements.append(table)

        if market.major_employers:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("Major Employers:", self.styles['SubsectionHeader']))
            elements.append(Paragraph(
                ", ".join(market.major_employers[:5]),
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_analysis_section(self, analysis: OMAnalysis) -> list:
        """Build the detailed analysis section"""
        elements = []
        elements.append(Paragraph("DETAILED ANALYSIS", self.styles['SectionHeader']))

        # Pros
        if analysis.pros:
            elements.append(Paragraph("Strengths", self.styles['SubsectionHeader']))
            for i, pro in enumerate(analysis.pros, 1):
                elements.append(Paragraph(
                    f"<b>{i}. {pro.description}</b> [{pro.category}]",
                    self.styles['ProText']
                ))
                if pro.details:
                    elements.append(Paragraph(
                        pro.details,
                        self.styles['DetailText']
                    ))
                if pro.actual_value and pro.benchmark_value:
                    elements.append(Paragraph(
                        f"<i>Value: {pro.actual_value} | Benchmark: {pro.benchmark_value}</i>",
                        ParagraphStyle(
                            'MetricDetail',
                            parent=self.styles['Normal'],
                            fontSize=8,
                            textColor=self.COLORS['gray'],
                            leftIndent=25,
                            spaceAfter=10,
                        )
                    ))
            elements.append(Spacer(1, 15))

        # Cons
        if analysis.cons:
            elements.append(Paragraph("Concerns", self.styles['SubsectionHeader']))
            for i, con in enumerate(analysis.cons, 1):
                elements.append(Paragraph(
                    f"<b>{i}. {con.description}</b> [{con.category}]",
                    self.styles['ConText']
                ))
                if con.details:
                    elements.append(Paragraph(
                        con.details,
                        self.styles['DetailText']
                    ))
                if con.actual_value and con.benchmark_value:
                    elements.append(Paragraph(
                        f"<i>Value: {con.actual_value} | Benchmark: {con.benchmark_value}</i>",
                        ParagraphStyle(
                            'MetricDetail',
                            parent=self.styles['Normal'],
                            fontSize=8,
                            textColor=self.COLORS['gray'],
                            leftIndent=25,
                            spaceAfter=10,
                        )
                    ))
            elements.append(Spacer(1, 15))

        # Red Flags
        if analysis.red_flags:
            elements.append(Paragraph("Red Flags", self.styles['SubsectionHeader']))
            for i, flag in enumerate(analysis.red_flags, 1):
                risk_label = f" ({flag.risk_level.value})" if flag.risk_level else ""
                elements.append(Paragraph(
                    f"<b>{i}. {flag.description}</b> [{flag.category}]{risk_label}",
                    self.styles['RedFlagText']
                ))
                if flag.details:
                    elements.append(Paragraph(
                        flag.details,
                        self.styles['DetailText']
                    ))
                if flag.actual_value and flag.benchmark_value:
                    elements.append(Paragraph(
                        f"<i>Value: {flag.actual_value} | Benchmark: {flag.benchmark_value}</i>",
                        ParagraphStyle(
                            'MetricDetail',
                            parent=self.styles['Normal'],
                            fontSize=8,
                            textColor=self.COLORS['gray'],
                            leftIndent=25,
                            spaceAfter=10,
                        )
                    ))
            elements.append(Spacer(1, 15))

        # Final recommendation box
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=self.COLORS['primary'],
            spaceBefore=15,
            spaceAfter=15,
        ))

        elements.append(Paragraph("INVESTMENT RECOMMENDATION", self.styles['SectionHeader']))

        recommendation = analysis.recommendation or "Complete analysis pending"
        score = analysis.overall_score or 0

        # Determine recommendation color
        if score >= 60:
            rec_color = self.COLORS['success']
        elif score >= 45:
            rec_color = self.COLORS['warning']
        else:
            rec_color = self.COLORS['danger']

        elements.append(Paragraph(
            f"<b>{recommendation}</b>",
            ParagraphStyle(
                'FinalRecommendation',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=rec_color,
                alignment=TA_CENTER,
                spaceBefore=10,
                spaceAfter=20,
            )
        ))

        # Disclaimer
        elements.append(Paragraph(
            "<i>Disclaimer: This analysis is for informational purposes only and should not be considered "
            "investment advice. Always conduct your own due diligence and consult with qualified "
            "professionals before making investment decisions.</i>",
            ParagraphStyle(
                'Disclaimer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=self.COLORS['gray'],
                alignment=TA_CENTER,
                spaceBefore=30,
            )
        ))

        return elements

    def _create_data_table(self, data: list) -> Table:
        """Create a consistently styled data table"""
        table = Table(data, colWidths=[2.5 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS['light_gray']),
            ('TEXTCOLOR', (0, 0), (0, -1), self.COLORS['primary']),
            ('TEXTCOLOR', (1, 0), (1, -1), self.COLORS['dark_gray']),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS['gray']),
        ]))
        return table
