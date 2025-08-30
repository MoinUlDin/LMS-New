import qrcode
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from django.http import HttpResponse

def generate_membership_card(member):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(85.6*mm, 53.98*mm))  # fixed!

    # Card Content
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10*mm, 45*mm, "Library Membership Card")
    c.setFont("Helvetica", 8)
    c.drawString(10*mm, 38*mm, f"Name: {member.user.get_full_name() or member.user.username}")
    c.drawString(10*mm, 33*mm, f"Member id: {member.member_id}")
    c.drawString(10*mm, 28*mm, f"Department: {member.department}")

    # QR Code
    qr_data = f"{member.user.username}-{member.roll_no}-{member.department}"
    qr_img = qrcode.make(qr_data)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)
    c.drawInlineImage(qr_buffer, 60*mm, 20*mm, width=20*mm, height=20*mm)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
