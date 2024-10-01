import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import toml
from functools import wraps
from dotenv import load_dotenv
import pandas as pd
import geopandas as gpd
import us

import datetime

import humanize

from invoke import task
import json


def get_project_config():
    config = {}
    with open('pyproject.toml', 'r') as f:
        config = toml.load(f)
    return config["project"]



def with_env(func):
    """Decorator to wrap a task after ENV vars are read, including data_dir."""
    @task
    @wraps(func)
    def wrapper(*args, **kwargs):
        load_dotenv()
        return func(*args, **kwargs)
    return wrapper



@task 
def clean(c):
    """Remove dist and docs directories."""
    c.run("rm -rf dist")
    c.run("rm -rf docs")

@task
def build(c):
    """Build the package."""
    project = get_project_config()
    name = {project['name']}
    print(f"building {name} v{project['version']} ")
    c.run("rm -rf dist")
    c.run("python -m build")
    c.run(f"cp dist/{name}-{project['version']}.tar.gz dist/{name}-latest.tar.gz")

@task
def push(c, production=False):
    """Push the current distribution to pypi.
    By default, this pushes to testpypi.
    To push to pypi, use the -p or --production flag.
    """

    api_token = os.getenv("PYPI_API_TOKEN")

    project = get_project_config()
    name = {project['name']}
    current = f"{name}-{project['version']}"
    if production:
        print("Pushing to pypi. This is NOT A DRILL.")
        c.run(f"twine upload dist/{current}* -u __token__ -p {api_token}")
    else:
        print("Pushing to testpypi")
        c.run(f"twine upload --repository testpypi dist/{current}*")

@task
def test(c, opt=""):
    """Run unit tests."""
    c.run(f"pytest {opt}")


@task
def tag(c):
    """Tag the current version."""
    project = get_project_config()
    version = project["version"]
    c.run(f"git tag -a {version} -m 'version {version}'")
    c.run(f"git push --tags")


@task
def hero_icons(c):
    """Download heroicons."""
    path = "./heroicons-master/optimized/16/solid"
    files = os.listdir(path)
    icons = {}
    for f in files:
        if f.endswith(".svg"):
            filepath = os.path.join(path, f)
            with open(filepath, "r") as svg:
                src = svg.read()
                key = f.replace(".svg", "")
                icons[key] = src
    # write it to icons.json with 2 tabs
    with open("hi-icons.json", "w") as f:
        json.dump(icons, f, indent=2)


@task
def tiger_places(c):
    """Download the census place data."""
    c.run("rm -rf _data/census_place")
    c.run("mkdir -p _data/census_place")
    c.run("mkdir -p data/census_place")
    places = list(range(1, 57)) + [60,66,69,72,78]

    results = []
    for num in places:
        place = f"tl_2023_{str(num).zfill(2)}_place"
        url = f"https://www2.census.gov/geo/tiger/TIGER2023/PLACE/{place}.zip"
        local = f"_data/census_place/{place}.zip"
        try:
            c.run(f"wget -nv -O {local} {url}")
        except:
            print("No data for place", place)
            continue
        c.run(f"unzip -q {local} -d _data/census_place/")
        c.run(f"rm {local}")
        df = gpd.read_file(f"_data/census_place/{place}.shp")
        df["STATE"] = df.STATEFP.map(us.states.mapping('fips', 'abbr'))
        df.to_file(f"data/census_place/{place}.geojson", driver="GeoJSON")
        results.append(df)

    combined = pd.concat(results)
    combined = gpd.GeoDataFrame(combined)
    combined.to_file("_data/census_place/census_place.geojson", driver="GeoJSON")


@task
def tiger_tracts(c):
    """Download the census tract data."""

    dir = "_data/tiger_tracts"

    c.run(f"rm -rf {dir}")
    c.run(f"mkdir -p {dir}")


    fips = list(range(1, 57)) + [60, 66, 69, 72, 78]

    results = []
    for fip in fips:
        
        tract = f"tl_2023_{str(fip).zfill(2)}_tract"
        url = f"https://www2.census.gov/geo/tiger/TIGER2023/TRACT/{tract}.zip"
        local = f"_data/census_place/{tract}.zip"
        try:
            c.run(f"wget -nv -O {local} {url}")
        except:
            print("No data for place", tract)
            continue
        c.run(f"unzip -q {local} -d {dir}/")
        c.run(f"rm {local}")
        df = gpd.read_file(f"{dir}/{tract}.shp")
        df["STATE"] = df.STATEFP.map(us.states.mapping('fips', 'abbr'))
        df.to_file(f"{dir}/{tract}.geojson", driver="GeoJSON")
        results.append(df)

    combined = pd.concat(results)
    combined = gpd.GeoDataFrame(combined)
    combined.to_file(f"{dir}/us_tiger_tracts.geojson", driver="GeoJSON")
