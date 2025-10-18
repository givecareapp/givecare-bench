"""
arXiv Paper Generator

This module provides functionality to generate arXiv-style academic papers programmatically.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from pylatex import Document, Section, Subsection, Command, NoEscape
from pylatex.base_classes import Environment
from pylatex.package import Package


class ArxivPaper:
    """Generate arXiv-style academic papers."""

    def __init__(
        self,
        title: str,
        authors: List[Dict[str, str]],
        abstract: str,
        keywords: Optional[List[str]] = None,
    ):
        """
        Initialize the arXiv paper generator.

        Args:
            title: Paper title
            authors: List of author dictionaries with 'name' and optional 'affiliation', 'email'
            abstract: Paper abstract
            keywords: List of keywords
        """
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.keywords = keywords or []

        # Initialize document with article class
        self.doc = Document(documentclass='article')

        # Add required packages
        self._setup_packages()

        # Setup preamble
        self._setup_preamble()

    def _setup_packages(self):
        """Add required LaTeX packages."""
        # Core packages
        self.doc.packages.append(Package('inputenc', options=['utf8']))
        self.doc.packages.append(Package('fontenc', options=['T1']))
        self.doc.packages.append(Package('hyperref'))
        self.doc.packages.append(Package('url'))
        self.doc.packages.append(Package('booktabs'))
        self.doc.packages.append(Package('amsfonts'))
        self.doc.packages.append(Package('amsmath'))
        self.doc.packages.append(Package('amssymb'))
        self.doc.packages.append(Package('nicefrac'))
        self.doc.packages.append(Package('microtype'))
        self.doc.packages.append(Package('graphicx'))
        self.doc.packages.append(Package('cleveref'))  # For robust cross-refs

        # Add arxiv style (assuming it's in the same directory or templates/)
        self.doc.preamble.append(NoEscape(r'\usepackage{arxiv}'))

        # Configure hyperref and URL styling
        self.doc.preamble.append(NoEscape(r'\urlstyle{same}'))
        self.doc.preamble.append(NoEscape(r'\hypersetup{colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue}'))

    def _setup_preamble(self):
        """Setup document preamble with title, authors, etc."""
        # Reset page numbering to 1 at start of document
        self.doc.preamble.append(NoEscape(r'\setcounter{page}{1}'))

        # Title
        self.doc.preamble.append(Command('title', self.title))

        # Authors
        author_str = self._format_authors()
        self.doc.preamble.append(NoEscape(r'\author{' + author_str + r'}'))

        # Date
        self.doc.preamble.append(Command('date', NoEscape(r'\today')))

    def _format_authors(self) -> str:
        """Format authors for LaTeX."""
        formatted_authors = []

        for author in self.authors:
            author_tex = author['name']

            if 'affiliation' in author:
                author_tex += NoEscape(r'\thanks{' + author['affiliation'])
                if 'email' in author:
                    author_tex += NoEscape(r'. Email: \texttt{' + author['email'] + r'}')
                author_tex += NoEscape(r'}')

            formatted_authors.append(author_tex)

        return NoEscape(r' \And '.join(formatted_authors))

    def add_abstract(self):
        """Add abstract to the document."""
        self.doc.append(NoEscape(r'\begin{abstract}'))
        self.doc.append(NoEscape(self.abstract))
        self.doc.append(NoEscape(r'\end{abstract}'))

        if self.keywords:
            keyword_str = ', '.join(self.keywords)
            self.doc.append(NoEscape(r'\keywords{' + keyword_str + r'}'))

    def add_section(self, title: str, content: str) -> Section:
        """
        Add a section to the paper.

        Args:
            title: Section title
            content: Section content

        Returns:
            The created Section object
        """
        section = Section(title)
        section.append(NoEscape(content))
        self.doc.append(section)
        return section

    def add_subsection(self, section: Section, title: str, content: str) -> Subsection:
        """
        Add a subsection to an existing section.

        Args:
            section: Parent section
            title: Subsection title
            content: Subsection content

        Returns:
            The created Subsection object
        """
        subsection = Subsection(title)
        subsection.append(NoEscape(content))
        section.append(subsection)
        return subsection

    def add_figure(self, image_path: str, caption: str, label: str, width: str = r'0.8\textwidth'):
        """
        Add a figure to the document.

        Args:
            image_path: Path to the image file
            caption: Figure caption
            label: Figure label for referencing
            width: Figure width (LaTeX dimension)
        """
        self.doc.append(NoEscape(r'\begin{figure}[htbp]'))
        self.doc.append(NoEscape(r'\centering'))
        self.doc.append(NoEscape(r'\includegraphics[width=' + width + r']{' + image_path + r'}'))
        self.doc.append(Command('caption', caption))
        self.doc.append(Command('label', 'fig:' + label))
        self.doc.append(NoEscape(r'\end{figure}'))

    def add_table(self, caption: str, label: str, table_spec: str, table_content: str):
        """
        Add a table to the document.

        Args:
            caption: Table caption
            label: Table label for referencing
            table_spec: LaTeX table specification (e.g., 'lcc')
            table_content: LaTeX table content
        """
        self.doc.append(NoEscape(r'\begin{table}[htbp]'))
        self.doc.append(NoEscape(r'\centering'))
        self.doc.append(Command('caption', caption))
        self.doc.append(Command('label', 'tab:' + label))
        self.doc.append(NoEscape(r'\begin{tabular}{' + table_spec + r'}'))
        self.doc.append(NoEscape(r'\toprule'))
        self.doc.append(NoEscape(table_content))
        self.doc.append(NoEscape(r'\bottomrule'))
        self.doc.append(NoEscape(r'\end{tabular}'))
        self.doc.append(NoEscape(r'\end{table}'))

    def add_bibliography(self, bib_file: str):
        """
        Add bibliography section.

        Args:
            bib_file: Path to .bib file (without extension)
        """
        self.doc.append(NoEscape(r'\bibliographystyle{plain}'))
        self.doc.append(NoEscape(r'\bibliography{' + bib_file + r'}'))

    def generate(self, output_path: str, clean_tex: bool = False, compiler: str = 'pdflatex'):
        """
        Generate the paper PDF.

        Args:
            output_path: Output file path (without extension)
            clean_tex: Whether to clean intermediate TeX files
            compiler: LaTeX compiler to use
        """
        # Insert maketitle and abstract at the BEGINNING of document body
        # We need to insert these before any content that was added
        self.doc.data.insert(0, NoEscape(r'\maketitle'))

        # Create abstract content
        abstract_content = [
            NoEscape(r'\begin{abstract}'),
            NoEscape(self.abstract),
            NoEscape(r'\end{abstract}')
        ]

        if self.keywords:
            keyword_str = ', '.join(self.keywords)
            abstract_content.append(NoEscape(r'\keywords{' + keyword_str + r'}'))

        # Insert abstract after maketitle (at position 1)
        for i, item in enumerate(abstract_content):
            self.doc.data.insert(1 + i, item)

        # Generate PDF
        output_dir = Path(output_path).parent
        output_name = Path(output_path).stem

        self.doc.generate_pdf(
            str(output_dir / output_name),
            clean_tex=clean_tex,
            compiler=compiler
        )

        return str(output_dir / f"{output_name}.pdf")

    def save_tex(self, output_path: str):
        """
        Save the LaTeX source without compiling.

        Args:
            output_path: Output .tex file path
        """
        self.doc.generate_tex(output_path)
