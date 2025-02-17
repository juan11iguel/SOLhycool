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