#!/usr/bin/env python3

"""
Smithsonian NMNH EZID Link (Ark URI) Lookup
===================================================

Queries the GBIF API for Smithsonian National Museum of Natural History specimens (collection code: US) and retrieves the corresponding
ARK/EZID URI for each catalog number.

Created: VLG Mon Sep 28 13:08:12 EDT 2026

INPUT
-----
A text file containing one catalog number per line.

Example: catalog_numbers.txt

US 2580143A
US 2580144A
US 1994015
US 1994016
US 35953

USAGE
-----
Basic usage:

    python retrieve_catalog_ark_link_v2.py catalog_numbers.txt

Specify an output file:

    python retrieve_catalog_ark_link_v2.py  catalog_numbers.txt -o botany_arks.tsv

Optional delay between GBIF API requests:

    python retrieve_catalog_ark_link_v2.py  catalog_numbers.txt -o botany_arks.tsv --delay 0.2

OUTPUT
------
A tab-delimited (TSV) file containing:

    catalog_number
    ark_uri_1
    ark_uri_2
    ark_uri_3
    ...
    gbif_key
    scientific_name
    status

If multiple ARK URIs are found for a catalog number, each ARK is written
to its own tab-delimited column.

REQUIREMENTS
------------
Python 3
requests

Install requests with:

    pip install requests
"""

import argparse
import csv
import re
import sys
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GBIF_API = "https://api.gbif.org/v1/occurrence/search"

# Smithsonian NMNH Extant Specimen Records
NMNH_DATASET_KEY = "821cc27a-e3bb-4bc5-ac34-89ada245069d"

# Smithsonian National Collection Code
COLLECTION_CODE = "US"

# Match Smithsonian ARK URIs
ARK_PATTERN = re.compile(
    r"https?://(?:n2t\.net/)?ark:/65665/[A-Za-z0-9._~-]+(?:-[A-Za-z0-9._~-]+)*",
    re.IGNORECASE,
)


def create_session():
    """
    Create a requests session with automatic retries.
    """

    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    session.mount(
        "https://",
        HTTPAdapter(max_retries=retries)
    )

    session.headers.update({
        "User-Agent": "Smithsonian-NMNH-Botany-GBIF-ARK-Lookup/1.0"
    })

    return session


def find_arks(obj):
    """
    Recursively search a GBIF JSON object for Smithsonian ARK URLs.

    The ARK may occur in occurrenceID, identifiers, references,
    or other fields in the GBIF record.
    """

    arks = set()

    if isinstance(obj, dict):

        for value in obj.values():
            arks.update(find_arks(value))

    elif isinstance(obj, list):

        for value in obj:
            arks.update(find_arks(value))

    elif isinstance(obj, str):

        for match in ARK_PATTERN.findall(obj):
            arks.add(match)

    return arks


def normalize_ark(ark):
    """
    Normalize Smithsonian ARK URIs to HTTPS n2t.net format.
    """

    if not ark:
        return ""

    if ark.startswith("http://"):
        ark = "https://" + ark[len("http://"):]

    if ark.startswith("ark:/"):
        ark = "https://n2t.net/" + ark

    return ark


