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

# Deploying Reports to GitHub Pages

The project includes HTML reports that can be deployed to GitHub Pages for easy viewing.

## Quick Setup

1. **Generate the reports:**
   ```zsh
   pipenv run python3 ./src/main.py
   # Select option 5: Generate HTML reports
   ```

2. **Copy reports to docs/ folder:**
   ```zsh
   pipenv run python3 ./src/main.py
   # Select option 6: Copy reports to docs/ for GitHub Pages
   ```
   
   Or manually:
   ```zsh
   pipenv run python3 copy_reports_to_docs.py
   ```

3. **Commit and push to GitHub:**
   ```zsh
   git add docs/
   git commit -m "Update reports for GitHub Pages"
   git push origin main
   ```

4. **Enable GitHub Pages:**
   - Go to your repository on GitHub
   - Click **Settings** → **Pages**
   - Under "Source", select:
     - **Deploy from a branch**
     - Branch: `main`
     - Folder: `/docs`
   - Click **Save**

5. **Access your site:**
   - Your reports will be available at: `https://[your-username].github.io/nu_choate_league/`
   - It may take a few minutes for the site to be available after first deployment

## Automatic Deployment (Optional)

The repository includes a GitHub Actions workflow (`.github/workflows/deploy-pages.yml`) that can automatically deploy reports when you push changes to the `docs/` folder. To use it:

1. Enable GitHub Actions in your repository settings
2. The workflow will automatically run when you push changes to `docs/`

# Current State/Roadmap
I think that the api calls here get all the data that we need. I've also managed to wrangle some of the data into a more readable format, but this is just for easier data validation/checking. The transactions in particular are still quite messy. Work on the data handling is still ongoing, and while this might be some time later I should probably think about ways this info can actually be presented.