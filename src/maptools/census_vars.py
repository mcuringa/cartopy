import pandas as pd
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
    census_vars = cv
    census_tables = ct


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
    var = var.replace(":!!", " ")
    var = "_".join(var.split(" "))
    if var.endswith(":"):
        var = var[:-1]
    return var




def get_variables():
    global census_vars
    if census_vars is None:
        _init_vars()
    return census_vars.copy()


def get_tables():
    global census_tables
    if census_tables is None:
        _init_vars()
    return census_vars.sort_values(by="group").copy()



def search(term):

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(census_tables.concept)

    query_vec = vectorizer.transform([term])
    similarity = cosine_similarity(query_vec, tfidf_matrix)
    tables = get_tables()
    tables['similarity'] = similarity.flatten()
    return tables[tables.similarity > .65].sort_values(by='similarity', ascending=False).head(10).copy()

