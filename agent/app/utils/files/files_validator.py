import gzip, re, os
from pathlib import Path

# --- Magic bytes for each container type ---
MAGIC = {
    "gz":  b"\x1f\x8b",          # gzip
    "pdf": b"%PDF",
}

MAX_SIZES = {
    "genomic":   5 * 1024**3,    # 5 GB (for S3 uploads)
    "knowledge": 50 * 1024**2,   # 50 MB (for local RAG)
}

# --- Dangerous patterns inside FASTA headers (shell injection guard) ---
FASTA_HEADER_BANNED = re.compile(r"[;&|`$<>]")


def validate_genomic_file(path: Path, filename: str) -> tuple[bool, str]:
    """
    Deep validation for files going to Object Storage + tool node.
    Handles both uncompressed text and GZIP archives.
    """
    size = os.path.getsize(path)
    if size == 0:
        return False, "File is empty"
    if size > MAX_SIZES["genomic"]:
        return False, f"File exceeds {MAX_SIZES["genomic"] / (1024**3)} GB limit ({size / 1024**3:.1f} GB)"

    # 1. Check if the file is gzipped via magic bytes
    with open(path, "rb") as f:
        header = f.read(2)
    
    is_gz = (header == MAGIC["gz"])

    # 2. Extract a 64KB sample safely
    try:
        if is_gz:
            with gzip.open(path, "rb") as gz:
                sample = gz.read(65536)
        else:
            with open(path, "rb") as f:
                sample = f.read(65536)
    except Exception as e:
        return False, f"Failed to read file sample: {e}"

    if len(sample) == 0:
        return False, "File or archive is effectively empty"

    # 3. Content structure check
    name = filename.lower()
    
    # Strip .gz for easier matching
    base_name = name[:-3] if name.endswith(".gz") else name

    if any(base_name.endswith(ext) for ext in (".fasta", ".fa", ".fna")):
        return _validate_fasta_sample(sample)

    if any(base_name.endswith(ext) for ext in (".gff3", ".gff", ".gtf")):
        return _validate_gff_sample(sample)

    if base_name.endswith(".vcf"):
        return _validate_vcf_sample(sample)

    # If it's a collinearity or custom data file, just accept if it made it this far
    return True, "ok"


def _validate_fasta_sample(sample: bytes) -> tuple[bool, str]:
    text = sample.decode("utf-8", errors="replace")
    lines = text.splitlines()

    if not lines or not lines[0].startswith(">"):
        return False, "FASTA file must start with a '>' header line"

    seq_chars = set("ACGTNacgtnRYSWKMBDHVryswkmbdhv \t\n\r-")
    for line in lines[1:30]:
        if line.startswith(">"):
            if FASTA_HEADER_BANNED.search(line):
                return False, f"Dangerous characters in FASTA header: {line[:80]}"
            continue
        if line and not all(c in seq_chars for c in line):
            return False, f"Non-IUPAC characters in sequence: {line[:40]}"

    return True, "ok"

def _validate_gff_sample(sample: bytes) -> tuple[bool, str]:
    text = sample.decode("utf-8", errors="replace")
    lines = [l for l in text.splitlines() if not l.startswith("#")]

    if not lines:
        return False, "GFF3 file has no data lines (only comments)"

    for line in lines[:10]:
        cols = line.split("\t")
        if len(cols) != 9:
            return False, f"GFF3 line has {len(cols)} columns, expected 9"
        try:
            _, _ = int(cols[3]), int(cols[4])
        except ValueError:
            return False, f"GFF3 start/end columns are not integers: {cols[3]}, {cols[4]}"

    return True, "ok"

def _validate_vcf_sample(sample: bytes) -> tuple[bool, str]:
    text = sample.decode("utf-8", errors="replace")
    if "##fileformat=VCF" not in text[:500]:
        return False, "VCF file missing ##fileformat header"
    return True, "ok"

def validate_knowledge_file(path: Path, filename: str) -> tuple[bool, str]:
    """Lightweight validation for files going to local memory/Qdrant."""
    size = os.path.getsize(path)
    if size == 0:
        return False, "File is empty"
    if size > MAX_SIZES["knowledge"]:
        return False, "File exceeds 50 MB limit"

    name = filename.lower()
    with open(path, "rb") as f:
        magic = f.read(4)

    if name.endswith(".pdf") and not magic.startswith(MAGIC["pdf"]):
        return False, "File claims to be PDF but magic bytes don't match"

    if any(name.endswith(e) for e in (".txt", ".csv", ".tsv", ".md")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.read(4096)
        except UnicodeDecodeError:
            return False, "File is not valid UTF-8 text"

    return True, "ok"

def extract_file_sample(path: Path, max_lines: int = 50) -> str:
    """
    Extracts the first N lines of a file (handling GZIP automatically)
    to inject directly into the LLM's context window.
    """
    sample_text = ""
    try:
        with open(path, "rb") as f:
            is_gz = (f.read(2) == MAGIC["gz"])

        if is_gz:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as gz:
                # Read enough characters to guarantee we get `max_lines`
                sample_text = gz.read(10000) 
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                sample_text = f.read(10000)
    except Exception as e:
        return f"[Error extracting sample: {e}]"

    lines = sample_text.splitlines()[:max_lines]
    return "\n".join(lines)