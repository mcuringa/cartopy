import pandas as pd
import geopandas as gpd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import us
import warnings

census_vars = None
census_tables = None


# http://api.census.gov/data/2022/acs/acs5/variables.json

def _init_vars():
    global census_vars
    global census_tables
    details = "https://api.census.gov/data/2022/acs/acs5/variables.json"
    subjects = "https://api.census.gov/data/2022/acs/acs5/subject/variables.json"
    urls = [details, subjects]
    def load_meta(url):
        response = requests.get(url)
        data = response.json()
        t = data["variables"]
        # var_names = [k for k in t.keys() if k.startswith("B")]

        # cols = ['var', 'label', 'concept', 'type', 'group', 'limit', 'attributes']

        def make_row(var, data):
            return {
                "var": var,
                "label": data.get("label", None),
                "concept": data.get("concept", None),
                "var_name": nice_name(data.get("label", None)),
                "type": data.get("predicateType", None),
                "group": data.get("group", None),
                "limit": data.get("limit", None),
                "attributes": data.get("attributes", None)
            }


        rows = [make_row(k, v) for k, v in t.items()]
        cv = pd.DataFrame(data=rows)
        cv = cv[~cv["var"].isin(["for", "in", "ucgid"])]
        cv.sort_values(by="group", inplace=True)
        cv = cv[['var', 'group', 'concept',  'label', 'var_name', 'type',  'limit', 'attributes']]
        return cv

    cv = pd.concat([load_meta(url) for url in urls])
    ct = cv[["group", "concept"]].drop_duplicates()
    ct["is_table"] = ct.group.apply(lambda x: len(x) == 6)
    ct = ct[ct.is_table]
    ct.dropna(inplace=True)
    ct.drop(columns=["is_table"], inplace=True)
    ct = ct[ct.concept.notnull()]
    census_vars = cv
    census_tables = ct
    return cv, ct


def merge_states(df):
    df["STATEFP"] = df.ucgid.str[-2:]
    states = gpd.read_file( "https://www2.census.gov/geo/tiger/TIGER2022/STATE/tl_2022_us_state.zip")
    states = states[["STATEFP", "STUSPS", "geometry"]]
    data = states.merge(df, on="STATEFP")
    data.rename(columns={"NAME": "state_name", "STUSPS": "state", "STATEFP":"statefp"}, inplace=True)
    cols = list(data.columns)
    cols.remove("geometry")
    cols = cols + ["geometry"]
    data = data[cols]
    return data


def merge_counties(df):
    land = gpd.read_file( "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_500k.zip")
    df["GEOID"] = df.ucgid.apply(lambda x: x.split("US")[1])
    df["state_name"] = df.NAME.apply(lambda x: x.split(",")[1].strip())
    df.drop(columns=["NAME"], inplace=True)
    county_url = "https://www2.census.gov/geo/tiger/TIGER2022/COUNTY/tl_2022_us_county.zip"
    counties = gpd.read_file(county_url)
    counties = counties[["GEOID", "STATEFP", "COUNTYFP", "NAME", "geometry"]]
    data = counties.merge(df, on="GEOID")
    data.rename(columns={"NAME": "county", "COUNTYFP": "countyfp", "STATEFP": "statefp"}, inplace=True)
    data["state"] = data.statefp.apply(lookup_state)
    cols = list(data.columns)
    cols.remove("geometry")
    cols = cols + ["geometry"]
    data = data[cols]
    land = land[land.STATEFP.isin(data.statefp.unique())]
    data = gpd.clip(data, land)
    return data

