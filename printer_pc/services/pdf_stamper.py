import io
from pathlib import Path
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import inch
from reportlab.lib import colors

from config import MARGIN_PT

def _build_stamp_page(page_w: float, page_h: float,
                      order_id, print_date: str) -> io.BytesIO:
    """
    Compact, low-visibility single-row stamp at the bottom-right of the page.
    Layout: [icon] PrintEase | Order ID: #__ | Date: __
    Intentionally subtle — muted color, thin border, small text.
    """
    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))

    ink = colors.HexColor("#8A95B8")

    font_sz  = 7            
    stamp_h  = 0.26 * inch 

    char_w   = font_sz * 0.45
    col_pad  = 10           

    brand_w   = len("PrintEase") * char_w
    icon_w    = stamp_h * 0.72         
    icon_gap  = 4                        
    col1_w    = icon_w + icon_gap + brand_w + col_pad

    oid_text  = f"Order ID: #{order_id}"
    col2_w    = len(oid_text) * char_w + col_pad * 2

    date_text = f"Date: {print_date}"
    col3_w    = len(date_text) * char_w + col_pad * 2  

    stamp_w  = col1_w + col2_w + col3_w + 12   
    pad_x    = 0.18 * inch
    pad_y    = 0.13 * inch

    x = page_w - stamp_w - pad_x
    y = pad_y
    cy = y + stamp_h / 2   

    c.setStrokeColor(ink)
    c.setFillColor(colors.white)
    c.setLineWidth(0.6)
    c.roundRect(x, y, stamp_w, stamp_h, radius=3, fill=1, stroke=1)

    ix = x + 6              
    iy = cy
    s  = icon_w / 18        

    c.setFillColor(ink)
    c.setStrokeColor(ink)
    c.setLineWidth(0)
    c.rect(ix + 2*s, iy - 8*s, 14*s, 4*s, fill=1, stroke=0)     
    c.roundRect(ix, iy - 4*s, 18*s, 10*s, radius=s, fill=1, stroke=0) 
    c.setFillColor(colors.white)
    c.rect(ix + 3*s, iy + 5*s, 12*s, 8*s, fill=1, stroke=0)    
    c.setStrokeColor(ink)
    c.setLineWidth(0.3)
    for i in range(2):
        ly = iy + 7*s + i * 3*s
        c.line(ix + 4*s, ly, ix + 14*s, ly)
    c.setFillColor(colors.white)
    c.circle(ix + 14*s, iy + 1*s, s * 0.9, fill=1, stroke=0)

    brand_x = ix + icon_w + icon_gap
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", font_sz)
    c.drawString(brand_x, cy - font_sz * 0.35, "PrintEase")

    d1 = x + col1_w + 4
    c.setStrokeColor(ink)
    c.setLineWidth(0.5)
    c.line(d1, y + 3, d1, y + stamp_h - 3)

    c.setFont("Helvetica-Bold", font_sz)
    c.drawString(d1 + col_pad, cy - font_sz * 0.35, oid_text)

    d2 = d1 + col2_w + 4
    c.line(d2, y + 3, d2, y + stamp_h - 3)

    date_col_cx = d2 + col3_w / 2 
    c.setFont("Helvetica-Bold", font_sz)
    c.drawCentredString(date_col_cx, cy - font_sz * 0.35, date_text)

    c.save()
    buf.seek(0)
    return buf


def stamp_pdf(input_path: Path, order_id, print_date: str) -> Path:
    print(f"[STAMP] Processing {input_path.name}  order={order_id}  date={print_date}")

    reader = PdfReader(str(input_path))
    writer = PdfWriter()

    for page_num, page in enumerate(reader.pages):
        page.transfer_rotation_to_content()
        orig_w = float(page.mediabox.width)
        orig_h = float(page.mediabox.height)

        scale_x = (orig_w - 2 * MARGIN_PT) / orig_w
        scale_y = (orig_h - 2 * MARGIN_PT) / orig_h
        tx = MARGIN_PT
        ty = MARGIN_PT

        print(f"[STAMP]  page {page_num+1}: {orig_w:.1f}x{orig_h:.1f}pt  "
              f"scale=({scale_x:.3f},{scale_y:.3f})")

        writer.add_page(page)
        wp = writer.pages[-1]

        transform = Transformation(ctm=(scale_x, 0, 0, scale_y, tx, ty))
        wp.add_transformation(transform)

        stamp_buf    = _build_stamp_page(orig_w, orig_h, order_id, print_date)
        stamp_reader = PdfReader(stamp_buf)
        wp.merge_page(stamp_reader.pages[0])

    stamped_path = input_path.parent / (input_path.stem + "_stamped.pdf")
    with open(stamped_path, "wb") as f:
        writer.write(f)

    print(f"[STAMP] Done -> {stamped_path.name}")
    return stamped_path