def query_catalog_number(session, catalog_number):
    """
    Query GBIF for one Smithsonian Botany catalog number.
    """

    params = {
        "catalogNumber": catalog_number,
        "collectionCode": COLLECTION_CODE,
        "datasetKey": NMNH_DATASET_KEY,
        "limit": 100,
    }

    response = session.get(
        GBIF_API,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    results = data.get("results", [])

    if not results:

        return {
            "catalog_number": catalog_number,
            "arks": [],
            "gbif_keys": [],
            "scientific_names": [],
            "status": "NOT_FOUND",
        }

    matches = []

    for record in results:

        arks = find_arks(record)

        if arks:

            for ark in sorted(arks):

                matches.append({
                    "ark": normalize_ark(ark),
                    "gbif_key": record.get("key", ""),
                    "scientific_name": record.get(
                        "scientificName",
                        record.get("acceptedScientificName", "")
                    ),
                })

    if not matches:

        return {
            "catalog_number": catalog_number,
            "arks": [],
            "gbif_keys": [
                str(results[0].get("key", ""))
            ],
            "scientific_names": [
                results[0].get("scientificName", "")
            ],
            "status": "RECORD_FOUND_NO_ARK",
        }

    # Remove duplicate ARKs while preserving their metadata
    unique = {}

    for match in matches:

        if match["ark"] not in unique:
            unique[match["ark"]] = match

    matches = list(unique.values())

    arks = [
        match["ark"]
        for match in matches
    ]

    gbif_keys = [
        str(match["gbif_key"])
        for match in matches
    ]

    scientific_names = [
        match["scientific_name"]
        for match in matches
    ]

    if len(matches) == 1:
        status = "FOUND"
    else:
        status = f"MULTIPLE_MATCHES_{len(matches)}"

    return {
        "catalog_number": catalog_number,
        "arks": arks,
        "gbif_keys": gbif_keys,
        "scientific_names": scientific_names,
        "status": status,
    }


def read_catalog_numbers(filename):
    """
    Read one catalog number per line from the input file.
    """

    catalog_numbers = []

    with open(
        filename,
        encoding="utf-8-sig"
    ) as handle:

        for line in handle:

            value = line.strip()

            if not value:
                continue

            # Ignore common header names
            if value.lower() in {
                "catalog_number",
                "catalognumber",
                "catalog number",
            }:
                continue

            catalog_numbers.append(value)

    return catalog_numbers


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Retrieve Smithsonian NMNH Botany ARK/EZID URIs "
            "from GBIF using catalog numbers."
        )
    )

    parser.add_argument(
        "input",
        help="Text file containing one catalog number per line",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="smithsonian_botany_arks.tsv",
        help=(
            "Output TSV file "
            "(default: smithsonian_botany_arks.tsv)"
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help=(
            "Delay between GBIF queries in seconds "
            "(default: 0.1)"
        ),
    )

    args = parser.parse_args()

    catalog_numbers = read_catalog_numbers(args.input)

    if not catalog_numbers:
        sys.exit(
            "No catalog numbers found in input file."
        )

    print(
        f"Catalog numbers loaded: "
        f"{len(catalog_numbers)}"
    )

    print(
        f"Collection code: "
        f"{COLLECTION_CODE}"
    )

    print(
        f"Dataset: "
        f"{NMNH_DATASET_KEY}"
    )

    print()

    session = create_session()

    all_results = []

    # Query each catalog number
    for i, catalog_number in enumerate(
        catalog_numbers,
        start=1,
    ):

        try:

            result = query_catalog_number(
                session,
                catalog_number,
            )

        except requests.RequestException as error:

            result = {
                "catalog_number": catalog_number,
                "arks": [],
                "gbif_keys": [],
                "scientific_names": [],
                "status": f"ERROR: {error}",
            }

        all_results.append(result)

        if result["arks"]:
            display_result = " | ".join(
                result["arks"]
            )
        else:
            display_result = result["status"]

        print(
            f"[{i}/{len(catalog_numbers)}] "
            f"{catalog_number} -> "
            f"{display_result}"
        )

        time.sleep(args.delay)

    # Determine the maximum number of ARKs
    # associated with any catalog number
    max_arks = max(
        (
            len(result["arks"])
            for result in all_results
        ),
        default=1,
    )

    if max_arks < 1:
        max_arks = 1

    # Build ARK column names dynamically
    ark_fields = [
        f"ark_uri_{i}"
        for i in range(
            1,
            max_arks + 1
        )
    ]

    fields = (
        ["catalog_number"]
        + ark_fields
        + [
            "gbif_key",
            "scientific_name",
            "status",
        ]
    )

    # Write results to TSV
    with open(
        args.output,
        "w",
        newline="",
        encoding="utf-8",
    ) as outfile:

        writer = csv.DictWriter(
            outfile,
            fieldnames=fields,
            delimiter="\t",
        )

        writer.writeheader()

        for result in all_results:

            row = {
                "catalog_number":
                    result["catalog_number"],

                "gbif_key":
                    ";".join(
                        result["gbif_keys"]
                    ),

                "scientific_name":
                    ";".join(
                        result["scientific_names"]
                    ),

                "status":
                    result["status"],
            }

            # Put each ARK into its own TSV column
            for i in range(max_arks):

                field_name = (
                    f"ark_uri_{i + 1}"
                )

                if i < len(result["arks"]):

                    row[field_name] = (
                        result["arks"][i]
                    )

                else:

                    row[field_name] = ""

            writer.writerow(row)

    print()

    print(
        f"Output written to: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