def merge_tracts(df):
    land = gpd.read_file("https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_500k.zip")


    df["GEOID"] = df.ucgid.apply(lambda x: x.split("US")[1])
    state_fips = df.ucgid.apply(lambda x: x.split("US")[1][:2])
    state_fips = state_fips.unique()
    for statefp in state_fips:
        
        url = f"https://www2.census.gov/geo/tiger/TIGER2022/TRACT/tl_2022_{statefp}_tract.zip"
        state = land[land.STATEFP == statefp]
        
        tracts = gpd.read_file(url)       
        tracts = tracts[["GEOID", "geometry", "STATEFP", "COUNTYFP", "TRACTCE"]]
        
        data = tracts.merge(df, on="GEOID")
        # push geometry cols to the end
        cols =  list(df.columns) + ["STATEFP", "COUNTYFP", "TRACTCE", "geometry"]
        data = data[cols]
        data.columns = [c.lower() for c in data.columns]
        data = gpd.clip(data, state)
    return data

def merge_geography(data):
    data = data.copy()
    level_codes = {
        "010": "Nation",
        "020": "Region",
        "030": "Division",
        "040": "State",
        "050": "County",
        "060": "County Subdivision",
        "067": "Subminor Civil Division",
        "140": "Census Tract",
        "150": "Census Block",
        "160": "Place",
        "170": "Consolidated City",
        "230": "Alaska Native Regional Corporation",
        "250": "American Indian Area/Alaska Native Area/Hawaiian Home Land",
        "251": "American Indian Area (Reservation or Off-Reservation Trust Land)",
        "252": "Alaska Native Village Statistical Area",
        "254": "Oklahoma Tribal Statistical Area",
        "256": "Tribal Designated Statistical Area",
        "258": "American Indian Joint-Use Area",
        "260": "Metropolitan Statistical Area/Micropolitan Statistical Area",
        "310": "Metropolitan Division",
        "314": "Combined Statistical Area",
        "330": "State Metropolitan Statistical Area",
        "335": "New England City and Town Area (NECTA)",
        "336": "NECTA Division",
        "350": "Combined NECTA",
        "400": "Urban Area",
        "500": "Congressional District",
        "610": "State Legislative District (Upper Chamber)",
        "620": "State Legislative District (Lower Chamber)",
        "700": "Public Use Microdata Area (PUMA)",
        "860": "ZIP Code Tabulation Area (ZCTA)",
        "970": "School District (Elementary)",
        "980": "School District (Secondary)",
        "990": "School District (Unified)"
    }
    geo_levels = data.ucgid.apply(lambda x: x[:3]).unique()
    assert len(geo_levels) == 1, "Data contains multiple geographic levels"
    level = level_codes[geo_levels[0]]
    print(f"Geographic level: {level}")
    if level == "Nation":
        warnings.warn("Nation level data is not merged with geography")
        return data
    
    
    if level == "State":
        data = merge_states(data)
        return data.sort_values(by="state")
    
    if level == "County":
        data = merge_counties(data)
        return data.sort_values(by=["state", "county"])
    
    if level == "Census Tract":
        return merge_tracts(data)

    warnings.warn(f"Unsupported geographic level: {level}, no geography available")
    return data

def merge_meta(data, meta):
    data = data.copy()
    geo_vars = ['AIANHH', 'ANRC', 'CBSA', 'CD', 'COUNTY', 'COUSUB', 'CSA',
                'GEOCOMP', 'GEO_ID', 'METDIV', 'NAME', 'NATION',
                'PLACE', 'PRINCITY', 'PUMA', 'REGION', 'SDELM',
                'SDSEC', 'SDUNI', 'STATE', 'SUMLEVEL', 'UA',
                'block group', 'congressional district', 'county', 'for', 'in',
                'place', 'state', 'tract', 'ucgid', 'zcta']
    
    metadata = requests.get(meta).json()
    vars_url = metadata["dataset"][0]["c_variablesLink"]
    vars = requests.get(vars_url).json()
    vars = vars["variables"]

    aliases = {}
    for c in data.columns:
        meta = vars.get(c, None)
        predicate = meta.get("predicateOnly", False) if meta is not None else False
        if c in geo_vars or predicate:
            aliases[c] = c
            continue
        
        if meta is None:
            # if not c.startswith("D"):
            #     print(f"{c},")
            continue

        # try to convert to the correct type
        t = meta.get("predicateType", None)
        try:
            if t in ["int", "float"]:
                i = data[c].astype(float)
                try:
                    i = i.astype(int)
                except:
                    pass
                data[c] = i
        except:
            print(f"Error converting {c} to {t}. Value ({data[c]})")
        
        n = nice_name(meta["label"])
        aliases[c] = n

    # print(aliases)
    aliases = de_dup(aliases)
    data = data[aliases.keys()]
    data.rename(columns=aliases, inplace=True)
    duplicates = data.columns[data.columns.duplicated()]
    assert len(duplicates) == 0, f"Duplicate columns:\n {duplicates}"
    return data

