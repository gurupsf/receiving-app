from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import qrcode
from pathlib import Path
import json
from urllib.parse import urlencode
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import csv
import re


def generate_qa_pdf(qa_data: dict, output_dir: Path) -> Path:
    """
    Generate a QA submission PDF with form data and embedded images.
    
    qa_data should contain:
        - qa_id: Unique ID for this submission
        - project: Project name/ID
        - drawing: Drawing name/ID
        - elevation: Elevation value
        - roomNumber: Room number
        - qaCheck: "Pass" or "Fail"
        - issueCategory: Issue category (if Fail)
        - resubmit: Boolean for resubmit flag
        - timestamp: ISO timestamp
        - image_data: List of dicts with 'filename' and 'data' (bytes)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF filename
    elevation_safe = qa_data['elevation'].replace('/', '_').replace('\\', '_').replace(' ', '_')
    room_safe = qa_data['roomNumber'].replace('/', '_').replace('\\', '_').replace(' ', '_')
    
    # Smart overwriting: use stable filename if resubmit=true (overwrites previous),
    # use qa_id if resubmit=false (keeps separate file for full history)
    if qa_data.get('resubmit', False):
        # Stable filename allows overwriting on resubmission
        project_safe = str(qa_data['project']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        drawing_safe = str(qa_data['drawing']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        pdf_path = output_dir / f"QA_{project_safe}_{drawing_safe}_{elevation_safe}_{room_safe}.pdf"
    else:
        # Unique filename preserves full history
        pdf_path = output_dir / f"QA_{qa_data['qa_id']}_{elevation_safe}_{room_safe}.pdf"
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=6
    )
    
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.black
    )
    
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black
    )
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("QA Submission Form", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Form data section
    story.append(Paragraph("Submission Details", heading_style))
    
    form_data = [
        ["Field", "Value"],
        ["QA ID", str(qa_data.get('qa_id', 'N/A'))],
        ["Project", str(qa_data.get('project', 'N/A'))],
        ["Drawing", str(qa_data.get('drawing', 'N/A'))],
        ["Elevation", str(qa_data.get('elevation', 'N/A'))],
        ["Room Number", str(qa_data.get('roomNumber', 'N/A'))],
        ["Description", str(qa_data.get('Description', 'N/A'))],
        ["QA Check", str(qa_data.get('qaCheck', 'N/A'))],
    ]
    
    if qa_data.get('issueCategory'):
        form_data.append(["Issue Category", str(qa_data.get('issueCategory'))])
    
    form_data.append(["Resubmit", "Yes" if qa_data.get('resubmit') else "No"])
    form_data.append(["Timestamp", str(qa_data.get('timestamp', 'N/A'))[:19]]) 
    
    # Create form table
    form_table = Table(form_data, colWidths=[2*inch, 4*inch])
    form_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    story.append(form_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Images section
    image_data = qa_data.get('image_data', [])
    if image_data:
        story.append(Paragraph("Uploaded Images", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        for idx, img_dict in enumerate(image_data, 1):
            try:
                from io import BytesIO
                
                # Create BytesIO object from image data
                img_bytes = BytesIO(img_dict['data'])
                img_filename = img_dict.get('filename', f'Image_{idx}')
                
                # Add image with max width of 5 inches
                try:
                    img = Image(img_bytes, width=5*inch, height=3.75*inch)
                    
                    # Create a table with image and caption
                    img_table = Table([[img]])
                    img_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (0, 0), (0, 0), 0),
                    ]))
                    
                    story.append(img_table)
                    story.append(Paragraph(f"Image {idx}: {img_filename}", label_style))
                    story.append(Spacer(1, 0.2*inch))
                    
                    # Add page break between images if there are more
                    if idx < len(image_data):
                        story.append(PageBreak())
                except Exception as e:
                    story.append(Paragraph(f"Error loading image {idx}: {str(e)}", value_style))
                    story.append(Spacer(1, 0.1*inch))
            except Exception as e:
                story.append(Paragraph(f"Error processing image {idx}: {str(e)}", value_style))
                story.append(Spacer(1, 0.1*inch))
            except Exception as e:
                story.append(Paragraph(f"Error processing image {idx}: {str(e)}", value_style))
                story.append(Spacer(1, 0.1*inch))
    
    # Build PDF
    doc.build(story)
    
    return pdf_path


def generate_receiving_pdf(receiving_data: dict, output_dir: Path) -> Path:
    """
    Generate a receiving submission PDF with form data, packing slip, and item images.
    
    receiving_data should contain:
        - receiving_id: Unique ID for this submission
        - project: Project name/ID
        - drawing: Drawing name/ID
        - po_number: Purchase order number
        - material_id: Material identifier
        - supplier: Supplier name
        - quantity_ordered: Ordered quantity
        - quantity_received: Received quantity
        - defective_count: Number of defective items
        - item_status: "Accepted" or "Rejected"
        - order_date: Order date from purchasing
        - received_date: Receipt date
        - delivery_days: Calculated delivery time
        - notes: Additional notes
        - timestamp: ISO timestamp
        - packing_slip_image: Dict with 'filename' and 'data' (bytes)
        - item_images: List of dicts with 'filename' and 'data' (bytes)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF filename
    po_safe = receiving_data['po_number'].replace('/', '_').replace('\\', '_').replace(' ', '_')
    material_safe = receiving_data['material_id'].replace('/', '_').replace('\\', '_').replace(' ', '_')
    
    pdf_path = output_dir / f"Receiving_{receiving_data['receiving_id']}_{po_safe}_{material_safe}.pdf"
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=6
    )
    
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.black
    )
    
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black
    )
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("Receiving Submission Form", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Form data section
    story.append(Paragraph("Receiving Details", heading_style))
    
    # Calculate defect rate
    qty_received = receiving_data.get('quantity_received', 0)
    defective = receiving_data.get('defective_count', 0)
    defect_rate = (defective / qty_received * 100) if qty_received > 0 else 0
    
    form_data = [
        ["Field", "Value"],
        ["Receiving ID", str(receiving_data.get('receiving_id', 'N/A'))],
        ["Project", str(receiving_data.get('project', 'N/A'))],
        ["Drawing", str(receiving_data.get('drawing', 'N/A'))],
        ["PO Number", str(receiving_data.get('po_number', 'N/A'))],
        ["Material ID", str(receiving_data.get('material_id', 'N/A'))],
        ["Supplier", str(receiving_data.get('supplier', 'N/A'))],
        ["Quantity Ordered", str(receiving_data.get('quantity_ordered', 'N/A'))],
        ["Quantity Received", str(receiving_data.get('quantity_received', 'N/A'))],
        ["Defective Count", str(defective)],
        ["Defect Rate", f"{defect_rate:.2f}%"],
        ["Item Status", str(receiving_data.get('item_status', 'N/A'))],
    ]
    
    if receiving_data.get('order_date'):
        form_data.append(["Order Date", str(receiving_data.get('order_date'))[:19]])
    
    form_data.append(["Received Date", str(receiving_data.get('received_date', 'N/A'))[:19]])
    
    if receiving_data.get('delivery_days') is not None:
        form_data.append(["Delivery Days", str(receiving_data.get('delivery_days'))])
    
    if receiving_data.get('notes'):
        form_data.append(["Notes", str(receiving_data.get('notes'))])
    
    form_data.append(["Timestamp", str(receiving_data.get('timestamp', 'N/A'))[:19]])
    
    # Create form table
    form_table = Table(form_data, colWidths=[2*inch, 4*inch])
    form_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    story.append(form_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Packing Slip section
    packing_slip = receiving_data.get('packing_slip_image')
    if packing_slip:
        story.append(Paragraph("Packing Slip", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        try:
            from io import BytesIO
            img_bytes = BytesIO(packing_slip['data'])
            img_filename = packing_slip.get('filename', 'Packing_Slip')
            
            try:
                img = Image(img_bytes, width=6*inch, height=4.5*inch)
                img_table = Table([[img]])
                img_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                ]))
                
                story.append(img_table)
                story.append(Paragraph(f"File: {img_filename}", label_style))
                story.append(Spacer(1, 0.2*inch))
                story.append(PageBreak())
            except Exception as e:
                story.append(Paragraph(f"Error loading packing slip: {str(e)}", value_style))
                story.append(Spacer(1, 0.1*inch))
        except Exception as e:
            story.append(Paragraph(f"Error processing packing slip: {str(e)}", value_style))
            story.append(Spacer(1, 0.1*inch))
    
    # Item Images section
    item_images = receiving_data.get('item_images', [])
    if item_images:
        story.append(Paragraph("Item Photos", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        for idx, img_dict in enumerate(item_images, 1):
            try:
                from io import BytesIO
                img_bytes = BytesIO(img_dict['data'])
                img_filename = img_dict.get('filename', f'Item_Image_{idx}')
                
                try:
                    img = Image(img_bytes, width=5*inch, height=3.75*inch)
                    img_table = Table([[img]])
                    img_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                    ]))
                    
                    story.append(img_table)
                    story.append(Paragraph(f"Item Image {idx}: {img_filename}", label_style))
                    story.append(Spacer(1, 0.2*inch))
                    
                    if idx < len(item_images):
                        story.append(PageBreak())
                except Exception as e:
                    story.append(Paragraph(f"Error loading item image {idx}: {str(e)}", value_style))
                    story.append(Spacer(1, 0.1*inch))
            except Exception as e:
                story.append(Paragraph(f"Error processing item image {idx}: {str(e)}", value_style))
                story.append(Spacer(1, 0.1*inch))
    
    # Build PDF
    doc.build(story)
    
    return pdf_path