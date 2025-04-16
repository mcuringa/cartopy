from shapely.geometry import MultiPolygon, Polygon, GeometryCollection
import os
import os.path
import requests
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import re
import zipfile
import pandas as pd
import geopandas as gpd
import us

from . import ui


def get_nyc_countyfps():
    return ['005', '047', '061', '081', '085']

def make_multi(geo):

    if isinstance(geo, GeometryCollection):
        print(geo)
        polygons = [geom for geom in geo if isinstance( geom, (Polygon, MultiPolygon))]
        return MultiPolygon(polygons)
    return geo


def shoreline(df, state):
    """
    Clip the land area to the continental US.
    """
    land = gpd.read_file("/home/mxc/Projects/cartopy/_data/cb_2018_us_state_500k.zip")
    land.to_crs(df.crs, inplace=True)
    state_fips = us.states.lookup(state).fips
    land = land[land.STATEFP == state_fips]
    land.geometry = land.geometry.apply(make_multi)

    return gpd.clip(df, land)


def get_state_county_map(state, year=2023):
    url = f"https://www2.census.gov/geo/tiger/TIGER{year}/COUNTY/tl_{year}_us_county.zip"
    gdf = gpd.read_file(url)
    state_fips = us.states.lookup(state).fips
    counties = gdf[gdf.STATEFP == state_fips].copy()
    counties = shoreline(counties, state)
    counties["tooltip"] = counties.apply(lambda x: f"{x.NAME} ({x.COUNTYFP})", axis=1)
    counties["popup"] = counties.apply(ui.popup(["NAME", "STATEFP", "COUNTYFP"]), axis=1)
    m = ui.base_map(counties, zoom=8)
    m = counties.explore(m=m, tooltip="tooltip", popup="popup", tooltip_kwds={"labels": False}, popup_kwds={"labels": False})
    m = ui.label_shapes(m, counties, "COUNTYFP")
    return m
    

def get_tracts_map(state, counties, year=2023):
    state_fips = us.states.lookup(state).fips
    url = f"https://www2.census.gov/geo/tiger/TIGER2022/TRACT/tl_2022_{state_fips}_tract.zip"
    gdf = gpd.read_file(url)
    counties = gdf[gdf.STATEFP == state_fips].copy()
    counties["tooltip"] = counties.apply(lambda x: f"{x.NAME} ({x.COUNTYFP})", axis=1)
    counties["popup"] = counties.apply(ui.popup(["NAME", "STATEFP", "COUNTYFP"]), axis=1)
    m = ui.base_map(counties, zoom=8)
    m = counties.explore(m=m, tooltip="tooltip", popup="popup", tooltip_kwds={"labels": False}, popup_kwds={"labels": False})
    m = ui.label_shapes(m, counties, "COUNTYFP")
    return m
    

def download(session, url, filename):
    with session.get(url, stream=True) as response:
        response.raise_for_status()

        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive chunks
                    file.write(chunk)
    geojson = unzip(filename)
    return geojson


def unzip(z):
    dir = os.path.dirname(z)
    filename = os.path.basename(z)
    outdir = os.path.join(dir, filename.split('.')[0])
    os.makedirs(outdir, exist_ok=True)
    with zipfile.ZipFile(z, 'r') as zip_ref:
        zip_ref.extractall(outdir)
    return to_geojson(outdir)


def to_geojson(dir):
    files = os.listdir(dir)
    parent = os.path.dirname(dir)
    for file in files:
        if file.endswith('.shp'):
            shp = os.path.join(dir, file)
            geojson = shp.replace('.shp', '.geojson')
            gdf = gpd.read_file(shp)
            json_out = os.path.join(parent, geojson)
            gdf.to_file(json_out, driver='GeoJSON')
            return json_out
    return None


def load_tiger_dir(url, root=None):
    """
    Find all of the .zip files at the url
    then download and unzip the archive,
    look for .shp shape files, and convert
    them to GeoJSON.

    Parameters:
    -----------
    url : str
        The tigerline url of the directory containing the .zip files
    root : str
        The root directory to save the files. Default is the current working directory.

    Returns:
    --------
    list
        A list of the GeoJSON files created from the shape files in the .zip archives.
    
    """
    if not root:
        root = os.getcwd()

    session = requests.Session()

    dir = url.split('/')[-2]

    dir = os.path.join(root, dir)
    os.makedirs(dir, exist_ok=True)
    html = session.get(url).text
    # get all the .zip a hrefs on the page
    files = re.findall(r'href=[\'"]?([^\'" >]+\.zip)', html)
    # remove possible duplicates
    files = list(files)
    files = list(set(files))

    results = []
    with ThreadPoolExecutor() as executor:
        futures = []
        for file in files:
            filename = os.path.join(dir, file)
            zipurl = os.path.join(url, file)
            futures.append(executor.submit(
                download, session, zipurl, filename))
        for future in as_completed(futures):
            results.append(future.result())
    return results
