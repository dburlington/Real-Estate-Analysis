"""PDF Report Generator for Real Estate OM Analysis"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .models import OMAnalysis, Finding, RiskLevel


# Color definitions
COLOR_PRIMARY = colors.HexColor("#1a365d")  # Dark blue
COLOR_SECONDARY = colors.HexColor("#2c5282")  # Medium blue
COLOR_ACCENT = colors.HexColor("#3182ce")  # Light blue
COLOR_RED = colors.HexColor("#c53030")  # Red for red flags
COLOR_ORANGE = colors.HexColor("#c05621")  # Orange for warnings
COLOR_GREEN = colors.HexColor("#276749")  # Green for pros
COLOR_GRAY = colors.HexColor("#4a5568")  # Gray for details
COLOR_LIGHT_GRAY = colors.HexColor("#e2e8f0")  # Light gray for backgrounds
COLOR_WHITE = colors.white


def create_styles() -> dict:
    """Create custom paragraph styles for the report"""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    ))

    # Subtitle style
    styles.add(ParagraphStyle(
        name='ReportSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=COLOR_GRAY,
        alignment=TA_CENTER,
        spaceAfter=20
    ))

    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLOR_PRIMARY,
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        borderPadding=(0, 0, 4, 0),
    ))

    # Subsection header
    styles.add(ParagraphStyle(
        name='SubsectionHeader',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=COLOR_SECONDARY,
        spaceBefore=10,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    ))

    # Normal text - modify existing BodyText style
    styles['BodyText'].fontSize = 10
    styles['BodyText'].textColor = COLOR_GRAY
    styles['BodyText'].spaceBefore = 2
    styles['BodyText'].spaceAfter = 2

    # Finding styles
    styles.add(ParagraphStyle(
        name='RedFlagTitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_RED,
        fontName='Helvetica-Bold',
        spaceBefore=6,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name='WarningTitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_ORANGE,
        fontName='Helvetica-Bold',
        spaceBefore=6,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name='ProTitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_GREEN,
        fontName='Helvetica-Bold',
        spaceBefore=6,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name='FindingDetail',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_GRAY,
        leftIndent=15,
        spaceBefore=1,
        spaceAfter=4
    ))

    # Score styles
    styles.add(ParagraphStyle(
        name='ScoreHigh',
        parent=styles['Normal'],
        fontSize=36,
        textColor=COLOR_GREEN,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    styles.add(ParagraphStyle(
        name='ScoreMedium',
        parent=styles['Normal'],
        fontSize=36,
        textColor=COLOR_ORANGE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    styles.add(ParagraphStyle(
        name='ScoreLow',
        parent=styles['Normal'],
        fontSize=36,
        textColor=COLOR_RED,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    styles.add(ParagraphStyle(
        name='Recommendation',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=10
    ))

    return styles


class PDFReportGenerator:
    """Generates PDF reports from OM analysis results"""

    def __init__(self):
        self.styles = create_styles()

    def generate(self, analysis: OMAnalysis, output_path: str) -> str:
        """Generate a PDF report from the analysis results

        Args:
            analysis: The OMAnalysis object containing all analysis data
            output_path: Path where the PDF should be saved

        Returns:
            The path to the generated PDF file
        """
        # Ensure output path has .pdf extension
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.pdf':
            output_path = output_path.with_suffix('.pdf')

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Build story (content)
        story = []

        # Add sections
        self._add_header(story, analysis)
        self._add_executive_summary(story, analysis)
        self._add_property_summary(story, analysis)
        self._add_financial_summary(story, analysis)
        self._add_fee_summary(story, analysis)
        self._add_market_analysis(story, analysis)
        self._add_investment_recommendation(story, analysis)
        self._add_red_flags(story, analysis)
        self._add_concerns(story, analysis)
        self._add_strengths(story, analysis)

        # Add detailed analysis section
        story.append(PageBreak())
        self._add_detailed_analysis(story, analysis)

        # Add footer info
        self._add_footer(story)

        # Build PDF
        doc.build(story)

        return str(output_path)

    def _add_header(self, story: list, analysis: OMAnalysis):
        """Add report header with property name and date"""
        # Title
        property_name = analysis.property.name or "Property Analysis"
        story.append(Paragraph(property_name, self.styles['ReportTitle']))

        # Subtitle with location and date
        location_parts = []
        if analysis.property.city:
            location_parts.append(analysis.property.city)
        if analysis.property.state:
            location_parts.append(analysis.property.state)

        subtitle = "Real Estate Investment Analysis Report"
        if location_parts:
            subtitle += f" | {', '.join(location_parts)}"
        subtitle += f" | {datetime.now().strftime('%B %d, %Y')}"

        story.append(Paragraph(subtitle, self.styles['ReportSubtitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY))
        story.append(Spacer(1, 12))

    def _add_executive_summary(self, story: list, analysis: OMAnalysis):
        """Add executive summary section"""
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))

        # Summary statistics
        score = analysis.overall_score or 0
        summary_data = [
            ['Investment Score', f'{score:.0f}/100'],
            ['Red Flags', str(len(analysis.red_flags))],
            ['Concerns', str(len(analysis.cons))],
            ['Strengths', str(len(analysis.pros))],
        ]

        # Add key financials if available
        if analysis.financials.asking_price:
            summary_data.append(['Asking Price', f'${analysis.financials.asking_price:,.0f}'])
        if analysis.financials.current_cap_rate:
            summary_data.append(['Cap Rate', f'{analysis.financials.current_cap_rate:.2%}'])
        if analysis.financials.irr_projected:
            summary_data.append(['Projected IRR', f'{analysis.financials.irr_projected:.1%}'])

        table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), COLOR_LIGHT_GRAY),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_GRAY),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

        # Add recommendation text
        if analysis.recommendation:
            story.append(Paragraph(
                f"<b>Recommendation:</b> {analysis.recommendation}",
                self.styles['BodyText']
            ))
        story.append(Spacer(1, 8))

    def _add_property_summary(self, story: list, analysis: OMAnalysis):
        """Add property summary section"""
        story.append(Paragraph("Property Summary", self.styles['SectionHeader']))

        prop = analysis.property
        data = []

        if prop.name:
            data.append(['Property Name', prop.name])
        if prop.address:
            data.append(['Address', prop.address])
        if prop.city or prop.state:
            location = f"{prop.city or ''}, {prop.state or ''} {prop.zip_code or ''}".strip(', ')
            data.append(['Location', location])
        if prop.property_type and prop.property_type.value != 'unknown':
            data.append(['Property Type', prop.property_type.value.replace('_', ' ').title()])
        if prop.total_units:
            data.append(['Total Units', f'{prop.total_units:,}'])
        if prop.total_sqft:
            data.append(['Square Feet', f'{prop.total_sqft:,.0f}'])
        if prop.year_built:
            data.append(['Year Built', str(prop.year_built)])
        if prop.num_buildings:
            data.append(['Number of Buildings', str(prop.num_buildings)])
        if prop.num_tenants:
            data.append(['Number of Tenants', str(prop.num_tenants)])
        if prop.walt_years:
            data.append(['WALT (Years)', f'{prop.walt_years:.1f}'])
        if prop.parking_spaces:
            data.append(['Parking Spaces', f'{prop.parking_spaces:,}'])
        if prop.amenities:
            data.append(['Amenities', ', '.join(prop.amenities[:5])])

        if data:
            table = self._create_data_table(data)
            story.append(table)
        else:
            story.append(Paragraph("No property details available.", self.styles['BodyText']))

        story.append(Spacer(1, 8))

    def _add_financial_summary(self, story: list, analysis: OMAnalysis):
        """Add financial metrics section"""
        story.append(Paragraph("Financial Metrics", self.styles['SectionHeader']))

        fin = analysis.financials
        data = []

        if fin.asking_price:
            data.append(['Asking Price', f'${fin.asking_price:,.0f}'])
        if fin.price_per_unit:
            data.append(['Price Per Unit', f'${fin.price_per_unit:,.0f}'])
        if fin.price_per_sqft:
            data.append(['Price Per Sq Ft', f'${fin.price_per_sqft:,.2f}'])
        if fin.current_cap_rate:
            data.append(['Cap Rate (In-Place)', f'{fin.current_cap_rate:.2%}'])
        if fin.proforma_cap_rate:
            data.append(['Cap Rate (Pro Forma)', f'{fin.proforma_cap_rate:.2%}'])
        if fin.current_noi:
            data.append(['NOI (In-Place)', f'${fin.current_noi:,.0f}'])
        if fin.proforma_noi:
            data.append(['NOI (Pro Forma)', f'${fin.proforma_noi:,.0f}'])
        if fin.current_occupancy:
            data.append(['Occupancy', f'{fin.current_occupancy:.1%}'])
        if fin.average_rent:
            data.append(['Average Rent', f'${fin.average_rent:,.0f}/mo'])
        if fin.market_rent:
            data.append(['Market Rent', f'${fin.market_rent:,.0f}/mo'])
        if fin.expense_ratio:
            data.append(['Expense Ratio', f'{fin.expense_ratio:.1%}'])
        if fin.cash_on_cash_return:
            data.append(['Cash-on-Cash Return', f'{fin.cash_on_cash_return:.1%}'])
        if fin.irr_projected:
            data.append(['Projected IRR', f'{fin.irr_projected:.1%}'])
        if fin.equity_multiple:
            data.append(['Equity Multiple', f'{fin.equity_multiple:.2f}x'])

        if data:
            table = self._create_data_table(data)
            story.append(table)
        else:
            story.append(Paragraph("No financial metrics available.", self.styles['BodyText']))

        story.append(Spacer(1, 8))

        # Add deal terms if available
        terms = analysis.deal_terms
        terms_data = []

        if terms.loan_to_value:
            terms_data.append(['Loan-to-Value', f'{terms.loan_to_value:.1%}'])
        if terms.interest_rate:
            terms_data.append(['Interest Rate', f'{terms.interest_rate:.2%}'])
        if terms.loan_type:
            terms_data.append(['Loan Type', terms.loan_type])
        if terms.preferred_return:
            terms_data.append(['Preferred Return', f'{terms.preferred_return:.1%}'])
        if terms.profit_split:
            terms_data.append(['Profit Split (LP/GP)', terms.profit_split])
        if terms.hold_period_years:
            terms_data.append(['Hold Period', f'{terms.hold_period_years} years'])
        if terms.minimum_investment:
            terms_data.append(['Minimum Investment', f'${terms.minimum_investment:,.0f}'])

        if terms_data:
            story.append(Paragraph("Deal Terms", self.styles['SubsectionHeader']))
            table = self._create_data_table(terms_data)
            story.append(table)
            story.append(Spacer(1, 8))

    def _add_fee_summary(self, story: list, analysis: OMAnalysis):
        """Add sponsor fee structure section"""
        fees = analysis.fees

        # Check if any fees were found
        has_fees = any([
            fees.acquisition_fee, fees.asset_management_fee,
            fees.property_management_fee, fees.construction_management_fee,
            fees.disposition_fee, fees.refinance_fee
        ])

        if not has_fees:
            return

        story.append(Paragraph("Sponsor Fee Structure", self.styles['SectionHeader']))

        data = []

        if fees.acquisition_fee:
            data.append(['Acquisition Fee', f'{fees.acquisition_fee:.1%}', '0.5-2.0%'])
        if fees.asset_management_fee:
            data.append(['Asset Management Fee', f'{fees.asset_management_fee:.1%}/yr', '1.0-2.0%/yr'])
        if fees.property_management_fee:
            data.append(['Property Management Fee', f'{fees.property_management_fee:.1%}', '3-6%'])
        if fees.construction_management_fee:
            data.append(['Construction Mgmt Fee', f'{fees.construction_management_fee:.1%}', '3-5%'])
        if fees.disposition_fee:
            data.append(['Disposition Fee', f'{fees.disposition_fee:.1%}', '0.5-1.5%'])
        if fees.refinance_fee:
            data.append(['Refinance Fee', f'{fees.refinance_fee:.1%}', '0.25-1.0%'])

        if fees.estimated_total_fees_over_hold:
            hold = analysis.deal_terms.hold_period_years or 5
            data.append([f'Est. Total Fees ({hold}yr)', f'{fees.estimated_total_fees_over_hold:.1%}', '15-25%'])

        if data:
            # Create table with benchmark column
            header = ['Fee Type', 'Rate', 'Benchmark']
            table_data = [header] + data

            table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 1), (0, -1), COLOR_LIGHT_GRAY),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 1), (-1, -1), COLOR_GRAY),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, COLOR_LIGHT_GRAY),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))

            story.append(table)

        story.append(Spacer(1, 8))

    def _add_market_analysis(self, story: list, analysis: OMAnalysis):
        """Add market analysis section"""
        market = analysis.market_data

        # Check if any market data is available
        has_data = any([
            market.market_cap_rate, market.market_vacancy_rate,
            market.rent_growth_1yr, market.job_growth, market.median_household_income
        ])

        if not has_data:
            return

        story.append(Paragraph("Market Analysis", self.styles['SectionHeader']))

        data = []

        if market.market_cap_rate:
            data.append(['Market Cap Rate', f'{market.market_cap_rate:.2%}'])
        if market.market_vacancy_rate:
            data.append(['Market Vacancy', f'{market.market_vacancy_rate:.1%}'])
        if market.market_rent_psf:
            data.append(['Market Rent', f'${market.market_rent_psf:,.0f}/mo'])
        if market.rent_growth_1yr:
            data.append(['Rent Growth (1yr)', f'{market.rent_growth_1yr:.1%}'])
        if market.rent_growth_5yr:
            data.append(['Rent Growth (5yr avg)', f'{market.rent_growth_5yr:.1%}'])
        if market.job_growth:
            data.append(['Job Growth', f'{market.job_growth:.1%}'])
        if market.unemployment_rate:
            data.append(['Unemployment Rate', f'{market.unemployment_rate:.1%}'])
        if market.population_growth:
            data.append(['Population Growth', f'{market.population_growth:.1%}'])
        if market.median_household_income:
            data.append(['Median Household Income', f'${market.median_household_income:,.0f}'])
        if market.walk_score:
            data.append(['Walk Score', str(market.walk_score)])
        if market.transit_score:
            data.append(['Transit Score', str(market.transit_score)])
        if market.new_supply_units:
            data.append(['New Supply (Units)', f'{market.new_supply_units:,}'])
        if market.major_employers:
            data.append(['Major Employers', ', '.join(market.major_employers[:3])])

        if data:
            table = self._create_data_table(data)
            story.append(table)

        story.append(Spacer(1, 8))

    def _add_investment_recommendation(self, story: list, analysis: OMAnalysis):
        """Add investment recommendation section with score"""
        story.append(Paragraph("Investment Recommendation", self.styles['SectionHeader']))

        score = analysis.overall_score or 0

        # Determine score style
        if score >= 70:
            score_style = 'ScoreHigh'
            rec_color = COLOR_GREEN
        elif score >= 50:
            score_style = 'ScoreMedium'
            rec_color = COLOR_ORANGE
        else:
            score_style = 'ScoreLow'
            rec_color = COLOR_RED

        # Create score display
        score_text = f"{score:.0f}/100"
        story.append(Paragraph(score_text, self.styles[score_style]))

        # Add recommendation
        if analysis.recommendation:
            rec_style = ParagraphStyle(
                name='RecText',
                parent=self.styles['Recommendation'],
                textColor=rec_color
            )
            story.append(Paragraph(analysis.recommendation, rec_style))

        # Summary counts
        summary_text = f"Strengths: {len(analysis.pros)} | Concerns: {len(analysis.cons)} | Red Flags: {len(analysis.red_flags)}"
        story.append(Paragraph(summary_text, ParagraphStyle(
            name='SummaryCount',
            parent=self.styles['BodyText'],
            alignment=TA_CENTER
        )))

        story.append(Spacer(1, 12))

    def _add_red_flags(self, story: list, analysis: OMAnalysis):
        """Add red flags section"""
        if not analysis.red_flags:
            return

        story.append(Paragraph("Red Flags", self.styles['SectionHeader']))

        # Add red underline
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_RED))
        story.append(Spacer(1, 6))

        for finding in analysis.red_flags:
            self._add_finding(story, finding, 'RedFlagTitle', 'CRITICAL')

        story.append(Spacer(1, 8))

    def _add_concerns(self, story: list, analysis: OMAnalysis):
        """Add concerns/cons section"""
        if not analysis.cons:
            return

        story.append(Paragraph("Concerns", self.styles['SectionHeader']))

        # Add orange underline
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_ORANGE))
        story.append(Spacer(1, 6))

        for finding in analysis.cons:
            self._add_finding(story, finding, 'WarningTitle', 'WARNING')

        story.append(Spacer(1, 8))

    def _add_strengths(self, story: list, analysis: OMAnalysis):
        """Add strengths/pros section"""
        if not analysis.pros:
            return

        story.append(Paragraph("Strengths", self.styles['SectionHeader']))

        # Add green underline
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_GREEN))
        story.append(Spacer(1, 6))

        for finding in analysis.pros:
            self._add_finding(story, finding, 'ProTitle', 'POSITIVE')

        story.append(Spacer(1, 8))

    def _add_finding(self, story: list, finding: Finding, title_style: str, label: str):
        """Add a single finding to the report"""
        # Title line with category and description
        title_text = f"[{finding.category}] {finding.description}"
        story.append(Paragraph(title_text, self.styles[title_style]))

        # Details
        if finding.details:
            story.append(Paragraph(finding.details, self.styles['FindingDetail']))

        # Actual vs benchmark values
        if finding.actual_value:
            metric_text = f"<b>Actual:</b> {finding.actual_value}"
            if finding.benchmark_value:
                metric_text += f" | <b>Benchmark:</b> {finding.benchmark_value}"
            story.append(Paragraph(metric_text, self.styles['FindingDetail']))

    def _add_detailed_analysis(self, story: list, analysis: OMAnalysis):
        """Add detailed analysis section with all findings"""
        story.append(Paragraph("Detailed Analysis", self.styles['ReportTitle']))
        story.append(Paragraph(
            "Comprehensive breakdown of all findings with metrics and benchmarks",
            self.styles['ReportSubtitle']
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY))
        story.append(Spacer(1, 12))

        # Red flags detailed
        if analysis.red_flags:
            story.append(Paragraph("Critical Issues (Red Flags)", self.styles['SectionHeader']))
            for i, finding in enumerate(analysis.red_flags, 1):
                self._add_detailed_finding(story, finding, i, COLOR_RED)

        # Concerns detailed
        if analysis.cons:
            story.append(Paragraph("Concerns & Warnings", self.styles['SectionHeader']))
            for i, finding in enumerate(analysis.cons, 1):
                self._add_detailed_finding(story, finding, i, COLOR_ORANGE)

        # Strengths detailed
        if analysis.pros:
            story.append(Paragraph("Positive Factors", self.styles['SectionHeader']))
            for i, finding in enumerate(analysis.pros, 1):
                self._add_detailed_finding(story, finding, i, COLOR_GREEN)

    def _add_detailed_finding(self, story: list, finding: Finding, index: int, color: colors.Color):
        """Add a detailed finding with all information"""
        # Create a table for each finding
        data = [
            ['Category', finding.category],
            ['Description', finding.description],
            ['Risk Level', finding.risk_level.value.title()],
        ]

        if finding.details:
            # Wrap details text
            details = finding.details
            if len(details) > 200:
                details = details[:200] + "..."
            data.append(['Details', details])

        if finding.actual_value:
            data.append(['Actual Value', finding.actual_value])

        if finding.benchmark_value:
            data.append(['Benchmark', finding.benchmark_value])

        table = Table(data, colWidths=[1.5*inch, 5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), COLOR_LIGHT_GRAY),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), color),
            ('TEXTCOLOR', (1, 0), (1, -1), COLOR_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(Spacer(1, 8))
        story.append(KeepTogether([
            Paragraph(f"Finding #{index}", ParagraphStyle(
                name='FindingNumber',
                parent=self.styles['SubsectionHeader'],
                textColor=color
            )),
            table
        ]))
        story.append(Spacer(1, 4))

    def _add_footer(self, story: list):
        """Add footer with disclaimer"""
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_LIGHT_GRAY))
        story.append(Spacer(1, 8))

        disclaimer = (
            "<b>Disclaimer:</b> This analysis is provided for informational purposes only and should not be "
            "considered as financial, investment, or legal advice. All projections and estimates are based on "
            "information provided in the Offering Memorandum and may not reflect actual outcomes. Investors "
            "should conduct their own due diligence and consult with qualified professionals before making "
            "any investment decisions."
        )

        story.append(Paragraph(disclaimer, ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['BodyText'],
            fontSize=8,
            textColor=COLOR_GRAY
        )))

        # Generated timestamp
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            ParagraphStyle(
                name='Timestamp',
                parent=self.styles['BodyText'],
                fontSize=8,
                textColor=COLOR_GRAY,
                alignment=TA_CENTER
            )
        ))

    def _create_data_table(self, data: list) -> Table:
        """Create a standard two-column data table"""
        table = Table(data, colWidths=[2.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), COLOR_LIGHT_GRAY),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_GRAY),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        return table


def generate_pdf_report(analysis: OMAnalysis, output_path: str) -> str:
    """Convenience function to generate a PDF report

    Args:
        analysis: The OMAnalysis object containing all analysis data
        output_path: Path where the PDF should be saved

    Returns:
        The path to the generated PDF file
    """
    generator = PDFReportGenerator()
    return generator.generate(analysis, output_path)
