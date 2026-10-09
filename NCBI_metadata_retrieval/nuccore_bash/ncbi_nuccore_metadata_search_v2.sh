#!/bin/bash

# ============================================================
# NCBI Nuccore Metadata Search
#
# Queries NCBI nuccore using EDirect and outputs selected
# metadata to a tab-delimited TSV file.
#
# BioSample is retrieved from the nuccore DocumentSummary.
# Authors are retrieved from the corresponding INSDC records.
#
# Created: VLG Wed Sep 30 10:38:11 EDT 2026
# ============================================================


usage() {
    cat << EOF

NCBI Nuccore Metadata Search

DESCRIPTION:
    Queries the NCBI nuccore database using EDirect and outputs
    nucleotide record metadata to a tab-delimited TSV file.

    BioSample metadata is retrieved from the NCBI DocumentSummary.

    Author information is retrieved from the corresponding INSDC
    nucleotide records using efetch.

USAGE:
    $0 -q "QUERY" [-o output.tsv]

REQUIRED ARGUMENTS:
    -q QUERY
        NCBI nuccore search query.

OPTIONAL ARGUMENTS:
    -o FILE
        Output TSV filename.

        If not specified, the output filename is automatically
        generated from the query:

            <query>_nuccore_records.tsv

    -h
        Display this help message and exit.

OUTPUT COLUMNS:
    AccessionVersion
    BioSample
    Title
    TaxId
    Organism
    Length
    CreateDate
    UpdateDate
    Authors

EXAMPLES:

    Search for all nuccore records containing USNM:FISH:

        $0 -q "USNM:FISH"

    Specify an output filename:

        $0 -q "USNM:FISH" -o USNM_FISH_records.tsv

    Search for a specific voucher:

        $0 -q "USNM:FISH:442417" -o USNM_442417.tsv

    Use a more complex NCBI query:

        $0 -q '"USNM:FISH"[All Fields] AND mitochondrion[Filter]' \
           -o mitochondrial_records.tsv

REQUIREMENTS:
    NCBI EDirect must be installed.

    The following commands must be available in PATH:

        esearch
        esummary
        efetch
        xtract

EOF
}


# ============================================================
# Parse command-line arguments
# ============================================================

QUERY=""
OUTPUT=""

while getopts "q:o:h" opt; do
    case "$opt" in

        q)
            QUERY="$OPTARG"
            ;;

        o)
            OUTPUT="$OPTARG"
            ;;

        h)
            usage
            exit 0
            ;;

        *)
            usage
            exit 1
            ;;

    esac
done


# ============================================================
# Check query
# ============================================================

if [ -z "$QUERY" ]; then
    echo "ERROR: A query must be provided with -q."
    echo ""
    usage
    exit 1
fi


# ============================================================
# Generate output filename if one was not supplied
# ============================================================

if [ -z "$OUTPUT" ]; then

    safe_query=$(echo "$QUERY" | sed 's/[^A-Za-z0-9._-]/_/g')

    OUTPUT="${safe_query}_nuccore_records.tsv"

fi


# ============================================================
# Check required EDirect programs
# ============================================================

for cmd in esearch esummary efetch xtract; do

    if ! command -v "$cmd" >/dev/null 2>&1; then

        echo "ERROR: Required command '$cmd' was not found in PATH."
        echo ""
        echo "Please install NCBI EDirect or add it to your PATH."

        exit 1

    fi

done


# ============================================================
# Create temporary directory
# ============================================================

tmpdir=$(mktemp -d)

if [ ! -d "$tmpdir" ]; then
    echo "ERROR: Could not create temporary directory."
    exit 1
fi


cleanup() {
    rm -rf "$tmpdir"
}

trap cleanup EXIT


# ============================================================
# Display search information
# ============================================================

echo ""
echo "NCBI Nuccore Metadata Search"
echo "----------------------------"
echo "Database: nuccore"
echo "Query:    $QUERY"
echo "Output:   $OUTPUT"
echo ""


