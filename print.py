import pypandoc
from docx import Document
import sys
import cups
import shutil
import mammoth
from html2image import Html2Image

from flask import Flask, render_template, request
import os






def convert_rtf_to_docx(rtf_path, docx_path):
    output = pypandoc.convert_file(rtf_path, 'docx', outputfile=docx_path)

def replace_string_in_docx(docx_path, old_string, new_string):
    doc = Document(docx_path)
    for paragraph in doc.paragraphs:
        if old_string in paragraph.text:
            paragraph.text = paragraph.text.replace(old_string, new_string)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if old_string in cell.text:
                    cell.text = cell.text.replace(old_string, new_string)
    doc.save(docx_path)
                # do something with the cell
                

def convert_docx_to_rtf(docx_path, rtf_path):
    output = pypandoc.convert_file(docx_path, 'rtf', outputfile=rtf_path)

def print_file_using_pycups(file_path, printer_name=None):
    conn = cups.Connection()
    
    # Get the default printer if not specified
    if not printer_name:
        printer_name = conn.getDefault()
    
    # Print the file
    job_id = conn.printFile(printer_name, file_path, "Print Job", {})
    print(f'Successfully sent {file_path} to the printer (Job ID: {job_id}).')

def adjust_string_length(variable, length):
    underscores = '_' * (length - len(variable))
    return variable + underscores




