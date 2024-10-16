import os
import os.path
import requests
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import re
import zipfile
import pandas as pd
import geopandas as gpd

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
