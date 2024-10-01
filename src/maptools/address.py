import warnings
import re

from shapely import Point

# USPS Street Suffix Abbreviations
# https://pe.usps.com/text/pub28/28apc_002.htm
# this most be sorted by length, longest first
# t = [(sfx, len(sfx)) for sfx in address.USPS_STREET_SUFF]
# t.sort(key=lambda x: x[1])
# [x[0] for x in x]

USPS_STREET_SUFF = ['TERRACE PLACE', 'TRAFFICWAY', 'THROUGHWAY', 'EXTENSIONS', 'EXPRESSWAY', "CONCOURSE",
    'CROSSROADS', 'BOULEVARD ', 'STRAVENUE', 'CROSSROAD', 'EXTENSION', 'CROSSING ', 
    'JUNCTIONS', 'MOUNTAINS', 'UNDERPASS', 'BOULEVARD', 'JUNCTION', 'TURNPIKE', 'PARKWAYS', 'BROADWAY',
    'MOUNTAIN', 'VILLIAGE', 'MOTORWAY', 'VILLAGES', 'OVERPASS', 'CRESCENT', 'CAUSEWAY', 
    'CENTERS ', 'CROSSING', 'STRAVEN', 'SPRINGS', 'DRIVES ', 'CRSSNG ', 'EXPRESS', 
    'ESTATES', 'RANCHES', 'TUNNELS', 'VIADUCT', 'VALLEYS', 'GARDENS', 'HARBORS', 'PASSAGE', 
    'HIGHWAY', 'JUNCTON', 'MISSION', 'ISLANDS', 'HEIGHTS', 'ORCHARD', 'MOUNTIN', 'PRAIRIE', 
    'PARKWAY', 'FREEWAY', 'FORESTS', 'STREETS', 'CORNERS', 'COMMONS', 'BLUFFS ', 'STATION', 
    'CENTERS', 'TERRACE', 'SQUARES', 'BROOKS ', 'TRAILER', 'STRVNUE', 'CIRCLES', 'LANDING', 
    'HOLLOWS', 'GATEWAY', 'ARCADE ', 'VILLAGE', 'MEADOWS', 'DIVIDE', 'RIDGES', 'RADIEL', 
    'SHORES', 'STRAVN', 'CLIFFS', 'CURVE ', 'EXTNSN', 'SHOARS', 'SHOALS', 'RAPIDS', 
    'MANORS', 'MNTAIN', 'HIGHWY', 'MEDOWS', 'JUNCTN', 'AVENUE', 'LIGHTS', 'KNOLLS', 
    'GROVES', 'ISLNDS', 'HARBOR', 'ORCHRD', 'STREAM', 'TURNPK', 'TUNNEL', 'ESTATE', 
    'FOREST', 'RADIAL', 'TRACKS', 'CORNER', 'CIRCLE', 'SQUARE', 'TRACES', 'SKYWAY', 
    'SPRNGS', 'STREET', 'SPRING', 'COURTS', 'DRIVES', 'COURSE', 'CRSENT', 'COMMON', 
    'BROOKS', 'BYPASS', 'CANYON', 'BRIDGE', 'CAUSWA', 'CENTER', 'BLUFFS', 'BRANCH', 
    'SUMITT', 'SUMMIT', 'CENTRE', 'BOTTOM', 'STREME', 'TRAILS', 'ARCADE', 'JCTION', 
    'MEADOW', 'VILLAG', 'ISLAND', 'GREENS', 'VALLEY', 'POINTS', 'PLAINS', 'PARKWY', 
    'GATEWY', 'FORGES', 'GATWAY', 'FREEWY', 'FIELDS', 'HOLLOW', 'GARDEN', 'UNIONS', 
    'VIADCT', 'SPRNG', 'SPNGS', 'RNCHS', 'RIVER', 'ROADS', 'SHORE', 'SHOAR', 'SHOAL', 
    'CRSNT', 'SPURS', 'DALE ', 'CRCLE', 'COVES', 'CREST', 'BOULV', 'CENTR', 'SUMIT', 
    'TRLRS', 'TRNPK', 'TUNEL', 'TUNLS', 'STRVN', 'WELLS', 'ALLEY', 'ALLEE', 'ANNEX', 
    'BEACH', 'TRAIL', 'BLUFF', 'BOTTM', 'BROOK', 'BRNCH', 'CNTER', 'COURT', 'DRIVE', 
    'CLIFF', 'BRDGE', 'BURGS', 'BYPAS', 'CANYN', 'TRACK', 'TRACE', 'STRAV', 'STATN', 
    'CIRCL', 'CREEK', 'RANCH', 'FORDS', 'ROUTE', 'RIDGE', 'HAVEN', 'HARBR', 'FRWAY', 
    'HOLWS', 'TUNNL', 'UNION', 'VALLY', 'FORKS', 'GTWAY', 'PKWYS', 'PLAIN', 'GARDN', 
    'FLATS', 'FIELD', 'FALLS', 'FERRY', 'PORTS', 'PLACE', 'PLAZA', 'POINT', 'PKWAY', 
    'PINES', 'PIKES', 'PATHS', 'GLENS', 'FORGE', 'GRDEN', 'RAPID', 'GREEN', 'GRDNS', 
    'HRBOR', 'MOUNT', 'MNTNS', 'HILLS', 'ISLES', 'ISLND', 'PARKS', 'GROVE', 'MILLS', 
    'MISSN', 'HIWAY', 'MANOR', 'INLET', 'KNOLL', 'JCTNS', 'LIGHT', 'LAKES', 'LNDNG', 
    'LOCKS', 'LODGE', 'LOOPS', 'AVENU', 'WALKS', 'BAYOU', 'BAYOO', 'AVNUE', 'VIEWS', 
    'VILLE', 'VILLG', 'VISTA', 'VLLY', 'VLGS', 'VIST', 'VILL', 'VLYS', 'VIEW', 'WALK', 
    'VSTA', 'LAKE', 'JCTN', 'JCTS', 'AVEN', 'KEYS', 'KNLS', 'LOCK', 'LOAF', 'LANE', 'LAND', 
    'LCKS', 'LDGE', 'HWAY', 'KNOL', 'MALL', 'MDWS', 'LODG', 'LOOP', 'HIWY', 'FRWY', 'ORCH', 
    'NECK', 'MSSN', 'MTIN', 'GROV', 'HLLW', 'INLT', 'PARK', 'ISLE', 'OVAL', 'MEWS', 'HILL', 
    'MILL', 'MNRS', 'MNTN', 'LNDG', 'PLZA', 'PNES', 'PORT', 'FRST', 'FRRY', 'FRKS', 'PASS', 
    'PATH', 'FLAT', 'FALL', 'GLEN', 'GDNS', 'VDCT', 'FORT', 'GTWY', 'HARB', 'FORK', 'FORG', 
    'HOLW', 'GRDN', 'EXTS', 'PIKE', 'PKWY', 'PINE', 'BLVD', 'BLUF', 'TRLR', 'BOUL', 'TRLS', 
    'TUNL', 'STRM', 'STRT', 'ANEX', 'DRIV', 'DALE', 'WALK', 'DAM ', 'SHLS', 'EXPW', 'EXPY', 'EXTN', 
    'CRSE', 'CRCL', 'CORS', 'COVE', 'SQRS', 'SQRE', 'CSWY', 'RPDS', 'PRTS', 'ROAD', 'RDGE', 
    'SHRS', 'RDGS', 'REST', 'RIVR', 'RNCH', 'FORD', 'FLTS', 'RAMP', 'FLDS', 'RADL', 'ESTS', 
    'EXPR', 'PLNS', 'ALLY', 'XING', 'ANNX', 'WALL', 'BURG', 'CNYN', 'BYPS', 'CAMP', 'BYPA', 
    'BEND', 'ARC ', 'WELL', 'WAYS', 'TRAK', 'TRCE', 'TRKS', 'STRA', 'CAPE', 'CENT', 'TERR', 
    'SLIP', 'SPGS', 'CNTR', 'SPUR', 'SPNG', 'CLUB', 'CLFS', 'CRES', 'CIRC', 'PRK', 'PKY', 'GRV', 
    'GLN', 'VST', 'VWS', 'LDG', 'VLY', 'AVE', 'AVN', 'VIS', 'VLG', 'FRD', 'VIA', 'NCK', 
    'MTN', 'GRN', 'HLS', 'FWY', 'FRY', 'OVL', 'HBR', 'JCT', 'ISS', 'MNT', 'MNR', 'LKS', 
    'LGT', 'KYS', 'LCK', 'HWY', 'MDW', 'HTS', 'HVN', 'KNL', 'KEY', 'FRG', 'FRK', 'FLD', 
    'FRT', 'COR', 'RST', 'RUE', 'SQR', 'DAM', 'DIV', 'DM ', 'DL ', 'EXT', 'SHL', 'RVR', 
    'RUN', 'SHR', 'FLT', 'DVD', 'PLZ', 'RDG', 'PLN', 'EXP', 'EST', 'ROW', 'RPD', 'PRR', 
    'PRT', 'RAD', 'PTS', 'RIV', 'RDS', 'FLS', 'CPE', 'CRK', 'DRV', 'SQU', 'STN', 'STR', 
    'CEN', 'SMT', 'SPG', 'CTR', 'CTS', 'CLF', 'CMP', 'CLB', 'CIR', 'BRG', 'BRK', 'BTM', 
    'BYP', 'STA', 'BOT', 'TER', 'BLF', 'TRL', 'BCH', 'BND', 'TRK', 'ALY', 'WLS', 'WAY', 
    'ANX', 'AV', 'VW', 'WY', 'ST', 'SQ', 'PT', 'RD', 'PR', 'PL', 'UN', 'MT', 'LN', 'LF', 
    'LK', 'KY', 'HT', 'IS', 'HL', 'FT', 'CV', 'DR', 'DV', 'CT', 'CP', 'BR', 'VL']

