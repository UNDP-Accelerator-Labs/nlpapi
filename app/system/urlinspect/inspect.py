# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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
