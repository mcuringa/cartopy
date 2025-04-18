# NYC School Data
# Copyright (C) 2022. Matthew X. Curinga
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU AFFERO GENERAL PUBLIC LICENSE (the "License") as
# published by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the License for more details.
#
# You should have received a copy of the License along with this program.
# If not, see <http://www.gnu.org/licenses/>.
# ==============================================================================
import pandas as pd
from IPython.display import Markdown as md
from IPython.display import display
from decimal import *

import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import networkx as nx
import folium
import numpy as np
import random
import math
from shapely import Point
from shapely.geometry import LineString
from functools import partial
import xyzservices.providers as xyz
import warnings
from shapely import affinity

from .icons import hi_icons


# def census_race_cmap():
#     demo_colors = {
#         "asian": "darkred",
#         "black": "darkblue",
#         "hispanic": "darkgreen",
#         "white": "darkorange",
#     }


def base_map(gdf=None, center=None, zoom=10, provider=xyz.CartoDB.Positron, name=""):
    """
    Create a base map using Folium.

    Parameters:
    - gdf: `GeoDataFrame` to use for the center of the map
    - center: [latitude, longitude] for the center of the map
    - zoom: Initial zoom level of the map, scale is 1-18 (zoomed out --> zoomed in)
    - provider: Map tile provider from `xyzservices` (e.g., xyz.CartoDB.Positron, xyz.CartoDB.DarkMatter, etc.)
    - name: Name of the map (will show up if Layer Control is added)

    Returns:
    - folium.Map object
    """
    # if no center is provided, center it near the middle of the US
    if center == None and gdf is not None:
        minx, miny, maxx, maxy = gdf.total_bounds
        center = [(miny + maxy) / 2, (minx + maxx) / 2]
    elif center == None:
        center = [40.69018448848042, -73.98654521557344] # AU Brooklyn

    attr = "maptools" if not provider.attribution else provider.attribution
    m = folium.Map(name=name, tiles=provider, attr=attr, location=center, zoom_start=zoom)
    return m



def ul(t):
    """Create an unordered markdown list from a list of items"""

    items =  [f"- {i}" for i in t]
    return str("\n".join(items))

def label_plot(ax, df, col):
    """
    Add labels onto a matplotlib map at the center
    of each shape in the GeoDataFrame.

    Parameters
    ----------
    ax: matplotlib.Axes
        The axes to add the labels to
    df: GeoDataFrame
        The data to add labels from. It **must** have
        "geometry" column and a column that matches
        the `col` argument.
    col: str
        The column to use for the labels

    Returns
    -------
    matplotlib.Axes with labels added
    """
    
    def label(row):
        xy = row.geometry.centroid.coords[0]
        ax.annotate(row[col], xy=xy, ha='center', fontsize=8)

    df.apply(label, axis=1)
    return ax


def div_icon(icon, row, m=None, size=16,
             color=None, column=None, cmap=None,
             style_kwds={}, style_func=None,
             tooltip=None, popup=None, **kwargs):


    if cmap and column:
        color = cmap(row[column])
    elif color:
        color = color
    else:
        color = "blue"

    default_style = {
        "color": f"{color}",
        "stroke": f"{color}",
        "fill": f"{color}",
        "stroke-width": "1",
        "stroke-opacity": "0.8",
        "fill-opacity": "1",
        "height": f"{size}px",
        "width": f"{size}px"
    }
    css = default_style | style_kwds
    if style_func:
        feature = {
            "type": "Feature",
            "properties": row.to_dict(),
            "geometry": row.geometry.__geo_interface__
            }
        custom = style_func(feature)
        css = css | custom
        print(custom)
    if icon.startswith("hi-"):
        icon = hi_icons[icon.replace("hi-", "")]

    css = ";".join([f"{k}:{v}" for k, v in css.items()])

    point = row.geometry.centroid
    html = f"""<div style="{css}">{icon}</div>"""
    # print(html)
    marker = folium.Marker(
        location=(point.y, point.x),
        icon=folium.DivIcon(html=html),
        tooltip=tooltip,
        popup=popup,
         **kwargs)
    if m:
        marker.add_to(m)

    return marker


