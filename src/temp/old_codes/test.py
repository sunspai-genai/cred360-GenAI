import re

import markdown2
import os
from pathlib import Path
#
# from adodbapi.examples.xls_read import filename


def convert_markdown_to_html(markdown_file_path, output_directory=None, file_encoding="utf-8"):
    """
    Converts a Markdown file to HTML.

    Args:
        markdown_file_path (str or Path): Path to the Markdown file.
        output_directory (str or Path, optional): Directory to save the HTML file.
            If None, the HTML file will be saved in the same directory as the Markdown file.
        file_encoding (str, optional): Encoding of the Markdown file. Defaults to "utf-8".

    Returns:
        str: Path to the generated HTML file.
    """
    markdown_file_path = Path(markdown_file_path)  # Ensure it's a Path object

    if not markdown_file_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file_path}")

    try:
        with open(markdown_file_path, "r", encoding=file_encoding) as f:
            markdown_text = f.read()

        html_text = markdown2.markdown(markdown_text)

        # Determine output file path
        if output_directory:
            output_directory = Path(output_directory)
            output_directory.mkdir(parents=True, exist_ok=True)  # Create if doesn't exist
            html_file_path = output_directory / f"{markdown_file_path.stem}.html"
        else:
            html_file_path = markdown_file_path.with_suffix(".html")  # Same directory

        with open(html_file_path, "w", encoding=file_encoding) as f:
            f.write(html_text)

        return str(html_file_path)  # Return as string for consistency
    except Exception as e:
        raise Exception(f"Error converting Markdown to HTML: {e}")

# Example usage:
# if __name__ == "__main__":
filename = "balance_sheet_20250402_122553.md"
timestamp_regex = re.compile(r'_\d{8}_\d{6}\.md$')
print(timestamp_regex.search(filename))

    # markdown_file = r"output/walmart/Cumulative Report.md"  # Replace with your Markdown file
    # # Create a dummy markdown file for testing
    # # with open(markdown_file, "w") as f:
    # #     f.write("# This is a heading\n\n* This is a list item\n\n**This is bold text**")
    #
    # output_dir = "output/walmart/reports/html_files"  # Optional output directory
    # try:
    #     html_file = convert_markdown_to_html(markdown_file, output_dir)
    #     print(f"HTML file created: {html_file}")
    # except Exception as e:
    #     print(f"Error: {e}")