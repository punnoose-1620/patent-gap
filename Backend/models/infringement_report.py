import io
import json
import textwrap

from pydantic import BaseModel, Field


class ReportReferenceCase(BaseModel):
    case_id: str
    title: str
    description: str = ""
    claims: list[str] = Field(default_factory=list)
    document_urls: list[str] = Field(default_factory=list)


class SimilarityClaim(BaseModel):
    claim: str
    similarity_score: float
    source: str
    url_to_claim: str


class InfringementEntry(BaseModel):
    source: str
    entry_id: str
    entry_title: str
    entry_url: str
    similar_claims: list[SimilarityClaim] = Field(default_factory=list)


class ClaimComparison(BaseModel):
    reference_claim: str
    infringing_claim: str
    source: str
    entry_id: str
    entry_title: str
    entry_url: str
    similarity_score: float
    commentary: str = ""


class ReportSection(BaseModel):
    name: str
    content: str
    key_points: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    level: str
    basis: list[str] = Field(default_factory=list)
    confidence: float


class InfringementLitigationReport(BaseModel):
    report_title: str
    generated_at: str
    reference_case: ReportReferenceCase
    infringements: list[InfringementEntry] = Field(default_factory=list)
    claim_analysis: list[ClaimComparison] = Field(default_factory=list)
    report_sections: list[ReportSection] = Field(default_factory=list)
    risk_assessment: RiskAssessment
    limitations: list[str] = Field(default_factory=list)
    source_traceability: list[str] = Field(default_factory=list)

    @classmethod
    def getDescription(cls):
        description = {
            "report_title": {
                "datatype": "string",
                "structure": "single line text",
                "what_it_is": "Title of the infringement report."
            },
            "generated_at": {
                "datatype": "string",
                "structure": "ISO-8601 timestamp text",
                "what_it_is": "Time the report was produced."
            },
            "reference_case": {
                "datatype": "object",
                "structure": {
                    "case_id": "string",
                    "title": "string",
                    "description": "string",
                    "claims": "list[string]",
                    "document_urls": "list[string]"
                },
                "what_it_is": "The reference patent or case the report is built around."
            },
            "infringements": {
                "datatype": "list[object]",
                "structure": {
                    "source": "string",
                    "entry_id": "string",
                    "entry_title": "string",
                    "entry_url": "string",
                    "similar_claims": "list[object]"
                },
                "what_it_is": "The infringement findings produced by the analysis step."
            },
            "claim_analysis": {
                "datatype": "list[object]",
                "structure": {
                    "reference_claim": "string",
                    "infringing_claim": "string",
                    "source": "string",
                    "entry_id": "string",
                    "entry_title": "string",
                    "entry_url": "string",
                    "similarity_score": "number",
                    "commentary": "string"
                },
                "what_it_is": "Claim-by-claim comparison items derived from the supplied analysis."
            },
            "report_sections": {
                "datatype": "list[object]",
                "structure": {
                    "name": "string",
                    "content": "string",
                    "key_points": "list[string]"
                },
                "what_it_is": "Narrative sections that present the report in a litigation-friendly format."
            },
            "risk_assessment": {
                "datatype": "object",
                "structure": {
                    "level": "string",
                    "basis": "list[string]",
                    "confidence": "number"
                },
                "what_it_is": "A neutral assessment based only on the supplied data."
            },
            "limitations": {
                "datatype": "list[string]",
                "structure": "List of short limitation statements.",
                "what_it_is": "Caveats about missing evidence or incomplete data."
            },
            "source_traceability": {
                "datatype": "list[string]",
                "structure": "List of source names, claim references, or URLs used in the report.",
                "what_it_is": "Evidence trail for the supplied findings."
            }
        }
        return json.dumps(description, indent=2)

    def verifyValues(self):
        errors = []

        if not isinstance(self.report_title, str) or self.report_title.strip() == "":
            errors.append("report_title must be a non-empty string")

        if not isinstance(self.generated_at, str) or self.generated_at.strip() == "":
            errors.append("generated_at must be a non-empty string")

        if not isinstance(self.reference_case, ReportReferenceCase):
            errors.append("reference_case must be a ReportReferenceCase object")
        else:
            if not isinstance(self.reference_case.case_id, str) or self.reference_case.case_id.strip() == "":
                errors.append("reference_case.case_id must be a non-empty string")
            if not isinstance(self.reference_case.title, str) or self.reference_case.title.strip() == "":
                errors.append("reference_case.title must be a non-empty string")
            if not isinstance(self.reference_case.description, str):
                errors.append("reference_case.description must be a string")
            if not isinstance(self.reference_case.claims, list) or any(not isinstance(item, str) for item in self.reference_case.claims):
                errors.append("reference_case.claims must be a list of strings")
            if not isinstance(self.reference_case.document_urls, list) or any(not isinstance(item, str) for item in self.reference_case.document_urls):
                errors.append("reference_case.document_urls must be a list of strings")

        if not isinstance(self.infringements, list):
            errors.append("infringements must be a list")
        else:
            for index, infringement in enumerate(self.infringements):
                if not isinstance(infringement, InfringementEntry):
                    errors.append(f"infringements[{index}] must be an InfringementEntry object")
                    continue
                if not isinstance(infringement.source, str) or infringement.source.strip() == "":
                    errors.append(f"infringements[{index}].source must be a non-empty string")
                if not isinstance(infringement.entry_id, str) or infringement.entry_id.strip() == "":
                    errors.append(f"infringements[{index}].entry_id must be a non-empty string")
                if not isinstance(infringement.entry_title, str) or infringement.entry_title.strip() == "":
                    errors.append(f"infringements[{index}].entry_title must be a non-empty string")
                if not isinstance(infringement.entry_url, str):
                    errors.append(f"infringements[{index}].entry_url must be a string")
                if not isinstance(infringement.similar_claims, list):
                    errors.append(f"infringements[{index}].similar_claims must be a list")
                else:
                    for claim_index, claim in enumerate(infringement.similar_claims):
                        if not isinstance(claim, SimilarityClaim):
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}] must be a SimilarityClaim object")
                            continue
                        if not isinstance(claim.claim, str) or claim.claim.strip() == "":
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}].claim must be a non-empty string")
                        if not isinstance(claim.similarity_score, (int, float)):
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}].similarity_score must be numeric")
                        elif not 0 <= float(claim.similarity_score) <= 1:
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}].similarity_score must be between 0 and 1")
                        if not isinstance(claim.source, str) or claim.source.strip() == "":
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}].source must be a non-empty string")
                        if not isinstance(claim.url_to_claim, str):
                            errors.append(f"infringements[{index}].similar_claims[{claim_index}].url_to_claim must be a string")

        if not isinstance(self.claim_analysis, list):
            errors.append("claim_analysis must be a list")
        else:
            for index, item in enumerate(self.claim_analysis):
                if not isinstance(item, ClaimComparison):
                    errors.append(f"claim_analysis[{index}] must be a ClaimComparison object")
                    continue
                if not isinstance(item.reference_claim, str):
                    errors.append(f"claim_analysis[{index}].reference_claim must be a string")
                if not isinstance(item.infringing_claim, str):
                    errors.append(f"claim_analysis[{index}].infringing_claim must be a string")
                if not isinstance(item.source, str) or item.source.strip() == "":
                    errors.append(f"claim_analysis[{index}].source must be a non-empty string")
                if not isinstance(item.entry_id, str):
                    errors.append(f"claim_analysis[{index}].entry_id must be a string")
                if not isinstance(item.entry_title, str):
                    errors.append(f"claim_analysis[{index}].entry_title must be a string")
                if not isinstance(item.entry_url, str):
                    errors.append(f"claim_analysis[{index}].entry_url must be a string")
                if not isinstance(item.similarity_score, (int, float)):
                    errors.append(f"claim_analysis[{index}].similarity_score must be numeric")
                elif not 0 <= float(item.similarity_score) <= 1:
                    errors.append(f"claim_analysis[{index}].similarity_score must be between 0 and 1")
                if not isinstance(item.commentary, str):
                    errors.append(f"claim_analysis[{index}].commentary must be a string")

        if not isinstance(self.report_sections, list):
            errors.append("report_sections must be a list")
        else:
            for index, section in enumerate(self.report_sections):
                if not isinstance(section, ReportSection):
                    errors.append(f"report_sections[{index}] must be a ReportSection object")
                    continue
                if not isinstance(section.name, str) or section.name.strip() == "":
                    errors.append(f"report_sections[{index}].name must be a non-empty string")
                if not isinstance(section.content, str):
                    errors.append(f"report_sections[{index}].content must be a string")
                if not isinstance(section.key_points, list) or any(not isinstance(point, str) for point in section.key_points):
                    errors.append(f"report_sections[{index}].key_points must be a list of strings")

        if not isinstance(self.risk_assessment, RiskAssessment):
            errors.append("risk_assessment must be a RiskAssessment object")
        else:
            if not isinstance(self.risk_assessment.level, str) or self.risk_assessment.level.strip() == "":
                errors.append("risk_assessment.level must be a non-empty string")
            if self.risk_assessment.level not in ["low", "medium", "high"]:
                errors.append("risk_assessment.level must be one of low, medium, or high")
            if not isinstance(self.risk_assessment.basis, list) or any(not isinstance(item, str) for item in self.risk_assessment.basis):
                errors.append("risk_assessment.basis must be a list of strings")
            if not isinstance(self.risk_assessment.confidence, (int, float)):
                errors.append("risk_assessment.confidence must be numeric")
            elif not 0 <= float(self.risk_assessment.confidence) <= 1:
                errors.append("risk_assessment.confidence must be between 0 and 1")

        if not isinstance(self.limitations, list) or any(not isinstance(item, str) for item in self.limitations):
            errors.append("limitations must be a list of strings")
        if not isinstance(self.source_traceability, list) or any(not isinstance(item, str) for item in self.source_traceability):
            errors.append("source_traceability must be a list of strings")

        return errors

    def buildPdf(self):
        errors = self.verifyValues()
        if errors:
            raise ValueError(f"Invalid infringement report values: {', '.join(errors)}")

        lines = []
        lines.extend(self._section_lines("Infringement Litigation Report"))
        lines.append(f"Report Title: {self.report_title}")
        lines.append(f"Generated At: {self.generated_at}")
        lines.append("")
        lines.extend(self._section_lines("Reference Case"))
        lines.extend(self._dict_lines(self.reference_case.model_dump()))
        lines.append("")
        lines.extend(self._section_lines("Infringements"))
        if self.infringements:
            for index, infringement in enumerate(self.infringements, start=1):
                lines.append(f"Infringement {index}")
                lines.extend(self._dict_lines(infringement.model_dump(), indent=2))
                lines.append("")
        else:
            lines.append("No infringement entries were provided.")
            lines.append("")
        lines.extend(self._section_lines("Claim Analysis"))
        if self.claim_analysis:
            for index, comparison in enumerate(self.claim_analysis, start=1):
                lines.append(f"Claim Comparison {index}")
                lines.extend(self._dict_lines(comparison.model_dump(), indent=2))
                lines.append("")
        else:
            lines.append("No claim-by-claim analysis was provided.")
            lines.append("")
        lines.extend(self._section_lines("Report Sections"))
        if self.report_sections:
            for section in self.report_sections:
                lines.append(f"Section: {section.name}")
                lines.extend(self._wrap_text(section.content, indent=2))
                if section.key_points:
                    lines.append("  Key Points:")
                    for point in section.key_points:
                        lines.append(f"    - {point}")
                lines.append("")
        else:
            lines.append("No narrative sections were provided.")
            lines.append("")
        lines.extend(self._section_lines("Risk Assessment"))
        lines.extend(self._dict_lines(self.risk_assessment.model_dump()))
        lines.append("")
        lines.extend(self._section_lines("Limitations"))
        if self.limitations:
            for limitation in self.limitations:
                lines.append(f"- {limitation}")
        else:
            lines.append("- None provided")
        lines.append("")
        lines.extend(self._section_lines("Source Traceability"))
        if self.source_traceability:
            for item in self.source_traceability:
                lines.append(f"- {item}")
        else:
            lines.append("- None provided")

        return self._lines_to_pdf_bytes(lines)

    @staticmethod
    def _section_lines(title: str):
        return [title, "=" * len(title), ""]

    @staticmethod
    def _wrap_text(value: str, indent: int = 0, width: int = 92):
        prefix = " " * indent
        wrapped_lines = []
        paragraphs = value.splitlines() or [""]
        for paragraph in paragraphs:
            if paragraph.strip() == "":
                wrapped_lines.append(prefix)
                continue
            wrapped = textwrap.wrap(
                paragraph,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            ) or [""]
            wrapped_lines.extend(f"{prefix}{line}" for line in wrapped)
        return wrapped_lines

    def _dict_lines(self, data, indent: int = 0):
        return self._wrap_text(json.dumps(data, indent=2, default=str), indent=indent)

    @staticmethod
    def _escape_pdf_text(value: str):
        return (
            value.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    def _lines_to_pdf_bytes(self, lines: list[str]):
        page_width = 612
        page_height = 792
        left_margin = 50
        top_margin = 50
        bottom_margin = 50
        line_height = 14
        max_lines_per_page = max(1, int((page_height - top_margin - bottom_margin) / line_height))

        wrapped_lines = []
        for line in lines:
            if line == "":
                wrapped_lines.append("")
            else:
                wrapped_lines.extend(self._wrap_text(line, width=92))

        if not wrapped_lines:
            wrapped_lines = ["Infringement report"]

        pages = [wrapped_lines[index:index + max_lines_per_page] for index in range(0, len(wrapped_lines), max_lines_per_page)]
        if not pages:
            pages = [["Infringement report"]]

        content_object_start = 4
        page_object_start = content_object_start + len(pages)
        content_object_numbers = list(range(content_object_start, content_object_start + len(pages)))
        page_object_numbers = list(range(page_object_start, page_object_start + len(pages)))

        objects = [None] * (page_object_start + len(pages) - 1)
        objects[0] = "<< /Type /Catalog /Pages 2 0 R >>"
        objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_num} 0 R' for page_num in page_object_numbers)}] /Count {len(pages)} >>"
        objects[2] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

        for index, page_lines in enumerate(pages):
            content_object_number = content_object_numbers[index]
            page_object_number = page_object_numbers[index]
            stream_lines = ["BT", "/F1 10 Tf"]
            y_position = page_height - top_margin - 2
            for line in page_lines:
                safe_line = self._escape_pdf_text(line if line.strip() else " ")
                stream_lines.append(f"1 0 0 1 {left_margin} {y_position} Tm")
                stream_lines.append(f"({safe_line}) Tj")
                y_position -= line_height
            stream_lines.append("ET")
            stream_data = "\n".join(stream_lines).encode("latin-1", "replace")
            objects[content_object_number - 1] = f"<< /Length {len(stream_data)} >>\nstream\n{stream_data.decode('latin-1', 'replace')}\nendstream"
            objects[page_object_number - 1] = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_number} 0 R >>"
            )

        pdf_buffer = io.BytesIO()
        pdf_buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_number, object_content in enumerate(objects, start=1):
            offsets.append(pdf_buffer.tell())
            pdf_buffer.write(f"{object_number} 0 obj\n".encode("latin-1"))
            pdf_buffer.write(object_content.encode("latin-1", "replace"))
            pdf_buffer.write(b"\nendobj\n")

        xref_position = pdf_buffer.tell()
        pdf_buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        pdf_buffer.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf_buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
        pdf_buffer.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode("latin-1")
        )
        return pdf_buffer.getvalue()