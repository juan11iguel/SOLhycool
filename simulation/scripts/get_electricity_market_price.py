# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "loguru",
# ]
# ///

"""
Script to fetch electricity market price data from the Spanish electricity system operator (REE) API.

This script can be run with `uv run get_electricity_market_price.py`.

Example:
Get data for the years 2022 to 2024:

```bash
uv run scripts/get_electricity_market_price.py 2022 2024
```
"""

import requests
import json
from datetime import datetime, timedelta
from loguru import logger
import argparse
from pathlib import Path
import time


def generate_monthly_intervals(start_year: int, end_year: int) -> list[tuple[datetime, datetime]]:
    current_date = datetime(start_year, 1, 1)
    final_date = datetime(end_year, 12, 31)
    intervals = []
    while current_date <= final_date:
        start_date = current_date.replace(day=1)
        next_month = start_date + timedelta(days=32)
        end_date = next_month.replace(day=1) - timedelta(seconds=1)
        intervals.append((start_date, end_date))
        current_date = next_month
    return intervals

def fetch_data(start_date: datetime, end_date: datetime) -> dict | None:
    url = (f"https://apidatos.ree.es/en/datos/mercados/precios-mercados-tiempo-real"
           f"?start_date={start_date.strftime('%Y-%m-%dT%H:%M')}"
           f"&end_date={end_date.strftime('%Y-%m-%dT%H:%M')}"
           f"&time_trunc=hour")
    headers = {'Content-Type': 'application/json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error fetching data for {start_date.strftime('%Y-%m')} - HTTP {response.status_code}")
        return None

def save_json(data: dict, filename: str, folder: Path) -> None:
    if not folder.exists():
        folder.mkdir(parents=True)
    with open(folder / filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_readme(folder: Path) -> None:
    readme_content = """
    # Electricity Price Data

    The data in this folder was fetched from the Spanish electricity system operator (REE) API.
    The API can be accessed at [REE API](https://www.ree.es/es/datos/apidatos).

    The data is fetched in hourly intervals and saved in JSON format.

    Each file is named as `{start_date:YYYYMMDD}_{end_date:YYYYMMDD}.json`.

    Example usage:
    ```bash
    uv run scripts/get_electricity_market_price.py 2022 2024
    ```

    This will fetch data for the years 2022 to 2024 and save it in the specified output folder.
    """
    with open(folder / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme_content.strip())

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch electricity market price data.")
    parser.add_argument("start_year", type=int, help="Start year for data fetching")
    parser.add_argument("end_year", type=int, help="End year for data fetching")
    parser.add_argument("--output-folder", type=Path, default=Path.home() / "electricity_price_data", help="Output folder for saving data")
    args = parser.parse_args()

    start_year, end_year = args.start_year, args.end_year
    output_folder = args.output_folder
    intervals = generate_monthly_intervals(start_year, end_year)
    logger.info(f"Fetching data for {start_year} - {end_year}. Total intervals/requests: {len(intervals)}")
    
    for idx, (start_date, end_date) in enumerate(intervals):
        filename = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
        if (output_folder / filename).exists():
            logger.info(f"File {filename} already exists, skipping.")
            continue
        logger.info(f"{idx:02d}/{len(intervals)} | Fetching data for {start_date.strftime('%Y-%m')}")
        data = fetch_data(start_date, end_date)
        if data:
            save_json(data, filename, output_folder)
            logger.info(f"Saved: {filename}")
            
        # Sleep to avoid rate limiting
        time.sleep(3)
        
    save_readme(output_folder)
    logger.info(f"Data fetching completed for {start_year} - {end_year}. Results saved in {output_folder}")

if __name__ == "__main__":
    main()
