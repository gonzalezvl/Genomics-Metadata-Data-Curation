#!/usr/bin/env python3

"""
NCBI BioSample Metadata Search
==============================

Created:VLG Wed Sep 30 10:38:11 EDT 2026

DESCRIPTION
-----------
Queries the NCBI BioSample database using NCBI EDirect and exports
selected BioSample metadata to a tab-delimited TSV file.

The script retrieves BioSample records using:

    esearch
    esummary
    xtract

It is designed to accommodate heterogeneous BioSample records by
checking multiple possible attribute names for fields such as organism,
specimen voucher, collector/author, BioProject, submission date, and URI.

OUTPUT COLUMNS
--------------
Accession
    NCBI BioSample accession, for example:

        SAMN18648691

Organism
    Scientific name of the organism.

Voucher
    Specimen voucher identifier. Preference is given to INSDC-style
    specimen voucher fields such as:

        USNM:FISH:442417

Author
    Collector or author information associated with the BioSample.
    The script preferentially uses the "collected_by" attribute.

BioProject
    Associated NCBI BioProject accession when available.

SubmissionDate
    BioSample submission/create/publication/update date, using the
    first available date field.

URI
    Specimen or voucher URI when available.

USAGE
-----
    python3 ncbi_biosample_metadata_search_v2.py -q "QUERY"

Optional output filename:

    python3 ncbi_biosample_metadata_search_v2.py \
        -q "QUERY" \
        -o output.tsv

EXAMPLES
--------
Query a single BioSample:

    python3 ncbi_biosample_metadata_search_v2.py \
        -q "SAMN18648691"

Query BioSample records containing a Smithsonian voucher identifier:

    python3 ncbi_biosample_metadata_search_v2.py \
        -q "USNM:FISH" \
        -o USNM_FISH_biosamples.tsv

Query a specific specimen voucher:

    python3 ncbi_biosample_metadata_search_v2.py \
        -q "USNM:FISH:442417" \
        -o USNM_442417_biosamples.tsv

HELP
----
Display command-line help:

    python3 ncbi_biosample_metadata_search_v2.py -h

or:

    python3 ncbi_biosample_metadata_search_v2.py --help

REQUIREMENTS
------------
Python 3

NCBI EDirect must be installed and the following commands must be
available in PATH:

    esearch
    esummary
    xtract

OUTPUT FORMAT
-------------
Tab-delimited TSV.

Default output filename:

    biosample_records.tsv
"""


import argparse
import csv
import subprocess
import sys


def run_command(cmd, input_text=None):
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"{result.stderr}"
        )

    return result.stdout


def get_esearch(query):
    return run_command(
        [
            "esearch",
            "-db",
            "biosample",
            "-query",
            query
        ]
    )


def get_esummary(esearch_output):
    return run_command(
        ["esummary"],
        input_text=esearch_output
    )


def get_summary_fields(esummary_xml):
    """
    Extract summary-level fields using xtract.

    Output columns:
        Accession
        Organism
        BioProject
        SubmissionDate
        CreateDate
        PublicationDate
        UpdateDate
    """

    output = run_command(
        [
            "xtract",
            "-pattern",
            "DocumentSummary",
            "-def",
            "-",
            "-element",
            "Accession",
            "Organism",
            "BioProject",
            "SubmissionDate",
            "CreateDate",
            "PublicationDate",
            "UpdateDate"
        ],
        input_text=esummary_xml
    )

    return output


def get_attributes(esummary_xml):
    """
    Extract all BioSample attributes.

    Output is one line per BioSample:

        Accession
        attribute_name
        value
        attribute_name
        value
        ...
    """

    output = run_command(
        [
            "xtract",
            "-pattern",
            "DocumentSummary",
            "-element",
            "Accession",
            "-block",
            "Attribute",
            "-element",
            "@attribute_name",
            "Attribute"
        ],
        input_text=esummary_xml
    )

    return output


def clean(value):
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    if value.lower() in {
        "-",
        "missing",
        "not provided",
        "not applicable",
        "na",
        "n/a"
    }:
        return None

    return value