def street_suffix(street):
    """
    Get the street type from the street name.
    e.g. "W 22 ST" -> "ST"

    Parameters:
    -----------
    street : str
        The street name to parse.

    Returns:
    --------
    str
        The street type.
    """
    street = street.strip().upper()
    for suffix in USPS_STREET_SUFF:
        if suffix in street:
            return suffix
    
    warnings.warn(f"Could not find street type in {street}")
    return ""


def ord(n):
    if 10 <= n % 100 <= 20:  # the teens are different
        return 'th'
    d = n % 10
    if d == 1:
        return 'st'
    if d == 2:
        return 'nd'
    if d == 3:
        return 'rd'
    return 'th'


def reverse(row, geocoder, addr_field="address", timeout=20, viewbox=None, multiple=False):
    """
    Run a reverse geocode on an address from a dataframe row.
    Creates a new column called `geometry` with the result as a `shapely.geometry.Point` object.
    If no result is found, the value is `None`.

    Parameters:
    -----------
    row : pandas.Series
        The row to geocode.
    addr_field : str
        The column name of the address field.
    geocoder : geopy.geocoders
        The geocoder to use. Default is `Nominatim` looking for service on the localhost.
    timeout : int
        The timeout for the geocoding request.
    viewbox : tuple of float
        The viewbox to limit the search. If not provided, the geocoder's default is used.
    multiple : bool
        If `True`, the returned values will contain the following new columns:
        - `geometry` : the `shapely.geometry.Point` object
        - `lookup_address` : the formatted address wihout the unit number
        - `full_address` : the full address, multiline address (with unit number)
        - `lat` : the latitude
        - `lon` : the longitude

    Returns:
    --------
    pandas.Series
        The original row with the new columns (see above).
    """
    x = row[addr_field]
    row["geometry"] = None
    if multiple:
        unit = None
        row["lat"] = None
        row["lon"] = None
        row["lookup_address"] = None
        row["full_address"] = None
    
    # if not x:
    #     print("Invalid address:", x)
    #     return row
    
    addr = parse_address(x)
    addr["postalcode"] = addr["zip"]

    if not addr:
        print("Invalid address:", addr)
        return row

    loc = None
    if viewbox:
        # loc = geocoder.geocode(addr["lookup"], timeout=20, viewbox=viewbox, bounded=True)
        loc = geocoder.geocode(addr, timeout=20, viewbox=viewbox, bounded=True)
    else:
        loc = geocoder.geocode(addr, timeout=20)
        # loc = geocoder.geocode(addr["lookup"], timeout=20)
    
    if not loc or not addr or not addr["lookup"]:
        print(f"""
failed to geocode: {addr["lookup"]}
         original: {x}""")
        row["geometry"] = None
        return row

    row["geometry"] = Point(loc.longitude, loc.latitude)
    if not multiple:
        return row
    unit = " " + addr["unit"] if addr["unit"] else ""
    row["lat"] = loc.latitude
    row["lon"] = loc.longitude
    row["lookup_address"] = addr["lookup"]
    row["full_address"] = f"""{addr["street"]}{unit}\n{addr["city"]}, {addr["state"]} {addr["zip"]}"""
    return row

