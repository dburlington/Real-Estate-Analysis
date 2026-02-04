#!/usr/bin/env python3
"""
Real Estate OM Analysis Tool
Analyzes Offering Memorandums for real estate investments
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Rich console for beautiful output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# PDF report generation
PDF_IMPORT_ERROR = None
try:
    from src.report_generator import PDFReportGenerator
    PDF_AVAILABLE = True
except ImportError as e:
    PDF_AVAILABLE = False
    PDF_IMPORT_ERROR = str(e)

from src.om_parser import OMParser
from src.deal_analyzer import DealAnalyzer
from src.market_data import MarketDataFetcher
from src.models import RiskLevel, Finding, OMAnalysis


def create_console():
    """Create a rich console or fallback"""
    if RICH_AVAILABLE:
        return Console()
    return None


def print_header(console):
    """Print application header"""
    if console:
        console.print()
        console.print(Panel.fit(
            "[bold blue]Real Estate OM Analysis Tool[/bold blue]\n"
            "[dim]Analyze Offering Memorandums for Pros, Cons & Red Flags[/dim]",
            border_style="blue"
        ))
        console.print()
    else:
        print("\n" + "=" * 60)
        print("Real Estate OM Analysis Tool")
        print("Analyze Offering Memorandums for Pros, Cons & Red Flags")
        print("=" * 60 + "\n")


def get_om_input(console) -> str:
    """Prompt user for OM input"""
    if console:
        console.print("[bold]How would you like to provide the OM?[/bold]")
        console.print("  1. Enter/paste text directly")
        console.print("  2. Provide a file path (PDF or TXT)")
        console.print()

        choice = Prompt.ask("Select option", choices=["1", "2"], default="1")

        if choice == "2":
            file_path = Prompt.ask("Enter file path")
            return f"FILE:{file_path}"
        else:
            console.print("\n[dim]Paste your OM text below. When done, enter 'END' on a new line:[/dim]\n")
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip().upper() == 'END':
                        break
                    lines.append(line)
                except EOFError:
                    break
            return "\n".join(lines)
    else:
        print("How would you like to provide the OM?")
        print("  1. Enter/paste text directly")
        print("  2. Provide a file path (PDF or TXT)")

        choice = input("Select option (1 or 2): ").strip()

        if choice == "2":
            file_path = input("Enter file path: ").strip()
            return f"FILE:{file_path}"
        else:
            print("\nPaste your OM text below. When done, enter 'END' on a new line:\n")
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip().upper() == 'END':
                        break
                    lines.append(line)
                except EOFError:
                    break
            return "\n".join(lines)


def display_property_summary(console, analysis: OMAnalysis):
    """Display property summary"""
    prop = analysis.property
    fin = analysis.financials

    if console:
        table = Table(title="Property Summary", box=box.ROUNDED)
        table.add_column("Attribute", style="cyan")
        table.add_column("Value", style="white")

        if prop.name:
            table.add_row("Property Name", prop.name)
        if prop.address:
            table.add_row("Address", prop.address)
        if prop.city and prop.state:
            table.add_row("Location", f"{prop.city}, {prop.state} {prop.zip_code or ''}")
        if prop.property_type:
            table.add_row("Property Type", prop.property_type.value.title())
        if prop.total_units:
            table.add_row("Units", f"{prop.total_units:,}")
        if prop.total_sqft:
            table.add_row("Square Feet", f"{prop.total_sqft:,.0f}")
        if prop.year_built:
            table.add_row("Year Built", str(prop.year_built))
        if prop.amenities:
            table.add_row("Amenities", ", ".join(prop.amenities[:5]))

        console.print(table)
        console.print()
    else:
        print("\n--- Property Summary ---")
        if prop.name:
            print(f"Property Name: {prop.name}")
        if prop.address:
            print(f"Address: {prop.address}")
        if prop.city and prop.state:
            print(f"Location: {prop.city}, {prop.state} {prop.zip_code or ''}")
        if prop.property_type:
            print(f"Property Type: {prop.property_type.value.title()}")
        if prop.total_units:
            print(f"Units: {prop.total_units:,}")
        if prop.total_sqft:
            print(f"Square Feet: {prop.total_sqft:,.0f}")
        if prop.year_built:
            print(f"Year Built: {prop.year_built}")
        print()


def display_financial_summary(console, analysis: OMAnalysis):
    """Display financial metrics"""
    fin = analysis.financials

    if console:
        table = Table(title="Financial Metrics", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Notes", style="dim")

        if fin.asking_price:
            table.add_row("Asking Price", f"${fin.asking_price:,.0f}", "")
        if fin.price_per_unit:
            table.add_row("Price/Unit", f"${fin.price_per_unit:,.0f}", "")
        if fin.current_cap_rate:
            table.add_row("Cap Rate (In-Place)", f"{fin.current_cap_rate:.2%}", "")
        if fin.proforma_cap_rate:
            table.add_row("Cap Rate (Pro Forma)", f"{fin.proforma_cap_rate:.2%}", "")
        if fin.current_noi:
            table.add_row("NOI (In-Place)", f"${fin.current_noi:,.0f}", "")
        if fin.current_occupancy:
            table.add_row("Occupancy", f"{fin.current_occupancy:.1%}", "")
        if fin.average_rent:
            table.add_row("Average Rent", f"${fin.average_rent:,.0f}/mo", "")
        if fin.expense_ratio:
            table.add_row("Expense Ratio", f"{fin.expense_ratio:.1%}", "")
        if fin.cash_on_cash_return:
            table.add_row("Cash-on-Cash", f"{fin.cash_on_cash_return:.1%}", "Year 1")
        if fin.irr_projected:
            table.add_row("Projected IRR", f"{fin.irr_projected:.1%}", "")
        if fin.equity_multiple:
            table.add_row("Equity Multiple", f"{fin.equity_multiple:.2f}x", "")

        console.print(table)
        console.print()
    else:
        print("--- Financial Metrics ---")
        if fin.asking_price:
            print(f"Asking Price: ${fin.asking_price:,.0f}")
        if fin.price_per_unit:
            print(f"Price/Unit: ${fin.price_per_unit:,.0f}")
        if fin.current_cap_rate:
            print(f"Cap Rate: {fin.current_cap_rate:.2%}")
        if fin.current_noi:
            print(f"NOI: ${fin.current_noi:,.0f}")
        if fin.current_occupancy:
            print(f"Occupancy: {fin.current_occupancy:.1%}")
        print()


def display_market_data(console, analysis: OMAnalysis):
    """Display market data"""
    market = analysis.market_data

    if not any([market.market_cap_rate, market.rent_growth_1yr, market.job_growth]):
        return

    if console:
        table = Table(title="Market Analysis", box=box.ROUNDED)
        table.add_column("Indicator", style="cyan")
        table.add_column("Value", style="white")

        if market.market_cap_rate:
            table.add_row("Market Cap Rate", f"{market.market_cap_rate:.2%}")
        if market.market_vacancy_rate:
            table.add_row("Market Vacancy", f"{market.market_vacancy_rate:.1%}")
        if market.market_rent_psf:
            table.add_row("Market Rent", f"${market.market_rent_psf:,.0f}/mo")
        if market.rent_growth_1yr:
            table.add_row("Rent Growth (1yr)", f"{market.rent_growth_1yr:.1%}")
        if market.job_growth:
            table.add_row("Job Growth", f"{market.job_growth:.1%}")
        if market.unemployment_rate:
            table.add_row("Unemployment Rate", f"{market.unemployment_rate:.1%}")
        if market.median_household_income:
            table.add_row("Median Income", f"${market.median_household_income:,.0f}")
        if market.walk_score:
            table.add_row("Walk Score", str(market.walk_score))
        if market.major_employers:
            table.add_row("Major Employers", ", ".join(market.major_employers[:3]))

        console.print(table)
        console.print()
    else:
        print("--- Market Analysis ---")
        if market.market_cap_rate:
            print(f"Market Cap Rate: {market.market_cap_rate:.2%}")
        if market.rent_growth_1yr:
            print(f"Rent Growth: {market.rent_growth_1yr:.1%}")
        if market.job_growth:
            print(f"Job Growth: {market.job_growth:.1%}")
        print()


def display_fee_summary(console, analysis: OMAnalysis):
    """Display sponsor fee structure"""
    fees = analysis.fees

    # Check if any fees were found
    has_fees = any([
        fees.acquisition_fee, fees.asset_management_fee,
        fees.property_management_fee, fees.construction_management_fee,
        fees.disposition_fee, fees.refinance_fee
    ])

    if not has_fees:
        return

    if console:
        table = Table(title="Sponsor Fee Structure", box=box.ROUNDED)
        table.add_column("Fee Type", style="cyan")
        table.add_column("Rate", style="white")
        table.add_column("Industry Benchmark", style="dim")

        if fees.acquisition_fee:
            table.add_row("Acquisition Fee", f"{fees.acquisition_fee:.1%}", "0.5-2.0%")
        if fees.asset_management_fee:
            table.add_row("Asset Management Fee", f"{fees.asset_management_fee:.1%}/yr", "1.0-2.0%/yr")
        if fees.property_management_fee:
            table.add_row("Property Management Fee", f"{fees.property_management_fee:.1%}", "3-6%")
        if fees.construction_management_fee:
            table.add_row("Construction Mgmt Fee", f"{fees.construction_management_fee:.1%}", "3-5%")
        if fees.disposition_fee:
            table.add_row("Disposition Fee", f"{fees.disposition_fee:.1%}", "0.5-1.5%")
        if fees.refinance_fee:
            table.add_row("Refinance Fee", f"{fees.refinance_fee:.1%}", "0.25-1.0%")

        if fees.estimated_total_fees_over_hold:
            hold = analysis.deal_terms.hold_period_years or 5
            table.add_row(
                f"Est. Total Fees ({hold}yr)",
                f"{fees.estimated_total_fees_over_hold:.1%}",
                "15-25%"
            )

        console.print(table)
        console.print()
    else:
        print("--- Sponsor Fee Structure ---")
        if fees.acquisition_fee:
            print(f"Acquisition Fee: {fees.acquisition_fee:.1%} (benchmark: 0.5-2%)")
        if fees.asset_management_fee:
            print(f"Asset Management Fee: {fees.asset_management_fee:.1%}/yr (benchmark: 1-2%/yr)")
        if fees.property_management_fee:
            print(f"Property Management Fee: {fees.property_management_fee:.1%} (benchmark: 3-6%)")
        if fees.disposition_fee:
            print(f"Disposition Fee: {fees.disposition_fee:.1%} (benchmark: 0.5-1.5%)")
        if fees.estimated_total_fees_over_hold:
            print(f"Est. Total Fees: {fees.estimated_total_fees_over_hold:.1%} (benchmark: 15-25%)")
        print()


def display_findings(console, findings: list[Finding], title: str, style: str):
    """Display findings (pros, cons, or red flags)"""
    if not findings:
        return

    if console:
        table = Table(title=title, box=box.ROUNDED, border_style=style)
        table.add_column("Category", style="bold")
        table.add_column("Finding", style="white")
        table.add_column("Details", style="dim", max_width=50)

        for f in findings:
            table.add_row(f.category, f.description, f.details[:100] + "..." if len(f.details) > 100 else f.details)

        console.print(table)
        console.print()
    else:
        print(f"\n--- {title} ---")
        for f in findings:
            print(f"[{f.category}] {f.description}")
            print(f"  {f.details[:100]}...")
        print()


def display_recommendation(console, analysis: OMAnalysis):
    """Display overall recommendation"""
    score = analysis.overall_score or 0
    rec = analysis.recommendation

    # Determine color based on score
    if score >= 70:
        color = "green"
        icon = "✓"
    elif score >= 50:
        color = "yellow"
        icon = "⚠"
    else:
        color = "red"
        icon = "✗"

    if console:
        console.print()
        console.print(Panel(
            f"[bold {color}]Overall Score: {score}/100[/bold {color}]\n\n"
            f"[{color}]{rec}[/{color}]\n\n"
            f"[dim]Pros: {len(analysis.pros)} | Cons: {len(analysis.cons)} | Red Flags: {len(analysis.red_flags)}[/dim]",
            title="[bold]Investment Recommendation[/bold]",
            border_style=color
        ))
    else:
        print("\n" + "=" * 60)
        print(f"INVESTMENT RECOMMENDATION")
        print("=" * 60)
        print(f"Overall Score: {score}/100")
        print(f"{icon} {rec}")
        print(f"\nPros: {len(analysis.pros)} | Cons: {len(analysis.cons)} | Red Flags: {len(analysis.red_flags)}")
        print("=" * 60)


def display_detailed_findings(console, analysis: OMAnalysis):
    """Display detailed findings with metrics"""
    all_findings = []

    for f in analysis.red_flags:
        all_findings.append(("RED FLAG", f, "red"))
    for f in analysis.cons:
        all_findings.append(("CON", f, "yellow"))
    for f in analysis.pros:
        all_findings.append(("PRO", f, "green"))

    if not all_findings:
        return

    if console:
        console.print()
        console.print("[bold]Detailed Analysis[/bold]")
        console.print()

        for label, finding, color in all_findings:
            console.print(f"[bold {color}][{label}][/bold {color}] [bold]{finding.category}[/bold]: {finding.description}")
            console.print(f"    [dim]{finding.details}[/dim]")
            if finding.actual_value:
                console.print(f"    Actual: [cyan]{finding.actual_value}[/cyan]", end="")
                if finding.benchmark_value:
                    console.print(f" | Benchmark: [cyan]{finding.benchmark_value}[/cyan]")
                else:
                    console.print()
            console.print()
    else:
        print("\n--- Detailed Analysis ---\n")
        for label, finding, _ in all_findings:
            print(f"[{label}] {finding.category}: {finding.description}")
            print(f"    {finding.details}")
            if finding.actual_value:
                print(f"    Actual: {finding.actual_value}", end="")
                if finding.benchmark_value:
                    print(f" | Benchmark: {finding.benchmark_value}")
                else:
                    print()
            print()


def analyze_om(om_input: str, console) -> OMAnalysis:
    """Parse and analyze the OM"""
    parser = OMParser()
    analyzer = DealAnalyzer()

    if console:
        console.print("[dim]Parsing OM...[/dim]")

    # Check if it's a file path
    if om_input.startswith("FILE:"):
        file_path = om_input[5:].strip()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        analysis = parser.parse_file(file_path)
    else:
        analysis = parser.parse_text(om_input)

    if console:
        console.print("[dim]Fetching market data...[/dim]")

    # Run analysis
    analysis = analyzer.analyze(analysis)

    return analysis


def generate_pdf_report(analysis: OMAnalysis, output_path: str, console) -> str:
    """Generate a PDF report from the analysis"""
    if not PDF_AVAILABLE:
        error_msg = f"PDF generation failed: {PDF_IMPORT_ERROR}" if PDF_IMPORT_ERROR else \
            "PDF generation requires reportlab. Install with: pip install reportlab"
        raise ImportError(error_msg)

    generator = PDFReportGenerator()
    report_path = generator.generate_report(analysis, output_path)

    if console:
        console.print(f"[green]PDF report generated: {report_path}[/green]")
    else:
        print(f"PDF report generated: {report_path}")

    return report_path


def get_default_pdf_name(analysis: OMAnalysis) -> str:
    """Generate a default PDF filename based on property name"""
    if analysis.property.name:
        # Sanitize the property name for filename
        name = analysis.property.name
        name = "".join(c if c.isalnum() or c in ' -_' else '' for c in name)
        name = name.replace(' ', '_')[:50]
    else:
        name = "om_analysis"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_report_{timestamp}.pdf"


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Analyze Real Estate Offering Memorandums for pros, cons, and red flags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                        # Interactive mode
  python3 main.py document.pdf           # Analyze a PDF file
  python3 main.py document.pdf -p        # Analyze and generate PDF report
  python3 main.py document.pdf -o report.pdf  # Specify output PDF name
        """
    )
    parser.add_argument(
        'file',
        nargs='?',
        help='Path to OM file (PDF or TXT) to analyze'
    )
    parser.add_argument(
        '-p', '--pdf',
        action='store_true',
        help='Generate a PDF report of the analysis'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output path for the PDF report (implies --pdf)'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Minimal console output (useful with --pdf)'
    )
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    console = create_console() if not args.quiet else None

    try:
        if not args.quiet:
            print_header(console)

        # Get OM input - from args or interactive
        if args.file:
            om_input = f"FILE:{args.file}"
        else:
            om_input = get_om_input(console)

        if not om_input or om_input.strip() == "":
            if console:
                console.print("[red]No OM content provided. Exiting.[/red]")
            else:
                print("No OM content provided. Exiting.")
            return 1

        # Analyze
        if console:
            console.print()
            with console.status("[bold green]Analyzing OM..."):
                analysis = analyze_om(om_input, console)
        else:
            if not args.quiet:
                print("\nAnalyzing OM...")
            analysis = analyze_om(om_input, None)

        # Display results (unless quiet mode)
        if not args.quiet:
            if console:
                console.print()

            display_property_summary(console, analysis)
            display_financial_summary(console, analysis)
            display_fee_summary(console, analysis)
            display_market_data(console, analysis)

            # Display findings
            display_findings(console, analysis.red_flags, "🚨 Red Flags", "red")
            display_findings(console, analysis.cons, "⚠️  Concerns", "yellow")
            display_findings(console, analysis.pros, "✅ Strengths", "green")

            # Display recommendation
            display_recommendation(console, analysis)

            # Ask for detailed view
            if console:
                console.print()
                show_details = Confirm.ask("Show detailed analysis?", default=True)
                if show_details:
                    display_detailed_findings(console, analysis)
            elif not args.quiet:
                print("\n")
                show_details = input("Show detailed analysis? (y/n): ").strip().lower()
                if show_details == 'y':
                    display_detailed_findings(console, analysis)

        # Handle PDF generation
        generate_pdf = args.pdf or args.output

        # If not specified via args, ask interactively
        if not generate_pdf and not args.quiet and console:
            console.print()
            generate_pdf = Confirm.ask("Generate PDF report?", default=False)

        if generate_pdf:
            # Determine output path
            if args.output:
                output_path = args.output
            else:
                output_path = get_default_pdf_name(analysis)

            try:
                generate_pdf_report(analysis, output_path, console)
            except ImportError as e:
                if console:
                    console.print(f"[red]Error: {e}[/red]")
                else:
                    print(f"Error: {e}")
                return 1

        return 0

    except FileNotFoundError as e:
        if console:
            console.print(f"[red]Error: {e}[/red]")
        else:
            print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        if console:
            console.print("\n[dim]Analysis cancelled.[/dim]")
        else:
            print("\nAnalysis cancelled.")
        return 0
    except Exception as e:
        if console:
            console.print(f"[red]Error analyzing OM: {e}[/red]")
            console.print_exception()
        else:
            print(f"Error analyzing OM: {e}")
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
