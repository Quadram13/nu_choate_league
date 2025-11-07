# nu_choate_league



# Overview
Fantasy football data from the Nu Choate League on sleeper, as well as code to retrieve it from the sleeper http api and reformat it. If you're just here for the data, here is the [unformatted](./src/unmunged) and [formatted](./src/munged) data. If you plan on contributing, please create a new branch instead of committing directly to main. Also, sleeper mentions in their [docs](https://docs.sleeper.com/#introduction) that excessive calls might lead to getting ip-blocked, so keep that in mind.

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
pipenv run python3 ./src/main.py

```

# Current State/Roadmap
I think that the api calls here get all the data that we need. I've also managed to wrangle some of the data into a more readable format, but this is just for easier data validation/checking. The transactions in particular are still quite messy. Work on the data handling is still ongoing, and while this might be some time later I should probably think about ways this info can actually be presented.