# Real Estate OM Analysis Tool

A Python tool for analyzing real estate investment Offering Memorandums (OMs). The tool extracts key deal metrics, fetches external market data, and identifies pros, cons, and red flags in deal terms.

## Features

- **OM Parsing**: Extracts property details, financial metrics, and deal terms from PDF or text OMs
- **Market Data Integration**: Fetches external data for geographic analysis including:
  - Market cap rates and vacancy rates
  - Rent trends and growth rates
  - Employment and population data
  - Walk scores and location metrics
- **Deal Analysis**: Comprehensive analysis that identifies:
  - ✅ **Pros**: Favorable deal characteristics
  - ⚠️ **Cons**: Areas of concern
  - 🚨 **Red Flags**: Critical issues requiring attention
- **Investment Scoring**: Overall deal score (0-100) with buy/pass recommendation

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Real-Estate-Analysis

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Interactive Mode

Run the tool and follow the prompts:

```bash
python main.py
```

You can either:
1. Paste OM text directly (type 'END' on a new line when done)
2. Provide a file path to a PDF or TXT file

### Programmatic Usage

```python
from src.om_parser import OMParser
from src.deal_analyzer import DealAnalyzer

# Parse an OM
parser = OMParser()
analysis = parser.parse_file("path/to/om.pdf")
# or
analysis = parser.parse_text(om_text_content)

# Run analysis
analyzer = DealAnalyzer()
analysis = analyzer.analyze(analysis)

# Access results
print(f"Score: {analysis.overall_score}/100")
print(f"Recommendation: {analysis.recommendation}")

for pro in analysis.pros:
    print(f"PRO: {pro.description}")

for con in analysis.cons:
    print(f"CON: {con.description}")

for flag in analysis.red_flags:
    print(f"RED FLAG: {flag.description}")
```

## Sample OMs

The `samples/` directory contains example OMs for testing:

- `sample_om_1.txt` - A standard multifamily deal in Austin, TX
- `sample_om_2_red_flags.txt` - A problematic deal with multiple red flags

Test with a sample:
```bash
python main.py
# Select option 2, then enter: samples/sample_om_1.txt
```

## What the Tool Analyzes

### Financial Metrics
- Cap rate vs. market benchmarks
- Price per unit / price per SF
- NOI and expense ratios
- Occupancy levels
- Rent levels vs. market
- Projected returns (IRR, CoC, equity multiple)

### Deal Structure
- Leverage (LTV)
- Interest rates and loan terms
- Preferred returns and profit splits
- Hold period

### Market Factors
- Rent growth trends
- Employment and job growth
- Population trends
- New supply pipeline
- Major employers

### Property Characteristics
- Age and condition
- Property type considerations
- Amenity packages
- Value-add potential

## Red Flags Detected

The tool automatically flags issues such as:

- Cap rates significantly below market
- Critically low occupancy (<80%)
- Above-market rents limiting growth
- High expense ratios (>65%)
- Properties over 50 years old
- LTV over 80%
- Bridge financing requiring refinance
- Variable/floating rate debt exposure
- Aggressive pro forma assumptions
- Low preferred returns
- GP-heavy profit splits

## API Keys (Optional)

For enhanced market data, set these environment variables:

```bash
export CENSUS_API_KEY=your_census_api_key
export HUD_API_KEY=your_hud_api_key
```

Without API keys, the tool uses built-in market data estimates.

## Output Example

```
================================================================================
                    INVESTMENT RECOMMENDATION
================================================================================
Overall Score: 68/100
✓ BUY - Deal merits consideration with appropriate due diligence

Pros: 6 | Cons: 3 | Red Flags: 1
================================================================================

[PRO] Cap Rate: Cap rate above market average
    Property cap rate of 5.50% exceeds market average of 5.25%

[PRO] Occupancy: Excellent occupancy rate
    Current occupancy of 96% indicates strong tenant demand

[CON] Financing: Aggressive leverage
    LTV of 75% is on the higher end, increasing refinance risk

[RED FLAG] Cap Rate Assumptions: Aggressive cap rate expansion assumed
    Proforma assumes 1.5% cap expansion which may not materialize
```

## Project Structure

```
Real-Estate-Analysis/
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── src/
│   ├── __init__.py
│   ├── models.py          # Data models
│   ├── om_parser.py       # OM parsing logic
│   ├── deal_analyzer.py   # Analysis engine
│   └── market_data.py     # External data fetching
└── samples/
    ├── sample_om_1.txt    # Good deal example
    └── sample_om_2_red_flags.txt  # Bad deal example
```

## License

MIT License