def cluster_radial(df, group_col, r):
    """
    Creates 2 new geometry columns for each row in df, arranging points radially around
    a computed cluster center for each group.

    Parameters
    ----------
    df : GeoDataFrame
         Contains point geometries.
    group_col : str
         Column name to group on. Points in each group will be arranged radially around the group center.
    r : int or callable
         The radius (in meters) for the radial placement. If r is an int, it is used as a fixed radius.
         If r is a function, it should accept (cluster_center, row) and return an int.

    Returns
    -------
    GeoDataFrame
         A copy of df with two new columns:
         - `geometry`: the new point geometry replaces the cluster center; 
            placed at a fixed distance from the cluster center.
         - `spoke_geom`: a LineString from the cluster center to the new point geometry.
         The GeoDataFrame’s active geometry will be set to `translated_geom`.
    """
    import numpy as np
    from shapely.geometry import LineString, Point
    from shapely import affinity
    import geopandas as gpd

    df = df.copy()

    def process_group(group):
        group = group.copy()
        n = len(group)
        union = group.unary_union
        if isinstance(union, Point):
            cluster_center = union
        else:
            cluster_center = union.centroid

        group["cluster_center"] = cluster_center

        group["angle"] = np.linspace(0, 360, n, endpoint=False)

        def update_row(row):
            meters = r
            if callable(r):
                meters = r(cluster_center, row)

            # Approximate conversion factors (these are rough estimates).
            d_lat = meters / 111320 
            d_lon = meters / (40075000 * np.cos(np.deg2rad(cluster_center.y)) / 360)

            angle_rad = np.deg2rad(row["angle"])
            dx = d_lon * np.cos(angle_rad)
            dy = d_lat * np.sin(angle_rad)

            new_point = affinity.translate(cluster_center, xoff=dx, yoff=dy)
            spoke = LineString([(cluster_center.x, cluster_center.y), (new_point.x, new_point.y)])

            row["geometry"] = new_point
            row["spoke_geom"] = spoke
            return row

        return group.apply(update_row, axis=1)

    result = df.groupby(group_col).apply(process_group).reset_index(drop=True)
    result = result.drop(columns=["angle", "cluster_center"])
    return gpd.GeoDataFrame(result, geometry="geometry", crs=df.crs)





def label_shapes(m, df, col, style={}):
    """Create a function that will add the string of `col`
    to the center of each shape in df """
    style_str = ";".join([f"{k}:{v}" for k,v in style.items()])
    def label(row):  
        point = row.geometry.centroid
        html=f"""<div style="{style_str}">{row[col]}</div>"""
        folium.Marker(
            location=(point.y, point.x), 
            icon=folium.DivIcon(html=html)).add_to(m)
    df.apply(label, axis=1)
    return m

