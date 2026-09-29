from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone


def _money(value):
    return f"INR {Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def generate_seller_invoice(seller_order, seller_profile=None):
    """Render an invoice PDF containing only this seller's share of the order."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice D2C-SO-{seller_order.id}",
        author=(seller_profile.business_name if seller_profile else seller_order.seller.email),
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvoiceTitle', parent=styles['Title'], alignment=TA_RIGHT, textColor=colors.HexColor('#17324D')
    )
    body_style = ParagraphStyle('InvoiceBody', parent=styles['BodyText'], leading=14)
    right_style = ParagraphStyle('InvoiceRight', parent=body_style, alignment=TA_RIGHT)
    story = []

    seller_name = (
        seller_profile.business_name
        if seller_profile and seller_profile.business_name
        else seller_order.seller.email
    )
    seller_lines = [seller_name, seller_order.seller.email]
    if seller_profile and seller_profile.gst_number:
        seller_lines.append(f"GSTIN: {seller_profile.gst_number}")

    order = seller_order.order
    customer_address = [
        order.address_line_1,
        order.address_line_2,
        order.landmark,
        ', '.join(part for part in (order.city, order.state, order.postal_code) if part),
        order.country,
    ]
    customer_address = [part for part in customer_address if part]
    if not customer_address and order.address:
        customer_address = [order.address]

    invoice_header = Table([
        [
            Paragraph('<br/>'.join(escape(line) for line in seller_lines), body_style),
            Paragraph(f"INVOICE<br/><font size='10'>D2C-SO-{seller_order.id}</font>", title_style),
        ]
    ], colWidths=[89 * mm, 85 * mm])
    invoice_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.extend([invoice_header, Spacer(1, 8 * mm)])

    created = timezone.localtime(order.created_at).strftime('%d %b %Y, %H:%M %Z')
    customer_lines = [order.name, order.email, order.phone, *customer_address]
    details = Table([
        [Paragraph('<b>Bill to</b><br/>' + '<br/>'.join(escape(line) for line in customer_lines), body_style),
         Paragraph(f"<b>Order</b> #{order.id}<br/><b>Date</b> {escape(created)}<br/><b>Payment</b> {escape(order.status)}", right_style)],
    ], colWidths=[99 * mm, 75 * mm])
    details.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#D6DEE8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F7F9FC')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.extend([details, Spacer(1, 8 * mm)])

    rows = [[
        Paragraph('<b>Item</b>', body_style),
        Paragraph('<b>Qty</b>', right_style),
        Paragraph('<b>Unit price</b>', right_style),
        Paragraph('<b>Amount</b>', right_style),
    ]]
    for item in seller_order.items.all():
        variant = item.product_variant
        product_description = (
            f"{variant.product.name} — {variant.size} — {variant.color}"
        )
        line_total = Decimal(str(item.price)) * item.quantity
        rows.append([
            Paragraph(escape(product_description), body_style),
            Paragraph(str(item.quantity), right_style),
            Paragraph(_money(item.price), right_style),
            Paragraph(_money(line_total), right_style),
        ])

    items_table = Table(rows, colWidths=[82 * mm, 18 * mm, 37 * mm, 37 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17324D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#D6DEE8')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.extend([items_table, Spacer(1, 5 * mm)])

    totals = Table([
        [Paragraph('<b>Seller order total</b>', body_style),
         Paragraph(f"<b>{_money(seller_order.total_amount)}</b>", right_style)],
    ], colWidths=[137 * mm, 37 * mm])
    totals.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.HexColor('#17324D')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.extend([totals, Spacer(1, 5 * mm), Paragraph('Generated by the marketplace.', styles['Italic'])])

    document.build(story)
    return output.getvalue()
