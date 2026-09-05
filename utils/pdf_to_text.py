import pdfplumber


def _extract_tables_clean(page):
    tables_text = ""
    for table in page.extract_tables():
        tables_text += "[TABLE START]\n"
        for row in table:
            row_text = " | ".join((cell or "").strip() for cell in row)
            tables_text += row_text + "\n"
        tables_text += "[TABLE END]\n\n"
    return tables_text


def pdf_to_text(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.find_tables()

            page_no_tables = page
            for t in tables:
                page_no_tables = page_no_tables.outside_bbox(t.bbox)

            text = page_no_tables.extract_text(layout=True) or ""
            full_text += text + "\n"

            full_text += _extract_tables_clean(page)

    return full_text


FILENAME_MAP = {
    "docs/Patent_rules.pdf": "patent",

    "docs/Biological diversity act 2022.pdf": "biodiversity",
    "docs/Biological diversity (amendment) act 2023.pdf": "biodiversity_amendment",

    "docs/tkdl/CGPDTM.pdf": "tkdl_cgpdtm",

    "docs/drugs and cosmetics act 1945/Schedule E1.pdf": "drugs_cosmetics_schedule_e1",

    "docs/drugs and cosmetics act 1945/PART XVI MANUFACTURE FOR SALE OF AYURVEDIC (INCLUDING SIDDHA) OR UNANI DRUGS.pdf": "drugs_cosmetics_part_xvi_ayurvedic_manufacture",

    "docs/drugs and cosmetics act 1945/LABELLING, PACKING AND LIMIT OF ALCOHOL IN AYURVEDIC OR UNANI DRUGS.pdf": "drugs_cosmetics_labelling_packing_alcohol_limit",

    "docs/drugs and cosmetics act 1945/Good manufacturing practices (GMP).pdf": "drugs_cosmetics_gmp",

    "docs/drugs and cosmetics act 1945/DrugsandCosmeticsAct1940Rules1945 - 1.pdf": "drugs_cosmetics_part_1",
    "docs/drugs and cosmetics act 1945/2016DrugsandCosmeticsAct1940Rules1945 - 2.pdf": "drugs_cosmetics_part_2",
    "docs/drugs and cosmetics act 1945/2016DrugsandCosmeticsAct1940Rules1945 - 3.pdf": "drugs_cosmetics_part_3",
}

def load_all_pdfs(pdf_paths: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}

    for path in pdf_paths:
        name = FILENAME_MAP[path]
        text = pdf_to_text(path)
        result[name] = text

    return result