# ============================================================
# Retrieve nuccore DocumentSummary metadata
#
# BioSample is intentionally obtained from esummary because
# BioSample is reliably available in the nuccore
# DocumentSummary for linked records.
# ============================================================

echo "Retrieving NCBI nuccore summaries..."

esearch \
    -db nuccore \
    -query "$QUERY" |
esummary |
xtract \
    -pattern DocumentSummary \
    -def "-" \
    -element \
        AccessionVersion \
        BioSample \
        Title \
        TaxId \
        Organism \
        Length \
        CreateDate \
        UpdateDate \
> "$tmpdir/summary.tsv"


# ============================================================
# Verify that records were returned
# ============================================================

if [ ! -s "$tmpdir/summary.tsv" ]; then

    echo ""
    echo "ERROR: No nuccore records were returned."
    echo "Query: $QUERY"

    exit 1

fi


record_count=$(wc -l < "$tmpdir/summary.tsv" | tr -d ' ')

echo "Records found: $record_count"


# ============================================================
# Retrieve INSDC records
#
# These records are used to obtain author information.
# ============================================================

echo ""
echo "Retrieving INSDC records for authors..."

esearch \
    -db nuccore \
    -query "$QUERY" |
efetch \
    -format gbc \
> "$tmpdir/records.xml"


# ============================================================
# Verify INSDC records
# ============================================================

if [ ! -s "$tmpdir/records.xml" ]; then

    echo ""
    echo "WARNING: Could not retrieve INSDC records."
    echo "Authors will be reported as '-' where unavailable."

    touch "$tmpdir/authors.tsv"

else

    # ========================================================
    # Extract authors
    #
    # AccessionVersion is included so authors can be joined
    # back to the correct nucleotide record.
    # ========================================================

    echo "Extracting authors..."

    xtract \
        -input "$tmpdir/records.xml" \
        -pattern INSDSeq \
        -element INSDSeq_accession-version \
        -block INSDReference \
            -sep "; " \
            -element INSDAuthor \
    > "$tmpdir/authors_raw.tsv"


    # ========================================================
    # Combine multiple references for the same accession
    # ========================================================

    awk -F '\t' '
    BEGIN {
        OFS="\t"
    }

    {
        acc=$1

        $1=""
        sub(/^\t/, "", $0)

        value=$0

        if (value == "")
            value="-"

        if (acc in authors) {

            if (value != "-" && index(authors[acc], value) == 0)
                authors[acc]=authors[acc] "; " value

        } else {

            authors[acc]=value

        }
    }

    END {

        for (acc in authors)
            print acc,authors[acc]

    }
    ' "$tmpdir/authors_raw.tsv" \
    > "$tmpdir/authors.tsv"

fi


# ============================================================
# Join summary metadata and authors by accession
#
# This avoids relying on row position between the two files.
# ============================================================

echo "Combining metadata and authors..."

awk -F '\t' '
BEGIN {
    OFS="\t"
}

FNR==NR {

    acc=$1

    $1=""
    sub(/^\t/, "", $0)

    author[acc]=$0

    next
}

{

    acc=$1

    if (acc in author && author[acc] != "")
        a=author[acc]
    else
        a="-"

    print \
        $1, \
        $2, \
        $3, \
        $4, \
        $5, \
        $6, \
        $7, \
        $8, \
        a
}
' \
"$tmpdir/authors.tsv" \
"$tmpdir/summary.tsv" \
> "$tmpdir/combined.tsv"


# ============================================================
# Write final TSV
# ============================================================

{
    printf "AccessionVersion\tBioSample\tTitle\tTaxId\tOrganism\tLength\tCreateDate\tUpdateDate\tAuthors\n"

    cat "$tmpdir/combined.tsv"

} > "$OUTPUT"


# ============================================================
# Final report
# ============================================================

echo ""
echo "Finished."
echo "Records written: $record_count"
echo "Output file: $OUTPUT"
echo ""