def normalize(name):
    if not name:
        return ""

    return (
        name.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def first_value(attributes, names):
    for name in names:
        key = normalize(name)

        if key in attributes:
            value = clean(attributes[key])

            if value:
                return value

    return None


def parse_attributes(text):
    """
    Convert xtract output into:

        {
            accession: {
                attribute_name: value
            }
        }
    """

    all_records = {}

    for line in text.splitlines():

        if not line.strip():
            continue

        fields = line.rstrip("\n").split("\t")

        if not fields:
            continue

        accession = fields[0]

        attributes = {}

        i = 1

        while i + 1 < len(fields):

            name = normalize(fields[i])
            value = clean(fields[i + 1])

            if name and value and name not in attributes:
                attributes[name] = value

            i += 2

        all_records[accession] = attributes

    return all_records


def parse_summary(text):
    records = {}

    for line in text.splitlines():

        if not line.strip():
            continue

        fields = line.rstrip("\n").split("\t")

        while len(fields) < 7:
            fields.append("-")

        accession = fields[0]

        records[accession] = {
            "Organism": clean(fields[1]),
            "BioProject": clean(fields[2]),
            "SubmissionDate": clean(fields[3]),
            "CreateDate": clean(fields[4]),
            "PublicationDate": clean(fields[5]),
            "UpdateDate": clean(fields[6])
        }

    return records


def get_organism(summary, attrs):

    value = summary.get("Organism")

    if value:
        return value

    return first_value(
        attrs,
        [
            "scientificName",
            "scientific_name",
            "organism",
            "organism_name"
        ]
    )


def get_voucher(attrs):
    """
    Prefer INSDC-style voucher identifiers.
    """

    return first_value(
        attrs,
        [
            "genbankSpecimenVoucher",
            "specimen_voucher",
            "specimenVoucher",
            "voucherCatalogNumber",
            "voucher",
            "materialSampleID",
            "catalogNumber"
        ]
    )


def get_author(attrs):
    """
    BioSample collector/author field.
    """

    return first_value(
        attrs,
        [
            "collected_by",
            "collector",
            "collectors",
            "author",
            "authors"
        ]
    )


def get_bioproject(summary, attrs):

    value = summary.get("BioProject")

    if value:
        return value

    return first_value(
        attrs,
        [
            "bioproject",
            "bioproject_accession",
            "bioproject_accn",
            "project_accession"
        ]
    )


def get_submission_date(summary, attrs):

    for key in [
        "SubmissionDate",
        "CreateDate",
        "PublicationDate",
        "UpdateDate"
    ]:

        value = summary.get(key)

        if value:
            return value

    return first_value(
        attrs,
        [
            "submission_date",
            "submissionDate"
        ]
    )


def get_uri(attrs):

    value = first_value(
        attrs,
        [
            "voucherURI",
            "specimenVoucher_link",
            "specimen_voucher_link"
        ]
    )

    if value:
        return value

    for key in [
        "catalogNumber",
        "materialSampleID",
        "bcid"
    ]:

        value = first_value(
            attrs,
            [key]
        )

        if value and (
            value.startswith("http://")
            or value.startswith("https://")
        ):
            return value

    return None


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Query the NCBI BioSample database and export selected "
            "metadata to a tab-delimited TSV file."
        ),
        epilog=(
            "Example: "
            'python3 ncbi_biosample_metadata_search_v2.py '
            '-q "USNM:FISH" -o USNM_FISH_biosamples.tsv'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "-q",
        "--query",
        required=True,
        help='BioSample query, e.g. "SAMN18648691" or "USNM:FISH"'
    )

    parser.add_argument(
        "-o",
        "--output",
        default="biosample_records.tsv",
        help="Output TSV file"
    )

    args = parser.parse_args()

    print(f"Querying NCBI BioSample for: {args.query}")

    try:

        search_results = get_esearch(args.query)

        if not search_results.strip():
            raise RuntimeError(
                "esearch returned no results."
            )

        summary_xml = get_esummary(
            search_results
        )

        if not summary_xml.strip():
            raise RuntimeError(
                "esummary returned no output."
            )

        summary_text = get_summary_fields(
            summary_xml
        )

        attribute_text = get_attributes(
            summary_xml
        )

        summaries = parse_summary(
            summary_text
        )

        attributes = parse_attributes(
            attribute_text
        )

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr
        )

        sys.exit(1)

    accessions = list(summaries.keys())

    if not accessions:

        print(
            "ERROR: No BioSample records found.",
            file=sys.stderr
        )

        sys.exit(1)

    fieldnames = [
        "Accession",
        "Organism",
        "Voucher",
        "Author",
        "BioProject",
        "SubmissionDate",
        "URI"
    ]

    rows = []

    for accession in accessions:

        summary = summaries.get(
            accession,
            {}
        )

        attrs = attributes.get(
            accession,
            {}
        )

        organism = get_organism(
            summary,
            attrs
        )

        voucher = get_voucher(
            attrs
        )

        author = get_author(
            attrs
        )

        bioproject = get_bioproject(
            summary,
            attrs
        )

        submission_date = get_submission_date(
            summary,
            attrs
        )

        uri = get_uri(
            attrs
        )

        rows.append(
            {
                "Accession": accession,
                "Organism": organism or "-",
                "Voucher": voucher or "-",
                "Author": author or "-",
                "BioProject": bioproject or "-",
                "SubmissionDate": submission_date or "-",
                "URI": uri or "-"
            }
        )

    try:

        with open(
            args.output,
            "w",
            newline="",
            encoding="utf-8"
        ) as handle:

            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n"
            )

            writer.writeheader()
            writer.writerows(rows)

    except OSError as exc:

        print(
            f"ERROR writing output: {exc}",
            file=sys.stderr
        )

        sys.exit(1)

    print("")
    print(f"Records returned: {len(rows)}")
    print(f"Output written to: {args.output}")


if __name__ == "__main__":
    main()
