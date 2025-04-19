import os
from docx import Document

def read_docx(file_path):
    try:
        doc = Document(file_path)
        content = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                content.append(paragraph.text)
        return "\n".join(content)
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

def main():
    docx_dir = './samples/python/agents/rovi_agent/teambuilding_concept/'
    for filename in os.listdir(docx_dir):
        if filename.endswith('.docx'):
            file_path = os.path.join(docx_dir, filename)
            print(f"\n\n=== {filename} ===\n")
            content = read_docx(file_path)
            print(content[:1000] + "..." if len(content) > 1000 else content)

if __name__ == "__main__":
    main()
