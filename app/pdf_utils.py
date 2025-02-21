# Standard library imports
import os
import base64
import tempfile
from pathlib import Path

# Third party imports
from pdfrw import PdfDict
from pdfrw import PdfName
from pdfrw import PdfReader
from pdfrw import PdfWriter
from dotenv import load_dotenv
from mailersend import emails


load_dotenv(dotenv_path=".env.local")

FROM_EMAIL = os.environ.get("MAILERSEND_EMAIL")
MAILERSEND_API_KEY = os.environ.get("MAILERSEND_API_KEY")


def write_form_to_pdf(form_file, form_data):
    """
    Fills a PDF form template with data and saves to a temporary file.

    Args:
        form_file (str): Path to the PDF template
        form_data (object): Object with form field values matching PDF field names

    Returns:
        Path: Path to the filled temporary PDF file
    """

    # Read in form template
    template = PdfReader(form_file)

    # Fill in fields given form_data
    for page in template.pages:
        if page["/Annots"]:
            for annotation in page["/Annots"]:
                if annotation["/T"]:
                    key = annotation["/T"][1:-1]  # Remove parentheses
                    key = "_".join(key.split(" ")).lower()

                    # Check if our form has any corresponding fields.
                    if hasattr(form_data, key):
                        # logger.debug(f"Updating `{key}` on new pdf.")
                        value = str(getattr(form_data, key))
                        annotation.update(
                            PdfDict(
                                **{
                                    "V": f"{value}",  # Wrap in parentheses for text fields
                                    "AS": (
                                        PdfName("Yes") if value == "Yes" else None
                                    ),  # For checkboxes
                                    "AP": None,  # Reset appearance
                                    "Ff": 1,  # Ensure field is editable
                                }
                            )
                        )

    # Create temporary file with .pdf extension
    temp_dir = tempfile.gettempdir()
    temp_file = Path(temp_dir) / f"filled_form_{os.urandom(8).hex()}.pdf"

    # Sync updates.
    template.update()

    # Add all pages from the template
    writer = PdfWriter()
    writer.addpages(template.pages)

    # Write to temp_file for sending.
    with open(temp_file, "wb") as output_file:
        writer.write(output_file, template)

    return temp_file


def send_email(to_email, html, subject, pdf_path):
    """
    Sends an email with HTML content and a PDF attachment via MailerSend.

    Args:
        to_email (str): Recipient's email
        html (str): Email body in HTML
        subject (str): Email subject
        pdf_path (str): Path to PDF attachment
    """

    mailer = emails.NewEmail(MAILERSEND_API_KEY)

    # Email parameters
    mail_from = {"name": "AI Water Chatbot", "email": FROM_EMAIL}
    recipients = [{"email": to_email}]

    # Read the PDF file and encode it to base64
    with open(pdf_path, "rb") as pdf_file:
        pdf_content = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

    # Set up the email data
    mail_body = {
        "from": mail_from,
        "to": recipients,
        "subject": subject,
        "html": html,
        "attachments": [
            {
                "filename": "utility_assistance_application.pdf",
                "content": pdf_base64,
                "disposition": "attachment",
            }
        ],
    }

    # Send the email with attachment and optional template
    try:
        response = mailer.send(mail_body)
        print(response)
    except Exception as e:
        print(f"An error occurred: {e}")


def compose_and_send_form(form_data):
    """
    Fills the utility assistance PDF form and emails it.

    Args:
        form_data (object): Form field values to fill in the PDF
    """

    form_file = "forms/utility_assistance_application.pdf"
    filled_pdf = write_form_to_pdf(form_file, form_data)
    send_email(
        to_email="aiwaterchatbot@gmail.com",
        subject="New Utility Service Form",
        pdf_path=filled_pdf,
        html="""
        <div style="font-family: Arial, sans-serif">
            <p>Hello!</p>
            
            <p>I've just helped a resident fill out this form for further
            assistance. Please see the PDF attached to this email.</p>
        
            <p>Thank you for your help!</p>
            
            <p style="margin-top: 20px;">
                Best regards,<br> Clara<br> <em>Raleigh's AI Assistant for Water
                Services</em>
            </p>

            <p>PS: We've observed some bugs when viewing this in Chrome's PDF
            viewer. If you encounter any issues reading it, try downloading and
            viewing in a separate app.</p>
        </div>
        """,
    )
