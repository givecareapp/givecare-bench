"""
Example script demonstrating how to generate an arXiv-style paper.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arxiv_paper_gen.paper_generator import ArxivPaper


def main():
    """Generate a sample arXiv paper."""

    # Define paper metadata
    title = "A Novel Approach to Machine Learning Interpretability"

    authors = [
        {
            "name": "John Doe",
            "affiliation": "Department of Computer Science, University of Example",
            "email": "john.doe@example.edu"
        },
        {
            "name": "Jane Smith",
            "affiliation": "AI Research Institute",
            "email": "jane.smith@research.org"
        }
    ]

    abstract = (
        "Machine learning models have achieved remarkable success in various domains, "
        "yet their interpretability remains a significant challenge. "
        "In this paper, we propose a novel framework for understanding and explaining "
        "the decision-making process of complex neural networks. "
        "Our approach combines gradient-based attribution methods with structural "
        "causal models to provide both local and global interpretability. "
        "We evaluate our method on several benchmark datasets and demonstrate "
        "superior performance compared to existing interpretability techniques. "
        "The proposed framework offers practitioners a powerful tool for building "
        "trust in AI systems and satisfying regulatory requirements."
    )

    keywords = [
        "Machine Learning",
        "Interpretability",
        "Explainable AI",
        "Neural Networks",
        "Causal Models"
    ]

    # Create paper
    paper = ArxivPaper(
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords
    )

    # Add Introduction
    intro_content = (
        "The rapid advancement of machine learning has led to increasingly complex models "
        "that often operate as ``black boxes.'' While these models achieve state-of-the-art "
        "performance on various tasks, their lack of transparency poses challenges for "
        "adoption in critical domains such as healthcare, finance, and autonomous systems.\\\\[1em]\n\n"
        "Recent efforts in explainable AI (XAI) have produced various techniques for "
        "interpreting model predictions, including LIME~\\cite{ribeiro2016lime}, "
        "SHAP~\\cite{lundberg2017shap}, and attention mechanisms. However, these methods "
        "often provide limited insights into the underlying causal mechanisms.\\\\[1em]\n\n"
        "In this work, we present a unified framework that addresses these limitations by "
        "combining gradient-based attribution with structural causal models."
    )
    paper.add_section("Introduction", intro_content)

    # Add Methods section
    methods = paper.add_section("Methods", "")
    paper.add_subsection(
        methods,
        "Problem Formulation",
        "Let $f: \\mathcal{X} \\rightarrow \\mathcal{Y}$ denote a trained neural network "
        "mapping inputs $x \\in \\mathcal{X}$ to predictions $y \\in \\mathcal{Y}$. "
        "Our goal is to provide interpretable explanations for individual predictions "
        "$\\hat{y} = f(x)$ while also capturing global model behavior."
    )

    paper.add_subsection(
        methods,
        "Attribution Framework",
        "We propose a gradient-based attribution method that computes feature importance "
        "scores $\\phi_i$ for each input feature $x_i$. The attribution is defined as:\n\n"
        "$$\\phi_i = \\int_{\\alpha=0}^{1} \\frac{\\partial f(x'(\\alpha))}{\\partial x_i} d\\alpha$$\n\n"
        "where $x'(\\alpha) = \\bar{x} + \\alpha(x - \\bar{x})$ interpolates between "
        "a baseline input $\\bar{x}$ and the actual input $x$."
    )

    # Add Results section
    results_content = (
        "We evaluate our framework on three benchmark datasets: MNIST, CIFAR-10, and "
        "ImageNet. For each dataset, we trained convolutional neural networks and applied "
        "our interpretability method to analyze model predictions.\\\\[1em]\n\n"
        "Table~\\ref{tab:results} summarizes the quantitative evaluation of our method "
        "compared to baseline approaches. Our framework achieves the highest fidelity "
        "scores across all datasets, indicating better alignment between explanations "
        "and actual model behavior."
    )
    paper.add_section("Results", results_content)

    # Add a sample table
    table_content = (
        "Method & MNIST & CIFAR-10 & ImageNet \\\\\n"
        "\\midrule\n"
        "LIME & 0.72 & 0.68 & 0.65 \\\\\n"
        "SHAP & 0.78 & 0.74 & 0.71 \\\\\n"
        "Ours & \\textbf{0.86} & \\textbf{0.82} & \\textbf{0.79} \\\\\n"
    )
    paper.add_table(
        caption="Fidelity scores of different interpretability methods",
        label="results",
        table_spec="lccc",
        table_content=table_content
    )

    # Add Discussion
    discussion_content = (
        "Our results demonstrate that combining gradient-based attribution with "
        "causal modeling provides superior interpretability compared to existing methods. "
        "The framework's ability to capture both local and global model behavior makes it "
        "particularly valuable for understanding complex neural networks.\\\\[1em]\n\n"
        "However, our approach has some limitations. The computational cost increases "
        "with model size, and the quality of causal explanations depends on the accuracy "
        "of the underlying causal graph. Future work should address these challenges."
    )
    paper.add_section("Discussion", discussion_content)

    # Add Conclusion
    conclusion_content = (
        "We presented a novel framework for machine learning interpretability that "
        "combines gradient-based attribution methods with structural causal models. "
        "Our experimental results show significant improvements over existing approaches "
        "in terms of explanation fidelity and comprehensiveness.\\\\[1em]\n\n"
        "This work opens several avenues for future research, including extensions to "
        "other model architectures, integration with counterfactual reasoning, and "
        "applications to multimodal learning systems."
    )
    paper.add_section("Conclusion", conclusion_content)

    # Generate the paper
    output_path = Path(__file__).parent / "output" / "sample_paper"
    output_path.parent.mkdir(exist_ok=True)

    print("Generating arXiv paper...")
    print(f"Title: {title}")
    print(f"Authors: {', '.join([a['name'] for a in authors])}")
    print(f"\nOutput directory: {output_path.parent}")

    try:
        # First, save the .tex file for inspection
        paper.save_tex(str(output_path) + ".tex")
        print(f"✓ LaTeX source saved: {output_path}.tex")

        # Then generate PDF (requires LaTeX installation)
        pdf_path = paper.generate(str(output_path), clean_tex=False)
        print(f"✓ PDF generated: {pdf_path}")

    except Exception as e:
        print(f"\n⚠ Error generating PDF: {e}")
        print("\nNote: PDF generation requires a LaTeX installation (pdflatex).")
        print("The .tex file has been saved and can be compiled manually.")
        print("\nTo install LaTeX:")
        print("  - macOS: brew install --cask mactex")
        print("  - Linux: sudo apt-get install texlive-full")
        print("  - Windows: Download MiKTeX from https://miktex.org/")


if __name__ == "__main__":
    main()
