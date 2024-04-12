import pandas as pd


COUNTRIES: dict[str, str] | None = None


def get_country_lookup() -> dict[str, str]:
    global COUNTRIES  # pylint: disable=global-statement

    if COUNTRIES is None:
        country_df = pd.read_csv("static/countries.csv")
        country_map: dict[str, str] = {}
        for _, row in country_df.iterrows():
            iso3 = f"{row['iso3']}".strip()
            country_map[f"{row['name']}".lower().replace(" ", "-")] = iso3
        print(f"loading {len(country_map)} countries done")
        COUNTRIES = country_map
    return COUNTRIES


def country_lookup(name: str) -> str | None:
    countries = get_country_lookup()
    return countries.get(name)


def inspect_url(url: str) -> str | None:
    purl = url.removeprefix(UNDP_PREFIX)
    for lang in LANGS:
        turl = purl.removeprefix(f"{lang}/")
        if turl != purl:
            purl = turl
            break
    fix = purl.find("/")
    if fix < 0:
        return None
    pres = purl[:fix]
    if pres in MISC_CATEGORIES:
        return None
    if pres in REGIONS:
        return None
    res = country_lookup(pres)
    if res is None:
        print(f"unknown country fragment {pres} in {url}")
    return res


UNDP_PREFIX = "https://www.undp.org/"


REGIONS: set[str] = {
    "africa",
    "arab-states",
    "asia-pacific",
    "eurasia",
    "european-union",
    "geneva",
    "latin-america",
    "pacific",
}


MISC_CATEGORIES: set[str] = {
    "about-us",
    "acceleratorlabs",
    "accountability",
    "approvisionnement",
    "blog",
    "careers",
    "energy",
    "events",
    "executive-board",
    "https:",  # NOTE: non-undp sites
    "node",
    "papp",
    "policy-centre",
    "press-releases",
    "procurement",
    "publications",
    "rolhr",
    "romecentre",
    "seoul-policy-centre",
    "sgtechcentre",
    "sites",
    "speeches",
    "stories",
}


LANGS: set[str] = {
    "ar",
    "az",
    "bs",
    "cnr",
    "da",
    "de",
    "es",
    "fi",
    "fr",
    "id",
    "ja",
    "ka",
    "kk",
    "km",
    "ko",
    "ku",
    "ky",
    "no",
    "pt",
    "ro",
    "ru",
    "sr",
    "sv",
    "tr",
    "uk",
    "uz",
    "vi",
    "zh",
}