def parse_address(addr):
    """
    Parse an address into its components.
    Look for an apartment or unit number.
    Convert numbered street names to ordinal form. (W 22 ST -> W 22ND ST)

    Parameters:
    -----------
    addr : str
        The address to parse. e.g. "179 Livingston St, 7th Fl, Brooklyn, NY 11201"

    Returns:
    --------
    dict
        A dictionary with the following keys:
        - lookup: single line address with street, city, state zip (excludes unit)
        - street: the street address (179 Livingston St)
        - unit: the apartment or unit number, or `None`
        - city
        - state
        - zip_code
    
    """
    clean = apt = street = city = state = zip_code = None
    try:
        street, city, state_zip = addr.split(", ")
        street = street.strip()
        city = city.strip()
        state, zip_code = state_zip.split(" ")
        state = state.strip()
        zip_code = zip_code.strip()

        sfx = street_suffix(street)
        parts = street.split(sfx)

        street_name = parts[0].strip()
        if len(parts) > 1:
            apt = parts[1].strip()
        
        match = re.search(r'\d+$', street_name)
        if match:
            numbered_street = match.group(0)
            if sfx != "BROADWAY":
                ordinal = ord(int(numbered_street))
                street_name += ordinal
        
        street = f"{street_name} {sfx}".strip()
        clean = f"{street}, {city}, {state} {zip_code}"

    except Exception as e:
        # warnings.warn("Could not parse address:" + str(addr), stacklevel=1)
        return None

    m = dict()
    m["lookup"] = clean
    m["street"] = street
    m["unit"] = apt
    m["city"] = city
    m["state"] = state
    m["zip"] = zip_code
    return m