def map_legend(m, items, title="", position="topleft"):
    """Create an interactive legend for the map with the items listed
    in the order they are passed in. The items should be a list
    of tuples with the first element being the label, the second
    being the html color, and (optional) third being the layer name.
    If a layer is included, the when that legend item is clicked, 
    items in that layer will be highlighted (toggled).


    Parameters
    ----------
    m: folium.Map the map to add the legend to
    items: list of tuples
        The items to include in the legend in the format (label, color)
        they will be displayed in the order they are passed in.
        For example: [("label1", "red"), ("label2", "blue"), ("label3", "#00ff00")]
        or [("label1", "red", "layer1"), ("label2", "blue", "layer2"), ("label3", "#00ff00", "layer3")]
        If the first tuple has 3 items, it is assumed that the legend will be
        interactive to toggle layers, i.e. each item **must** have a layer.
    title: str
        The title of the legend, appears at the top of the legend (default is "").
    position: string
        topleft | topright | bottomleft | bottomright (default is "topleft")
        Where to position the legend on the map. Not implemented yet.
    
    Returns
    -------
    folium.Map
        The map with the legend added to it.
    """

    css = """
.MapLegend {
  position: absolute;
  top: 10px;
  left: 80px;
  width: 200px;
  max-height: 600px;
  background: rgba(255,255,255,.8);
  z-index: 1000;
  padding: 1em;
  border: 2px solid lightgray;
  border-radius: 8px;
  overflow: auto;
  font-size: 14px;
  font-weight: bold;
}
.LegendItem {
    display: flex; 
    align-items: start; 
    margin-bottom: .5em;
}
.LegendMarker {
    width: 12px;
    height: 12px;
}

.LegendLabel {
    line-height: 14px; 
    padding-left: .25em; 
    font-size: 12px;
}
.MapLegend .clickable {
    cursor: pointer;
}
.dim {
    opacity: .2;
}
"""

    js = """
function toggleMarkers(color) {
  console.log("toggling markers with color", color);
  const markers = document.querySelectorAll('path.leaflet-interactive');
  console.log(markers);
  const toggle = document.querySelectorAll('path.leaflet-interactive[stroke="'+color+'"]');
  console.log(toggle);
  markers.forEach(marker => marker.classList.add("dim"));
  toggle.forEach(marker => marker.classList.remove("dim"));
}
"""

    
    def legend_item(label, color, layer=None):
        onclick = ""
        clickable = ""
        if layer:
            onclick = f"toggleMarkers('{color}')"
            clickable = " clickable"
        return f"""
        <div class="LegendItem">
          <div class="LegendMarker{clickable}" onclick="{onclick}" style="background:{color};">&nbsp;</div>
          <div class="LegendLabel{clickable}" onclick="{onclick}"><strong>{label}</strong></div>
        </div>
"""
    
    if len(items[0]) == 2:
        legend_items = "".join([legend_item(label, color) for label, color in items])
    elif len(items[0]) == 3:
        legend_items = "".join([legend_item(label, color, layer) for label, color, layer in items])
    else:
        raise ValueError("Legend items must be a list of tuples with 2 or 3 elements.")

    html = f"""
<div class="MapLegend">
  <style>{css}</style>
  <script>{js}</script>
  <h4><strong>{title}</strong></h4>
  {legend_items}
</div>
"""

    m.get_root().html.add_child(folium.Element(html))
    return m


def map_layers(m, df, radius=5):

    def create_layer(df, name, color="color", popup="popup",title="title", radius=5):
        layer = folium.FeatureGroup(name=name)
        def marker(row):
            
            info = row[popup] if popup in row else None
            tooltip = row[title] if title in row else None

            return folium.Circle(
                location=(row['geometry'].y, row['geometry'].x),
                radius=20,
                color=row[color],
                fill=True,
                fill_color=row[color],
                fill_opacity=1,
                opacity=1,
                popup=info,
                tooltip=tooltip,
                className=f"layer-marker layer-{name} zoomable"
            )
        df.apply(lambda row: marker(row).add_to(layer), axis=1)

        layer.add_to(m)

        return layer

    groups = df.groupby("layer")
    for name, group in groups:
        create_layer(group, name, radius=radius)
    # add layer control
    # folium.LayerControl().add_to(m)
    return m


def rand_points(geometry, n, max_conflicts=0):
    """
    Create n random points within the bounds of the geometry.
    
    Parameters
    ----------
    geometry: shapely.geometry
        The geometry to create points within
    n: int
        The number of points to create

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame with n random points within the geometry

    """
    minx, miny, maxx, maxy = geometry.bounds

    plotted_points = set()
    conflicts = 0

    def occupied(p):
        if p in plotted_points:
            conflicts += 1
            return True or conflicts > max_conflicts
        plotted_points.add(p)
        return False

    def rand_point():

        x = random.uniform(minx, maxx)
        y = random.uniform(miny, maxy)
        p = Point(x, y)
        if p.within(geometry) and not occupied(p):
            return p
        return rand_point()

    points = [rand_point() for i in range(n)]
    if conflicts > 0:
        print(f"Conflicts in plotting {n} points:", conflicts)
    # create a GeoDataFrame from the points
    points = pd.DataFrame({"geometry": points})
    return points


