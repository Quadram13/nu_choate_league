# nu_choate_league
Python wrapper for sleeper fantasy http api

If you're just here for the raw data, go to [src/unmunged](./src/unmunged/)

# Overview
I just threw this together to grab data from sleeper. Most of the data that we can use is here, except for draft info. Next step is to wrangle this data into usable parts. If you plan on contributing, please create a new branch instead of committing directly to main. Also, sleeper mentions in their [docs](https://docs.sleeper.com/#introduction) that excessive calls might lead to getting ip-blocked, so keep that in mind.

# Setup
Assuming you have python installed(version>=3.12)
```zsh
# with nu_choate_league as root dir(and pipenv is not installed)
pip install pipenv

# install dependencies with pipenv
pipenv install

# start virtual env
pipenv shell

# or directly run code
pipenv run python3 ./yourcodehere

```