def de_dup(aliases):
    rev = {v:k for k, v in aliases.items()}
    new_aliases = {}
    for var, label in aliases.items():
        if label in rev and rev[label] != var:
            label = f"{label}_(var)"
        new_aliases[var] = label
    
    return new_aliases


def get(api, meta, raw=False):
    json = requests.get(api).json()
    data = pd.DataFrame(json[1:], columns=json[0])
    if raw:
        return data
    data = merge_meta(data, meta)

    data = merge_geography(data)
    return data.copy()



def lookup_state(statefp):
    if statefp == "11":
        return "DC"

    state = us.states.lookup(statefp)
    if state is not None:
        return state.abbr

    territory = us.states.lookup(statefp)
    if territory is not None:
        return territory.abbr

    return statefp

def nice_name(var):
    var = var.replace("Estimate!!", "")
    var = var.lower()

    var = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', re.sub(r'[^a-zA-Z0-9]+', '_', var))

    if var.startswith("total_"):
        var = var[6:]
    
    var = "_".join(var.split(" "))
    if var.endswith(":"):
        var = var[:-1]
    return var


def col_name(var):
    if "!!" in var:
        var = var.split("!!")[-1]
    return nice_name(var)

def rename_columns(data, year=2023):

    url = f"http://api.census.gov/data/{year}/acs/acs1/subject/variables.json"
    resp = requests.get(url)
    json = resp.json()

    df = pd.DataFrame(json['variables']).T

    df["var_name"] = df.label.apply(col_name)
    df.var_name = df.var_name.str.replace("total_households_", "")
    df.var_name = df.var_name.str.replace("percent_total_households_", "")
    col_map = df["var_name"].to_dict()
    col_map['[["GEO_ID"'] = 'GEOID'

    results = data.rename(columns=col_map)
    # get cols not in col_map
    def check(c):
        if c not in col_map.values() and "_" in c and not c.endswith("E"):
            return True
        if c.startswith("Unnamed"):
            return True
    
    drop_cols = [c for c in results.columns if check(c)]
    results.drop(columns=drop_cols, inplace=True)

    return results


def get_variables():
    global census_vars
    if census_vars is None:
        _init_vars()
    return census_vars.copy()


def get_tables():
    global census_tables
    if census_tables is None:
        _init_vars()
    return census_tables.sort_values(by="group").copy()



def search(term, results=20):
    tables = get_tables()
    tables = tables[tables.concept.notnull()]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(tables.concept)

    query_vec = vectorizer.transform([term])
    tables["match"] = cosine_similarity(query_vec, tfidf_matrix).flatten()
    tables.sort_values(by='match', ascending=False, inplace=True)
    tables = tables.head(results).copy()
    results = tables.style.set_properties(subset=['concept'], **{'white-space': 'pre-wrap', 'word-wrap': 'break-word'})
    results.format({'match': '{:.2%}', 'concept': lambda x: x.title()})
    return results


def get_table(table, as_dict=True):
    table = table.upper()
    variables = get_variables()
    results = census_vars[variables.group == table].copy()
    results.sort_values(by="var", inplace=True)
    if as_dict:
        return results.set_index('var')['var_name'].to_dict()
    return results