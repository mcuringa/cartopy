import pandas as pd
import geopandas as gpd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import us

census_vars = None
census_tables = None

def _init_vars():
    global census_vars
    global census_tables
    url = "https://api.census.gov/data/2020/acs/acs5/variables.json"
    response = requests.get(url)
    data = response.json()
    t = data["variables"]
    var_names = [k for k in t.keys() if k.startswith("B")]

    cols = ['var', 'label', 'concept', 'type', 'group', 'limit', 'attributes']

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


    ct = cv[["group", "concept"]].drop_duplicates()
    ct["is_table"] = ct.group.apply(lambda x: len(x) == 6)
    ct = ct[ct.is_table]
    ct.dropna(inplace=True)
    ct.drop(columns=["is_table"], inplace=True)
    ct = ct[ct.concept.notnull()]
    census_vars = cv
    census_tables = ct
    return cv, ct


def merge_sates(df):
    df["STATEFP"] = df.geography.str[-2:]
    states = gpd.read_file( "https://www2.census.gov/geo/tiger/TIGER2022/STATE/tl_2022_us_state.zip")
    states = states[["STATEFP", "STUSPS", "NAME", "geometry"]]
    data = states.merge(df, on="STATEFP")
    data.rename(columns={"NAME": "state_name", "STUSPS": "state"}, inplace=True)
    data.drop(columns=["STATEFP", "geography", "ucgid"], inplace=True)
    cols = list(data.columns)
    cols.remove("geometry")
    cols = cols + ["geometry"]
    data = data[cols]
    return data

def get(api, meta, multi=False):
    metadata = requests.get(meta).json()
    json = requests.get(api).json()
    data = pd.DataFrame(json[1:], columns=json[0])
    vars_url = metadata["dataset"][0]["c_variablesLink"]
    vars = requests.get(vars_url).json()
    vars = vars["variables"]

    drop = [c for c in data.columns if c not in vars]
    data.drop(columns=drop, inplace=True)

    field_names = dict()
    for k, v in vars.items():
        if k in json[0]:
            if "predicateOnly" in v and v["predicateOnly"]:
                field_names[k] = k
            else:
                field_names[k] = nice_name(v["label"])
    data.rename(columns=field_names, inplace=True)
    data = merge_sates(data)

    return data


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