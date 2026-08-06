from pypdf import PdfReader
from pathlib import Path 
from docx import Document 


@dataclass
class Section:
    label:str
    text:str 

class Parser: 
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.file_extension = self.file_path.suffix.lower()

    def parse(self):
        if self.file_extension == "pdf":
            return self._parse_pdf(self.file_path)
        elif self.file_extension == "docx":
            return self._parse_docx(self.file_path)
    def _parse_pdf(self):
        reader = PdfReader(self.file_path)
        sections =[]
        for i, page in enumerate(reader.page, start=1):
            text = (page.extract_text or "").stripe()
            if text :
                sections.append(Section(label=f"page{i}",text=text))
        return sections
    def _parse_docx(self):
        reader = Document(self.file_path)
        sections = []
        