def dot_density(gdf, scale=100, count_col='n', radius=5, column=None, color="blue", cmap=None, title=None, popup=None):
    """
    Create a dot density map from the data in gdf. The map will
    have a layer for each unique value in the "layer" column of the
    DataFrame. The "color" column will be used to color the dots.
    The "title" column will be used for the tooltip, and the "popup"
    column will be used for the popup.

    Parameters
    ----------
    m: folium.Map
        The map to add the dot density map to
    gdf: GeoDataFrame
        The data to plot
    count_col: str
        The column to use for the dot density (i.e. plot `n` items for each geometry)
    scale: int
        Each dot represents `n` items; `count_col` is divided by `scale` to get the number of dots

    radius: int
        The radius of the dots
    color: str
        The column to use for the color of the dots
    title: str
        The column to use for the tooltip
    popup: str
        The column to use for the popup

    Returns
    -------
    folium.Map
        The map with the dot density map added
    """
    results = []

    def fill_space(geometry):
        def make_rand_points(row):
            num_points = row[count_col] // scale
            points = rand_points(row.geometry, num_points)
            if color in row and cmap:
                points["color"] = hexmap(cmap)(row[color])
            elif color in row:
                points["color"] = row[color]
            else:
                points["color"] = color

            results.append(points)

        gdf[gdf.geometry == geometry].apply(make_rand_points, axis=1)
    
    for geometry in gdf.geometry:
        fill_space(geometry)


    points = pd.concat(results)

    return points

