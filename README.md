# Genomics Metadata & Data Curation

A collection of scripts for retrieving and curating biodiversity genomics metadata from public repositories: National Center for Biotechnology Information (NCBI) and the Global Biodiversity Information Facility (GBIF).

These tools support metadata reconciliation, specimen-data integration, and linking genetic sequence records with natural history museum collections, particularly those of the Smithsonian National Museum of Natural History (NMNH).

## Repository Contents

### 1. GBIF ARK Link Retrieval
**Directory:** [`GBIF_ark_link_script/`](https://github.com/gonzalezvl/Genomics-Metadata-Data-Curation/tree/main/GBIF_ark_link_script)

Scripts for querying GBIF occurrence records and retrieving associated Archival Resource Key (ARK) identifiers.

- Query GBIF using specimen catalog numbers.
- Retrieve ARK URIs associated with museum specimens.
- Writes resulting metadata in tab-delimited (TSV) format.

### 2. NCBI Metadata Retrieval
**Directory:** [`NCBI_metadata_retrieval/`](https://github.com/gonzalezvl/Genomics-Metadata-Data-Curation/tree/main/NCBI_metadata_retrieval)

Scripts for querying NCBI databases and extracting metadata associated with genetic sequence and biological sample records.

- Query NCBI Nucleotide and BioSample databases.
- Retrieve accession numbers, organism names, specimen vouchers, BioProject identifiers, and other available metadata.
- Support queries using museum specimen voucher identifiers (e.g., `USNM:FISH`).
- Returns metadata in tab-delimited (TSV) format.

#### *Usage instructions and requirements are provided within each script.*

Updated: Fri Oct  9 12:05:55 EDT 2026
