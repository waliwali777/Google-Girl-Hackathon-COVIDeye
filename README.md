<p>
<img src="https://github.com/architmodi/En-route-to-safety/raw/52d2db96942b0501ff8c87fe029a3143f5ef07c1/static/erts-logo.png" width="100" alt="ERTS logo">
</p>

## En Route To Safety

En route to safety is a Facebook messenger bot that provides the user a safer alternative to travel in the midst of COVID-19 pandemic by suggesting nearby safer places or the statistics (cases, deaths, etc.) of the location user is planning to travel to. User can also subscribe to these statistics. App hosted [here](https://erts.herokuapp.com)

NOTE: This bot is currently supported in USA only (More countries to be added soon)

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install the bot.

```bash
pip3 install -r requirements.txt
```

## Setup

Edit the .sample.env to set ACCESS_TOKEN, VERIFY_TOKEN and MAPS_API_TOKEN fields and save as .env
```bash
$ mv .sample.env .env
$ # set the necessary fields the .env file 
$ source .env
$ python3 app.py
```

## Features

* Search provides a safer county adjacent to the user provided address' county
* Quick select (Grocery, Pharmacy, Hospital, Other) options to search for a category for the location
* Upto two search results for a category selected
* Subscribe to county updates

## Sources

En Route To Safety uses the following sources:
* County wise COVID data [nytimes/covid-19-data](https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv)
* State COVID site data [covidtracking.com](https://covidtracking.com/api/)
* County adjacency data [Census Bureau](https://www2.census.gov/geo/docs/reference/county_adjacency.txt)

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[Apache 2.0](http://www.apache.org/licenses/LICENSE-2.0)