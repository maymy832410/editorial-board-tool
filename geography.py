"""Continent and country mappings (ISO 3166-1 alpha-2)."""

CONTINENTS = {
    "Asia": [
        "AF", "AM", "AZ", "BH", "BD", "BN", "KH", "CN", "GE", "IN",
        "ID", "IR", "IQ", "IL", "JP", "JO", "KZ", "KW", "KG", "LA",
        "LB", "MY", "MV", "MN", "MM", "NP", "KP", "OM", "PK", "PS",
        "PH", "QA", "SA", "SG", "KR", "LK", "SY", "TW", "TJ", "TH",
        "TL", "TR", "TM", "AE", "UZ", "VN", "YE",
    ],
    "Europe": [
        "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ",
        "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT",
        "XK", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL",
        "MK", "NO", "PL", "PT", "RO", "RU", "SM", "RS", "SK", "SI",
        "ES", "SE", "CH", "UA", "GB", "VA",
    ],
    "North America": [
        "AG", "BS", "BB", "BZ", "CA", "CR", "CU", "DM", "DO", "SV",
        "GD", "GT", "HT", "HN", "JM", "MX", "NI", "PA", "KN", "LC",
        "VC", "TT", "US",
    ],
    "South America": [
        "AR", "BO", "BR", "CL", "CO", "EC", "GY", "PY", "PE", "SR",
        "UY", "VE",
    ],
    "Africa": [
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD",
        "KM", "CD", "CG", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET",
        "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG",
        "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW",
        "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG",
        "TN", "UG", "ZM", "ZW",
    ],
    "Oceania": [
        "AU", "FJ", "KI", "MH", "FM", "NR", "NZ", "PW", "PG", "WS",
        "SB", "TO", "TV", "VU",
    ],
}

# Flat dict: country name → code  (common countries for quick selection)
COUNTRIES = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "Argentina": "AR",
    "Armenia": "AM", "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ",
    "Bahrain": "BH", "Bangladesh": "BD", "Belarus": "BY", "Belgium": "BE",
    "Bolivia": "BO", "Bosnia & Herzegovina": "BA", "Botswana": "BW",
    "Brazil": "BR", "Brunei": "BN", "Bulgaria": "BG", "Cambodia": "KH",
    "Cameroon": "CM", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Colombia": "CO", "Costa Rica": "CR", "Croatia": "HR", "Cuba": "CU",
    "Cyprus": "CY", "Czech Republic": "CZ", "Denmark": "DK",
    "Dominican Republic": "DO", "Ecuador": "EC", "Egypt": "EG",
    "El Salvador": "SV", "Estonia": "EE", "Ethiopia": "ET", "Finland": "FI",
    "France": "FR", "Georgia": "GE", "Germany": "DE", "Ghana": "GH",
    "Greece": "GR", "Guatemala": "GT", "Honduras": "HN", "Hong Kong": "HK",
    "Hungary": "HU", "Iceland": "IS", "India": "IN", "Indonesia": "ID",
    "Iran": "IR", "Iraq": "IQ", "Ireland": "IE", "Israel": "IL",
    "Italy": "IT", "Jamaica": "JM", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kuwait": "KW", "Kyrgyzstan": "KG",
    "Latvia": "LV", "Lebanon": "LB", "Libya": "LY", "Lithuania": "LT",
    "Luxembourg": "LU", "Malaysia": "MY", "Malta": "MT", "Mexico": "MX",
    "Moldova": "MD", "Mongolia": "MN", "Montenegro": "ME", "Morocco": "MA",
    "Mozambique": "MZ", "Myanmar": "MM", "Nepal": "NP", "Netherlands": "NL",
    "New Zealand": "NZ", "Nicaragua": "NI", "Nigeria": "NG",
    "North Macedonia": "MK", "Norway": "NO", "Oman": "OM", "Pakistan": "PK",
    "Palestine": "PS", "Panama": "PA", "Paraguay": "PY", "Peru": "PE",
    "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Qatar": "QA",
    "Romania": "RO", "Russia": "RU", "Rwanda": "RW", "Saudi Arabia": "SA",
    "Senegal": "SN", "Serbia": "RS", "Singapore": "SG", "Slovakia": "SK",
    "Slovenia": "SI", "South Africa": "ZA", "South Korea": "KR",
    "Spain": "ES", "Sri Lanka": "LK", "Sudan": "SD", "Sweden": "SE",
    "Switzerland": "CH", "Syria": "SY", "Taiwan": "TW", "Tanzania": "TZ",
    "Thailand": "TH", "Tunisia": "TN", "Turkey": "TR", "Uganda": "UG",
    "Ukraine": "UA", "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
    "Venezuela": "VE", "Vietnam": "VN", "Yemen": "YE", "Zambia": "ZM",
    "Zimbabwe": "ZW",
}

# Reverse lookup: code → name
CODE_TO_COUNTRY = {v: k for k, v in COUNTRIES.items()}


def get_country_codes_for_continents(continent_names: list[str]) -> list[str]:
    """Return the union of country codes for the given continents."""
    codes = set()
    for name in continent_names:
        codes.update(CONTINENTS.get(name, []))
    return sorted(codes)


# OpenAlex continent filter values
CONTINENT_TO_OPENALEX = {
    "Asia": "asia",
    "Europe": "europe",
    "North America": "north_america",
    "South America": "south_america",
    "Africa": "africa",
    "Oceania": "oceania",
}


def get_openalex_continent_codes(continent_names: list[str]) -> list[str]:
    """Return OpenAlex continent filter values for the given continent display names."""
    return [CONTINENT_TO_OPENALEX[c] for c in continent_names if c in CONTINENT_TO_OPENALEX]