def map_js(m, file_path, js):
    """Add the custom javascript to the map
    that will load after the body is rendered
    and all other map elements are ready.
    Do not wrap js in <script> tags."""
    m.save(file_path)

    html = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {""" + js + """

    });
    </script>
    """

    # open the map html and insert the footer at the bottom of page
    with open(file_path, 'r') as file:
        content = file.read()

    with open(file_path, 'w') as file:
        file.write(content.replace('</html>', f"{html}</html>"))
    
    return file_path


def map_footer(m, file_path, html):
    """Add the html to the bottom of the map html file"""
    m.save(file_path)

    # open the map html and insert the footer at the bottom of page
    with open(file_path, 'r') as file:
        content = file.read()

    with open(file_path, 'w') as file:
        file.write(content.replace('</body>', f"{html}</body>"))
    
    return file_path

def map_header(m, file_path, html):
    """Add the html to the top of the map html file"""
    m.save(file_path)

    # open the map html and insert the header at the top of page
    with open(file_path, 'r') as file:
        content = file.read()

    with open(file_path, 'w') as file:
        file.write(content.replace('<body>', f"<body>{html}"))
    
    return file_path


def create_layer(m, data, name, style={"color": "blue", "weight": 0, "opacity": 0},tooltip=None,radius=2):
    """Create a folium layer from the data. A new CircleMarker is created for
    each row in the DataFrame and added to map `m`.
    Parameters
    ----------
    m: folium.Map
        The map to add the layer to
    data: GeoDataFrame
        The data to plot
    name: str
        The name of the layer
    style: dict
        The style of the layer. Default is {"color": "blue", "weight": 0, "opacity": 0}
    tooltip: str
        The column name to use for the tooltip. Default is None.
    radius: int
        The radius of the circle markers. Default is 2.

    Returns
    -------
    folium.FeatureGroup
        The layer created from the data
    """
    layer = folium.FeatureGroup(name=name)

    def marker(row):
        tool = row[tooltip] if tooltip else False
        return folium.CircleMarker(
            location=(row['geometry'].y, row['geometry'].x),
            radius=radius,
            style=style,
            fill=True,
            popup=tool
        )
    data.apply(lambda row: marker(row).add_to(layer), axis=1)

    layer.add_to(m)

    return layer


def popup(cols, style={"min-width": "200px"}, title=True, fmt_funcs={}):
    """
    Create a function that will generate an HTML popup for a folium map.
    The function will use column names as keys and row data as values.
    If the column name has the special value `----`, a horizontal rule
    will be created as a separator in the popup.

    This is useful to create a popup with a sub-selection of columns
    from a `GeoDataFrame`. Column names are automatically converted
    to "nice names" by replacing underscores with spaces and capitalizing
    the first letter of each word.

    Numerical data is formatted with commas and 3 decimal places.
    For columns with names ending in `_pct`, the data is formatted as a percentage.

    Parameters
    ----------
    cols: list
        The columns to include in the popup
    style: dict
        The CSS style to apply to the popup <div>. Default is {"min-width": "200px"}
    title: bool
        If `True`, the value of the first column will be bold and appear without a label
    fmt_funcs: dict
        A dictionary of functions to apply to the data in each column.
        The keys are the column names and the values are the functions to apply.
    """

    style_str = ";".join([f"{k}:{v}" for k,v in style.items()])

    def html(row):
        def content(c):
            if c == "----":
                return """<hr style="padding: 0;margin:0; margin-bottom: .25em; border: none; border-top: 2px solid black;">"""
            # make a partial of fmt_num that includes the column name

            f = fmt_funcs.get(c, partial(fmt_num, c))
            if c == cols[0] and title:
                return f"<b>{f(row[c])}</b><br>"
            return f"{nice_name(c)}: {f(row[c])}<br>"
        
        items = [content(c) for c in cols]
        items = "".join(items)
        return f'<div style="{style_str}">{items}</div>'

    return html


def fmt_num(col, n):
    if col.endswith("_pct"):
        return pct(n)
    try:
        n = float(n)
        if round(n) == n:
            return f"{int(n):,}"
        else:
            return f"{n:,.2f}"
    except:
        return n

def hexmap(cmap):

    def f(color):
        return mpl.colors.rgb2hex(cmap(color))

    return f

def pct(n):
    try:
        whole = int(n)
        if whole == float(n):
            return f"{whole}%"
        n = float(n)
        return f"{n:.1%}"
    except:
        return "-"

def commas(n):
    try:
        float(n)
        return f"{round(n, 3):,}"
    except:
        return "-"


def fmt_table(df, col_map=None, pct_cols=[], num_cols=[]):
    result = df.copy()
    for col in pct_cols:
        result[col] = result[col].apply(pct)

    for col in num_cols:
        result[col] = result[col].apply(commas)

    if col_map:
        result = result.rename(columns=col_map)
    return result


def show_md(s):
    display(md(s))

def infinite():
    n = 0
    while True:
        n += 1
        yield n


def counter():
    x = infinite()
    return x.__next__

# strips the leading zero from a rounded float
def round_f(f, places):

    s = str(round(f, places))
    if not "." in s:
        return f

    whole, frac = s.split(".")
    if whole == "0":
        whole = ""
    frac = frac.ljust(places, "0")
    return f"{whole}.{frac}"


def fmt_pearson(r):
    """Formats the Pearson's R correlation table returned
    from `pengouin.corr` in the format r(df)={r}, p={p}.
    The r is rounded to 2 decimals, and p is rounded to 3 decimals.
    """
    df = r.n[0] - 2
    p = round_f(r['p-val'][0], 3)
    r_val = round_f(r['r'][0], 2)
    return f"r({df})={r_val}, p={p}"


def edge_label(p, r):
    return f"{p}={round_f(r,2)}"

def nice_name(n):
    allcaps = ["dbn", "beds"]
    if n in allcaps:
        return n.upper()

    return n.replace("_", " ").title()
